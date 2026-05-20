"""性能优化配置

统一管理性能优化相关的配置参数，
包括SIMD优化、多进程并行、GPU加速等。
"""

import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerformanceOptimizationConfig:
    """性能优化配置

    集中管理所有性能优化相关的参数。
    """

    # ===== SIMD优化配置 =====
    enable_simd: bool = True
    simd_batch_size: int = 100000

    # ===== 多进程配置 =====
    use_multiprocess: bool = True
    num_workers: int = field(default_factory=lambda: mp.cpu_count())
    process_batch_size: int = 10000

    # ===== GPU配置 =====
    use_gpu: bool = False
    gpu_device_index: int = 0
    gpu_batch_size: int = 1000000

    # ===== 内存优化配置 =====
    enable_memory_pool: bool = True
    max_memory_mb: int = 4096  # 最大内存使用（MB）

    # ===== Bloom Filter配置 =====
    enable_bloom_filter: bool = True
    bloom_max_size: int = 10_000_000
    bloom_false_positive_rate: float = 0.001

    # ===== 缓存配置 =====
    enable_caching: bool = True
    cache_max_size: int = 100000

    # ===== 性能监控配置 =====
    enable_performance_monitoring: bool = True
    monitoring_interval: float = 5.0  # 秒

    def __post_init__(self) -> None:
        """初始化后验证"""
        # 自动检测CPU核心数
        if self.num_workers is None:
            self.num_workers = mp.cpu_count()

        # 验证参数范围
        if self.simd_batch_size < 1000:
            self.simd_batch_size = 1000

        if self.process_batch_size < 1000:
            self.process_batch_size = 1000

        if self.bloom_false_positive_rate <= 0 or self.bloom_false_positive_rate >= 1:
            self.bloom_false_positive_rate = 0.001

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "enable_simd": self.enable_simd,
            "simd_batch_size": self.simd_batch_size,
            "use_multiprocess": self.use_multiprocess,
            "num_workers": self.num_workers,
            "process_batch_size": self.process_batch_size,
            "use_gpu": self.use_gpu,
            "gpu_device_index": self.gpu_device_index,
            "gpu_batch_size": self.gpu_batch_size,
            "enable_memory_pool": self.enable_memory_pool,
            "max_memory_mb": self.max_memory_mb,
            "enable_bloom_filter": self.enable_bloom_filter,
            "bloom_max_size": self.bloom_max_size,
            "bloom_false_positive_rate": self.bloom_false_positive_rate,
            "enable_caching": self.enable_caching,
            "cache_max_size": self.cache_max_size,
            "enable_performance_monitoring": self.enable_performance_monitoring,
            "monitoring_interval": self.monitoring_interval,
        }

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "PerformanceOptimizationConfig":
        """从字典创建配置"""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})

    def optimize_for_cpu(self, num_cores: int | None = None) -> "PerformanceOptimizationConfig":
        """针对CPU优化"""
        cores = num_cores or mp.cpu_count()

        self.use_multiprocess = True
        self.num_workers = cores
        self.process_batch_size = 50000
        self.enable_simd = True
        self.simd_batch_size = 200000

        return self

    def optimize_for_gpu(self, device_index: int = 0) -> "PerformanceOptimizationConfig":
        """针对GPU优化"""
        self.use_gpu = True
        self.gpu_device_index = device_index
        self.gpu_batch_size = 2000000
        self.use_multiprocess = False  # GPU不需要多进程

        return self

    def optimize_for_memory(self, max_memory_mb: int = 2048) -> "PerformanceOptimizationConfig":
        """针对内存优化（降低内存使用）"""
        self.max_memory_mb = max_memory_mb
        self.simd_batch_size = 50000
        self.process_batch_size = 5000
        self.bloom_max_size = 1_000_000
        self.cache_max_size = 10000

        return self

    def optimize_for_speed(self, num_cores: int | None = None) -> "PerformanceOptimizationConfig":
        """针对速度优化（高内存使用）"""
        cores = num_cores or mp.cpu_count()

        self.use_multiprocess = True
        self.num_workers = cores
        self.process_batch_size = 100000
        self.enable_simd = True
        self.simd_batch_size = 500000
        self.bloom_max_size = 100_000_000
        self.cache_max_size = 500000

        return self


class PerformanceTuner:
    """性能调优器

    根据系统资源自动调整优化配置。
    """

    @staticmethod
    def detect_system_resources() -> dict[str, Any]:
        """检测系统资源

        Returns:
            系统资源信息字典
        """
        try:
            import psutil
        except ImportError:
            return {
                "cpu_count": mp.cpu_count(),
                "cpu_frequency_mhz": 0,
                "total_memory_gb": 0,
                "available_memory_gb": 0,
                "memory_usage_percent": 0,
            }

        # CPU信息
        cpu_count = mp.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # 内存信息
        memory = psutil.virtual_memory()

        return {
            "cpu_count": cpu_count,
            "cpu_frequency_mhz": cpu_freq.current if cpu_freq else 0,
            "total_memory_gb": memory.total / (1024**3),
            "available_memory_gb": memory.available / (1024**3),
            "memory_usage_percent": memory.percent,
        }

    @classmethod
    def auto_tune(cls) -> PerformanceOptimizationConfig:
        """自动调优

        根据系统资源自动选择最优配置。

        Returns:
            优化后的配置
        """
        resources = cls.detect_system_resources()
        config = PerformanceOptimizationConfig()

        # 根据CPU核心数调整
        cpu_count = resources["cpu_count"]
        if cpu_count >= 16:
            config.optimize_for_speed(cpu_count)
        elif cpu_count >= 8:
            config.optimize_for_cpu(cpu_count)
        else:
            config.optimize_for_cpu(cpu_count)

        # 根据内存调整
        available_memory_gb = resources["available_memory_gb"]
        if available_memory_gb < 4:
            config.optimize_for_memory(max_memory_mb=1024)
        elif available_memory_gb < 8:
            config.optimize_for_memory(max_memory_mb=2048)
        elif available_memory_gb >= 16:
            config.optimize_for_speed(cpu_count)

        return config

    @classmethod
    def recommend_config(cls, scenario: str = "balanced") -> PerformanceOptimizationConfig:
        """推荐配置

        Args:
            scenario: 使用场景 ("balanced", "speed", "memory", "gpu")

        Returns:
            推荐的配置
        """
        config = PerformanceOptimizationConfig()

        if scenario == "balanced":
            config.optimize_for_cpu()
            config.enable_bloom_filter = True
            config.enable_simd = True

        elif scenario == "speed":
            config.optimize_for_speed()

        elif scenario == "memory":
            config.optimize_for_memory()

        elif scenario == "gpu":
            config.optimize_for_gpu()

        else:
            raise ValueError(f"未知场景: {scenario}")

        return config


def create_optimized_config(
    scenario: str = "balanced", num_cores: int | None = None, max_memory_mb: int | None = None
) -> PerformanceOptimizationConfig:
    """创建优化配置的便捷函数

    Args:
        scenario: 使用场景
        num_cores: 指定CPU核心数
        max_memory_mb: 最大内存限制（MB）

    Returns:
        优化配置实例
    """
    if scenario == "auto":
        config = PerformanceTuner.auto_tune()
    else:
        config = PerformanceTuner.recommend_config(scenario)

    # 覆盖特定参数
    if num_cores:
        config.num_workers = num_cores

    if max_memory_mb:
        config.max_memory_mb = max_memory_mb

    return config
