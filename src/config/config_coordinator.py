"""配置协调器 - 统一管理多个配置管理器

提供统一的配置访问接口,协调ConfigManager、CryptoConfig和GPUConfig之间的配置同步。
"""

import logging
import threading
from typing import Any

from .config_manager import ConfigManager
from .crypto_config import CryptoConfig

logger = logging.getLogger(__name__)


class ConfigCoordinator:
    """配置协调器 - 统一管理多个配置管理器

    职责:
    1. 初始化并协调所有配置管理器
    2. 提供统一的配置访问接口
    3. 同步各配置管理器的配置
    4. 统一配置验证
    """

    def __init__(self, config_file: str = "config.json") -> None:
        """初始化配置协调器

        参数:
            config_file: 配置文件路径
        """
        # W13修复: 添加实例级锁，避免多线程访问时的竞态条件
        self._sync_lock = threading.Lock()

        # 初始化ConfigManager(主配置管理器)
        self.config_manager = ConfigManager(config_file)

        # 初始化CryptoConfig,并传入ConfigManager引用
        self.crypto_config = CryptoConfig(
            config_file=None,
            config_manager=self.config_manager,  # 不再使用独立的配置文件
        )

        # 初始化GPUConfig(从ConfigManager读取配置)
        from ..gpu.config import GPUConfig

        self.gpu_config = GPUConfig(config_file=None)  # 不再使用独立的配置文件

        # 同步配置
        self._sync_configs()

        logger.info("配置协调器初始化完成")

    def _sync_configs(self) -> None:
        """同步各配置管理器的配置（线程安全）"""
        # W13修复: 使用锁保护配置同步操作，避免多线程竞态条件
        with self._sync_lock:
            try:
                # 从ConfigManager同步到GPUConfig
                self._sync_gpu_config()

                # 从ConfigManager同步到CryptoConfig
                self._sync_crypto_config()

                logger.debug("配置同步完成")
            except Exception as e:
                logger.warning("配置同步失败: %s", e)

    def _sync_gpu_config(self) -> None:
        """同步GPU配置到GPUConfig"""
        try:
            gpu_config = {
                "use_gpu": self.config_manager.get("gpu.use_gpu", True),
                "gpu_device_index": self.config_manager.get("gpu.device_index", -1),
                "gpu_batch_size": self.config_manager.get("gpu.batch_size", 65536),
                "auto_detect": self.config_manager.get("gpu.auto_detect", True),
                "memory_usage_ratio": self.config_manager.get("gpu.memory_usage_ratio", 0.5),
                "enable_vendor_optimizations": self.config_manager.get(
                    "gpu.enable_vendor_optimizations", True,
                ),
            }

            # 更新GPUConfig内部配置(如果GPUConfig支持set_gpu_config)
            if hasattr(self.gpu_config, "set_gpu_config"):
                self.gpu_config.set_gpu_config(**gpu_config)

            logger.debug("GPU配置同步成功")
        except Exception as e:
            logger.warning("GPU配置同步失败: %s", e)

    def _sync_crypto_config(self) -> None:
        """同步Crypto配置到CryptoConfig"""
        try:
            crypto_backend = self.config_manager.get("crypto.backend", "auto")
            constant_time = self.config_manager.get("crypto.constant_time", False)
            verify_checksums = self.config_manager.get("crypto.verify_checksums", True)
            strict_wif = self.config_manager.get("crypto.strict_wif_validation", True)

            # 更新CryptoConfig
            self.crypto_config.set("backend", crypto_backend)
            self.crypto_config.set("constant_time", constant_time)
            self.crypto_config.set("verify_checksums", verify_checksums)
            self.crypto_config.set("strict_wif_validation", strict_wif)

            logger.debug("Crypto配置同步成功")
        except Exception as e:
            logger.warning("Crypto配置同步失败: %s", e)

    def get_unified_config(self) -> dict[str, Any]:
        """获取统一的配置视图（线程安全）

        返回:
            包含所有配置的统一字典
        """
        # S1修复: 使用锁保护读取操作，防止多线程并发访问导致的数据不一致
        with self._sync_lock:
            return {
                "collision": self.config_manager.get("collision", {}),
                "gpu": self.config_manager.get("gpu", {}),
                "crypto": self.crypto_config.to_dict(),
                "logging": self.config_manager.get("logging", {}),
            }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值(统一接口，线程安全)

        参数:
            key: 配置键,支持点号分隔的路径,如 "gpu.batch_size"
            default: 默认值

        返回:
            配置值
        """
        # S1修复: 使用锁保护读取操作
        with self._sync_lock:
            # 优先从ConfigManager获取
            value = self.config_manager.get(key, None)
            if value is not None:
                return value

            # 特殊处理crypto配置
            if key.startswith("crypto."):
                return self.crypto_config.get(key.split(".", 1)[1], default)

            return default

    def set(self, key: str, value: Any) -> bool:
        """设置配置值(统一接口，线程安全)

        参数:
            key: 配置键,支持点号分隔的路径
            value: 配置值

        返回:
            设置成功返回True
        """
        # S1修复: 使用锁保护写入操作
        with self._sync_lock:
            # 路由到对应的配置管理器
            if key.startswith("crypto."):
                return self.crypto_config.set(key.split(".", 1)[1], value)
            return self.config_manager.set(key, value)

    def validate_all(self) -> dict[str, Any]:
        """验证所有配置

        返回:
            验证错误字典,key为配置管理器名称,value为错误列表
        """
        errors: dict[str, Any] = {}

        # 验证ConfigManager
        config_errors = self.config_manager.validate()
        if config_errors:
            errors["config_manager"] = config_errors

        # 验证CryptoConfig
        crypto_errors = self.crypto_config.validate()
        if crypto_errors:
            errors["crypto_config"] = crypto_errors

        # 验证GPUConfig
        gpu_errors = self.gpu_config.validate()
        if gpu_errors:
            errors["gpu_config"] = gpu_errors

        return errors

    def save_all(self) -> bool:
        """保存所有配置到文件

        返回:
            保存成功返回True
        """
        success = True

        # 保存ConfigManager(包含所有配置)
        if not self.config_manager.save_config():
            logger.error("ConfigManager保存失败")
            success = False

        return success

    def get_gpu_config(self) -> dict[str, Any]:
        """获取GPU配置"""
        return self.gpu_config.get_gpu_config()

    def get_crypto_config(self) -> dict[str, Any]:
        """获取Crypto配置"""
        return self.crypto_config.to_dict()

    def apply_crypto_config(self) -> bool:
        """应用Crypto配置到加密管理器"""
        return self.crypto_config.apply_to_crypto_manager()
