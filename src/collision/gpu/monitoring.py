"""性能监控管道

整合GPU性能监控、引擎监控、数据日志，
提供统一的性能指标收集和异常检测。

职责:
- 多监控器协调
- 数据聚合与存储
- 异常检测与告警
- 性能报告生成

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Optional, Dict, Any, List
import logging
import time

from .protocols import IMonitoringPipeline, MatchResult

logger = logging.getLogger(__name__)


class PerformanceMonitoringPipeline(IMonitoringPipeline):
    """性能监控管道
    
    职责:
    - 协调多个监控器（性能/引擎/厂商特定）
    - 统一数据记录到DataLogger
    - 异常检测和告警
    - 性能报告生成
    
    实现接口: IMonitoringPipeline
    
    使用示例:
        >>> monitoring = PerformanceMonitoringPipeline(engine, config)
        >>> monitoring.start()
        >>> monitoring.record_metrics(batch_size=1000000, execution_time_ms=50.0)
        >>> monitoring.stop()
    """
    
    def __init__(
        self,
        engine: Any = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """初始化监控管道
        
        Args:
            engine: 引擎实例（用于监控回调）
            config: 配置字典
        """
        self.engine = engine
        self.config = config or {}
        self._running = False
        
        # 监控组件（延迟初始化）
        self._perf_monitor = None
        self._engine_monitor = None
        self._data_logger = None
        self._vendor_monitors: List[Any] = []
        
        logger.debug("PerformanceMonitoringPipeline 初始化完成")
    
    def start(self) -> None:
        """启动所有监控器"""
        if self._running:
            logger.warning("监控管道已运行，跳过重复启动")
            return
        
        try:
            # 1. 初始化性能监控器
            self._perf_monitor = self._create_performance_monitor()
            if self._perf_monitor:
                self._perf_monitor.start()
            
            # 2. 初始化引擎监控器
            self._engine_monitor = self._create_engine_monitor()
            if self._engine_monitor:
                self._engine_monitor.start()
            
            # 3. 初始化数据日志
            self._data_logger = self._create_data_logger()
            
            # 4. 初始化厂商特定监控
            self._vendor_monitors = self._create_vendor_monitors()
            for monitor in self._vendor_monitors:
                if hasattr(monitor, 'start'):
                    monitor.start()
            
            self._running = True
            logger.info("性能监控管道已启动")
            
        except Exception as e:
            logger.error(f"性能监控管道启动失败: {e}")
            self.stop()
            raise
    
    def stop(self) -> None:
        """停止所有监控器"""
        if not self._running:
            return
        
        try:
            # 1. 停止厂商监控
            for monitor in self._vendor_monitors:
                if hasattr(monitor, 'stop'):
                    monitor.stop()
            
            # 2. 停止引擎监控
            if self._engine_monitor:
                self._engine_monitor.stop()
            
            # 3. 停止性能监控
            if self._perf_monitor:
                self._perf_monitor.stop()
            
            # 4. 刷写数据日志
            if self._data_logger:
                self._data_logger.flush()
            
            self._running = False
            logger.info("性能监控管道已停止")
            
        except Exception as e:
            logger.error(f"性能监控管道停止失败: {e}")
    
    def record_metrics(
        self,
        batch_size: int,
        execution_time_ms: float,
        **metrics: Any
    ) -> None:
        """记录性能指标
        
        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间（毫秒）
            **metrics: 其他指标（gpu_usage, memory_usage, errors等）
        """
        if not self._running:
            logger.debug("监控管道未运行，跳过指标记录")
            return
        
        try:
            # 1. 记录到性能监控器
            if self._perf_monitor:
                self._perf_monitor.record_kernel_metrics(
                    batch_size=batch_size,
                    execution_time_ms=execution_time_ms
                )
            
            # 2. 记录到数据日志
            if self._data_logger:
                self._data_logger.log_performance({
                    'batch_size': batch_size,
                    'execution_time_ms': execution_time_ms,
                    'timestamp': time.time(),
                    **metrics
                })
            
            # 3. 异常检测
            self._detect_anomalies(batch_size, execution_time_ms, metrics)
            
        except Exception as e:
            logger.error(f"记录性能指标失败: {e}")
    
    def flush(self) -> None:
        """刷写所有缓冲数据"""
        if self._data_logger:
            try:
                self._data_logger.flush()
                logger.debug("数据日志缓冲已刷写")
            except Exception as e:
                logger.error(f"刷写数据日志失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计
        
        Returns:
            监控统计字典
        """
        stats: Dict[str, Any] = {}
        
        if self._perf_monitor and hasattr(self._perf_monitor, 'get_stats'):
            stats['performance'] = self._perf_monitor.get_stats()
        
        if self._engine_monitor and hasattr(self._engine_monitor, 'get_stats'):
            stats['engine'] = self._engine_monitor.get_stats()
        
        return stats
    
    def is_running(self) -> bool:
        """检查监控管道是否运行"""
        return self._running
    
    # ========== 私有方法 ==========
    
    def _create_performance_monitor(self):
        """创建GPU性能监控器"""
        # TODO: Phase 3实现 - 从现有GPUPerformanceMonitor适配
        try:
            from ..monitoring.gpu_performance_monitor import get_gpu_performance_monitor
            return get_gpu_performance_monitor()
        except Exception as e:
            logger.warning(f"创建GPU性能监控器失败: {e}")
            return None
    
    def _create_engine_monitor(self):
        """创建引擎监控器"""
        # TODO: Phase 3实现 - 从现有GPUEngineMonitor适配
        try:
            from ..gpu.engine_monitor import GPUEngineMonitor
            if self.engine:
                return GPUEngineMonitor(self.engine)
            return None
        except Exception as e:
            logger.warning(f"创建引擎监控器失败: {e}")
            return None
    
    def _create_data_logger(self):
        """创建数据日志适配器"""
        # TODO: Phase 3实现 - 从现有DataLogger适配
        try:
            if self.engine and hasattr(self.engine, 'data_logger'):
                return self.engine.data_logger
            return None
        except Exception as e:
            logger.warning(f"创建数据日志适配器失败: {e}")
            return None
    
    def _create_vendor_monitors(self) -> List[Any]:
        """创建厂商特定监控器
        
        Returns:
            厂商监控器列表
        """
        monitors = []
        
        # 检测GPU厂商
        vendor = self._detect_vendor()
        
        # Intel特定监控
        if vendor == 'intel':
            try:
                from ..gpu.intel_memory_monitor import IntelMemoryMonitor
                from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager
                
                if self.engine and hasattr(self.engine, '_gpu_device'):
                    monitors.append(IntelMemoryMonitor(self.engine._gpu_device))
                    monitors.append(AdaptiveTimeoutManager())
            except Exception as e:
                logger.warning(f"创建Intel监控器失败: {e}")
        
        return monitors
    
    def _detect_anomalies(
        self,
        batch_size: int,
        execution_time_ms: float,
        metrics: Dict[str, Any]
    ) -> None:
        """异常检测
        
        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间
            metrics: 其他指标
        """
        # 1. 执行时间异常检测
        threshold_ms = self.config.get('slow_threshold_ms', 5000)
        if execution_time_ms > threshold_ms:
            logger.warning(
                f"慢操作检测: execution_time={execution_time_ms:.0f}ms "
                f"> threshold={threshold_ms}ms"
            )
        
        # 2. 错误率检测
        gpu_errors = metrics.get('gpu_errors', 0)
        if gpu_errors > 0:
            error_rate_threshold = self.config.get('error_rate_threshold', 0.01)
            error_rate = gpu_errors / max(batch_size, 1)
            if error_rate > error_rate_threshold:
                logger.error(
                    f"高错误率检测: error_rate={error_rate:.2%} "
                    f"> threshold={error_rate_threshold:.2%}"
                )
    
    def _detect_vendor(self) -> str:
        """检测GPU厂商"""
        try:
            if self.engine and hasattr(self.engine, '_gpu_device'):
                from ..gpu.device import identify_vendor
                return identify_vendor(self.engine._gpu_device)  # type: ignore[no-any-return]
        except Exception:
            pass
        return "unknown"
