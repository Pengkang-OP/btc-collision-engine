"""Unified exception handler.

Provides unified exception handling for CPU engine, GPU engine,
and configuration systems.

P3-6 enhancements:
- New handle_gpu_async_error(): GPU async execution error handling
- 新增 handle_cl_resource_error(): OpenCL资源错误分类
- 新增 handle_gpu_cleanup_error(): GPU清理操作错误处理
- 细化 handle_gpu_error(): 增加 MemoryError/ImportError 分类
"""

# 统一日志获取
from typing import Any

from .logging_config import get_configured_logger

logger = get_configured_logger("ExceptionHandler")


class ExceptionHandler:
    """统一异常处理器

    提供标准化的异常处理方法,确保:
    1. 异常日志格式统一
    2. 错误分类清晰
    3. 恢复策略一致
    """

    @staticmethod
    def handle_engine_error(
        engine_type: str, error: Exception, stats: Any = None, context: str = "",
    ) -> None:
        """统一处理引擎错误

        参数:
            engine_type: 引擎类型 ("CPU" 或 "GPU")
            error: 捕获的异常
            stats: 统计对象(可选),用于记录错误
            context: 错误发生的上下文描述
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # 分类处理
        if isinstance(error, (RuntimeError, ValueError)):
            # 可恢复的运行时错误
            logger.warning("%s引擎%s失败(%s): %s", engine_type, context, error_type, error_msg)
            # 使用getattr替代hasattr避免竞态条件
            record_func = getattr(stats, "record_worker_error", None)
            if record_func and callable(record_func):
                record_func()
        elif isinstance(error, KeyboardInterrupt):
            # 用户中断 - 使用 raise error from None 避免 RuntimeError
            logger.info("%s引擎被用户中断", engine_type)
            raise error from None  # 重新抛出,让上层处理
        elif isinstance(error, MemoryError):
            # 内存错误(严重)
            logger.critical("%s引擎内存不足: %s", engine_type, error_msg)
            record_func = getattr(stats, "record_error", None)
            if record_func and callable(record_func):
                record_func("memory_error", error_msg)
        elif isinstance(error, ImportError):
            # 模块导入错误（新增分类）
            logger.error("%s引擎%s模块导入失败: %s", engine_type, context, error_msg)
            record_func = getattr(stats, "record_worker_error", None)
            if record_func and callable(record_func):
                record_func()
        elif isinstance(error, OSError):
            # 系统I/O错误
            logger.error(
                "%s引擎%s系统I/O错误: %s: %s",
                engine_type,
                context,
                type(error).__name__,
                str(error),
            )
            record_func = getattr(stats, "record_worker_error", None)
            if record_func and callable(record_func):
                record_func()
        else:
            # 未知错误 — 使用 error 级别而非 exception 以避免堆栈泄露私钥上下文
            logger.error(
                "%s引擎%s未知错误: %s: %s", engine_type, context, type(error).__name__, str(error),
            )
            record_func = getattr(stats, "record_worker_error", None)
            if record_func and callable(record_func):
                record_func()

    @staticmethod
    def handle_gpu_error(mode: str, error: Exception, stats: Any = None) -> bool:
        """统一处理GPU错误(复用GPUDevice.handle_gpu_batch_error逻辑)

        P3-6增强: 新增 MemoryError 分类，避免被归类为"未知错误"

        参数:
            mode: 计算模式("随机碰撞"/"范围扫描"/"暴力穷举")
            error: 捕获的异常
            stats: 统计对象(可选)

        返回:
            bool: 是否应该继续执行(总是返回True)
        """
        if isinstance(error, (RuntimeError, ValueError)):
            # OpenCL运行时错误或数据验证错误
            error_msg = str(error).lower()
            resource_keywords = [
                "out of resources",
                "memory",
                "out of memory",
                "allocation failed",
                "insufficient",
                "resource exhausted",
                "cl_out_of_resources",
                "cl_mem_object_allocation_failure",
            ]
            is_resource_error = any(keyword in error_msg for keyword in resource_keywords)

            if is_resource_error:
                logger.warning(f"GPU {mode}失败(资源不足): {type(error).__name__}: {error}")
            else:
                logger.warning(f"GPU {mode}失败(运行时错误): {type(error).__name__}: {error}")
            # 使用getattr替代hasattr避免竞态条件
            record_func = getattr(stats, "record_gpu_error", None)
            if record_func and callable(record_func):
                record_func(is_resource_error=is_resource_error)
        elif isinstance(error, MemoryError):
            # 内存不足(独立分类，便于监控告警)
            logger.critical("GPU %s内存不足(MemoryError): %s", mode, error)
            record_func = getattr(stats, "record_gpu_error", None)
            if record_func and callable(record_func):
                record_func(is_resource_error=True)
        elif isinstance(error, (TypeError, OverflowError)):
            # 数据编码错误
            logger.warning(f"GPU {mode}失败(数据错误): {type(error).__name__}: {error}")
            # 使用getattr替代hasattr避免竞态条件
            gpu_err_func = getattr(stats, "record_gpu_error", None)
            if gpu_err_func and callable(gpu_err_func):
                gpu_err_func(is_resource_error=False)
            wif_err_func = getattr(stats, "record_wif_encode_error", None)
            if wif_err_func and callable(wif_err_func):
                wif_err_func()
        else:
            # 未知错误：记录异常类型和消息，帮助诊断（如 OpenCL LogicError 等非标准异常）
            logger.error(
                "GPU %s失败(未知错误): %s: %s", mode, type(error).__name__, str(error),
            )
            logger.debug("详细堆栈:", exc_info=True)
            record_func = getattr(stats, "record_gpu_error", None)
            if record_func and callable(record_func):
                record_func(is_resource_error=False)

        return True  # 总是继续执行

    @staticmethod
    def handle_gpu_async_error(error: Exception, context: str = "") -> bool:
        """P3-6新增: 统一处理GPU异步执行错误

        用于 async_executor.py 中的异步执行回退逻辑，
        区分 OpenCL 运行时错误与其他可恢复错误。

        参数:
            error: 捕获的异常
            context: 错误上下文("种子写入"/"内核执行"/"结果回读"/"缓冲清理")

        返回:
            bool: True=应回退到同步模式, False=应向上传播
        """
        error_type = type(error).__name__

        if isinstance(error, (RuntimeError, MemoryError)):
            # OpenCL 运行时/内存错误 → 可回退
            logger.warning("GPU异步%sOpenCL错误(%s): %s", context, error_type, error)
            return True
        if isinstance(error, (ValueError, TypeError, IndexError)):
            # 数据/参数错误 → 可回退
            logger.warning("GPU异步%s数据异常(%s): %s", context, error_type, error)
            return True
        if isinstance(error, AttributeError):
            # 对象状态异常 → 可回退
            logger.warning("GPU异步%s对象状态异常(%s): %s", context, error_type, error)
            return True
        if isinstance(error, (SystemExit, KeyboardInterrupt)):
            # 系统级异常 → 不回退，让其向上传播
            logger.info("GPU异步%s系统级异常(%s): %s", context, error_type, error)
            return False
        # 未知错误 → 根据错误消息判断是否可回退
        error_msg = str(error).lower()
        critical_keywords = ["fatal", "corruption", "segmentation", "access violation"]
        if any(kw in error_msg for kw in critical_keywords):
            # 严重错误 → 不回退，记录后向上传播
            logger.error("GPU异步%s严重未知异常(%s): %s", context, error_type, error)
            return False
        # 其他未知错误 → 回退到同步模式
        logger.warning("GPU异步%s未知异常(%s): %s", context, error_type, error)
        return True

    @staticmethod
    def handle_cl_resource_error(error: Exception, resource_type: str = "") -> bool:
        """P3-6新增: 分类处理OpenCL资源错误

        根据错误消息关键字判断是否为资源耗尽型错误，
        为自动降批/重试策略提供决策依据。

        参数:
            error: 捕获的异常
            resource_type: 资源类型("buffer"/"kernel"/"queue"/"event")

        返回:
            bool: True=资源耗尽(应降批/释放), False=其他错误
        """
        error_msg = str(error).lower()
        resource_keywords = [
            "out of resources",
            "memory",
            "out of memory",
            "allocation failed",
            "insufficient",
            "resource exhausted",
            "cl_out_of_resources",
            "cl_mem_object_allocation_failure",
            "cl_out_of_host_memory",
            "invalid buffer size",
        ]

        is_resource_error = any(keyword in error_msg for keyword in resource_keywords)

        if is_resource_error:
            logger.warning(f"OpenCL {resource_type}资源耗尽: {type(error).__name__}: {error}")
        else:
            logger.error(f"OpenCL {resource_type}操作失败: {type(error).__name__}: {error}")

        return is_resource_error

    @staticmethod
    def handle_gpu_cleanup_error(error: Exception, resource_name: str = "") -> None:
        """P3-6新增: 统一处理GPU资源清理错误

        GPU资源清理（buffer释放、队列完成）时的错误处理。
        清理失败通常为非致命错误，使用 WARNING 级别。

        参数:
            error: 捕获的异常
            resource_name: 资源名称("seed_buffer"/"precomp_buffer"/"compute_queue")
        """
        if isinstance(error, RuntimeError):
            logger.warning("GPU清理%sOpenCL错误: %s", resource_name, error)
        elif isinstance(error, OSError):
            logger.warning("GPU清理%s系统I/O错误: %s", resource_name, error)
        else:
            logger.warning(f"GPU清理{resource_name}失败: {type(error).__name__}: {error}")

    @staticmethod
    def handle_config_error(error: Exception, config_type: str = "") -> None:
        """统一处理配置错误

        参数:
            error: 捕获的异常
            config_type: 配置类型("ConfigManager"/"CryptoConfig"/"GPUConfig")
        """
        if isinstance(error, (FileNotFoundError, OSError)):
            logger.warning("%s配置文件不存在或无法读取: %s", config_type, error)
        elif isinstance(error, (ValueError, TypeError)):
            logger.error("%s配置值无效: %s", config_type, error)
        elif isinstance(error, PermissionError):
            logger.error("%s配置文件权限不足: %s", config_type, error)
        else:
            logger.exception("%s配置加载未知错误", config_type)

    @staticmethod
    def handle_file_error(error: Exception, operation: str, filepath: str = "") -> None:
        """统一处理文件操作错误

        参数:
            error: 捕获的异常
            operation: 操作类型("读取"/"写入"/"删除")
            filepath: 文件路径
        """
        if isinstance(error, FileNotFoundError):
            logger.error("文件不存在(%s): %s", operation, filepath)
        elif isinstance(error, PermissionError):
            logger.error("文件权限不足(%s): %s", operation, filepath)
        elif isinstance(error, OSError):
            logger.error("文件I/O错误(%s): %s - %s", operation, filepath, error)
        else:
            logger.exception("文件操作未知错误(%s): %s", operation, filepath)
