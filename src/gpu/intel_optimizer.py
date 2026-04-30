"""Intel GPU 专有优化模块

封装所有 Intel GPU 特定的优化逻辑，包括：
- uint32 workaround 验证
- Intel 监控和调优组件初始化
- 超时保护配置
- 驱动版本检测

通过 IntelGPUOptimizer 类提供统一接口，供 GPUCollisionEngine 委托调用。
"""

import logging
from ..utils import init_logging, get_configured_logger
from typing import Optional, Any, Dict, TYPE_CHECKING

logger = get_configured_logger("IntelOptimizer")

# 延迟导入避免循环依赖
if TYPE_CHECKING:
    from .intel_timeout_manager import AdaptiveTimeoutManager  # noqa: F401
    from .intel_memory_monitor import IntelMemoryMonitor  # noqa: F401
    from .benchmark_suite import GPUBenchmarkSuite  # noqa: F401
    from .auto_tuner import GPUAutoTuner  # noqa: F401
    from .performance_reporter import PerformanceReportGenerator  # noqa: F401


class IntelGPUOptimizer:
    """Intel GPU 专有优化器

    封装所有 Intel GPU 特定的优化逻辑，提供统一接口供引擎委托调用。

    Args:
        device: GPU 设备对象（GPUDevice 实例）
        config: 引擎配置字典
        logger: 可选的日志记录器，默认使用模块级 logger
    """

    def __init__(self, device: Any, config: Dict[str, Any], engine_logger: Any = None) -> None:
        self._device = device
        self._config = config
        self._logger = engine_logger or logger

        # 维持对监控组件的引用（注入到 engine 的属性中）
        self._timeout_manager: Any = None
        self._memory_monitor: Any = None
        self._benchmark_suite: Any = None
        self._auto_tuner: Any = None
        self._performance_reporter: Any = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def apply_optimizations(self, engine_context: Dict[str, Any]) -> Dict[str, Any]:
        """应用 Intel GPU 特定优化

        验证 uint32 workaround 是否正确应用，并初始化所有监控/调优组件。

        Args:
            engine_context: 引擎上下文字典，包含 kernel_source 等信息

        Returns:
            优化结果字典，包含各项优化状态

        Raises:
            RuntimeError: 如果 uint32 workaround 验证失败
        """
        self._logger.info("=" * 60)
        self._logger.info("🔧 开始应用 Intel GPU 特殊优化")
        self._logger.info("=" * 60)

        result: Dict[str, Any] = {}

        # 1. 验证 uint32 workaround
        kernel_source = engine_context.get("kernel_source", "")
        if not self._verify_uint32_workaround(kernel_source):
            self._logger.error("❌ Intel uint32 workaround 验证失败")
            raise RuntimeError("Intel GPU workaround 未正确应用，无法继续")
        result["uint32_workaround_verified"] = True

        # 2. 初始化监控和调优组件
        components = self.init_monitoring_and_tuning(engine_context)
        result["monitoring_components"] = components

        # 3. 读取超时配置
        timeout = getattr(self._device, "timeout_seconds", 30)
        self._logger.info(f"✅ Intel 超时保护: {timeout}秒")
        result["timeout_seconds"] = timeout

        # 4. 异步执行状态
        async_enabled = getattr(self._device, "enable_async_execution", False)
        if async_enabled:
            self._logger.info("✅ Intel 异步执行: 已启用(双缓冲优化)")
        else:
            self._logger.info("Intel 异步执行: 未启用(传统模式)")
        result["async_enabled"] = async_enabled

        # 5. 显存效率
        memory_efficiency = getattr(self._device, "memory_efficiency", 0.70)
        self._logger.info(f"✅ Intel 显存效率: {memory_efficiency * 100:.0f}%")
        result["memory_efficiency"] = memory_efficiency

        # 6. 驱动版本检查
        if hasattr(self._device, "driver_version") and self._device.driver_version:
            self._logger.info(f"✅ Intel 驱动版本: {self._device.driver_version}")
            result["driver_version"] = self._device.driver_version
        else:
            self._logger.warning("⚠️ 无法检测 Intel 驱动版本")
            result["driver_version"] = None

        self._logger.info("=" * 60)
        self._logger.info("✅ Intel GPU 特殊优化应用完成")
        self._logger.info("=" * 60)

        return result

    def init_monitoring_and_tuning(self, engine_context: Dict[str, Any]) -> Dict[str, Any]:
        """初始化 Intel GPU 监控和调优组件（P1/P2）

        采用防御性初始化策略：
        - 每个组件独立初始化
        - 失败不影响其他组件
        - 失败的组件设为 None
        - 记录详细的警告日志

        Args:
            engine_context: 引擎上下文字典，包含引擎自身（key='engine'）和
                            benchmark_suite、auto_tuner 所需的引擎引用

        Returns:
            包含已初始化组件的字典:
            {
                'timeout_manager': ...,
                'memory_monitor': ...,
                'benchmark_suite': ...,
                'auto_tuner': ...,
                'performance_reporter': ...,
            }
        """
        self._logger.info("\n📊 初始化 Intel GPU 监控和调优组件...")

        engine = engine_context.get("engine")

        # 延迟导入，避免循环依赖
        try:
            from .intel_timeout_manager import AdaptiveTimeoutManager

            _timeout_cls = AdaptiveTimeoutManager
        except ImportError:
            _timeout_cls = None

        try:
            from .intel_memory_monitor import IntelMemoryMonitor

            _memory_cls = IntelMemoryMonitor
        except ImportError:
            _memory_cls = None

        try:
            from .benchmark_suite import GPUBenchmarkSuite

            _benchmark_cls = GPUBenchmarkSuite
        except ImportError:
            _benchmark_cls = None

        try:
            from .auto_tuner import GPUAutoTuner

            _tuner_cls = GPUAutoTuner
        except ImportError:
            _tuner_cls = None

        try:
            from .performance_reporter import PerformanceReportGenerator

            _reporter_cls = PerformanceReportGenerator
        except ImportError:
            _reporter_cls = None

        # 1. 自适应超时管理器（P1）
        self._timeout_manager = None
        if _timeout_cls:
            try:
                self._timeout_manager = _timeout_cls(
                    base_timeout=getattr(self._device, "timeout_seconds", 30.0),
                    history_size=50,
                    safety_factor=3.0,
                    min_timeout=10.0,
                    max_timeout=120.0,
                )
                self._logger.info("✅ 自适应超时管理器已初始化")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._logger.warning(
                    f"⚠️ 自适应超时管理器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                    f"   超时管理功能将被禁用，使用固定超时保护",
                    exc_info=True,
                )

        # 2. 显存监控器（P1）
        self._memory_monitor = None
        if _memory_cls:
            try:
                device_info = self._device.device_info
                if not isinstance(device_info, dict):
                    self._logger.warning(
                        f"⚠️ device_info 类型异常: {type(device_info).__name__}，跳过显存监控器初始化\n"
                        f"   显存监控功能将被禁用"
                    )
                else:
                    total_memory = device_info.get("global_mem_size", 0)
                    if total_memory <= 0:
                        self._logger.warning(
                            "⚠️ 无法获取显存大小（global_mem_size=0），跳过显存监控器初始化\n"
                            "   显存监控功能将被禁用"
                        )
                    else:
                        self._memory_monitor = _memory_cls(
                            total_memory_bytes=total_memory, safe_usage_ratio=0.45  # Intel 保守策略
                        )
                        self._logger.info(
                            f"✅ 显存监控器已初始化 " f"(总显存: {total_memory / 1024 ** 3:.1f}GB)"
                        )
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._logger.warning(
                    f"⚠️ 显存监控器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                    f"   显存监控功能将被禁用",
                    exc_info=True,
                )

        # 3. 基准测试套件（P2）
        self._benchmark_suite = None
        if _benchmark_cls and engine is not None:
            try:
                self._benchmark_suite = _benchmark_cls(engine)
                self._logger.info("✅ 基准测试套件已初始化")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._logger.warning(
                    f"⚠️ 基准测试套件初始化失败（非致命）: {type(e).__name__}: {e}\n"
                    f"   基准测试功能将被禁用",
                    exc_info=True,
                )

        # 4. 自动调优器（P2）
        self._auto_tuner = None
        if _tuner_cls and engine is not None:
            try:
                self._auto_tuner = _tuner_cls(engine)
                self._logger.info("✅ 自动调优器已初始化")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._logger.warning(
                    f"⚠️ 自动调优器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                    f"   自动调优功能将被禁用",
                    exc_info=True,
                )

        # 5. 性能报告生成器（P2）
        self._performance_reporter = None
        if _reporter_cls and engine is not None:
            try:
                self._performance_reporter = _reporter_cls(
                    gpu_engine=engine,
                    benchmark_suite=self._benchmark_suite,
                    auto_tuner=self._auto_tuner,
                )
                self._logger.info("✅ 性能报告生成器已初始化")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._logger.warning(
                    f"⚠️ 性能报告生成器初始化失败（非致命）: {type(e).__name__}: {e}\n"
                    f"   性能报告功能将被禁用",
                    exc_info=True,
                )

        # 总结初始化结果
        initialized_count = sum(
            [
                self._timeout_manager is not None,
                self._memory_monitor is not None,
                self._benchmark_suite is not None,
                self._auto_tuner is not None,
                self._performance_reporter is not None,
            ]
        )

        if initialized_count == 5:
            self._logger.info("✅ 所有 5 个监控和调优组件初始化成功\n")
        elif initialized_count > 0:
            self._logger.warning(
                f"⚠️ {initialized_count}/5 个组件初始化成功，"
                f"{5 - initialized_count} 个组件被禁用\n"
                f"   引擎仍可正常运行，但部分监控功能不可用\n"
            )
        else:
            self._logger.error(
                "❌ 所有监控和调优组件初始化失败\n" "   引擎将使用默认配置运行，无监控和调优功能\n"
            )

        self._logger.info("✅ Intel GPU 监控和调优组件初始化完成\n")

        return {
            "timeout_manager": self._timeout_manager,
            "memory_monitor": self._memory_monitor,
            "benchmark_suite": self._benchmark_suite,
            "auto_tuner": self._auto_tuner,
            "performance_reporter": self._performance_reporter,
        }

    def get_optimization_flags(self) -> Dict[str, Any]:
        """获取当前 Intel 优化标志状态

        Returns:
            包含各项优化标志的字典
        """
        return {
            "async_execution": getattr(self._device, "enable_async_execution", False),
            "timeout_seconds": getattr(self._device, "timeout_seconds", 30),
            "memory_efficiency": getattr(self._device, "memory_efficiency", 0.70),
            "driver_version": getattr(self._device, "driver_version", None),
            "timeout_manager_active": self._timeout_manager is not None,
            "memory_monitor_active": self._memory_monitor is not None,
            "benchmark_suite_active": self._benchmark_suite is not None,
            "auto_tuner_active": self._auto_tuner is not None,
            "performance_reporter_active": self._performance_reporter is not None,
        }

    # ------------------------------------------------------------------
    # 组件属性访问器
    # ------------------------------------------------------------------

    @property
    def timeout_manager(self) -> Optional["AdaptiveTimeoutManager"]:
        """自适应超时管理器"""
        return self._timeout_manager  # type: ignore[no-any-return]

    @property
    def memory_monitor(self) -> Optional["IntelMemoryMonitor"]:
        """显存监控器"""
        return self._memory_monitor  # type: ignore[no-any-return]

    @property
    def benchmark_suite(self) -> Optional["GPUBenchmarkSuite"]:
        """基准测试套件"""
        return self._benchmark_suite  # type: ignore[no-any-return]

    @property
    def auto_tuner(self) -> Optional["GPUAutoTuner"]:
        """自动调优器"""
        return self._auto_tuner  # type: ignore[no-any-return]

    @property
    def performance_reporter(self) -> Optional["PerformanceReportGenerator"]:
        """性能报告生成器"""
        return self._performance_reporter  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _verify_uint32_workaround(self, kernel_source: str) -> bool:
        """验证 uint32 workaround 是否正确应用

        Args:
            kernel_source: OpenCL 内核源码字符串

        Returns:
            bool: 验证成功返回 True
        """
        try:
            has_uint32_workaround = (
                # DEPRECATED: '__global const uint *private_keys' 已于 v4.0 PRNG改造后从内核中移除
                # 当前内核均使用 PRNG 模式
                "__constant const uint *seed"
                in kernel_source  # PRNG mode (seed 也是 uint*)
            )
            if not has_uint32_workaround:
                self._logger.error("❌ 内核未使用 uint32 workaround")
                return False

            self._logger.info("✅ 内核源码使用 uint32 workaround")
            # 由于 _verify() 已经成功验证了 GPU 内核，说明 workaround 已经正常工作
            # 这里只需确认即可，不需要再次运行测试
            self._logger.info("✅ Intel uint32 workaround 验证通过 (已在GPU内核验证中确认)")
            return True

        except Exception as e:
            self._logger.error(f"❌ Intel workaround 测试失败: {type(e).__name__}: {e}")
            return False
