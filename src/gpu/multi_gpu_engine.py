"""多GPU碰撞引擎

协调多个GPU工作器进行并行私钥碰撞搜索。
采用任务分割策略,每个GPU独立搜索不同的私钥范围。

增强功能：
- 实时工作负载监控
- 性能指标收集和分析
- 负载均衡器集成
- 工作状态跟踪
- 自动重平衡触发
- 分布式统计聚合（减少锁竞争，可配置）
"""

import threading
import time
from collections.abc import Callable
from typing import Any, cast

from ..config.optimization_config import is_feature_enabled

# 统一日志获取
from ..utils import get_configured_logger

# 根据配置条件导入优化模块
_aggregator_available = is_feature_enabled("distributed_aggregator")

from .data_monitor import DataMonitor  # noqa: E402
from .gpu_config import MultiGPUConfig, WorkerConfig  # noqa: E402
from .gpu_recovery_manager import GPURecoveryManager  # noqa: E402
from .load_balancer import GPULoadBalancer  # noqa: E402
from .memory_pool import GPUMemoryPool  # noqa: E402
from .metrics import get_metrics_collector  # noqa: E402
from .selector import get_gpu_selector  # noqa: E402
from .worker import SingleGPUWorker  # noqa: E402

if _aggregator_available:
    from .distributed_stats_aggregator import DistributedStatsAggregator

logger = get_configured_logger("MultiGPUEngine")


class MultiGPUCollisionEngine:
    """多GPU碰撞引擎

    协调多个GPU并行工作,自动分配任务和汇总结果。

    使用示例:
        engine = MultiGPUCollisionEngine()

        # 初始化(自动选择2个最佳GPU)
        engine.initialize(device_count=2)

        # 启动碰撞
        engine.start(targets=target_addresses, mode='random')

        # 获取统计
        stats = engine.get_combined_stats()

        # 停止
        engine.stop()
    """

    def __init__(self, config: dict | MultiGPUConfig | None = None) -> None:
        """初始化多GPU引擎

        Args:
            config: 配置字典（兼容旧接口）或 MultiGPUConfig 实例
        """
        # M-3修复: 添加配置验证（dict 和 MultiGPUConfig 均需验证）
        if isinstance(config, dict):
            config = self._validate_config_values(config)
        elif isinstance(config, MultiGPUConfig):
            self._validate_config_object(config)

        # 统一转换为 MultiGPUConfig（兼容 Dict 旧接口）
        if config is None:
            self.config = MultiGPUConfig()
        elif isinstance(config, MultiGPUConfig):
            self.config = config
        else:
            self.config = MultiGPUConfig.from_dict(config)

        # 核心组件
        self.selector = get_gpu_selector()
        self.load_balancer: GPULoadBalancer | None = None
        self.workers: dict[int, Any] = {}

        # 状态管理 (使用锁保护)
        #
        # 🔒 锁顺序约定 (MUST follow to avoid deadlock):
        #    _state_lock → _workers_lock → _matches_lock
        #    即: 如果同一方法需要获取多把锁,必须按此顺序获取。
        self._state_lock = threading.Lock()
        self._running = False
        self._initialized = False
        self._devices: list[dict[str, Any]] = []
        self._targets: set[str] = set()

        # 工作器字典锁
        self._workers_lock = threading.Lock()

        # 匹配结果锁
        self._matches_lock = threading.Lock()

        # 结果收集
        self._all_matches: list[dict[str, Any]] = []
        self._match_callback: Callable[..., Any] | None = None

        # 统计信息
        self._start_time: float | None = None
        self._total_keys_checked = 0

        # 数据监控器
        self.data_monitor = DataMonitor(config=cast(Any, self.config.data_monitor))
        self._monitor_enabled = self.config.enable_data_monitor

        # GPU恢复管理器
        rc = self.config.gpu_recovery
        self.recovery_manager = GPURecoveryManager(
            max_retry_count=rc.max_retry_count,
            retry_delay_seconds=rc.retry_delay_seconds,
            batch_size_reduction_factor=rc.batch_size_reduction_factor,
            auto_redistribute=rc.auto_redistribute,
        )

        # 同厂商内核编译缓存: vendor_key -> 编译配置元数据
        # 注意: OpenCL Program 不能跨 context 共享。
        # 此处缓存厂商编译配置（编译选项等元数据），内核内核由
        # GPUContext 独立编译并缓存自身 context 级别的 program。
        self._compiled_programs: dict[str, Any] = {}  # vendor_key -> {source, options}

        # Per-GPU 内存池分配配置: device_index -> max_memory_mb
        # 由 create_proportional_pools 按显存比例计算
        self._device_memory_pool_config: dict[int, int] = {}

        # 可配置的工作器等待超时（秒）
        self._worker_join_timeout = self.config.worker_join_timeout

        # 工作负载监控
        self._workload_monitor = None
        self._monitor_thread: threading.Thread | None = None
        self._monitor_interval = self.config.workload_monitor_interval
        self._auto_rebalance = self.config.auto_rebalance

        # 性能历史数据（添加锁防止竞态条件）
        self._performance_history: list[dict[str, Any]] = []
        self._performance_history_lock = threading.Lock()  # 修复: 防止并发访问导致数据竞争
        # P2修复: 配置化历史长度上限（原硬编码100）
        self._max_history_size = self.config.performance_history_max_size

        # 分布式统计聚合器（减少锁竞争，支持大规模GPU集群）- 根据配置启用
        self._stats_aggregator = None
        if _aggregator_available:
            self._stats_aggregator = DistributedStatsAggregator()
            logger.info("分布式统计聚合器已启用")

        # 结构化metrics收集器（可观测性增强）
        self._metrics = get_metrics_collector()

        logger.info("MultiGPUCollisionEngine已创建")

    def initialize(
        self,
        device_indices: list[int] | None = None,
        device_count: int = -1,
        strategy: str = "performance",
    ) -> bool:
        """初始化GPU设备

        Args:
            device_indices: 指定GPU索引列表(为None时自动选择)
            device_count: 自动选择的GPU数量(-1表示使用所有可用GPU)
            strategy: 负载策略('performance'或'equal')

        Returns:
            初始化是否成功
        """
        try:
            # 检测设备
            all_devices = self.selector.detect_all_devices()
            if not all_devices:
                logger.error("未检测到GPU设备")
                return False

            # 选择设备
            if device_indices:
                # 手动指定
                self._devices = self.selector.select_devices_by_indices(device_indices)
            elif device_count > 0:
                # 自动选择前N个最佳
                sorted_devices = sorted(all_devices, key=lambda d: d.get("score", 0), reverse=True)
                self._devices = sorted_devices[:device_count]
            else:
                # 使用所有GPU
                self._devices = all_devices

            if not self._devices:
                logger.error("无可用GPU设备")
                return False

            logger.info(f"初始化 {len(self._devices)} 个GPU设备: {[d['name'] for d in self._devices]}")

            # 按显存比例计算 Per-GPU 内存池分配配置
            total_pool_mb = self.config.total_pool_mb
            proportional_pools = GPUMemoryPool.create_proportional_pools(
                devices=self._devices,
                contexts=None,  # context 由 GPUCollisionEngine 自行管理
                total_pool_mb=total_pool_mb,
            )
            # 保存各设备的内存池大小配置，以全局索引为键
            self._device_memory_pool_config = {}
            total_allocated_mb = 0
            for local_i, device in enumerate(self._devices):
                global_idx = device["global_index"]
                pool = proportional_pools.get(local_i)
                if pool is not None:
                    mb = pool.get_stats()["max_memory_mb"]
                    self._device_memory_pool_config[global_idx] = int(mb)
                    total_allocated_mb += int(mb)
                    logger.info(f"GPU {global_idx} 内存池分配: {int(mb)}MB")

            # P2修复: 检查系统总内存限制，防止多GPU内存池分配超出系统可用RAM
            # GPU内存池虽然没有立即分配显存，但OpenCL驱动需要系统RAM作为后备
            self._check_system_memory_limit(
                total_allocated_mb=total_allocated_mb,
                device_count=len(self._devices),
            )

            # 创建负载均衡器
            self.load_balancer = GPULoadBalancer(devices=self._devices, strategy=strategy)

            with self._state_lock:
                self._initialized = True

            logger.info("多GPU引擎初始化成功")
            return True

        except Exception as e:
            logger.error(f"多GPU引擎初始化失败: {e}")
            return False

    def _validate_config_values(self, config: dict) -> dict:
        """M-3修复: 验证配置值边界

        配置值边界验证说明:
        1. 检查数值类型配置参数是否在合理范围内
        2. 防止无效配置导致运行时错误或异常行为
        3. 超出范围时自动使用默认值，保证程序稳定运行
        4. 记录警告日志，帮助用户发现配置问题

        验证的参数:
        - worker_join_timeout: 工作线程Join超时（1-300秒）
        - workload_monitor_interval: 工作负载监控间隔（1-3600秒）
        - total_pool_mb: GPU内存池总大小（64-65536MB）

        Args:
            config: 配置字典

        Returns:
            验证后的配置字典
        """
        validated = config.copy()

        int_configs = [
            ("worker_join_timeout", 1, 300, 30),
            ("workload_monitor_interval", 1, 3600, 60),
            ("total_pool_mb", 64, 65536, 512),
        ]

        for key, min_val, max_val, default in int_configs:
            if key in validated:
                val = validated[key]
                if not isinstance(val, (int, float)):
                    logger.warning(f"配置 {key} 应为数值，使用默认值 {default}")
                    validated[key] = default
                elif val < min_val or val > max_val:
                    logger.warning(
                        f"配置 {key}={val} 超出范围 [{min_val}, {max_val}]，使用默认值 {default}"
                    )
                    validated[key] = default

        return validated

    @staticmethod
    def _validate_config_object(config: "MultiGPUConfig") -> None:
        """M-3修复: 验证 MultiGPUConfig 对象参数边界

        检查配置对象中数值类型字段的合理性，超出范围时重置为默认值。
        此方法直接修改 config 对象属性。

        验证的参数:
        - worker_join_timeout: 工作线程Join超时（1-300秒）
        - workload_monitor_interval: 工作负载监控间隔（1-3600秒）
        - total_pool_mb: GPU内存池总大小（64-65536MB）
        - max_retry_count: 最大重试次数（0-100）
        - retry_delay_seconds: 重试延迟秒数（1-300）
        - batch_size_reduction_factor: 批次缩减因子（0.1-1.0）
        """
        checks = [
            ("worker_join_timeout", 1, 300, 30),
            ("workload_monitor_interval", 1, 3600, 60),
            ("total_pool_mb", 64, 65536, 512),
        ]
        for attr, min_val, max_val, default in checks:
            val = getattr(config, attr, default)
            if not isinstance(val, (int, float)) or val < min_val or val > max_val:
                logger.warning(
                    f"配置 {attr}={val} 超出范围 [{min_val}, {max_val}]，使用默认值 {default}"
                )
                setattr(config, attr, default)

        # GPU恢复管理器参数
        rc = config.gpu_recovery
        if rc.max_retry_count < 0 or rc.max_retry_count > 100:
            logger.warning(f"max_retry_count={rc.max_retry_count} 超出范围，使用默认值 3")
            rc.max_retry_count = 3
        if rc.retry_delay_seconds < 1 or rc.retry_delay_seconds > 300:
            logger.warning(f"retry_delay_seconds={rc.retry_delay_seconds} 超出范围，使用默认值 5")
            rc.retry_delay_seconds = 5
        if rc.batch_size_reduction_factor < 0.1 or rc.batch_size_reduction_factor > 1.0:
            logger.warning(
                f"batch_size_reduction_factor={rc.batch_size_reduction_factor} 超出范围，使用默认值 0.5"
            )
            rc.batch_size_reduction_factor = 0.5

    def _check_system_memory_limit(
        self, total_allocated_mb: int, device_count: int
    ) -> None:
        """P2修复: 检查系统内存限制

        多GPU场景下，内存池总分配量需在系统可用RAM范围内。
        OpenCL 驱动需要使用系统RAM作为GPU显存的后备缓冲区，
        如果内存池总和超出系统容量会导致性能下降甚至OOM。

        检查逻辑:
        1. 尝试获取系统总内存（跨平台）
        2. 计算安全上限（系统总内存的70%）
        3. 如果总分配超出安全上限，记录警告
        4. 如果总分配超出系统总内存，记录严重警告

        Args:
            total_allocated_mb: 所有GPU内存池分配总量 (MB)
            device_count: GPU数量
        """
        total_system_ram_mb = self._get_system_total_memory_mb()
        if total_system_ram_mb <= 0:
            # 无法获取系统内存信息，跳过检查
            logger.debug("无法获取系统内存信息，跳过多GPU内存池系统限制检查")
            return

        safe_limit_mb = int(total_system_ram_mb * 0.70)
        total_system_gb = total_system_ram_mb / 1024
        allocated_gb = total_allocated_mb / 1024
        safe_gb = safe_limit_mb / 1024

        if total_allocated_mb > total_system_ram_mb:
            logger.critical(
                f"⚠️ 多GPU内存池总量 ({allocated_gb:.1f}GB, {device_count}个GPU) "
                f"超出系统总RAM ({total_system_gb:.1f}GB)! "
                f"建议降低 total_pool_mb 配置或减少GPU数量"
            )
        elif total_allocated_mb > safe_limit_mb:
            logger.warning(
                f"⚠️ 多GPU内存池总量 ({allocated_gb:.1f}GB, {device_count}个GPU) "
                f"超出系统RAM安全上限 ({safe_gb:.1f}GB, 70% of {total_system_gb:.1f}GB). "
                f"可能导致系统内存压力"
            )
        else:
            logger.info(
                f"✅ 多GPU内存池总量 ({allocated_gb:.1f}GB) 在系统RAM安全范围内 "
                f"({total_system_gb:.1f}GB 总RAM, {safe_gb:.1f}GB 安全上限)"
            )

    @staticmethod
    def _get_system_total_memory_mb() -> int:
        """获取系统总内存 (MB)，跨平台实现

        Returns:
            系统总内存 (MB)，获取失败返回 -1
        """
        try:
            import ctypes

            # Windows
            if hasattr(ctypes, "windll"):
                kernel32 = ctypes.windll.kernel32

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                    ]

                mem_status = MEMORYSTATUSEX()
                mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status)):
                    return int(mem_status.ullTotalPhys // (1024 * 1024))

            # Linux
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            # 格式: "MemTotal:       16384000 kB"
                            parts = line.split()
                            if len(parts) >= 2:
                                kb = int(parts[1])
                                return kb // 1024  # kB -> MB
            except (OSError, ValueError, IndexError):
                pass

        except Exception:
            pass

        return -1

    def start(
        self,
        targets: set[str],
        mode: str = "random",
        total_keys: int = 10000000,
        match_callback: Callable | None = None,
        range_start: int | None = None,  # range/brute_force 的起始私钥
        range_end: int | None = None,  # range 的结束私钥
    ) -> bool:
        """启动多GPU碰撞搜索

        Args:
            targets: 目标地址集合
            mode: 碰撞模式 ('random' | 'range' | 'brute_force')
            total_keys: 总私钥搜索数量（random 模式下用于负载分配）
            match_callback: 找到匹配时的回调函数(device_idx, match)
            range_start: range/brute_force 模式的起始私钥（十进制整数）
            range_end: range 模式的结束私钥（十进制整数）

        Returns:
            启动是否成功
        """
        if not self._initialized:
            logger.error("引擎未初始化,请先调用initialize()")
            return False

        try:
            # 在锁内完成所有检查和状态修改,避免TOCTOU竞态条件
            with self._state_lock:
                if self._running:
                    logger.warning("引擎已在运行中")
                    return False

                # 设置状态变量
                self._targets = targets
                self._match_callback = match_callback
                self._start_time = time.time()

            # _all_matches使用单独的锁
            with self._matches_lock:
                self._all_matches = []

            # 分配任务
            assert self.load_balancer is not None
            key_ranges = self.load_balancer.assign_all_key_ranges(total_keys)

            # 创建工作器
            for device in self._devices:
                idx = device["global_index"]
                key_range = key_ranges[idx]

                # 获取设备特定配置
                device_config = self._get_device_config(device)

                # 创建工作器（传入 mode 及范围参数）
                worker = SingleGPUWorker(
                    device_idx=idx,
                    key_range=key_range,
                    targets=targets,
                    config=device_config,
                    result_callback=self._on_match_found,
                    data_monitor=self.data_monitor if self._monitor_enabled else None,
                    mode=mode,
                    range_start=range_start,
                    range_end=range_end,
                )

                with self._workers_lock:
                    self.workers[idx] = worker

                # 注册工作器到分布式统计聚合器（如果启用）
                if self._stats_aggregator:
                    self._stats_aggregator.register_worker(idx)

            # 启动所有工作器
            with self._workers_lock:
                workers_snapshot = dict(self.workers)

            for idx, worker in workers_snapshot.items():
                worker.start()
                # 更新工作器状态（如果聚合器已启用）
                if self._stats_aggregator:
                    self._stats_aggregator.update_worker_stats(idx, {"status": "running"})
                # 记录设备状态到 metrics
                self._metrics.record_device_status(idx, True)
                logger.info(f"GPU {idx} 工作器已启动")

            # 启动数据监控器
            if self._monitor_enabled:
                self.data_monitor.start(anomaly_callback=self._on_anomaly_detected)
                logger.info("数据监控器已启动")

            # 启动工作负载监控
            self._start_workload_monitor()

            with self._state_lock:
                self._running = True

            logger.info(f"多GPU碰撞已启动: {len(self.workers)}个GPU, 总私钥数={total_keys:,}")

            return True

        except Exception as e:
            logger.error(f"启动多GPU碰撞失败: {e}")
            return False

    def stop(self) -> None:
        """停止所有GPU工作器

        线程安全：使用 _stopping 标志 + _state_lock 防止重入。
        cleanup() 在调用此方法前已确保不存在并发 stop()。
        """
        # 在锁内检查并设置停止标志
        with self._state_lock:
            if not self._running:
                return
            # 防止重复进入stop()
            if getattr(self, "_stopping", False):
                logger.debug("stop() already in progress, skipping duplicate call")
                return
            self._stopping = True

        try:
            self._do_stop()
        finally:
            # 确保状态被正确更新，即使 _do_stop() 中抛出异常
            with self._state_lock:
                self._running = False
                self._stopping = False

    def _do_stop(self):
        """执行停止逻辑（内部方法，调用者需持有 _stopping 标志）"""
        logger.info("停止多GPU碰撞...")

        # 停止工作负载监控
        self._stop_workload_monitor()

        # 停止所有工作器
        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        for idx, worker in workers_snapshot.items():
            try:
                worker.stop_search()
                logger.info(f"GPU {idx} 工作器停止信号已发送")
            except Exception as e:
                logger.error(f"停止GPU {idx} 工作器失败: {e}")

        # 等待所有工作器结束
        for idx, worker in workers_snapshot.items():
            try:
                worker.join(timeout=self._worker_join_timeout)
                if worker.is_alive():
                    logger.warning(f"GPU {idx} 工作器未在{self._worker_join_timeout}秒内停止")
                else:
                    logger.info(f"GPU {idx} 工作器已停止")
            except Exception as e:
                logger.error(f"等待GPU {idx} 工作器失败: {e}")

        # 更新统计
        self._update_combined_stats()

        # 停止数据监控器
        if self._monitor_enabled:
            self.data_monitor.stop()
            logger.info("数据监控器已停止")

        logger.info("多GPU碰撞已停止")

    def pause(self) -> None:
        """暂停所有GPU工作器"""
        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        for idx, worker in workers_snapshot.items():
            try:
                worker.pause_search()
            except Exception as e:
                logger.error(f"暂停GPU {idx} 失败: {e}")

        logger.info("所有GPU工作器已暂停")

    def resume(self) -> None:
        """恢复所有GPU工作器"""
        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        for idx, worker in workers_snapshot.items():
            try:
                worker.resume_search()
            except Exception as e:
                logger.error(f"恢复GPU {idx} 失败: {e}")

        logger.info("所有GPU工作器已恢复")

    def get_combined_stats(self) -> dict:
        """获取汇总统计信息

        Returns:
            汇总统计字典
        """
        # 使用分布式统计聚合器（如果启用）
        if self._stats_aggregator:
            aggregated = self._stats_aggregator.get_combined_stats()

            stats = {
                "status": "running" if self._running else "stopped",
                "device_count": aggregated.get("device_count", len(self.workers)),
                "active_device_count": aggregated.get("active_device_count", 0),
                "total_keys_checked": aggregated.get("total_keys_checked", 0),
                "total_matches": len(self._all_matches),
                "combined_throughput": aggregated.get("combined_throughput", 0),
                "average_throughput": aggregated.get("average_throughput", 0),
                "total_errors": aggregated.get("total_errors", 0),
                "elapsed_time": self._get_elapsed_time(),
                "per_device": aggregated.get("per_device", {}),
            }

            return stats

        # 回退到原有逻辑
        stats = {
            "status": "running" if self._running else "stopped",
            "device_count": len(self.workers),
            "total_keys_checked": 0,
            "total_matches": 0,
            "combined_throughput": 0,
            "elapsed_time": 0,
            "per_device": {},
        }

        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        with self._matches_lock:
            stats["total_matches"] = len(self._all_matches)

        total_keys = 0
        total_throughput = 0

        for idx, worker in workers_snapshot.items():
            worker_stats = worker.get_stats()
            stats["per_device"][idx] = worker_stats

            total_keys += worker_stats.get("keys_checked", 0)
            total_throughput += worker_stats.get("throughput", 0)

        stats["total_keys_checked"] = total_keys
        stats["combined_throughput"] = total_throughput

        if self._start_time:
            stats["elapsed_time"] = time.time() - self._start_time

        return stats

    def _get_elapsed_time(self) -> float:
        """获取运行时间"""
        if self._start_time:
            return time.time() - self._start_time
        return 0.0

    def get_per_device_stats(self) -> dict[int, dict]:
        """获取每个GPU的独立统计

        Returns:
            设备索引 -> 统计信息映射
        """
        # 使用锁保护workers访问
        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        stats = {}
        for idx, worker in workers_snapshot.items():
            stats[idx] = worker.get_stats()

        return stats

    def get_matches(self) -> list[dict]:
        """获取所有匹配结果

        Returns:
            匹配结果列表
        """
        # 使用锁保护_all_matches读取
        with self._matches_lock:
            return self._all_matches.copy()

    def is_running(self) -> bool:
        """检查引擎是否在运行

        Returns:
            True表示正在运行
        """
        # 使用锁保护_running读取
        with self._state_lock:
            return self._running

    def is_initialized(self) -> bool:
        """检查引擎是否已初始化

        Returns:
            True表示已初始化
        """
        # 使用锁保护_initialized读取
        with self._state_lock:
            return self._initialized

    def get_devices(self) -> list[dict]:
        """获取当前使用的GPU设备列表

        Returns:
            设备信息列表
        """
        # 使用锁保护_devices读取
        with self._state_lock:
            return self._devices.copy()

    def get_load_balancer(self) -> GPULoadBalancer | None:
        """获取负载均衡器

        Returns:
            GPULoadBalancer实例
        """
        return self.load_balancer

    def _on_match_found(self, device_idx: int, match: dict):
        """处理匹配结果(回调)

        Args:
            device_idx: 发现匹配的设备索引
            match: 匹配信息
        """
        match["device_idx"] = device_idx
        match["timestamp"] = time.time()

        # 使用锁保护_all_matches
        with self._matches_lock:
            self._all_matches.append(match)

        # 记录到 metrics
        self._metrics.record_match_found(device_idx)

        # 报告给数据监控器
        if self._monitor_enabled:
            self.data_monitor.report_match(device_idx, match)

        # 安全脱敏: 仅显示地址前6和后4字符
        masked = match.get("address", "Unknown")
        if len(masked) > 10:
            masked = f"{masked[:6]}...{masked[-4:]}"
        logger.info(f"GPU {device_idx} 发现匹配: {masked}")

        # 调用外部回调
        if self._match_callback:
            try:
                self._match_callback(device_idx, match)
            except Exception as e:
                logger.error(f"匹配回调异常: {e}")

    def _on_anomaly_detected(self, device_idx: int, issue: dict):
        """处理数据异常检测回调

        Args:
            device_idx: GPU设备索引
            issue: 数据质量问题
        """
        severity = issue.get("severity", "low")
        issue.get("issue_type", "unknown")
        message = issue.get("message", "")

        # 根据严重程度采取不同措施
        if severity == "critical":
            logger.critical(f"GPU {device_idx} 严重数据异常: {message}")
            # 可选择暂停该GPU工作器
            if self.config.auto_pause_on_critical:
                logger.warning(f"自动暂停GPU {device_idx}")
                self._pause_device(device_idx)

        elif severity == "high":
            logger.error(f"GPU {device_idx} 高级别数据异常: {message}")

        elif severity == "medium":
            logger.warning(f"GPU {device_idx} 中级别数据异常: {message}")

        else:  # low
            logger.debug(f"GPU {device_idx} 低级别数据异常: {message}")

    def _pause_device(self, device_idx: int):
        """暂停指定GPU工作器

        Args:
            device_idx: GPU设备索引
        """
        with self._workers_lock:
            if device_idx in self.workers:
                try:
                    self.workers[device_idx].pause_search()
                    logger.info(f"GPU {device_idx} 已暂停")
                except Exception as e:
                    logger.error(f"暂停GPU {device_idx} 失败: {e}")

    def get_monitor_stats(self) -> dict:
        """获取数据监控统计

        Returns:
            监控统计字典
        """
        if self._monitor_enabled:
            return cast(dict, self.data_monitor.get_stats())
        else:
            return {"enabled": False}

    def get_monitor_issues(
        self, severity: str | None = None, device_idx: int | None = None, limit: int = 100
    ) -> list[dict]:
        """获取数据质量问题

        Args:
            severity: 过滤严重程度
            device_idx: 过滤设备索引
            limit: 返回数量限制

        Returns:
            问题列表
        """
        if self._monitor_enabled:
            return cast(
                list[dict],
                self.data_monitor.get_issues(severity=severity, device_idx=device_idx, limit=limit),
            )
        else:
            return []

    def _get_device_config(self, device: dict) -> WorkerConfig:
        """获取设备特定配置

        Args:
            device: 设备信息

        Returns:
            WorkerConfig 实例
        """
        # 基础配置
        config = WorkerConfig(
            batch_size=device.get("recommended_batch_size", 65536),
            work_group_size=device.get("recommended_work_group", 256),
        )

        # 应用 Per-GPU 内存池分配配置（按显存比例）
        global_idx = device["global_index"]
        if global_idx in self._device_memory_pool_config:
            config.max_memory_mb = self._device_memory_pool_config[global_idx]
            logger.debug(f"GPU {global_idx} 内存池配置: {config.max_memory_mb}MB")

        # 合并用户配置
        device_idx_str = str(device["global_index"])
        per_config = self.config.per_device_config.get(device_idx_str, {})
        if per_config:
            if "batch_size" in per_config:
                config.batch_size = per_config["batch_size"]
            if "work_group_size" in per_config:
                config.work_group_size = per_config["work_group_size"]
            if "max_memory_mb" in per_config:
                config.max_memory_mb = per_config["max_memory_mb"]

        return config

    def _get_vendor_key(self, device: dict) -> str:
        """生成厂商+平台的唯一键，用于同厂商内核编译配置共享

        Args:
            device: 设备信息字典

        Returns:
            格式为 '{vendor}_{platform}' 的唯一键
        """
        vendor = str(device.get("vendor", "unknown")).lower().strip()
        platform = str(device.get("platform_name", "unknown")).lower().strip()
        # 移除特殊字符，保留字母数字和下划线
        vendor = "".join(c if c.isalnum() else "_" for c in vendor)
        platform = "".join(c if c.isalnum() else "_" for c in platform)
        return f"{vendor}_{platform}"

    def _get_or_cache_compile_config(self, device: dict, kernel_source: str, build_options: str) -> dict:
        """获取或缓存内核编译配置（同厂商GPU共享编译配置）

        OpenCL Program 不能跨 context 共享，但同厂商 GPU 可共享相同的
        编译选项和源码，避免重复预处理。每个 GPUContext 负责自身 context
        内的 program 编译和缓存（见 GPUContext._kernel_cache）。
        此处缓存的是编译元数据，供日志和监控使用。

        Args:
            device: 设备信息字典
            kernel_source: 内核源码
            build_options: 编译选项字符串

        Returns:
            编译配置字典
        """
        vendor_key = self._get_vendor_key(device)

        if vendor_key in self._compiled_programs:
            logger.info(f"同厂商 '{vendor_key}' 编译配置已存在，无需重新预处理")
            return cast(dict, self._compiled_programs[vendor_key])

        # 首次为该厂商记录编译配置
        compile_config = {
            "vendor_key": vendor_key,
            "build_options": build_options,
            "source_len": len(kernel_source),
        }
        self._compiled_programs[vendor_key] = compile_config
        logger.info(f"注册厂商 '{vendor_key}' 编译配置: options='{build_options}'")
        return compile_config

    def _handle_gpu_worker_failure(self, gpu_id: int, error: Exception):
        """处理GPU工作器失败

        Args:
            gpu_id: GPU设备ID
            error: 捕获的异常
        """
        logger.error(f"GPU {gpu_id} 工作器失败: {type(error).__name__}: {error}")

        # 使用恢复管理器处理
        self.recovery_manager.handle_gpu_failure(
            gpu_id=gpu_id,
            error=error,
            redistribute_callback=self._redistribute_workload,
            alert_callback=self._send_failure_alert,
        )

    def _redistribute_workload(self, failed_gpu_id: int):
        """重新分配工作负载

        Args:
            failed_gpu_id: 失败的GPU ID
        """
        logger.info(f"GPU {failed_gpu_id} 失败，正在重新分配工作负载...")

        # 获取健康GPU列表
        failed_gpus = self.recovery_manager.get_failed_gpus()
        healthy_gpus = [idx for idx in self.workers if idx not in failed_gpus]

        if not healthy_gpus:
            logger.critical("所有GPU都已失败，无法继续运行")
            self.stop()
            return

        logger.info(f"健康GPU列表: {healthy_gpus}")

        # 获取失败GPU的剩余工作量
        with self._workers_lock:
            if failed_gpu_id not in self.workers:
                logger.warning(f"GPU {failed_gpu_id} 不在工作器列表中")
                return

            failed_worker = self.workers[failed_gpu_id]
            failed_stats = failed_worker.get_stats()
            key_range = failed_worker.get_key_range()
            # P1修复: 剩余工作量 = 总分配范围 - 已完成量（而非错误使用已完成量作为剩余量）
            total_work = key_range[1] - key_range[0]
            keys_done = failed_stats.get("keys_checked", 0)
            remaining_keys = max(0, total_work - keys_done)
            logger.info(
                f"GPU {failed_gpu_id} 工作范围: {key_range[0]:,}-{key_range[1]:,} "
                f"(总计={total_work:,}, 已完成={keys_done:,}, 剩余={remaining_keys:,})"
            )
        if remaining_keys > 0:
            keys_per_gpu = remaining_keys // len(healthy_gpus)
            logger.info(f"将 {remaining_keys:,} 个密钥重新分配到 {len(healthy_gpus)} 个GPU")

            # 更新健康GPU的工作范围
            for idx in healthy_gpus:
                try:
                    with self._workers_lock:
                        if idx in self.workers:
                            worker = self.workers[idx]
                            # 增加工作范围
                            worker.add_key_range(keys_per_gpu)
                            logger.info(f"GPU {idx} 已增加 {keys_per_gpu:,} 个密钥")
                except Exception as e:
                    logger.error(f"更新GPU {idx} 工作范围失败: {e}")

        # 移除失败的工作器
        with self._workers_lock:
            if failed_gpu_id in self.workers:
                try:
                    failed_worker = self.workers[failed_gpu_id]
                    failed_worker.stop_search()
                    failed_worker.join(timeout=10)
                    del self.workers[failed_gpu_id]
                    logger.info(f"GPU {failed_gpu_id} 工作器已移除")
                except Exception as e:
                    logger.error(f"移除GPU {failed_gpu_id} 工作器失败: {e}")

        logger.info("工作负载重新分配完成")

    def _send_failure_alert(self, gpu_id: int, failure_type, error: Exception):
        """发送失败告警

        Args:
            gpu_id: GPU ID
            failure_type: 失败类型
            error: 异常对象
        """
        alert_message = (
            f"GPU {gpu_id} 失败: {failure_type.value}\n"
            f"错误: {type(error).__name__}: {error}\n"
            f"恢复状态: {'成功' if not self.recovery_manager.is_gpu_failed(gpu_id) else '失败'}"
        )

        logger.critical(alert_message)

        # 这里可以集成告警系统（邮件、Webhook等）
        # 例如：
        # if self.alert_system:
        # self.alert_system.send_alert(alert_message)

    def _update_combined_stats(self):
        """更新汇总统计"""
        # 使用锁保护workers访问
        with self._workers_lock:
            workers_snapshot = dict(self.workers)

        total_keys = 0
        for worker in workers_snapshot.values():
            stats = worker.get_stats()
            total_keys += stats.get("keys_checked", 0)

        # 使用state_lock保护_total_keys_checked赋值
        with self._state_lock:
            self._total_keys_checked = total_keys

    def cleanup(self) -> None:
        """清理所有资源

        安全设计：仅在引擎非运行状态或已停止时执行清理。
        如果 stop() 正在执行中，等待其完成后再清理。
        """
        # 等待任何正在进行的 stop() 完成
        wait_start = time.time()
        while getattr(self, "_stopping", False):
            if time.time() - wait_start > 60:  # 最多等待60秒
                logger.warning("stop() 超时未完成，强制执行清理")
                break
            time.sleep(0.1)

        # 调用 stop() 确保引擎停止（内部有 _running 和 _stopping 检查，安全幂等）
        self.stop()

        with self._workers_lock:
            self.workers.clear()

        self._devices.clear()

        # 清理恢复管理器（含其ThreadPoolExecutor）
        if hasattr(self, "recovery_manager") and self.recovery_manager is not None:
            try:
                self.recovery_manager.cleanup()
            except Exception as e:
                logger.warning(f"GPURecoveryManager清理异常: {e}")

        with self._matches_lock:
            self._all_matches.clear()

        with self._state_lock:
            self._initialized = False
            self._running = False

        logger.info("多GPU引擎资源已清理")

    def __enter__(self) -> "MultiGPUCollisionEngine":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None) -> None:
        """上下文管理器出口"""
        self.cleanup()

    def _start_workload_monitor(self):
        """启动工作负载监控线程"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("工作负载监控线程已在运行")
            return

        # 启动监控线程
        self._monitor_thread = threading.Thread(target=self._workload_monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("工作负载监控线程已启动")

    def _stop_workload_monitor(self):
        """停止工作负载监控线程"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            # 等待线程结束
            try:
                self._monitor_thread.join(timeout=5)
                if self._monitor_thread.is_alive():
                    logger.warning("工作负载监控线程未在5秒内停止")
                else:
                    logger.info("工作负载监控线程已停止")
            except Exception as e:
                logger.error(f"停止工作负载监控线程失败: {e}")
            finally:
                self._monitor_thread = None

    def _workload_monitor_loop(self):
        """工作负载监控循环"""
        while True:
            try:
                # 检查引擎是否运行
                with self._state_lock:
                    if not self._running:
                        break

                # 收集性能数据
                self._collect_performance_data()

                # 检查是否需要自动重平衡
                if self._auto_rebalance:
                    self._check_auto_rebalance()

                # 等待下一次监控
                time.sleep(self._monitor_interval)

            except Exception as e:
                logger.error(f"工作负载监控异常: {e}")
                # 短暂休眠后继续
                time.sleep(1)

    def _collect_performance_data(self):
        """收集性能数据"""
        try:
            # 获取当前统计
            stats = self.get_combined_stats()

            # 记录性能历史
            performance_data = {
                "timestamp": time.time(),
                "total_keys_checked": stats["total_keys_checked"],
                "combined_throughput": stats["combined_throughput"],
                "device_count": stats["device_count"],
                "elapsed_time": stats["elapsed_time"],
                "per_device": stats["per_device"],
            }

            self._performance_history.append(performance_data)

            # 记录到结构化 metrics（可观测性增强）
            for device_idx, worker_stats in stats["per_device"].items():
                worker_stats.get("keys_checked", 0)
                throughput = worker_stats.get("throughput", 0)
                if throughput > 0:
                    self._metrics.record_throughput(device_idx, throughput)

            # 保持历史数据大小（添加锁保护）
            with self._performance_history_lock:
                if len(self._performance_history) > self._max_history_size:
                    self._performance_history = self._performance_history[-self._max_history_size :]

            # 记录负载均衡器状态
            if self.load_balancer:
                self.load_balancer.get_all_loads()
                # 记录性能数据到负载均衡器
                for device_idx, worker_stats in stats["per_device"].items():
                    throughput = worker_stats.get("throughput", 0)
                    error_rate = worker_stats.get("error_rate", 0)
                    self.load_balancer.record_performance(device_idx, throughput, error_rate)

                    # 记录内存使用
                    if "memory_usage" in worker_stats:
                        memory_usage = worker_stats["memory_usage"]
                        # 估算内存使用
                        total_memory = 0
                        for device in self._devices:
                            if device["global_index"] == device_idx:
                                total_memory = device.get("global_mem_size", 0)
                                break
                        if total_memory > 0:
                            used_memory = total_memory * memory_usage
                            self.load_balancer.record_memory_usage(device_idx, used_memory, total_memory)

        except Exception as e:
            logger.error(f"收集性能数据失败: {e}")

    def _check_auto_rebalance(self):
        """检查是否需要自动重平衡"""
        try:
            if not self.load_balancer:
                return

            # 检查是否需要重平衡
            if self.load_balancer.should_rebalance():
                logger.info("触发自动负载重平衡")
                self.load_balancer.redistribute_load()

                # 这里可以添加工作负载重新分配的逻辑
                # 例如，根据新的权重调整工作器的任务范围

        except Exception as e:
            logger.error(f"自动重平衡检查失败: {e}")

    def get_metrics(self) -> "dict":
        """获取结构化性能指标（Prometheus/JSON格式）

        Returns:
            GPUMetricsCollector 的导出数据
        """
        return self._metrics.export_json()

    def export_prometheus_metrics(self) -> str:
        """导出 Prometheus 格式指标

        Returns:
            Prometheus text exposition format 字符串
        """
        return self._metrics.export_prometheus()

    def get_performance_history(self) -> list[dict]:
        """获取性能历史数据

        Returns:
            性能历史数据列表
        """
        with self._performance_history_lock:
            return self._performance_history.copy()

    def get_workload_stats(self) -> dict:
        """获取工作负载统计信息

        Returns:
            工作负载统计字典
        """
        with self._performance_history_lock:
            history_count = len(self._performance_history)
        stats = {
            "monitor_enabled": self._auto_rebalance,
            "monitor_interval": self._monitor_interval,
            "performance_history_count": history_count,
            "load_balancer_stats": {},
        }

        if self.load_balancer:
            stats["load_balancer_stats"] = self.load_balancer.get_stats()

        return stats

    def __del__(self) -> None:
        """析构函数

        注意：建议使用上下文管理器或显式调用cleanup()方法，
        以确保资源能够被正确释放。

        示例:
            with MultiGPUEngine(...) as engine:
                engine.run()
        """
        try:
            self.cleanup()
        except Exception as e:
            # 记录警告，但不抛出异常（对象正在销毁）
            import sys

            print(f"WARNING: MultiGPUEngine清理失败: {type(e).__name__}: {e}", file=sys.stderr)
