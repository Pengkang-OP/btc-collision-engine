"""统一异常处理器

提供统一的异常处理机制,适用于CPU引擎、GPU引擎和配置系统。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """统一异常处理器
    
    提供标准化的异常处理方法,确保:
    1. 异常日志格式统一
    2. 错误分类清晰
    3. 恢复策略一致
    """
    
    @staticmethod
    def handle_engine_error(engine_type: str, error: Exception, stats=None, context: str = ""):
        """
        统一处理引擎错误
        
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
            logger.error(f"{engine_type}引擎{context}失败({error_type}): {error_msg}")
            if stats and hasattr(stats, 'record_worker_error'):
                stats.record_worker_error()
        elif isinstance(error, KeyboardInterrupt):
            # 用户中断
            logger.info(f"{engine_type}引擎被用户中断")
            raise  # 重新抛出,让上层处理
        elif isinstance(error, MemoryError):
            # 内存错误(严重)
            logger.critical(f"{engine_type}引擎内存不足: {error_msg}")
            if stats and hasattr(stats, 'record_error'):
                stats.record_error("memory_error", error_msg)
        else:
            # 未知错误
            logger.exception(f"{engine_type}引擎{context}未知错误")
            if stats and hasattr(stats, 'record_worker_error'):
                stats.record_worker_error()
    
    @staticmethod
    def handle_gpu_error(mode: str, error: Exception, stats=None):
        """
        统一处理GPU错误(复用GPUDevice.handle_gpu_batch_error逻辑)
        
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
                "out of resources", "memory", "out of memory", 
                "allocation failed", "insufficient", "resource exhausted",
                "cl_out_of_resources", "cl_mem_object_allocation_failure"
            ]
            is_resource_error = any(keyword in error_msg for keyword in resource_keywords)
            
            if is_resource_error:
                logger.error(f"GPU {mode}失败(资源不足): {type(error).__name__}: {error}")
                if stats and hasattr(stats, 'record_gpu_error'):
                    stats.record_gpu_error(is_resource_error=True)
            else:
                logger.error(f"GPU {mode}失败(运行时错误): {type(error).__name__}: {error}")
                if stats and hasattr(stats, 'record_gpu_error'):
                    stats.record_gpu_error(is_resource_error=False)
        elif isinstance(error, (TypeError, OverflowError)):
            # 数据编码错误
            logger.error(f"GPU {mode}失败(数据错误): {type(error).__name__}: {error}")
            if stats:
                if hasattr(stats, 'record_gpu_error'):
                    stats.record_gpu_error(is_resource_error=False)
                if hasattr(stats, 'record_wif_encode_error'):
                    stats.record_wif_encode_error()
        else:
            # 未知错误
            logger.exception(f"GPU {mode}失败(未知错误)")
            if stats and hasattr(stats, 'record_gpu_error'):
                stats.record_gpu_error(is_resource_error=False)
        
        return True  # 总是继续执行
    
    @staticmethod
    def handle_config_error(error: Exception, config_type: str = ""):
        """
        统一处理配置错误
        
        参数:
            error: 捕获的异常
            config_type: 配置类型("ConfigManager"/"CryptoConfig"/"GPUConfig")
        """
        if isinstance(error, (FileNotFoundError, IOError)):
            logger.warning(f"{config_type}配置文件不存在或无法读取: {error}")
        elif isinstance(error, (ValueError, TypeError)):
            logger.error(f"{config_type}配置值无效: {error}")
        elif isinstance(error, PermissionError):
            logger.error(f"{config_type}配置文件权限不足: {error}")
        else:
            logger.exception(f"{config_type}配置加载未知错误")
    
    @staticmethod
    def handle_file_error(error: Exception, operation: str, filepath: str = ""):
        """
        统一处理文件操作错误
        
        参数:
            error: 捕获的异常
            operation: 操作类型("读取"/"写入"/"删除")
            filepath: 文件路径
        """
        if isinstance(error, FileNotFoundError):
            logger.error(f"文件不存在({operation}): {filepath}")
        elif isinstance(error, PermissionError):
            logger.error(f"文件权限不足({operation}): {filepath}")
        elif isinstance(error, IOError):
            logger.error(f"文件I/O错误({operation}): {filepath} - {error}")
        else:
            logger.exception(f"文件操作未知错误({operation}): {filepath}")
