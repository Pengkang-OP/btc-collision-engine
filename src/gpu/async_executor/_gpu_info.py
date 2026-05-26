"""GPU 型号检测和配置适配。

为 AsyncGPUExecutor 提供 GPU 型号检测、配置选择和 work_group 调优。

v5.2.3: 从 async_executor.py 提取为独立模块（代码质量优化 #M1）。
"""

from contextlib import suppress

from ...utils import get_configured_logger
from ..executor_types import GPU_SPECIFIC_CONFIG

logger = get_configured_logger("AsyncGPUExecutor.GPUInfo")


class _GPUInfoMixin:
    """GPU 型号检测和配置适配 Mixin。

    为 AsyncGPUExecutor 提供 GPU 型号检测、配置选择和 work_group 调优。
    使用 Mixin 模式以避免对 self 属性的侵入性访问。

    Note:
        Mixin 方法通过 self 访问 AsyncGPUExecutor 实例属性。

    """

    def _detect_gpu_model(self) -> str:
        """检测GPU型号并返回配置标识。

        通过设备信息中的 name 字段检测具体 GPU 型号，
        返回与 GPU_SPECIFIC_CONFIG 中对应的配置键名。

        检测优先级:
        1. 具体型号匹配 (如 "1660", "rtx40")
        2. 系列匹配 (如 "rtx30", "amd6000")
        3. 厂商匹配 (如 "intel", "amd")
        4. 回退到 "default"

        Returns:
            GPU型号标识，如 "1660", "rtx40", "intel", "default" 等

        """
        if hasattr(self, "device") and hasattr(self.device, "device_info") and self.device.device_info:
            device_name = self.device.device_info.get("name", "").lower()
            if "1660" in device_name:
                return "1660"
            if "rtx 40" in device_name or "rtx40" in device_name:
                return "rtx40"
            if "rtx 30" in device_name or "rtx30" in device_name:
                return "rtx30"
            if "rtx" in device_name:
                return "rtx30"
            if (
                "gtx 10" in device_name
                or "1060" in device_name
                or "1070" in device_name
                or "1080" in device_name
            ):
                return "10"
            if (
                "gtx 9" in device_name
                or "960" in device_name
                or "970" in device_name
                or "980" in device_name
            ):
                return "9"
            if "rx 7" in device_name or "rx7" in device_name:
                return "amd7000"
            if "rx 6" in device_name or "rx6" in device_name:
                return "amd6000"
            if "amd" in device_name or "radeon" in device_name:
                return "amd6000"
            if "intel" in device_name or "iris" in device_name or "arc" in device_name:
                return "intel"
        return "default"

    def _get_gpu_config(self, gpu_model: str) -> dict:
        """获取GPU特定配置。

        Args:
            gpu_model: GPU型号标识

        Returns:
            GPU配置字典

        """
        return GPU_SPECIFIC_CONFIG.get(gpu_model, GPU_SPECIFIC_CONFIG.get("default", {}))

    def _detect_optimal_work_group_size(self, gpu_config: dict) -> int:
        """检测最优 work_group_size。

        从 GPU 设备信息和型号配置推断最优 work_group_size。
        显式设置 work_group_size 可避免 OpenCL 运行时自动选择次优值。

        Args:
            gpu_config: GPU 型号特定配置字典

        Returns:
            最优 work_group_size (64-1024)

        """
        # 优先从 GPU 设备信息获取（如果设备已初始化）
        device_ws = None
        with suppress(AttributeError):
            if (hasattr(self, "device") and hasattr(self.device, "device_info")
                    and self.device.device_info):
                device_ws = self.device.device_info.get("work_group_size")

        if device_ws and isinstance(device_ws, int) and 64 <= device_ws <= 1024:
            return device_ws

        # 从 GPU 型号配置获取默认值
        model_ws_map: dict[str, int] = {
            "1660": 256,
            "rtx30": 256,
            "rtx40": 512,
            "10": 256,
            "9": 256,
            "amd6000": 256,
            "amd7000": 256,
            "intel": 256,
            "default": 256,
        }
        gpu_model = self._detect_gpu_model()
        return model_ws_map.get(gpu_model, 256)
