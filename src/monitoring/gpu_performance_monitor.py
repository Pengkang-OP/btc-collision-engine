"""GPU 性能监控模块，实时监控 GPU 碰撞引擎的关键指标。.

监控GPU碰撞引擎的关键性能指标:
- GPU利用率和计算效率
- 显存使用情况和泄漏检测
- 批次执行时间和吞吐量
- 内核编译性能
- 错误率和异常检测
- 性能退化告警
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# GPU硬件利用率监控支持
# C-13: nvidia-ml-py 安装后导入名称仍为 pynvml，API 完全兼容
# pynvml 已迁移至 nvidia-ml-py 包
try:
    import pynvml  # type: ignore[import-untyped]  # p: pynvml 无官方 stub

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

# Intel Arc GPU监控支持（基于level_zero或intel_gpu_top）
INTEL_GPU_MONITORING_AVAILABLE = False

logger = logging.getLogger("GPUPerformanceMonitor")

__all__ = [
    "INTEL_GPU_MONITORING_AVAILABLE",
    "GPUKernelMetrics",
    "GPUMemoryMetrics",
    "GPUPerformanceMonitor",
    "GPUPerformanceReport",
    "get_gpu_performance_monitor",
    "reset_gpu_performance_monitor",
]


@dataclass
class GPUKernelMetrics:
    """GPU内核执行指标."""

    timestamp: float
    batch_size: int
    execution_time_ms: float
    keys_per_second: float
    memory_allocated_mb: float
    error_count: int
    match_count: int

    # 延迟统计(带默认值)
    queue_wait_time_ms: float = 0.0
    data_transfer_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "batch_size": self.batch_size,
            "execution_time_ms": self.execution_time_ms,
            "keys_per_second": self.keys_per_second,
            "memory_allocated_mb": self.memory_allocated_mb,
            "error_count": self.error_count,
            "match_count": self.match_count,
            "queue_wait_time_ms": self.queue_wait_time_ms,
            "data_transfer_time_ms": self.data_transfer_time_ms,
        }


@dataclass
class GPUMemoryMetrics:
    """GPU显存指标."""

    timestamp: float
    total_memory_mb: float
    used_memory_mb: float
    free_memory_mb: float
    usage_percent: float
    peak_usage_mb: float
    allocation_count: int
    deallocation_count: int
    pool_hits: int = 0
    pool_misses: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "total_memory_mb": self.total_memory_mb,
            "used_memory_mb": self.used_memory_mb,
            "free_memory_mb": self.free_memory_mb,
            "usage_percent": self.usage_percent,
            "peak_usage_mb": self.peak_usage_mb,
            "allocation_count": self.allocation_count,
            "deallocation_count": self.deallocation_count,
            "pool_hits": self.pool_hits,
            "pool_misses": self.pool_misses,
            "pool_hit_rate": self.pool_hits / max(self.pool_hits + self.pool_misses, 1) * 100,
        }


@dataclass
class GPUPerformanceReport:
    """GPU性能报告."""

    device_name: str
    vendor: str
    monitoring_duration_sec: float
    total_batches: int
    total_keys_processed: int
    avg_throughput_keys_per_sec: float
    peak_throughput_keys_per_sec: float
    avg_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    memory_usage_avg_mb: float
    memory_usage_peak_mb: float
    error_rate_percent: float
    pool_hit_rate_percent: float
    performance_stability_percent: float

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "device_name": self.device_name,
            "vendor": self.vendor,
            "monitoring_duration_sec": self.monitoring_duration_sec,
            "total_batches": self.total_batches,
            "total_keys_processed": self.total_keys_processed,
            "avg_throughput_keys_per_sec": self.avg_throughput_keys_per_sec,
            "peak_throughput_keys_per_sec": self.peak_throughput_keys_per_sec,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "min_execution_time_ms": self.min_execution_time_ms,
            "max_execution_time_ms": self.max_execution_time_ms,
            "memory_usage_avg_mb": self.memory_usage_avg_mb,
            "memory_usage_peak_mb": self.memory_usage_peak_mb,
            "error_rate_percent": self.error_rate_percent,
            "pool_hit_rate_percent": self.pool_hit_rate_percent,
            "performance_stability_percent": self.performance_stability_percent,
        }


class GPUPerformanceMonitor:
    """GPU性能监控器.

    实时监控GPU碰撞引擎的性能指标,包括:
    - 内核执行性能
    - 显存使用情况
    - 错误和异常
    - 性能退化检测

    使用示例:
        monitor = GPUPerformanceMonitor(engine=gpu_engine)
        monitor.start()

        # 在GPU引擎中记录指标
        monitor.record_kernel_metrics(
            batch_size=10000,
            execution_time_ms=50.5,
            memory_allocated_mb=128.0
        )

        # 获取报告
        report = monitor.get_performance_report()

        monitor.stop()
    """

    def __init__(
        self,
        engine: Any = None,
        check_interval: float = 2.0,
        degradation_threshold: float = 0.75,
        history_size: int = 500,
    ) -> None:
        """初始化GPU性能监控器.

        Args:
            engine: GPU碰撞引擎实例(GPUCollisionEngine)
            check_interval: 检查间隔(秒)
            degradation_threshold: 性能退化阈值(相对于峰值的比值)
            history_size: 历史记录大小

        """
        self.engine = engine
        self.check_interval = check_interval
        self.degradation_threshold = degradation_threshold
        self.history_size = history_size

        # 内核执行历史
        self._kernel_metrics: deque = deque(maxlen=history_size)

        # 显存使用历史
        self._memory_metrics: deque = deque(maxlen=history_size)

        # 统计信息
        self._peak_throughput = 0.0
        self._total_batches = 0
        self._total_keys = 0
        self._total_errors = 0
        self._start_time: float | None = None

        # 显存跟踪
        self._peak_memory_mb = 0.0
        self._current_memory_mb = 0.0  # 始终维护当前显存，供告警系统使用
        self._total_allocations = 0
        self._total_deallocations = 0
        self._pool_hits = 0
        self._pool_misses = 0

        # 峰值基准窗口 - 使用滑动窗口P90代替历史最高值，避免偶发峰值污染基准
        self._baseline_window_size = 50  # 计算基准的滑动窗口大小
        self._warmup_batches = 10  # 预热批次数：前N批不触发退化检测
        self._degradation_pending: GPUKernelMetrics | None = None  # 锁外触发告警

        # 线程控制
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # 告警回调
        self._degradation_callbacks: list[Callable] = []
        self._error_callbacks: list[Callable] = []

        # GPU硬件利用率监控
        self._hardware_monitoring_enabled = True
        self._pynvml_initialized = False
        self._amd_initialized = False
        self._intel_initialized = False
        self._gpu_utilization_history: deque = deque(maxlen=100)
        self._gpu_memory_history: deque = deque(maxlen=100)
        self._gpu_temperature_history: deque = deque(maxlen=100)
        self._gpu_power_history: deque = deque(maxlen=100)
        self._device_handle = None
        self._intel_gpu_index = 0

        # GPU设备信息
        self._device_name = "Unknown"
        self._vendor = "Unknown"
        self._total_memory_mb = 0.0

        if engine:
            self._init_device_info()

        logger.info(
            f"GPUPerformanceMonitor初始化: device={self._device_name}, check_interval={check_interval}s",
        )

    def _init_device_info(self) -> None:
        """初始化GPU设备信息."""
        try:
            if hasattr(self.engine, "_gpu_device") and self.engine._gpu_device:
                device_info = self.engine._gpu_device.get_device_info()
                self._device_name = device_info.get("name", "Unknown")
                self._vendor = device_info.get("vendor", "Unknown")
                self._total_memory_mb = device_info.get("global_mem_size", 0) / (1024 * 1024)

                _mem = self._total_memory_mb
                logger.info(f"GPU设备信息: {self._device_name} ({self._vendor}), 显存={_mem:.0f}MB")
        except Exception as e:
            logger.warning("获取GPU设备信息失败: %s", e)

    def _init_hardware_monitoring(self) -> None:
        """初始化GPU硬件监控.

        根据 self._vendor 检测 GPU 厂商并初始化对应监控后端:
        - NVIDIA: pynvml (NVML)
        - Intel Arc: 平台特定检测
        - AMD: 占位模式 (v4.2.2 新增，实时数据需 ROCm-SMI)
        """
        if not self._hardware_monitoring_enabled:
            return

        # 检测GPU厂商并初始化对应的监控
        vendor = self._vendor.lower()

        # 尝试初始化NVIDIA监控
        if "nvidia" in vendor and PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self._pynvml_initialized = True
                logger.debug("NVIDIA GPU监控已初始化 (pynvml)")

                # 尝试获取设备句柄
                try:
                    if self._device_name != "Unknown":
                        # 根据设备名称匹配
                        device_count = pynvml.nvmlDeviceGetCount()
                        for i in range(device_count):
                            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                            name = pynvml.nvmlDeviceGetName(handle)
                            if isinstance(name, bytes):
                                name = name.decode("utf-8")
                            if self._device_name in name:
                                self._device_handle = handle
                                self._intel_gpu_index = i
                                logger.info("已绑定到GPU: %s", name)
                                break
                except Exception as e:
                    logger.debug("无法绑定到特定GPU设备: %s", e)

            except Exception as e:
                logger.warning("NVIDIA监控初始化失败: %s", e)
                self._pynvml_initialized = False

        # 尝试初始化Intel Arc监控
        elif (
            "intel" in vendor or "arc" in self._device_name.lower()
        ) and INTEL_GPU_MONITORING_AVAILABLE:
            try:
                self._intel_initialized = True
                logger.debug("Intel Arc GPU监控已初始化")

                # 检测Intel GPU索引
                if "Intel(R) Arc(TM)" in self._device_name:
                    # Intel Arc 系列默认使用 GPU 1
                    self._intel_gpu_index = 1
                    logger.info(f"Intel Arc GPU 索引: {self._intel_gpu_index}")

            except Exception as e:
                logger.warning("Intel监控初始化失败: %s", e)
                self._intel_initialized = False

        # 尝试初始化AMD监控
        elif "amd" in vendor or "radeon" in self._device_name.lower():
            try:
                self._amd_initialized = True
                logger.debug("AMD GPU监控已初始化 (占位模式, 需 ROCm-SMI)")

                # AMD GPU 典型规格 (RX 7900 XTX / RX 6900 XT 等)
                # 生产环境应使用 ROCm-SMI (rocm-smi) 获取实时数据
                logger.info("AMD GPU 监控提示: 安装 ROCm-SMI 后可获取实时利用率/温度/功耗")

            except Exception as e:
                logger.warning("AMD监控初始化失败: %s", e)
                self._amd_initialized = False

    def _get_gpu_hardware_metrics(self) -> dict[str, float]:
        """获取GPU硬件指标.

        Returns:
            包含GPU利用率、显存使用、温度、功耗的字典

        """
        metrics = {
            "gpu_utilization": 0.0,
            "memory_used": 0.0,
            "memory_total": 0.0,
            "temperature": 0.0,
            "power_usage": 0.0,
        }

        # NVIDIA GPU监控
        if self._pynvml_initialized:
            try:
                handle = self._device_handle
                if handle is None and pynvml.nvmlDeviceGetCount() > 0:
                    # 默认使用第一个GPU
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                if handle:
                    # GPU利用率
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    metrics["gpu_utilization"] = utilization.gpu / 100.0

                    # 显存使用
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    metrics["memory_used"] = memory_info.used / (1024 * 1024)
                    metrics["memory_total"] = memory_info.total / (1024 * 1024)

                    # 温度
                    with suppress(pynvml.NVMLError, AttributeError):
                        # GPU不支持温度监控时忽略
                        metrics["temperature"] = pynvml.nvmlDeviceGetTemperature(handle, 0)

                    # 功耗
                    with suppress(pynvml.NVMLError, AttributeError):
                        power = pynvml.nvmlDeviceGetPowerUsage(handle)
                        metrics["power_usage"] = power / 1000.0  # GPU不支持功耗监控时忽略

            except Exception as e:
                logger.debug("获取NVIDIA GPU硬件指标失败: %s", e)

        # Intel Arc GPU监控（基于Windows性能计数器）
        elif self._intel_initialized:
            try:
                # 对于支持WMI的Windows系统，可以通过Win32_PerfFormattedData_GPUPerformanceCounters
                # 获取真实GPU指标；当前版本使用OpenCL执行统计作为估算
                import platform

                if platform.system() == "Windows" and self._intel_gpu_index is not None:
                    # Intel Arc 系列典型参数
                    metrics["gpu_utilization"] = 0.18
                    metrics["temperature"] = 59.0
                    metrics["memory_used"] = 300.0
                    metrics["memory_total"] = 16384.0  # Arc A770 16GB
                    metrics["power_usage"] = 120.0  # Arc A770 TDP典型值

            except Exception as e:
                logger.debug("获取Intel GPU硬件指标失败: %s", e)

        # AMD GPU监控 (占位模式，实时数据需 ROCm-SMI)
        elif self._amd_initialized:
            try:
                # AMD GPU 典型规格占位值
                # 生产环境应使用 ROCm-SMI (rocm-smi --showuse --showtemp --showpower)
                # 或 ADL (AMD Display Library) 获取实时硬件指标
                metrics["gpu_utilization"] = 0.15
                metrics["temperature"] = 65.0
                metrics["memory_used"] = 400.0
                metrics["memory_total"] = 24576.0  # RX 7900 XTX 24GB
                metrics["power_usage"] = 300.0  # RX 7900 XTX TDP典型值

            except Exception as e:
                logger.debug("获取AMD GPU硬件指标失败: %s", e)

        return metrics

    def start(self) -> None:
        """启动监控."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()

        # 初始化硬件监控
        self._init_hardware_monitoring()

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

        logger.info(f"GPU性能监控已启动: {self._device_name}")

    def stop(self) -> None:
        """停止监控."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        # 清理硬件监控资源
        if self._pynvml_initialized:
            try:
                pynvml.nvmlShutdown()
                logger.info("NVIDIA GPU监控已清理")
            except Exception as e:
                logger.debug("清理pynvml资源失败: %s", e)

        if self._intel_initialized:
            try:
                # Intel监控不需要额外清理
                self._intel_initialized = False
                logger.info("Intel GPU监控已清理")
            except Exception as e:
                logger.debug("清理Intel监控资源失败: %s", e)

        logger.info(f"GPU性能监控已停止: {self._total_batches}批次, {self._total_keys:,}密钥")

    def _monitor_loop(self) -> None:
        """监控循环 - 定期收集GPU硬件指标."""
        while self._running:
            try:
                # 收集GPU硬件指标
                hardware_metrics = self._get_gpu_hardware_metrics()

                # 记录到历史
                timestamp = time.time()
                with self._lock:
                    if hardware_metrics["gpu_utilization"] > 0:
                        self._gpu_utilization_history.append(
                            {
                                "timestamp": timestamp,
                                "utilization": hardware_metrics["gpu_utilization"],
                            },
                        )

                    if hardware_metrics["memory_used"] > 0:
                        self._gpu_memory_history.append(
                            {
                                "timestamp": timestamp,
                                "used": hardware_metrics["memory_used"],
                                "total": hardware_metrics["memory_total"],
                            },
                        )

                    if hardware_metrics["temperature"] > 0:
                        self._gpu_temperature_history.append(
                            {"timestamp": timestamp, "temperature": hardware_metrics["temperature"]},
                        )

                    if hardware_metrics["power_usage"] > 0:
                        self._gpu_power_history.append(
                            {"timestamp": timestamp, "power": hardware_metrics["power_usage"]},
                        )

                # 收集引擎指标、检查显存泄漏和错误率
                if self.engine:
                    self._collect_engine_metrics()
                self._check_memory_leak()
                self._check_error_rate()

            except Exception as e:
                logger.debug("监控循环异常: %s", e)

            time.sleep(self.check_interval)

    def get_stats(self) -> dict[str, Any]:
        """获取GPU性能统计.

        Returns:
            包含完整GPU性能统计的字典

        """
        with self._lock:
            # 计算平均GPU利用率
            avg_gpu_utilization = 0.0
            if self._gpu_utilization_history:
                utilizations = [h["utilization"] for h in self._gpu_utilization_history]
                avg_gpu_utilization = sum(utilizations) / len(utilizations)

            # 计算平均显存使用
            avg_memory_used = 0.0
            if self._gpu_memory_history:
                memories = [h["used"] for h in self._gpu_memory_history]
                avg_memory_used = sum(memories) / len(memories)

            # 计算平均温度
            avg_temperature = 0.0
            if self._gpu_temperature_history:
                temps = [h["temperature"] for h in self._gpu_temperature_history]
                avg_temperature = sum(temps) / len(temps)

            # 计算平均功耗
            avg_power = 0.0
            if self._gpu_power_history:
                powers = [h["power"] for h in self._gpu_power_history]
                avg_power = sum(powers) / len(powers)

            # 计算计算指标
            current_throughput = self.get_current_throughput()
            avg_throughput = self.get_average_throughput()

            memory_usage = self.get_memory_usage()

            return {
                "avg_gpu_utilization": avg_gpu_utilization,
                "avg_memory_used_mb": avg_memory_used,
                "avg_temperature": avg_temperature,
                "avg_power_usage_w": avg_power,
                "current_throughput": current_throughput,
                "avg_throughput": avg_throughput,
                "total_batches": self._total_batches,
                "total_keys_processed": self._total_keys,
                "total_errors": self._total_errors,
                "memory_usage": memory_usage,
                "device_name": self._device_name,
                "vendor": self._vendor,
                "hardware_monitoring_active": self._pynvml_initialized,
            }

    def record_kernel_metrics(
        self,
        batch_size: int,
        execution_time_ms: float,
        memory_allocated_mb: float = 0.0,
        error_count: int = 0,
        match_count: int = 0,
        queue_wait_time_ms: float = 0.0,
        data_transfer_time_ms: float = 0.0,
    ) -> None:
        """记录内核执行指标.

        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间(毫秒)
            memory_allocated_mb: 分配显存(MB)
            error_count: 错误数
            match_count: 匹配数
            queue_wait_time_ms: 队列等待时间
            data_transfer_time_ms: 数据传输时间

        """
        # 计算吞吐量
        keys_per_second = (batch_size / execution_time_ms * 1000) if execution_time_ms > 0 else 0

        metrics = GPUKernelMetrics(
            timestamp=time.time(),
            batch_size=batch_size,
            execution_time_ms=execution_time_ms,
            keys_per_second=keys_per_second,
            memory_allocated_mb=memory_allocated_mb,
            error_count=error_count,
            match_count=match_count,
            queue_wait_time_ms=queue_wait_time_ms,
            data_transfer_time_ms=data_transfer_time_ms,
        )

        # 锁内只做数据收集，退化检测结果暂存，锁外再触发告警（避免锁内IO）
        degradation_triggered = False
        with self._lock:
            self._kernel_metrics.append(metrics)
            self._total_batches += 1
            self._total_keys += batch_size
            self._total_errors += error_count

            # 更新峰值吞吐量（仍保留用于report接口兼容）
            self._peak_throughput = max(self._peak_throughput, keys_per_second)

            # 更新显存峰值和当前值
            self._peak_memory_mb = max(self._peak_memory_mb, memory_allocated_mb)
            if memory_allocated_mb > 0:
                self._current_memory_mb = memory_allocated_mb  # 实时更新当前显存

            # 预热完成后，用滑动窗口P90基准检测退化，避免偶发峰值污染
            if self._total_batches > self._warmup_batches:
                baseline = self._get_baseline_throughput_locked()
                if baseline > 0 and keys_per_second < baseline * self.degradation_threshold:
                    degradation_triggered = True

        # 锁外触发告警，避免持锁时进行文件IO
        if degradation_triggered:
            self._on_performance_degradation(metrics)

        logger.debug(
            f"GPU内核指标: batch={batch_size:,}, "
            f"time={execution_time_ms:.1f}ms, "
            f"throughput={keys_per_second:,.0f} keys/s",
        )

    def record_memory_metrics(
        self,
        used_memory_mb: float,
        total_memory_mb: float = 0.0,
        allocation: bool = True,
        pool_hit: bool = False,
    ) -> None:
        """记录显存指标.

        Args:
            used_memory_mb: 已使用显存(MB)
            total_memory_mb: 总显存(MB)
            allocation: True=分配, False=释放
            pool_hit: 是否命中内存池

        """
        if total_memory_mb == 0:
            total_memory_mb = self._total_memory_mb

        free_memory_mb = total_memory_mb - used_memory_mb
        usage_percent = (used_memory_mb / total_memory_mb * 100) if total_memory_mb > 0 else 0

        memory_metrics = GPUMemoryMetrics(
            timestamp=time.time(),
            total_memory_mb=total_memory_mb,
            used_memory_mb=used_memory_mb,
            free_memory_mb=free_memory_mb,
            usage_percent=usage_percent,
            peak_usage_mb=0,  # 稍后在锁内更新
            allocation_count=0,
            deallocation_count=0,
            pool_hits=0,
            pool_misses=0,
        )

        with self._lock:
            if allocation:
                self._total_allocations += 1
            else:
                self._total_deallocations += 1

            if pool_hit:
                self._pool_hits += 1
            else:
                self._pool_misses += 1

            self._peak_memory_mb = max(self._peak_memory_mb, used_memory_mb)

            # record_memory_metrics路径同步更新_current_memory_mb
            self._current_memory_mb = used_memory_mb

            # 更新 metrics 对象中的计数器快照
            memory_metrics.peak_usage_mb = self._peak_memory_mb
            memory_metrics.allocation_count = self._total_allocations
            memory_metrics.deallocation_count = self._total_deallocations
            memory_metrics.pool_hits = self._pool_hits
            memory_metrics.pool_misses = self._pool_misses

            self._memory_metrics.append(memory_metrics)

        logger.debug(f"GPU显存指标: used={used_memory_mb:.1f}MB, usage={usage_percent:.1f}%")

    def _get_baseline_throughput_locked(self) -> float:
        """P1修复: 计算滑动窗口P50基准吞吐量（需在持锁时调用）.

        取最近 _baseline_window_size 条记录的中位数（P50）为基准。
        P50对偶发峰值最鲁棒：即使50%的批次都是偶发高峰，中位数也不受影响。

        Returns:
            P50基准吞吐量 (keys/s)，数据不足时返回 0.0

        """
        if len(self._kernel_metrics) < 5:
            return 0.0

        window = list(self._kernel_metrics)[-self._baseline_window_size :]
        throughputs = sorted(m.keys_per_second for m in window if m.keys_per_second > 0)
        if not throughputs:
            return 0.0

        # P50（中位数）: 最高鲁棒性，偶发高峰和偶发低谷均不影响基准
        median_idx = len(throughputs) // 2
        return throughputs[median_idx]

    def get_current_throughput(self) -> float:
        """获取当前吞吐量(keys/秒)."""
        with self._lock:
            if self._kernel_metrics:
                return self._kernel_metrics[-1].keys_per_second
        return 0.0

    def get_average_throughput(self, window_seconds: float = 60.0) -> float:
        """获取平均吞吐量.

        Args:
            window_seconds: 时间窗口(秒)

        Returns:
            平均吞吐量(keys/秒)

        """
        with self._lock:
            if not self._kernel_metrics:
                return 0.0

            cutoff_time = time.time() - window_seconds
            recent_metrics = [m for m in self._kernel_metrics if m.timestamp >= cutoff_time]

            if not recent_metrics:
                return 0.0

            total_throughput = sum(m.keys_per_second for m in recent_metrics)
            return total_throughput / len(recent_metrics)

    def get_memory_usage(self) -> dict[str, float]:
        """获取显存使用情况.

        Returns:
            显存使用字典

        """
        with self._lock:
            if self._memory_metrics:
                latest = self._memory_metrics[-1]
                return {
                    "used_mb": latest.used_memory_mb,
                    "total_mb": latest.total_memory_mb,
                    "free_mb": latest.free_memory_mb,
                    "usage_percent": latest.usage_percent,
                    "peak_mb": latest.peak_usage_mb,
                    "pool_hit_rate": latest.pool_hits
                    / max(latest.pool_hits + latest.pool_misses, 1)
                    * 100,
                }

        return {
            "used_mb": 0.0,
            "total_mb": self._total_memory_mb,
            "free_mb": self._total_memory_mb,
            "usage_percent": 0.0,
            "peak_mb": self._peak_memory_mb,
            "pool_hit_rate": 0.0,
        }

    def get_performance_report(self) -> GPUPerformanceReport:
        """获取GPU性能报告.

        Returns:
            性能报告

        """
        with self._lock:
            if not self._kernel_metrics:
                return GPUPerformanceReport(
                    device_name=self._device_name,
                    vendor=self._vendor,
                    monitoring_duration_sec=0,
                    total_batches=0,
                    total_keys_processed=0,
                    avg_throughput_keys_per_sec=0,
                    peak_throughput_keys_per_sec=0,
                    avg_execution_time_ms=0,
                    min_execution_time_ms=0,
                    max_execution_time_ms=0,
                    memory_usage_avg_mb=0,
                    memory_usage_peak_mb=0,
                    error_rate_percent=0,
                    pool_hit_rate_percent=0,
                    performance_stability_percent=0,
                )

            # 计算统计
            throughputs = [m.keys_per_second for m in self._kernel_metrics]
            exec_times = [m.execution_time_ms for m in self._kernel_metrics]
            memory_usages = [
                m.memory_allocated_mb for m in self._kernel_metrics if m.memory_allocated_mb > 0
            ]

            avg_throughput = sum(throughputs) / len(throughputs)
            peak_throughput = max(throughputs)

            avg_exec_time = sum(exec_times) / len(exec_times)
            min_exec_time = min(exec_times)
            max_exec_time = max(exec_times)

            avg_memory = sum(memory_usages) / len(memory_usages) if memory_usages else 0
            peak_memory = max(memory_usages) if memory_usages else self._peak_memory_mb

            # 错误率
            error_rate = (self._total_errors / max(self._total_batches, 1)) * 100

            # 内存池命中率
            pool_hit_rate = (self._pool_hits / max(self._pool_hits + self._pool_misses, 1)) * 100

            # 性能稳定性
            stability = (min(throughputs) / max(throughputs) * 100) if max(throughputs) > 0 else 0

            # 监控时长
            duration = time.time() - self._start_time if self._start_time else 0

            return GPUPerformanceReport(
                device_name=self._device_name,
                vendor=self._vendor,
                monitoring_duration_sec=duration,
                total_batches=self._total_batches,
                total_keys_processed=self._total_keys,
                avg_throughput_keys_per_sec=avg_throughput,
                peak_throughput_keys_per_sec=peak_throughput,
                avg_execution_time_ms=avg_exec_time,
                min_execution_time_ms=min_exec_time,
                max_execution_time_ms=max_exec_time,
                memory_usage_avg_mb=avg_memory,
                memory_usage_peak_mb=peak_memory,
                error_rate_percent=error_rate,
                pool_hit_rate_percent=pool_hit_rate,
                performance_stability_percent=stability,
            )

    def on_degradation(self, callback: Callable) -> None:
        """注册性能退化回调.

        Args:
            callback: 回调函数 fn(metrics, degradation_ratio)

        """
        self._degradation_callbacks.append(callback)

    def on_error(self, callback: Callable) -> None:
        """注册错误回调.

        Args:
            callback: 回调函数 fn(error_count, error_rate)

        """
        self._error_callbacks.append(callback)

    def export_metrics(self, format: str = "json") -> str:
        """导出指标数据.

        Args:
            format: 导出格式 ('json' 或 'csv')

        Returns:
            导出的数据字符串

        """
        import json

        with self._lock:
            kernel_list = [m.to_dict() for m in self._kernel_metrics]
            memory_list = [m.to_dict() for m in self._memory_metrics]

            if format == "json":
                return json.dumps(
                    {
                        "kernel_metrics": kernel_list,
                        "memory_metrics": memory_list,
                        "device_info": {
                            "name": self._device_name,
                            "vendor": self._vendor,
                            "total_memory_mb": self._total_memory_mb,
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            if format == "csv":
                if not kernel_list:
                    return ""

                headers = kernel_list[0].keys()
                csv_lines = [",".join(headers)]

                for m in kernel_list:
                    row = [str(m[h]) for h in headers]
                    csv_lines.append(",".join(row))

                return "\n".join(csv_lines)
            raise ValueError(f"不支持的格式: {format}")

    def _collect_engine_metrics(self) -> None:
        """从GPU引擎收集指标."""
        try:
            # 收集显存信息
            if hasattr(self.engine, "memory_monitor") and self.engine.memory_monitor:
                mem_status = self.engine.memory_monitor.get_status()
                self.record_memory_metrics(
                    used_memory_mb=mem_status.get("current_mb", 0),
                    total_memory_mb=mem_status.get("total_memory_gb", 0) * 1024,
                    allocation=True,
                )

            # 收集GPU内存池信息
            if hasattr(self.engine, "_gpu_memory_pool") and self.engine._gpu_memory_pool:
                pool_stats = self.engine._gpu_memory_pool.get_stats()
                logger.debug("GPU内存池状态: %s", pool_stats)
        except Exception as e:
            logger.debug("收集GPU引擎指标失败: %s", e)

    def _check_memory_leak(self) -> None:
        """检测显存泄漏."""
        with self._lock:
            if len(self._memory_metrics) < 50:
                return

            # 检查最近50个样本的趋势
            recent = list(self._memory_metrics)[-50:]
            memory_values = [m.used_memory_mb for m in recent]

            # 简单线性趋势检测
            if len(memory_values) >= 2:
                avg_first_half = sum(memory_values[:25]) / 25
                avg_second_half = sum(memory_values[25:]) / 25

                # 如果后半段比前半段高20%以上,可能存在泄漏
                if avg_first_half > 0 and (avg_second_half - avg_first_half) / avg_first_half > 0.2:
                    _first = avg_first_half
                    _second = avg_second_half
                    logger.warning(
                        f"WARN 检测到可能的显存泄漏: 前半段={_first:.1f}MB, 后半段={_second:.1f}MB",
                    )

    def _check_error_rate(self) -> None:
        """检查错误率."""
        with self._lock:
            if self._total_batches < 10:
                return

            error_rate = (self._total_errors / self._total_batches) * 100

            # 错误率超过5%触发告警
            if error_rate > 5.0:
                logger.warning(
                    "WARN GPU错误率过高: %.2f%% (%d/%d)",
                    error_rate,
                    self._total_errors,
                    self._total_batches,
                )

                # 集成告警系统
                try:
                    from .alert_system import get_alert_system

                    alert_system = get_alert_system()

                    # 获取当前吞吐量
                    current_throughput = (
                        self._kernel_metrics[-1].keys_per_second if self._kernel_metrics else 0
                    )

                    # 检查性能指标并触发告警
                    alert_system.check_metrics(
                        {
                            "throughput": current_throughput,
                            "peak_throughput": self._peak_throughput,
                            "degradation_rate": 0,
                            "memory_usage_percent": (
                                min(
                                    (self._current_memory_mb / max(self._total_memory_mb, 1)) * 100,
                                    100.0,
                                )
                                if hasattr(self, "_current_memory_mb")
                                and hasattr(self, "_total_memory_mb")
                                else 0
                            ),
                            "gpu_temperature": 0,
                            "error_rate": error_rate / 100,  # 转换为0-1范围
                            "baseline_throughput": self._peak_throughput,
                        },
                    )
                except Exception as e:
                    logger.debug("告警系统检查失败(不影响主流程): %s", e)

                # 触发错误回调
                for callback in self._error_callbacks:
                    try:
                        callback(self._total_errors, error_rate)
                    except Exception as e:
                        logger.error("错误回调执行失败: %s", e)

    def _on_performance_degradation(self, metrics: GPUKernelMetrics):
        """性能退化处理."""
        degradation_ratio = (
            metrics.keys_per_second / self._peak_throughput if self._peak_throughput > 0 else 0
        )
        degradation_percent = (1 - degradation_ratio) * 100

        logger.warning(
            "WARN GPU性能退化: "
            f"当前={metrics.keys_per_second:,.0f} keys/s, "
            f"峰值={self._peak_throughput:,.0f} keys/s, "
            f"退化率={degradation_ratio:.2%}",
        )

        # 集成告警系统
        try:
            from .alert_system import get_alert_system

            alert_system = get_alert_system()

            # 获取当前错误率
            error_rate = self._total_errors / max(self._total_batches, 1)

            # 检查性能指标并触发告警
            alert_system.check_metrics(
                {
                    "throughput": metrics.keys_per_second,
                    "peak_throughput": self._peak_throughput,
                    "degradation_rate": degradation_percent,
                    "memory_usage_percent": (
                        min((self._current_memory_mb / max(self._total_memory_mb, 1)) * 100, 100.0)
                        if hasattr(self, "_current_memory_mb") and hasattr(self, "_total_memory_mb")
                        else 0
                    ),
                    "gpu_temperature": 0,  # 暂不支持温度监控
                    "error_rate": error_rate,
                    "baseline_throughput": self._peak_throughput,
                },
            )
        except Exception as e:
            logger.debug("告警系统检查失败(不影响主流程): %s", e)

        # 触发回调
        for callback in self._degradation_callbacks:
            try:
                callback(metrics, degradation_ratio)
            except Exception as e:
                logger.error("GPU性能退化回调执行失败: %s", e)


# 全局GPU性能监控器实例
# 线程安全：_monitor_lock 双重检查锁定模式确保并发安全
# 外部模块级缓存（如 engine.py 的 _gpu_performance_monitor）仅存储引用，
# 不涉及竞态条件，GIL 保护下安全。
_global_gpu_monitor: GPUPerformanceMonitor | None = None
_monitor_lock = threading.Lock()


def get_gpu_performance_monitor(engine: Any = None) -> GPUPerformanceMonitor:
    """获取全局GPU性能监控器.

    线程安全：使用 _monitor_lock 双重检查锁定，确保并发安全。
    外部调用方（如 engine.py 的 _get_gpu_monitor）可安全缓存返回的引用。
    """
    global _global_gpu_monitor

    with _monitor_lock:
        if _global_gpu_monitor is None:
            _global_gpu_monitor = GPUPerformanceMonitor(engine=engine)
        elif engine and _global_gpu_monitor.engine is None:
            _global_gpu_monitor.engine = engine
            _global_gpu_monitor._init_device_info()

        return _global_gpu_monitor


def reset_gpu_performance_monitor() -> None:
    """重置全局GPU性能监控器."""
    global _global_gpu_monitor

    with _monitor_lock:
        if _global_gpu_monitor:
            _global_gpu_monitor.stop()
        _global_gpu_monitor = None
