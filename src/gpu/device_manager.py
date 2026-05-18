"""GPU设备管理器

负责GPU设备的初始化、配置和管理。
"""

# 统一日志获取
from pathlib import Path
from typing import Any, cast

from ..utils import get_configured_logger
from ..utils.exception_handler import ExceptionHandler
from ..utils.performance_monitor import EnhancedPerformanceMonitor
from .amd_optimizer import AmdGPUOptimizer
from .async_executor import AsyncGPUExecutor
from .context import GPUContext
from .device import GPUDevice, GPUDeviceDetector
from .intel_optimizer import IntelGPUOptimizer
from .kernel import OPENCL_KERNEL_SOURCE
from .kernel_impl import GPUKernel
from .memory_pool import get_gpu_memory_pool
from .nvidia_optimizer import NvidiaGPUOptimizer
from .profiles.loader import GPUProfileLoader

_logger = get_configured_logger("GPUDeviceManager")


class NoValidTargetsError(ValueError):
    """没有有效的目标地址 (仅 P2PKH 格式可用, 其他格式已被跳过)"""
    pass


class GPUDeviceManager:
    """GPU设备管理器

    负责GPU设备的初始化、配置和管理。
    """

    def __init__(
        self,
        device_index: int = -1,
        config: dict[str, Any] | None = None,
        logger: Any | None = None,
    ) -> None:
        """
        Args:
            device_index: GPU设备索引（-1表示自动选择）
            config: 配置字典
            logger: 日志记录器
        """
        self.device_index = device_index
        self.config = config or {}
        self.logger = logger or _logger

        self._gpu_device: GPUDevice | None = None
        self._gpu_context: GPUContext | None = None
        self._gpu_kernel: GPUKernel | None = None
        self._async_executor: AsyncGPUExecutor | None = None
        self._gpu_memory_pool: Any | None = None

        self._profile_loader = GPUProfileLoader()
        self._intel_optimizer: Any | None = None
        self._nvidia_optimizer: Any | None = None
        self._amd_optimizer: Any | None = None

    def _require_device(self) -> GPUDevice:
        """返回已初始化的 GPU 设备，未初始化则抛出 RuntimeError。

        替代 assert，确保 python -O 模式下仍有效。
        """
        if self._gpu_device is None:
            raise RuntimeError("GPU device not initialized")
        return self._gpu_device

    def _require_context(self) -> GPUContext:
        """返回已初始化的 GPU 上下文。"""
        if self._gpu_context is None:
            raise RuntimeError("GPU context not initialized")
        return self._gpu_context

    def _require_async_executor(self) -> AsyncGPUExecutor:
        """返回已初始化的异步执行器。"""
        if self._async_executor is None:
            raise RuntimeError("Async executor not initialized")
        return self._async_executor

    def initialize(
        self, targets: set[str], batch_size: int | None = None, check_uncompressed: int = 0
    ) -> "GPUDeviceManager":
        """初始化GPU设备

        Args:
            targets: 目标地址集合
            batch_size: 批次大小（None表示自动计算）
            check_uncompressed: 是否同时检查非压缩格式 (0=仅压缩, 1=双格式)

        Returns:
            self，支持链式调用
        """
        with EnhancedPerformanceMonitor(self.logger, "GPU设备初始化", level="INFO") as pm:
            try:
                if not GPUDeviceDetector.is_gpu_available():
                    raise RuntimeError("pyopencl 不可用")

                # 1. 初始化GPU设备
                self._init_device()
                assert self._gpu_device is not None  # _init_device 保证设置

                # 2. 准备目标地址
                target_hash160s, target_list = self._prepare_targets(targets)
                self.target_hash160s = target_hash160s
                self.target_list = target_list

                # 3. 计算最优batch_size
                if batch_size is None:
                    batch_size = self._calculate_optimal_batch_size()

                # 4. 创建GPU上下文
                self._init_context()
                assert self._gpu_context is not None  # _init_context 保证设置

                # 5. 编译和创建内核
                self._init_kernel(batch_size)
                assert self._gpu_kernel is not None  # _init_kernel 保证初始化

                # 6. 初始化内存池（含预分配）
                self._init_memory_pool(batch_size)

                # 7. 初始化异步执行器
                self._init_async_executor(batch_size)

                # 8. 设置目标地址
                if target_hash160s:
                    self._gpu_kernel.set_targets(
                        target_hash160s,
                        len(target_list),
                        check_uncompressed=check_uncompressed,
                    )

                # 8.1 传递 check_uncompressed 给异步执行器
                if self._async_executor:
                    self._async_executor.check_uncompressed = check_uncompressed

                # 9. 应用厂商优化
                self._apply_vendor_optimizations()

                # 10. 记录初始化完成
                device_info = self._gpu_device.get_device_info()
                self.logger.info(
                    f"GPU 设备初始化成功: {device_info.get('name', 'Unknown')} "
                    f"(厂商: {device_info.get('vendor', 'Unknown')}, batch_size: {batch_size}, "
                    f"work_group_size: {self._gpu_kernel._work_group_size if self._gpu_kernel else 'N/A'})"
                )

                pm.add_metadata("device_name", device_info.get("name", "Unknown"))
                pm.add_metadata("vendor", device_info.get("vendor", "Unknown"))
                pm.add_metadata("batch_size", batch_size)

            except NoValidTargetsError as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                # 目标地址格式不兼容 (仅支持 P2PKH)
                self.logger.error(
                    f"GPU初始化失败: {e}\n"
                    "原因: 目标地址格式不兼容\n"
                    "  GPU 引擎当前仅支持 P2PKH 地址 (1... 开头, Base58 编码)。\n"
                    "  如果你的目标包含 P2SH (3...) 或 Bech32/Taproot (bc1...) 地址,\n"
                    "  请使用 CPU 模式或仅使用 P2PKH 地址。"
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e}"
                    " (GPU 引擎仅支持 P2PKH 地址格式, 其他格式请使用 CPU 模式)"
                ) from e
            except ValueError as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                self.logger.error(
                    f"GPU初始化失败: {e}\n"
                    "建议操作:\n"
                    "  1. 检查GPU驱动是否正常\n"
                    "  2. 验证OpenCL环境配置\n"
                    "  3. 使用CPU引擎作为备选方案\n"
                    "  4. 查看日志获取详细错误信息"
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e}。请检查GPU驱动和OpenCL环境,或使用CPU引擎作为备选方案。"
                ) from e
            except Exception as e:
                # 使用ExceptionHandler记录详细错误
                ExceptionHandler.handle_engine_error("GPU", e, context="设备初始化")
                self.logger.error(
                    f"GPU初始化失败: {e}\n"
                    "建议操作:\n"
                    "  1. 检查GPU驱动是否正常\n"
                    "  2. 验证OpenCL环境配置\n"
                    "  3. 使用CPU引擎作为备选方案\n"
                    "  4. 查看日志获取详细错误信息"
                )
                raise RuntimeError(
                    f"GPU初始化失败: {e}。请检查GPU驱动和OpenCL环境,或使用CPU引擎作为备选方案。"
                ) from e

        return self

    def _init_device(self):
        """初始化GPU设备"""
        with EnhancedPerformanceMonitor(self.logger, "GPU设备初始化", level="DEBUG"):
            self._gpu_device = GPUDevice()

            # 读取异步执行配置
            enable_async = self._read_async_config()

            # 初始化设备
            self._gpu_device.initialize(self.device_index, enable_async=enable_async)

            device_info = self._gpu_device.get_device_info()
            self.logger.info(
                f"检测到GPU设备: {device_info.get('name', 'Unknown')} ({device_info.get('vendor', 'Unknown')})"
            )
            self.logger.info(
                f"  - 显存: {device_info.get('global_mem_size', 0) / (1024**3):.1f} GB\n"
                f"  - 计算单元: {device_info.get('max_compute_units', 'N/A')}\n"
                f"  - 平台: {device_info.get('platform', 'Unknown')}"
            )

    def _read_async_config(self) -> bool:
        """读取异步执行配置"""
        enable_async = True
        config_source = "默认"

        # 优先级1: 构造函数传入的配置
        if self.config:
            gpu_config = self.config.get("gpu", {})
            if "async_execution" in gpu_config:
                enable_async = gpu_config["async_execution"]
                config_source = "构造参数"
                self.logger.info(f"✅ 从构造参数读取异步设置: {enable_async} (优先级1)")

        # 优先级2: 自动读取配置文件
        if config_source == "默认":
            project_root = Path(__file__).parent.parent.parent
            config_files = [
                project_root / "config.intel_arc.json",
                project_root / "config.json",
            ]

            for cfg_file in config_files:
                if cfg_file.exists():
                    try:
                        import json

                        with open(cfg_file, encoding="utf-8") as f:
                            cfg = json.load(f)
                            gpu_cfg = cfg.get("gpu", {})
                            if "async_execution" in gpu_cfg:
                                enable_async = bool(gpu_cfg["async_execution"])
                                config_source = f"配置文件 {cfg_file.name}"
                                self.logger.info(
                                    f"✅ 从{config_source}读取异步设置: {enable_async} (优先级2)"
                                )
                                break
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"配置文件 {cfg_file} JSON格式错误: {e}")
                    except PermissionError:
                        self.logger.warning(f"无法读取 {cfg_file}: 权限不足")
                    except Exception as e:
                        self.logger.debug(f"读取配置文件 {cfg_file} 失败(非关键): {e}")

        # 应用配置
        if enable_async:
            self._require_device().enable_async_execution = True
            self.logger.info(f"✅ GPU异步执行已启用 (来源: {config_source}) - 双缓冲优化")
        else:
            self.logger.info(f"GPU异步执行未启用 (来源: {config_source}) - 使用同步模式")
            self.logger.info("提示: 在配置文件中设置 'gpu.async_execution': true 以启用异步优化")

        return enable_async

    def _prepare_targets(self, targets: set[str]):
        """准备目标地址 (仅 P2PKH 格式通过 Base58 校验)"""
        from ..core.base58 import Base58

        target_list = []
        hash160_list = []
        skipped_non_p2pkh = 0

        for address in sorted(targets):
            try:
                version, payload = Base58.check_decode(address)
                if version == 0x00 and len(payload) == 20:
                    target_list.append(address)
                    hash160_list.append(payload)
                else:
                    skipped_non_p2pkh += 1
            except (ValueError, TypeError) as e:
                # 非 Base58 编码地址 (如 Bech32 bc1...), 跳过
                skipped_non_p2pkh += 1
                masked = (f"{address[:6]}...{address[-4:]}" if len(address) >= 10
                          else "***")
                self.logger.debug(f"目标地址格式无效 [{masked}]: {type(e).__name__}")
                continue
            except Exception as e:
                # 未知错误：记录日志
                masked = (f"{address[:6]}...{address[-4:]}" if len(address) >= 10
                          else "***")
                self.logger.warning(f"目标地址解析失败 [{masked}]: {type(e).__name__}")
                continue

        if skipped_non_p2pkh:
            self.logger.warning(
                f"已跳过 {skipped_non_p2pkh} 个非 P2PKH 格式目标地址"
                " (GPU 引擎仅支持 P2PKH)"
            )

        if not hash160_list:
            raise NoValidTargetsError("没有有效的目标地址")

        target_hash160s = b"".join(hash160_list)
        return target_hash160s, target_list

    def _calculate_optimal_batch_size(self) -> int:
        """计算最优batch_size"""
        self._require_device()
        assert self._gpu_device is not None  # _require_device ensures non-None
        device_info: dict[str, Any] = self._gpu_device.get_device_info()
        device_name = device_info.get("name", "")
        vendor = device_info.get("vendor_identifier", "unknown")

        # 尝试从GPU配置文件中获取推荐的batch_size
        profile = self._profile_loader.get_profile(vendor, device_name)
        if profile and "recommended_batch_size" in profile:
            recommended_batch_size = profile["recommended_batch_size"]
            self.logger.info(f"从GPU配置文件获取推荐 batch_size: {recommended_batch_size}")
            return int(recommended_batch_size)

        # 基于显存大小计算
        global_mem_size = device_info.get("global_mem_size", 1024**3)  # 默认1GB

        # 保守估计：每100万私钥需要约100MB显存
        estimated_batch_size = int((global_mem_size / (100 * 1024 * 1024)) * 1_000_000)

        # 限制范围
        estimated_batch_size = max(100_000, min(estimated_batch_size, 16_777_216))  # 100K到16M

        self.logger.info(f"自动计算 batch_size: {estimated_batch_size} (基于GPU显存)")
        return estimated_batch_size

    def _init_context(self):
        """初始化GPU上下文"""
        with EnhancedPerformanceMonitor(self.logger, "GPU上下文初始化", level="DEBUG"):
            self._gpu_context = GPUContext(self._require_device())

            # 应用优化
            self._gpu_context.apply_optimizations()

    def _init_kernel(self, batch_size: int):
        """初始化GPU内核"""
        with EnhancedPerformanceMonitor(self.logger, "OpenCL内核编译", level="INFO"):
            ctx = self._require_context()
            dev = self._require_device()
            # 编译内核
            ctx.compile_kernel(OPENCL_KERNEL_SOURCE)

            # 创建GPUKernel
            self._gpu_kernel = GPUKernel(
                dev,
                max_batch_size=batch_size,
                program=self._gpu_context.program,  # type: ignore[union-attr]
            )

    def _init_memory_pool(self, batch_size: int = 0):
        """初始化GPU内存池（含常用缓冲区预分配）

        在池创建后立即预分配常用大小的缓冲区，
        消除运行时首次分配的延迟开销（通常节省 5-15ms）。

        Args:
            batch_size: 当前引擎批大小，用于预分配匹配结果缓冲区
        """
        # 从配置读取内存池设置
        gpu_config = self.config.get("gpu", {})
        use_gpu_memory_pool = gpu_config.get("use_memory_pool", True)
        gpu_pool_max_buffers = gpu_config.get("pool_max_buffers", 100)

        if use_gpu_memory_pool:
            self._gpu_memory_pool = get_gpu_memory_pool(
                self._require_device().context,
                max_buffers=gpu_pool_max_buffers,
            )
            # 预分配常用缓冲区，减少运行时首次分配延迟
            preallocate_sizes = self._compute_prealloc_sizes(batch_size)
            if preallocate_sizes:
                try:
                    self._gpu_memory_pool.preallocate_buffers(preallocate_sizes, count_per_size=2)
                    self.logger.debug(f"GPU内存池预分配: {len(preallocate_sizes)} 种大小 × 2")
                except (RuntimeError, MemoryError, ValueError):
                    self.logger.debug("GPU内存池预分配跳过（非致命）", exc_info=True)
            self.logger.info(f"GPU内存池初始化完成: {self._gpu_memory_pool.get_stats()}")
        else:
            self.logger.info("GPU内存池未启用,使用直接分配模式")

    @staticmethod
    def _compute_prealloc_sizes(batch_size: int) -> list:
        """计算引擎常用缓冲区的预分配大小列表

        基于引擎批大小推导关键缓冲区尺寸:
        - 匹配结果缓冲区: batch_size × 4 字节
        - 256/1K/64K 通用对齐尺寸（覆盖小/中/大分配）

        Args:
            batch_size: 引擎批大小

        Returns:
            去重后的缓冲区大小列表（字节）
        """
        sizes = {256, 1024, 65536}  # 通用对齐尺寸
        if batch_size > 0:
            sizes.add(batch_size * 4)  # 匹配结果缓冲区
        return sorted(sizes)

    def _init_async_executor(self, batch_size: int):
        """初始化异步执行器"""
        dev = self._require_device()
        if dev.enable_async_execution:
            self.logger.info("初始化GPU异步执行器...")

            # 从配置读取queue_depth
            gpu_config = self.config.get("gpu", {})
            queue_depth = gpu_config.get("queue_depth", 4)

            # 尝试从GPU配置文件中获取推荐的队列深度
            device_info = dev.get_device_info()
            device_name = device_info.get("name", "")
            vendor = device_info.get("vendor_identifier", "unknown")

            profile = self._profile_loader.get_profile(vendor, device_name)
            if profile and "queue_depth" in profile:
                queue_depth = profile["queue_depth"]
                self.logger.info(f"从GPU配置文件获取推荐队列深度: {queue_depth}")

            self._async_executor = AsyncGPUExecutor(
                dev, max_batch_size=batch_size, queue_depth=queue_depth
            )

            # 初始化双缓冲
            executor = self._require_async_executor()
            executor.initialize_buffers(dev.context, num_keys=batch_size)

            self.logger.info(f"✅ GPU异步执行器已初始化(双缓冲, 队列深度: {queue_depth})")
        else:
            self._async_executor = None
            self.logger.info("GPU异步执行器未初始化(使用同步模式)")

    def _apply_vendor_optimizations(self):
        """应用厂商特定优化

        v2.2.2 修复: Intel 优化路径现在传递 self 引用作为 engine，
        使 benchmark_suite / auto_tuner / performance_reporter 三个
        P2 组件能够正常初始化（之前因缺少 engine 引用而始终为 None）。
        """
        dev = self._require_device()
        device_info = dev.get_device_info()
        device_info.get("name", "")
        vendor = device_info.get("vendor", "")
        vendor_lower = vendor.lower()

        if vendor_lower.startswith("intel") or "intel" in vendor_lower:
            self.logger.info("🔧 检测到 Intel GPU，应用特殊优化")
            self._intel_optimizer = IntelGPUOptimizer(
                device=self._gpu_device,
                config=self.config,
                engine_logger=self.logger,
            )
            self._intel_optimizer.apply_optimizations(
                {
                    "kernel_source": OPENCL_KERNEL_SOURCE,
                    "engine": self,  # v2.2.2: 传递 engine 引用，启用 P2 组件
                }
            )
        elif "nvidia" in vendor_lower:
            self.logger.info("🔧 检测到 NVIDIA GPU，应用特殊优化")
            try:
                self._nvidia_optimizer = NvidiaGPUOptimizer(
                    device_info=device_info,
                    config=self.config,
                    engine_logger=self.logger,
                )
                optimization_result = self._nvidia_optimizer.apply_optimizations()
                self.logger.info(
                    f"✅ NVIDIA 优化器已初始化: 架构={optimization_result.get('arch_name', 'Unknown')}, "
                    f"memory_ratio={optimization_result.get('recommended_memory_ratio', 0.60):.2f}"
                )
            except Exception as e:
                self.logger.warning(f"⚠️ NVIDIA 优化器初始化失败（非致命）: {e}")
                self._nvidia_optimizer = None
        elif "amd" in vendor_lower or "advanced micro" in vendor_lower:
            self.logger.info("🔧 检测到 AMD GPU，应用特殊优化")
            try:
                self._amd_optimizer = AmdGPUOptimizer(
                    device_info=device_info,
                    config=self.config,
                    engine_logger=self.logger,
                )
                optimization_result = self._amd_optimizer.apply_optimizations()
                self.logger.info(
                    f"✅ AMD 优化器已初始化: 架构={optimization_result.get('arch_name', 'Unknown')}, "
                    f"memory_ratio={optimization_result.get('recommended_memory_ratio', 0.60):.2f}"
                )
            except Exception as e:
                self.logger.warning(f"⚠️ AMD 优化器初始化失败（非致命）: {e}")
                self._amd_optimizer = None

    def cleanup(self) -> None:
        """清理GPU资源"""
        import time

        try:
            # 清理异步执行器
            if self._async_executor:
                start_time = time.time()
                self._async_executor.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(f"设备管理器：异步执行器已清理 (耗时: {elapsed:.2f}秒)")

            # 清理内核
            if self._gpu_kernel:
                start_time = time.time()
                self._gpu_kernel.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(f"设备管理器：内核已清理 (耗时: {elapsed:.2f}秒)")

            # 清理内存池
            if self._gpu_memory_pool:
                start_time = time.time()
                self._gpu_memory_pool.clear()
                self._gpu_memory_pool = None
                elapsed = time.time() - start_time
                self.logger.info(f"设备管理器：内存池已清理 (耗时: {elapsed:.2f}秒)")

            # 清理上下文
            if self._gpu_context:
                start_time = time.time()
                self._gpu_context.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(f"设备管理器：上下文已清理 (耗时: {elapsed:.2f}秒)")

            # 清理设备
            if self._gpu_device:
                start_time = time.time()
                self._gpu_device.cleanup()
                elapsed = time.time() - start_time
                self.logger.info(f"设备管理器：设备已清理 (耗时: {elapsed:.2f}秒)")

            self.logger.info("设备管理器：GPU资源清理完成")
        except Exception as e:
            self.logger.warning(f"设备管理器：GPU资源清理失败: {e}")
            import traceback

            traceback.print_exc()

    @property
    def device(self) -> GPUDevice:
        """获取GPU设备实例"""
        return cast(GPUDevice, self._gpu_device)

    @property
    def context(self) -> GPUContext:
        """获取GPU上下文实例"""
        return cast(GPUContext, self._gpu_context)

    @property
    def kernel(self) -> GPUKernel:
        """获取GPU内核实例"""
        return cast(GPUKernel, self._gpu_kernel)

    @property
    def async_executor(self) -> AsyncGPUExecutor:
        """获取异步执行器实例"""
        return cast(AsyncGPUExecutor, self._async_executor)

    @property
    def memory_pool(self) -> Any:
        """获取内存池实例"""
        return self._gpu_memory_pool
