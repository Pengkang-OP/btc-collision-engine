"""加密配置管理.

管理加密后端的选择和配置。
支持从配置文件加载和保存加密设置。
"""

import json
import os
import pathlib
from enum import StrEnum
from typing import Any


class CryptoBackendType(StrEnum):
    """加密后端类型（字符串版本，用于配置）.

    使用 (str, Enum) 而非 StrEnum 以保证一致性。
    StrEnum 在 Python 3.11 引入，本项目最低要求 3.12 但保持该约定。
    """

    PURE_PYTHON = "pure_python"
    PURE_PYTHON_CONST_TIME = "pure_python_const_time"
    OPENSSL = "openssl"
    COINCURVE = "coincurve"
    ECDSA = "ecdsa"
    AUTO = "auto"


class CryptoConfig:
    """加密配置管理器.

    管理加密相关的配置选项。
    """

    DEFAULT_CONFIG = {
        "backend": "auto",  # auto, pure_python, pure_python_const_time, openssl, coincurve, ecdsa
        "constant_time": False,  # 是否优先使用恒定时间算法
        "verify_checksums": True,  # 验证所有Base58Check校验和
        "strict_wif_validation": True,  # 严格WIF格式验证
    }

    def __init__(self, config_file: str | None = None, config_manager=None) -> None:
        """初始化加密配置.

        Args:
            config_file: 配置文件路径，None表示使用默认配置
            config_manager: ConfigManager实例，用于获取统一配置

        """
        self.config_file = config_file
        self.config_manager = config_manager  # 引用ConfigManager
        self.config = self.DEFAULT_CONFIG.copy()

        if config_file and pathlib.Path(config_file).exists():
            self.load()

    def load(self) -> bool:
        """从文件加载配置.

        Returns:
            加载成功返回True

        """
        try:
            if self.config_file is None:
                return False
            with pathlib.Path(self.config_file).open(encoding="utf-8") as f:
                user_config = json.load(f)
            self.config.update(user_config)
            return True
        except (OSError, json.JSONDecodeError, ValueError, KeyError) as e:
            import logging

            logging.warning("加载加密配置失败: %s", e)
            return False

    def save(self) -> bool:
        """保存配置到文件.

        Returns:
            保存成功返回True

        """
        if not self.config_file:
            return False

        try:
            # 确保目录存在
            pathlib.Path(os.path.dirname(self.config_file)).mkdir(exist_ok=True, parents=True)

            with pathlib.Path(self.config_file).open("w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except (OSError, ValueError, TypeError) as e:
            import logging

            logging.exception("保存加密配置失败: %s", e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值.

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值

        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """设置配置值.

        Args:
            key: 配置键
            value: 配置值

        Returns:
            设置成功返回True

        """
        self.config[key] = value
        return True

    def get_backend_type(self) -> CryptoBackendType:
        """获取当前配置的后端类型.

        Returns:
            CryptoBackendType枚举值

        """
        backend_str = self.config.get("backend", "auto")
        try:
            return CryptoBackendType(backend_str)
        except ValueError:
            return CryptoBackendType.AUTO

    def set_backend_type(self, backend_type: CryptoBackendType) -> bool:
        """设置后端类型.

        Args:
            backend_type: 后端类型

        Returns:
            设置成功返回True

        """
        self.config["backend"] = backend_type.value
        return True

    def apply_to_crypto_manager(self) -> bool:
        """将配置应用到加密后端管理器（线程安全）.

        Returns:
            应用成功返回True

        """
        from ..core.crypto_backend import BackendType, crypto_manager

        backend_type = self.get_backend_type()

        if backend_type == CryptoBackendType.AUTO:
            # 自动选择最佳后端（使用线程安全的公开方法）
            crypto_manager.reset_to_best_backend()
            return True

        backend_mapping = {
            CryptoBackendType.PURE_PYTHON: (BackendType.PURE_PYTHON, {"use_const_time": False}),
            CryptoBackendType.PURE_PYTHON_CONST_TIME: (
                BackendType.PURE_PYTHON,
                {"use_const_time": True},
            ),
            CryptoBackendType.OPENSSL: (BackendType.OPENSSL, {}),
            CryptoBackendType.COINCURVE: (BackendType.COINCURVE, {}),
            CryptoBackendType.ECDSA: (BackendType.ECDSA, {}),
        }

        if backend_type in backend_mapping:
            bt, kwargs = backend_mapping[backend_type]
            try:
                crypto_manager.set_backend(bt, **kwargs)
                return True
            except RuntimeError as e:
                import logging

                logging.warning(f"无法设置后端 {backend_type.value}: {e}")
                # 回退到自动选择（使用线程安全的公开方法）
                crypto_manager.reset_to_best_backend()
                return False

        return False

    @staticmethod
    def is_gpu_available() -> bool:
        """检测GPU环境是否就绪（pyopencl可用且有设备）.

        Returns:
            True if GPU可用，False otherwise

        """
        from ..gpu.device import GPUDeviceDetector

        return GPUDeviceDetector.is_gpu_available()

    def get_gpu_device_info(self) -> list:
        """获取可用GPU设备列表.

        Returns:
            可用GPU设备信息列表，每个设备是一个字典
            格式: [{"name": str, "type": str, "platform": str, ...}, ...]
            如果无可用设备或pyopencl不可用，返回空列表

        """
        from ..gpu.config import GPUConfig

        gpu_config = GPUConfig()
        return gpu_config.get_gpu_device_info()

    def create_gpu_engine(self, targets) -> Any:
        """根据当前GPU配置创建GPU碰撞引擎.

        Args:
            targets: 目标地址集合

        Returns:
            GPUCollisionEngine实例

        Raises:
            RuntimeError: 当GPU不可用时

        """
        from ..collision.gpu.engine import GPUCollisionEngine

        gpu_config = self.get_gpu_config()
        return GPUCollisionEngine(
            targets=targets,
            batch_size=gpu_config["batch_size"],
            device_index=gpu_config["device_index"],
        )

    def get_gpu_config(self) -> dict[str, Any]:
        """获取GPU配置.

        优先从ConfigManager获取,如果没有则使用默认值

        Returns:
            GPU配置字典

        """
        # 如果有ConfigManager,从它获取GPU配置
        if self.config_manager:
            return {
                "use_gpu": self.config_manager.get("gpu.use_gpu", True),
                "device_index": self.config_manager.get("gpu.device_index", -1),
                "batch_size": self.config_manager.get("gpu.batch_size", 65536),
                "auto_detect": self.config_manager.get("gpu.auto_detect", True),
                "memory_usage_ratio": self.config_manager.get("gpu.memory_usage_ratio", 0.5),
                "enable_vendor_optimizations": self.config_manager.get(
                    "gpu.enable_vendor_optimizations",
                    True,
                ),
            }

        # 否则返回默认值(向后兼容)
        return {
            "use_gpu": self.config.get("use_gpu", True),
            "device_index": self.config.get("gpu_device_index", -1),
            "batch_size": self.config.get("gpu_batch_size", 65536),
        }

    def set_gpu_config(
        self,
        use_gpu: bool | None = None,
        device_index: int | None = None,
        batch_size: int | None = None,
    ) -> bool:
        """设置GPU配置.

        Args:
            use_gpu: 是否使用GPU
            device_index: GPU设备索引
            batch_size: 批处理大小

        Returns:
            设置成功返回True

        """
        if use_gpu is not None:
            self.config["use_gpu"] = use_gpu
        if device_index is not None:
            self.config["gpu_device_index"] = device_index
        if batch_size is not None:
            self.config["gpu_batch_size"] = batch_size
        return True

    def validate(self) -> list:
        """验证配置.

        Returns:
            错误信息列表，空列表表示验证通过

        """
        errors = []

        # 验证后端类型
        backend = self.config.get("backend", "auto")
        valid_backends = [b.value for b in CryptoBackendType]
        if backend not in valid_backends:
            errors.append(f"无效的后端类型: {backend}")

        # 验证constant_time配置
        constant_time = self.config.get("constant_time", False)
        if not isinstance(constant_time, bool):
            errors.append("constant_time 必须是布尔值")

        # 验证verify_checksums配置
        verify_checksums = self.config.get("verify_checksums", True)
        if not isinstance(verify_checksums, bool):
            errors.append("verify_checksums 必须是布尔值")

        # 验证strict_wif_validation配置
        strict_wif = self.config.get("strict_wif_validation", True)
        if not isinstance(strict_wif, bool):
            errors.append("strict_wif_validation 必须是布尔值")

        # 注意: GPU配置验证已迁移到ConfigManager.validate()
        # 如果需要使用GPU配置,通过ConfigCoordinator或ConfigManager获取

        return errors

    def to_dict(self) -> dict[str, Any]:
        """导出配置为字典.

        Returns:
            配置字典

        """
        return self.config.copy()

    def reset_to_defaults(self) -> None:
        """重置为默认配置."""
        self.config = self.DEFAULT_CONFIG.copy()


# 全局配置实例
def get_crypto_config(config_file: str | None = None) -> CryptoConfig:
    """获取加密配置实例.

    Args:
        config_file: 配置文件路径

    Returns:
        CryptoConfig实例

    """
    if config_file is None:
        # 使用默认配置文件路径
        config_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".config")
        config_file = os.path.join(config_dir, "crypto.json")

    return CryptoConfig(config_file)


# 便捷函数
def init_crypto_from_config(config_file: str | None = None) -> CryptoConfig:
    """从配置文件初始化加密系统.

    Args:
        config_file: 配置文件路径

    Returns:
        CryptoConfig实例

    """
    config = get_crypto_config(config_file)
    config.apply_to_crypto_manager()
    return config
