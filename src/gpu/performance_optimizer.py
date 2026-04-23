"""GPU自适应性能优化器

基于性能监控数据动态调整GPU碰撞引擎参数，实现：
1. 根据GPU设备类型和性能特征自动优化参数
2. 实时监测性能瓶颈并自适应调整
3. 跨厂商优化（NVIDIA/AMD/Intel）
4. 防止内存溢出和资源竞争
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GPUVendor(Enum):
    """GPU厂商枚举"""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    UNKNOWN = "unknown"


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    kernel_compile_time_ms: float = 0.0  # 内核编译时间
    engine_init_time_ms: float = 0.0     # 引擎初始化时间
    batch_execution_time_ms: float = 0.0 # 批次执行时间
    keys_per_second: float = 0.0         # 每秒处理密钥数
    memory_usage_mb: float = 0.0         # 显存使用量
    error_count: int = 0                 # 错误计数
    timestamp: float = field(default_factory=time.time)


@dataclass
class GPUProfile:
    """GPU性能配置文件"""
    vendor: GPUVendor
    device_name: str
    
    # 核心参数
    max_batch_size: int = 65536
    work_group_size: int = 256
    memory_usage_ratio: float = 0.5
    
    # 计算模式
    preferred_mode: str = "random_collision"  # random_collision/range_scan/brute_force
    
    # 优化标志
    use_uint32_workaround: bool = False  # Intel Arc workaround
    enable_async_execution: bool = True
    enable_buffer_pooling: bool = True
    
    # 性能阈值
    slow_compile_threshold_ms: float = 30000.0
    slow_execution_threshold_ms: float = 1000.0
    error_rate_threshold: float = 0.01  # 1%错误率
    
    # 调整策略
    batch_size_step: int = 8192  # 批次调整步长
    min_batch_size: int = 1024
    max_batch_size_limit: int = 16777216  # 16M上限


class GPUPerformanceOptimizer:
    """GPU自适应性能优化器
    
    根据性能监控数据动态调整GPU碰撞引擎参数。
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._metrics_history: List[PerformanceMetrics] = []
        self._current_profile: Optional[GPUProfile] = None
        self._vendor_profiles = self._init_vendor_profiles()
        self._performance_degraded = False
        self._adjustment_count = 0
        self._last_adjustment_time = 0
        self._adjustment_cooldown_sec = 10  # 调整冷却期10秒
        
        logger.info("GPU性能优化器初始化完成")
    
    def _init_vendor_profiles(self) -> Dict[GPUVendor, GPUProfile]:
        """初始化各厂商默认配置"""
        return {
            GPUVendor.NVIDIA: GPUProfile(
                vendor=GPUVendor.NVIDIA,
                device_name="NVIDIA GPU",
                max_batch_size=1048576,  # 1M
                work_group_size=256,
                memory_usage_ratio=0.7,  # NVIDIA可以使用更多显存
                preferred_mode="random_collision",
                enable_async_execution=True,
                enable_buffer_pooling=True,
            ),
            GPUVendor.AMD: GPUProfile(
                vendor=GPUVendor.AMD,
                device_name="AMD GPU",
                max_batch_size=524288,  # 512K
                work_group_size=256,
                memory_usage_ratio=0.6,
                preferred_mode="random_collision",
                enable_async_execution=True,
                enable_buffer_pooling=True,
            ),
            GPUVendor.INTEL: GPUProfile(
                vendor=GPUVendor.INTEL,
                device_name="Intel GPU",
                max_batch_size=262144,  # 256K
                work_group_size=128,
                memory_usage_ratio=0.5,
                preferred_mode="range_scan",
                use_uint32_workaround=True,  # Intel Arc需要workaround
                enable_async_execution=False,  # Intel异步支持较差
                enable_buffer_pooling=True,
            ),
        }
    
    def detect_vendor(self, device_name: str, vendor_str: str = "") -> GPUVendor:
        """检测GPU厂商"""
        name_lower = device_name.lower()
        vendor_lower = vendor_str.lower()
        
        if 'nvidia' in vendor_lower or 'nvidia' in name_lower or \
           'geforce' in name_lower or 'rtx' in name_lower or 'gtx' in name_lower:
            return GPUVendor.NVIDIA
        elif 'amd' in vendor_lower or 'amd' in name_lower or \
             'radeon' in name_lower:
            return GPUVendor.AMD
        elif 'intel' in vendor_lower or 'intel' in name_lower:
            return GPUVendor.INTEL
        else:
            return GPUVendor.UNKNOWN
    
    def create_optimized_profile(
        self,
        device_name: str,
        vendor_str: str,
        global_mem_size: int,
        compile_time_ms: float = 0.0
    ) -> GPUProfile:
        """创建优化的GPU配置
        
        Args:
            device_name: GPU设备名称
            vendor_str: 厂商标识
            global_mem_size: 全局显存大小（字节）
            compile_time_ms: 内核编译时间（毫秒）
            
        Returns:
            优化后的GPU配置
        """
        vendor = self.detect_vendor(device_name, vendor_str)
        
        # 获取厂商默认配置
        if vendor in self._vendor_profiles:
            profile = GPUProfile(
                vendor=vendor,
                device_name=device_name,
                **{k: v for k, v in self._vendor_profiles[vendor].__dict__.items() 
                   if k not in ['vendor', 'device_name']}
            )
        else:
            profile = GPUProfile(
                vendor=GPUVendor.UNKNOWN,
                device_name=device_name
            )
        
        # 根据显存大小调整batch_size（优化版：更细粒度的分段）
        mem_gb = global_mem_size / (1024 ** 3)
        if mem_gb >= 16:
            # 16GB+ 旗舰级GPU
            profile.max_batch_size = min(profile.max_batch_size * 4, profile.max_batch_size_limit)
            profile.memory_usage_ratio = min(profile.memory_usage_ratio + 0.15, 0.85)
        elif mem_gb >= 8:
            # 8-16GB 高端GPU
            profile.max_batch_size = min(profile.max_batch_size * 2, profile.max_batch_size_limit)
            profile.memory_usage_ratio = min(profile.memory_usage_ratio + 0.1, 0.8)
        elif mem_gb >= 4:
            # 4-8GB 中端GPU
            profile.max_batch_size = max(profile.max_batch_size // 2, profile.min_batch_size)
            profile.memory_usage_ratio = max(profile.memory_usage_ratio - 0.05, 0.4)
        elif mem_gb >= 2:
            # 2-4GB 入门级GPU
            profile.max_batch_size = max(profile.max_batch_size // 4, profile.min_batch_size)
            profile.memory_usage_ratio = max(profile.memory_usage_ratio - 0.15, 0.3)
        else:
            # <2GB 低端GPU/集成显卡
            profile.max_batch_size = profile.min_batch_size
            profile.memory_usage_ratio = 0.3
        
        # 根据编译时间调整（编译慢说明内核复杂，减少batch）
        if compile_time_ms > 20000:
            logger.warning(f"内核编译时间较长({compile_time_ms:.0f}ms)，降低batch_size")
            profile.max_batch_size = max(profile.max_batch_size // 2, profile.min_batch_size)
        
        # 记录配置
        self._current_profile = profile
        logger.info(
            f"GPU配置已优化: {device_name}, "
            f"batch_size={profile.max_batch_size}, "
            f"work_group={profile.work_group_size}, "
            f"mem_ratio={profile.memory_usage_ratio}"
        )
        
        return profile
    
    def record_performance(self, metrics: PerformanceMetrics):
        """记录性能指标
        
        Args:
            metrics: 性能指标数据
        """
        # 验证数据有效性
        if metrics.batch_execution_time_ms < 0:
            logger.warning(f"无效的批次执行时间: {metrics.batch_execution_time_ms}")
            return
        
        if metrics.keys_per_second < 0:
            logger.warning(f"无效的吞吐量: {metrics.keys_per_second}")
            return
        
        if metrics.error_count < 0:
            logger.warning(f"无效的错误计数: {metrics.error_count}")
            return
        
        with self._lock:
            self._metrics_history.append(metrics)
            
            # 保留最近100条记录
            if len(self._metrics_history) > 100:
                self._metrics_history = self._metrics_history[-100:]
    
    def analyze_and_adjust(
        self,
        current_batch_size: int,
        error_rate: float = 0.0
    ) -> Tuple[int, Dict[str, Any]]:
        """分析性能数据并调整参数
        
        Args:
            current_batch_size: 当前批次大小
            error_rate: 错误率（0.0-1.0）
            
        Returns:
            (new_batch_size, adjustment_info)
        """
        if not self._current_profile:
            return current_batch_size, {"action": "no_profile", "reason": "未创建配置文件"}
        
        # 检查冷却期
        now = time.time()
        with self._lock:
            if now - self._last_adjustment_time < self._adjustment_cooldown_sec:
                remaining = self._adjustment_cooldown_sec - (now - self._last_adjustment_time)
                return current_batch_size, {
                    "action": "cooldown",
                    "reason": f"调整冷却期，剩余{remaining:.1f}秒"
                }
        
        with self._lock:
            if len(self._metrics_history) < 3:
                return current_batch_size, {"action": "insufficient_data", "reason": "数据不足"}
            
            # 获取最近的性能指标
            recent_metrics = self._metrics_history[-10:]
            avg_execution_time = sum(m.batch_execution_time_ms for m in recent_metrics) / len(recent_metrics)
            avg_speed = sum(m.keys_per_second for m in recent_metrics) / len(recent_metrics)
            
            adjustments = {}
            new_batch_size = current_batch_size
            profile = self._current_profile
            
            # 1. 错误率过高 - 减小batch_size
            if error_rate > profile.error_rate_threshold:
                reduction = max(profile.batch_size_step, current_batch_size // 4)
                new_batch_size = max(profile.min_batch_size, current_batch_size - reduction)
                adjustments["error_rate_too_high"] = {
                    "current": error_rate,
                    "threshold": profile.error_rate_threshold,
                    "action": "reduce_batch",
                    "old_batch": current_batch_size,
                    "new_batch": new_batch_size
                }
                logger.warning(
                    f"错误率过高({error_rate:.2%})，减小batch: {current_batch_size} -> {new_batch_size}"
                )
            
            # 2. 执行时间过长 - 减小batch_size
            elif avg_execution_time > profile.slow_execution_threshold_ms:
                reduction = max(profile.batch_size_step, current_batch_size // 4)
                new_batch_size = max(profile.min_batch_size, current_batch_size - reduction)
                adjustments["execution_too_slow"] = {
                    "avg_time_ms": avg_execution_time,
                    "threshold_ms": profile.slow_execution_threshold_ms,
                    "action": "reduce_batch",
                    "old_batch": current_batch_size,
                    "new_batch": new_batch_size
                }
                logger.warning(
                    f"执行时间过长({avg_execution_time:.0f}ms)，减小batch: {current_batch_size} -> {new_batch_size}"
                )
            
            # 3. 性能良好且有余量 - 增大batch_size（优化v2.2.1: 更激进的策略）
            elif (avg_execution_time < profile.slow_execution_threshold_ms * 0.5 and
                  error_rate < profile.error_rate_threshold * 0.5):
                # 根据性能余量计算增长因子
                time_ratio = profile.slow_execution_threshold_ms * 0.5 / max(avg_execution_time, 1)
                
                if time_ratio > 3.0:
                    # 性能非常优秀，大幅增加
                    increase = profile.batch_size_step * 4
                elif time_ratio > 2.0:
                    # 性能良好，适度增加
                    increase = profile.batch_size_step * 2
                else:
                    # 性能尚可，小幅增加
                    increase = profile.batch_size_step
                
                new_batch_size = min(profile.max_batch_size_limit, current_batch_size + increase)
                adjustments["performance_good"] = {
                    "avg_time_ms": avg_execution_time,
                    "avg_speed": avg_speed,
                    "time_ratio": time_ratio,
                    "action": "increase_batch",
                    "old_batch": current_batch_size,
                    "new_batch": new_batch_size
                }
                logger.info(
                    f"性能良好(time_ratio={time_ratio:.1f}x)，增大batch: {current_batch_size} -> {new_batch_size}"
                )
            
            # 4. 记录调整
            if new_batch_size != current_batch_size:
                self._adjustment_count += 1
                self._last_adjustment_time = now  # 记录调整时间
                adjustments["adjustment_count"] = self._adjustment_count
            
            return new_batch_size, adjustments
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        if not self._current_profile:
            return {"status": "no_profile"}
        
        with self._lock:
            if not self._metrics_history:
                return {
                    "status": "no_metrics",
                    "profile": {
                        "vendor": self._current_profile.vendor.value,
                        "device": self._current_profile.device_name,
                        "batch_size": self._current_profile.max_batch_size
                    }
                }
            
            recent = self._metrics_history[-10:]
            avg_speed = sum(m.keys_per_second for m in recent) / len(recent)
            avg_error = sum(m.error_count for m in recent) / len(recent)
            
            # 计算时间范围
            time_range_sec = self._metrics_history[-1].timestamp - self._metrics_history[0].timestamp
            
            return {
                "status": "active",
                "time_range": {
                    "start": self._metrics_history[0].timestamp,
                    "end": self._metrics_history[-1].timestamp,
                    "duration_sec": time_range_sec,
                    "duration_min": time_range_sec / 60
                },
                "profile": {
                    "vendor": self._current_profile.vendor.value,
                    "device": self._current_profile.device_name,
                    "batch_size": self._current_profile.max_batch_size,
                    "work_group_size": self._current_profile.work_group_size,
                    "memory_ratio": self._current_profile.memory_usage_ratio
                },
                "performance": {
                    "avg_speed_keys_per_sec": avg_speed,
                    "avg_error_count": avg_error,
                    "total_adjustments": self._adjustment_count,
                    "metrics_count": len(self._metrics_history)
                },
                "recommendations": self._generate_recommendations()
            }
    
    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if not self._current_profile or not self._metrics_history:
            return recommendations
        
        profile = self._current_profile
        recent = self._metrics_history[-5:]
        
        # 检查编译时间
        compile_times = [m.kernel_compile_time_ms for m in recent if m.kernel_compile_time_ms > 0]
        if compile_times:
            avg_compile = sum(compile_times) / len(compile_times)
            if avg_compile > profile.slow_compile_threshold_ms:
                recommendations.append(
                    f"内核编译时间较长({avg_compile:.0f}ms)，考虑使用内核缓存或预编译"
                )
        
        # 检查错误率
        total_errors = sum(m.error_count for m in recent)
        if total_errors > 0:
            recommendations.append(
                f"检测到{total_errors}个错误，建议检查GPU驱动和显存使用"
            )
        
        # 厂商特定建议
        if profile.vendor == GPUVendor.INTEL:
            if not profile.use_uint32_workaround:
                recommendations.append("Intel GPU建议启用uint32 workaround避免hang bug")
        elif profile.vendor == GPUVendor.NVIDIA:
            if profile.memory_usage_ratio < 0.6:
                recommendations.append("NVIDIA GPU可以尝试提高显存使用率至60-70%")
        
        return recommendations
    
    def reset(self):
        """重置优化器状态"""
        with self._lock:
            self._metrics_history.clear()
            self._current_profile = None
            self._adjustment_count = 0
            self._last_adjustment_time = 0
        logger.info("GPU性能优化器已重置")


# 全局优化器实例
_global_optimizer = None
_optimizer_lock = threading.Lock()


def get_gpu_optimizer() -> GPUPerformanceOptimizer:
    """获取全局GPU性能优化器实例（单例模式）"""
    global _global_optimizer
    
    if _global_optimizer is None:
        with _optimizer_lock:
            if _global_optimizer is None:
                _global_optimizer = GPUPerformanceOptimizer()
    
    return _global_optimizer
