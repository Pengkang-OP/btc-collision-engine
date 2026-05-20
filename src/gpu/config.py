"""GPU配置管理器

与crypto_config.py集成,提供GPU配置管理功能。
"""

import os
from typing import Any

from src.utils.fast_json import fast_dump, fast_load

from ..utils import get_configured_logger
from .device import GPUDevice, GPUDeviceDetector
from .profiles.loader import GPUProfileLoader

logger = get_configured_logger("GPUConfig")


class GPUConfig:
    """
    GPU配置管理器

    负责:
    1. 加载和保存GPU配置
    2. 提供GPU设备信息
    3. 创建GPU引擎实例
    """

    DEFAULT_CONFIG = {
        "use_gpu": True,
        "gpu_device_index": -1,  # -1表示自动选择
        "gpu_batch_size": 65536,
        "auto_detect": True,
        "memory_usage_ratio": 0.5,
        "enable_vendor_optimizations": True,
    }

    def __init__(self, config_file: str | None = None) -> None:
        """
        初始化GPU配置

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.profile_loader = GPUProfileLoader()

        if config_file and os.path.exists(config_file):
            self._load_config()

    def _load_config(self) -> None:
        """从文件加载配置"""
        if self.config_file is None:
            return
        try:
            with open(self.config_file, encoding="utf-8") as f:
                user_config = fast_load(f)

            # 只加载gpu相关配置
            if "gpu" in user_config:
                self.config.update(user_config["gpu"])
            else:
                # 兼容旧格式
                self.config.update(
                    {k: v for k, v in user_config.items() if k.startswith("gpu_") or k == "use_gpu"}
                )

            logger.info("GPU配置加载成功")

        except Exception as e:
            logger.warning(f"加载GPU配置失败: {e}")

    def get_gpu_config(self) -> dict[str, Any]:
        """
        获取GPU配置

        Returns:
            GPU配置字典
        """
        return {
            "use_gpu": self.config.get("use_gpu", True),
            "device_index": self.config.get("gpu_device_index", -1),
            "batch_size": self.config.get("gpu_batch_size", 65536),
            "auto_detect": self.config.get("auto_detect", True),
            "memory_usage_ratio": self.config.get("memory_usage_ratio", 0.5),
            "enable_vendor_optimizations": self.config.get("enable_vendor_optimizations", True),
        }

    def set_gpu_config(
        self,
        use_gpu: bool | None = None,
        device_index: int | None = None,
        batch_size: int | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        设置GPU配置

        Args:
            use_gpu: 是否使用GPU
            device_index: GPU设备索引
            batch_size: 批处理大小
            **kwargs: 其他配置项

        Returns:
            设置成功返回True
        """
        if use_gpu is not None:
            self.config["use_gpu"] = use_gpu

        if device_index is not None:
            self.config["gpu_device_index"] = device_index

        if batch_size is not None:
            self.config["gpu_batch_size"] = batch_size

        # 其他配置
        for key, value in kwargs.items():
            self.config[key] = value

        return True

    def get_gpu_device_info(self) -> list:
        """
        获取可用GPU设备列表

        Returns:
            GPU设备信息列表
        """
        try:
            devices = GPUDeviceDetector.detect_devices()

            # 移除内部对象,只返回可序列化信息
            return [
                {
                    "name": dev["name"],
                    "vendor": dev["vendor"],
                    "platform": dev["platform"],
                    "global_mem_size": dev["global_mem_size"],
                    "max_compute_units": dev["max_compute_units"],
                    "type": dev["type"],
                }
                for dev in devices
            ]

        except Exception as e:
            logger.error(f"获取GPU设备信息失败: {e}")
            return []

    def is_gpu_available(self) -> bool:
        """
        检查GPU是否可用

        Returns:
            True如果GPU可用
        """
        return GPUDeviceDetector.is_gpu_available()

    def create_gpu_device(self, device_index: int | None = None) -> GPUDevice:
        """
        创建并初始化GPU设备

        Args:
            device_index: 设备索引,None则使用配置中的值

        Returns:
            已初始化的GPUDevice实例
        """
        if device_index is None:
            device_index = int(self.config.get("gpu_device_index", -1))

        device = GPUDevice()
        device.initialize(device_index)

        return device

    def create_gpu_engine(self, targets: Any) -> Any:
        """
        创建GPU碰撞引擎

        Args:
            targets: 目标地址集合

        Returns:
            GPUCollisionEngine实例
        """
        try:
            from ..collision.gpu_collision_engine import GPUCollisionEngine

            gpu_config = self.get_gpu_config()

            return GPUCollisionEngine(
                targets=targets,
                device_index=gpu_config["device_index"],
                batch_size=gpu_config["batch_size"],
            )

        except ImportError as e:
            logger.error(f"创建GPU引擎失败: {e}")
            raise RuntimeError("GPUCollisionEngine不可用") from e

    def save_config(self) -> bool:
        """
        保存配置到文件

        Returns:
            保存成功返回True
        """
        if not self.config_file:
            return False

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # 读取现有配置
            existing_config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, encoding="utf-8") as f:
                    existing_config = fast_load(f)

            # 更新GPU配置
            existing_config["gpu"] = self.config

            # 保存
            with open(self.config_file, "w", encoding="utf-8") as f:
                fast_dump(existing_config, f, indent=2, ensure_ascii=False)

            logger.info("GPU配置已保存")
            return True

        except Exception as e:
            logger.error(f"保存GPU配置失败: {e}")
            return False

    def validate(self) -> list:
        """
        验证配置

        Returns:
            错误信息列表
        """
        errors = []

        # 验证batch_size
        batch_size = self.config.get("gpu_batch_size", 65536)
        if not isinstance(batch_size, int) or batch_size <= 0:
            errors.append("gpu_batch_size必须是正整数")

        # 验证device_index
        device_index = self.config.get("gpu_device_index", -1)
        if not isinstance(device_index, int):
            errors.append("gpu_device_index必须是整数")

        # 验证memory_usage_ratio
        memory_ratio = self.config.get("memory_usage_ratio", 0.5)
        if not isinstance(memory_ratio, (int, float)) or not (0 < memory_ratio <= 1.0):
            errors.append("memory_usage_ratio必须在(0, 1]范围内")

        return errors
