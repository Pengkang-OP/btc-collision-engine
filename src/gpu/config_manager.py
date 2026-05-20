"""GPU配置管理器

负责GPU配置的加载、合并、验证和应用。
"""

# 统一日志获取
from typing import Any

from ..utils import get_configured_logger
from .auto_config import get_gpu_configurator
from .device import identify_vendor
from .profiles.loader import GPUProfileLoader

_logger = get_configured_logger("GPUConfigManager")


class GPUConfigManager:
    """GPU配置管理器

    负责GPU配置的加载、合并、验证和应用。
    """

    # 配置来源优先级
    PRIORITY_CONSTRUCTOR = 1  # 构造函数参数
    PRIORITY_PROFILE = 2  # 型号配置文件
    PRIORITY_AUTO = 3  # 自动生成配置
    PRIORITY_DEFAULT = 4  # 默认值

    def __init__(self, user_config: dict[str, Any] | None = None, logger: Any | None = None) -> None:  # noqa: E501
        """
        Args:
            user_config: 用户提供的配置
            logger: 日志记录器
        """
        self.user_config: dict[str, Any] = user_config or {}
        self.logger = logger or _logger

        self._auto_configurator = get_gpu_configurator()
        self._profile_loader = GPUProfileLoader()

    def prepare_config(self, device: Any, user_batch_size: int | None = None) -> dict:
        """准备完整的GPU配置

        Args:
            device: GPU设备实例
            user_batch_size: 用户指定的批次大小

        Returns:
            合并后的配置字典
        """
        device_info = device.get_device_info()

        # 1. 生成自动配置
        auto_config = self._generate_auto_config(device_info)

        # 2. 加载型号配置
        profile_config = self._load_profile_config(device_info)

        # 3. 合并配置
        merged_config = self._merge_configs(auto_config, profile_config or {}, self.user_config)

        # 4. 处理用户指定的batch_size
        if user_batch_size is not None:
            merged_config["batch_size"] = user_batch_size

        # 5. 验证配置
        self._validate_config(merged_config)

        return merged_config

    def _generate_auto_config(self, device_info: dict) -> dict:
        """生成自动配置"""
        config = self._auto_configurator.configure_for_device(device_info)
        _bs = config['batch_size']
        _wa = config.get('use_uint32_workaround', False)
        self.logger.info(
            f"自动配置: batch={_bs:,}, vendor_workaround={_wa}"
        )
        return config

    def _load_profile_config(self, device_info: dict) -> dict | None:
        """加载型号配置"""
        device_name = device_info.get("name", "")
        vendor = device_info.get("vendor", "")

        vendor_type = identify_vendor(device_name, vendor)

        if vendor_type != "unknown":
            profile = self._profile_loader.get_profile(vendor_type, device_name)
            if profile:
                self.logger.info(f"成功加载GPU型号配置: {vendor_type}/{device_name}")
                return profile.get("config", None)
            else:
                self.logger.warning(f"未找到GPU型号配置，使用默认配置: {device_name}")
        else:
            self.logger.warning(f"未知GPU厂商，跳过型号配置加载: {vendor}")

        return None

    def _merge_configs(self, *configs: dict) -> dict:
        """合并多个配置源

        优先级: 后面的配置覆盖前面的配置
        """
        merged = {}

        for config in configs:
            if config:
                for key, value in config.items():
                    if value is not None:
                        merged[key] = value

        return merged

    def _validate_config(self, config: dict):
        """验证配置"""
        # 验证batch_size
        batch_size = config.get("batch_size")
        if batch_size is not None:
            if not isinstance(batch_size, int) or batch_size <= 0:
                raise ValueError(f"batch_size必须是正整数，当前值: {batch_size}")

            _max_batch_size_limit = 16777216  # 16M
            if batch_size > _max_batch_size_limit:
                raise ValueError(f"batch_size {batch_size} 超出最大限制 {_max_batch_size_limit}")

        # 验证queue_depth
        queue_depth = config.get("queue_depth")
        if queue_depth is not None:
            if not isinstance(queue_depth, int) or queue_depth <= 0:
                raise ValueError(f"queue_depth必须是正整数，当前值: {queue_depth}")
            if queue_depth > 16:
                self.logger.warning(f"queue_depth {queue_depth} 过大，可能导致性能下降")

        # 验证seed_prefetch_size
        seed_prefetch_size = config.get("seed_prefetch_size")
        if seed_prefetch_size is not None:
            if not isinstance(seed_prefetch_size, int) or seed_prefetch_size <= 0:
                raise ValueError(f"seed_prefetch_size必须是正整数，当前值: {seed_prefetch_size}")
            if seed_prefetch_size > 100:
                self.logger.warning(
                    f"seed_prefetch_size {seed_prefetch_size} 过大，可能导致内存使用过高"
                )

        # 验证memory_ratio
        memory_ratio = config.get("memory_ratio")
        if memory_ratio is not None and (
            not isinstance(memory_ratio, (int, float)) or memory_ratio <= 0 or memory_ratio > 1.0
        ):
            raise ValueError(f"memory_ratio必须是0-1之间的数，当前值: {memory_ratio}")

        # 验证use_memory_pool
        use_memory_pool = config.get("use_memory_pool")
        if use_memory_pool is not None and not isinstance(use_memory_pool, bool):
            raise ValueError(f"use_memory_pool必须是布尔值，当前值: {use_memory_pool}")

        # 验证async_execution
        async_execution = config.get("async_execution")
        if async_execution is not None and not isinstance(async_execution, bool):
            raise ValueError(f"async_execution必须是布尔值，当前值: {async_execution}")

        # 验证use_uint32_workaround
        use_uint32_workaround = config.get("use_uint32_workaround")
        if use_uint32_workaround is not None and not isinstance(use_uint32_workaround, bool):
            raise ValueError(f"use_uint32_workaround必须是布尔值，当前值: {use_uint32_workaround}")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值或默认值
        """
        return self.user_config.get(key, default)

    def get_gpu_config(self) -> dict:
        """获取GPU相关配置

        Returns:
            GPU配置字典
        """
        return self.user_config.get("gpu", {})

    def update_config(self, updates: dict) -> None:
        """更新配置

        Args:
            updates: 要更新的配置
        """
        for key, value in updates.items():
            if isinstance(value, dict) and key in self.user_config:
                # 递归更新嵌套字典
                self.user_config[key].update(value)
            else:
                self.user_config[key] = value

    def validate_and_apply(self, config: dict, device: Any) -> dict:
        """验证并应用配置

        Args:
            config: 配置字典
            device: GPU设备实例

        Returns:
            应用后的配置
        """
        # 验证配置
        self._validate_config(config)

        # 应用配置到设备
        if "async_execution" in config:
            device.enable_async_execution = config["async_execution"]
            self.logger.info(f"✅ 应用配置: async_execution={config['async_execution']}")

        if "use_uint32_workaround" in config:
            # uint32_workaround 在 kernel 层由 intel_optimizer 自动应用，
            # 此处仅记录配置状态（设备层无直接属性设置）
            self.logger.info(f"✅ 应用配置: use_uint32_workaround={config['use_uint32_workaround']}")

        return config

    def get_default_config(self) -> dict:
        """获取默认配置

        Returns:
            默认配置字典
        """
        return {
            "batch_size": 1_000_000,
            "async_execution": True,
            "queue_depth": 8,
            "seed_prefetch_size": 10,
            "memory_ratio": 0.70,
            "use_memory_pool": True,
            "pool_max_buffers": 100,
            "pool_max_memory_mb": 512,
            "use_uint32_workaround": False,
            "max_error_retries": 100,
        }
