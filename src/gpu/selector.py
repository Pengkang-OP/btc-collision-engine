# -*- coding: utf-8 -*-
"""GPU设备选择器

提供GPU设备评分、自动选择和手动指定功能。
支持多厂商GPU(NVIDIA/AMD/Intel)的智能评估。
"""

from ..utils import get_configured_logger
import threading
from typing import List, Dict, Optional, Any

from .device import GPUDeviceDetector, identify_vendor
from .scorer import GPUDeviceScorer, get_gpu_scorer

logger = get_configured_logger("GPUSelector")


class GPUDeviceSelector:
    """GPU设备选择器

    负责检测、评分和选择GPU设备。

    使用示例:
        selector = GPUDeviceSelector()

        # 检测所有设备
        devices = selector.detect_all_devices()

        # 自动选择最佳设备
        best_device = selector.select_best_device()

        # 手动指定设备
        device = selector.get_device_info(0)
    """

    def __init__(self, scorer: Optional[GPUDeviceScorer] = None) -> None:
        """初始化GPU设备选择器

        Args:
            scorer: GPU设备评分器，为None时使用全局单例
        """
        self._scorer = scorer or get_gpu_scorer()
        self._devices_cache: Optional[List[Dict[str, Any]]] = None
        self._scores_cache: Dict[int, float] = {}

    def detect_all_devices(self, force_refresh: bool = False) -> List[Dict]:
        """检测所有GPU设备

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            设备信息列表
        """
        # 使用缓存
        if not force_refresh and self._devices_cache:
            logger.debug("使用设备检测缓存")
            return self._devices_cache

        try:
            # 调用现有检测器
            raw_devices = GPUDeviceDetector.detect_devices()

            if not raw_devices:
                logger.warning("未检测到GPU设备")
                self._devices_cache = []
                return []

            # 增强设备信息
            devices = []
            for idx, raw_device in enumerate(raw_devices):
                device_info = self._enrich_device_info(raw_device, idx)
                devices.append(device_info)

            # 计算评分
            for device in devices:
                device["score"] = self.score_device(device)

            # 缓存结果
            self._devices_cache = devices
            self._scores_cache = {d["global_index"]: d["score"] for d in devices}

            logger.info(f"检测到 {len(devices)} 个GPU设备")
            return devices

        except Exception as e:
            logger.error(f"GPU设备检测失败: {e}")
            self._devices_cache = []
            return []

    def score_device(self, device: Dict) -> float:
        """计算GPU设备评分

        委托给统一的 GPUDeviceScorer 进行评分。

        Args:
            device: 设备信息字典

        Returns:
            评分(越高越好)
        """
        return self._scorer.score(device)

    def select_best_device(
        self, devices: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """自动选择评分最高的GPU设备

        Args:
            devices: 设备列表(为None时自动检测)

        Returns:
            最佳设备信息,无设备时返回None
        """
        if devices is None:
            devices = self.detect_all_devices()

        if not devices:
            logger.warning("无可用GPU设备")
            return None

        # 按评分排序
        best_device = max(devices, key=lambda d: d.get("score", 0))

        logger.info(
            f"自动选择最佳GPU: {best_device['name']} " f"(评分: {best_device['score']:.1f})"
        )

        return best_device

    def get_device_info(self, device_idx: int) -> Optional[Dict]:
        """获取指定索引的设备信息

        Args:
            device_idx: 设备全局索引

        Returns:
            设备信息,不存在时返回None
        """
        devices = self.detect_all_devices()

        for device in devices:
            if device.get("global_index") == device_idx:
                return device

        logger.warning(f"设备索引 {device_idx} 不存在")
        return None

    def format_device_info(self, device: Dict, detailed: bool = False) -> str:
        """格式化设备信息用于展示

        Args:
            device: 设备信息字典
            detailed: 是否显示详细信息

        Returns:
            格式化后的字符串
        """
        name = device.get("name", "Unknown")
        vendor = device.get("vendor", "unknown").upper()
        memory_gb = device.get("global_mem_gb", 0)
        compute_units = device.get("max_compute_units", 0)
        score = device.get("score", 0)
        global_idx = device.get("global_index", -1)

        # 基本信息
        lines = [
            f"GPU {global_idx}: {name}",
            f"  厂商: {vendor}",
            f"  显存: {memory_gb:.2f} GB",
            f"  计算单元: {compute_units}",
            f"  评分: {score:.1f}",
        ]

        # 详细信息
        if detailed:
            work_group = device.get("max_work_group_size", 0)
            cache_kb = device.get("global_mem_cache_kb", 0)
            local_mem_kb = device.get("local_mem_kb", 0)
            batch_size = device.get("recommended_batch_size", 0)
            work_group_size = device.get("recommended_work_group", 0)

            lines.extend(
                [
                    f"  最大工作组: {work_group:,}",
                    f"  全局缓存: {cache_kb:.0f} KB",
                    f"  本地内存: {local_mem_kb:.0f} KB",
                    f"  推荐批次大小: {batch_size:,}",
                    f"  推荐工作组大小: {work_group_size}",
                ]
            )

        return "\n".join(lines)

    def format_all_devices(self, devices: Optional[List[Dict[str, Any]]] = None) -> str:
        """格式化所有设备信息

        Args:
            devices: 设备列表(为None时自动检测)

        Returns:
            格式化后的字符串
        """
        if devices is None:
            devices = self.detect_all_devices()

        if not devices:
            return "未检测到GPU设备"

        lines = [f"检测到 {len(devices)} 个GPU设备:", "=" * 60]

        # 按评分排序
        sorted_devices = sorted(devices, key=lambda d: d.get("score", 0), reverse=True)

        for i, device in enumerate(sorted_devices):
            is_best = i == 0
            marker = "⭐ " if is_best else "   "
            lines.append(marker + self.format_device_info(device, detailed=False))
            if i < len(sorted_devices) - 1:
                lines.append("-" * 60)

        return "\n".join(lines)

    def select_devices_by_indices(self, indices: List[int]) -> List[Dict]:
        """根据索引列表选择设备

        Args:
            indices: 设备索引列表

        Returns:
            选中的设备列表

        Raises:
            ValueError: 索引无效时
        """
        devices = self.detect_all_devices()
        available_indices = [d["global_index"] for d in devices]

        selected = []
        invalid_indices = []

        for idx in indices:
            if idx == -1:
                # -1表示自动选择最佳
                best = self.select_best_device(devices)
                if best:
                    selected.append(best)
            elif idx in available_indices:
                device = self.get_device_info(idx)
                if device:
                    selected.append(device)
            else:
                invalid_indices.append(idx)

        if invalid_indices:
            raise ValueError(
                f"无效的设备索引: {invalid_indices}\n" f"可用索引: {available_indices}"
            )

        return selected

    def recommend_batch_size(self, device: Dict) -> int:
        """推荐批次大小

        基于显存大小计算合适的批次大小。

        Args:
            device: 设备信息

        Returns:
            推荐的批次大小
        """
        memory_gb = device.get("global_mem_gb", 0)
        vendor = device.get("vendor", "unknown")

        # 基础批次大小(基于显存)
        if memory_gb >= 16:
            base_batch = 131072  # 128K
        elif memory_gb >= 8:
            base_batch = 65536  # 64K
        elif memory_gb >= 4:
            base_batch = 32768  # 32K
        else:
            base_batch = 16384  # 16K

        # 厂商调整
        if vendor == "intel":
            # Intel Arc需要较小的批次
            base_batch = max(base_batch // 2, 8192)
        elif vendor == "amd":
            # AMD适中
            base_batch = int(base_batch * 0.8)

        return base_batch

    def recommend_work_group_size(self, device: Dict) -> int:
        """推荐工作组大小

        Args:
            device: 设备信息

        Returns:
            推荐的工作组大小
        """
        max_work_group = device.get("max_work_group_size", 1024)
        vendor = device.get("vendor", "unknown")

        # NVIDIA适合大工作组
        if vendor == "nvidia":
            return int(min(512, max_work_group))
        # AMD/Intel适合中等工作组
        elif vendor in ("amd", "intel"):
            return int(min(256, max_work_group))
        else:
            return int(min(256, max_work_group))

    def _enrich_device_info(self, raw_device: Dict, global_idx: int) -> Dict:
        """增强设备信息,添加评分所需的字段

        Args:
            raw_device: 原始设备信息
            global_idx: 全局索引

        Returns:
            增强后的设备信息
        """
        device_name = raw_device.get("name", "")
        vendor_str = raw_device.get("vendor", "")

        # 识别厂商
        vendor = identify_vendor(device_name, vendor_str)

        # 识别GPU型号 (用于世代加分)
        gpu_model = self._scorer.identify_model(device_name, vendor)

        # 显存(字节转GB)
        global_mem_bytes = raw_device.get("global_mem_bytes", 0)
        global_mem_gb = global_mem_bytes / (1024**3)

        # 推荐参数
        enriched = {
            "global_index": global_idx,
            "platform_index": raw_device.get("platform_index", 0),
            "name": device_name,
            "vendor": vendor,
            "model": gpu_model,
            "global_mem_gb": global_mem_gb,
            "global_mem_bytes": global_mem_bytes,
            "max_compute_units": raw_device.get("max_compute_units", 0),
            "max_work_group_size": raw_device.get("max_work_group_size", 1024),
            "global_mem_cache_kb": raw_device.get("global_mem_cache_kb", 0),
            "local_mem_kb": raw_device.get("local_mem_kb", 0),
            "platform_name": raw_device.get("platform_name", ""),
        }

        # 添加推荐参数
        enriched["recommended_batch_size"] = self.recommend_batch_size(enriched)
        enriched["recommended_work_group"] = self.recommend_work_group_size(enriched)

        return enriched

    def clear_cache(self) -> None:
        """清除设备缓存"""
        self._devices_cache = None
        self._scores_cache = {}
        logger.debug("GPU设备选择器缓存已清除")


# 线程安全的单例
_selector_instance = None
_selector_lock = threading.Lock()


def get_gpu_selector() -> GPUDeviceSelector:
    """获取GPU设备选择器单例（线程安全）

    Returns:
        GPUDeviceSelector实例
    """
    global _selector_instance

    # 双重检查锁定模式
    if _selector_instance is None:
        with _selector_lock:
            if _selector_instance is None:
                _selector_instance = GPUDeviceSelector()

    return _selector_instance


def reset_gpu_selector() -> None:
    """重置GPU设备选择器单例(用于测试)"""
    global _selector_instance
    with _selector_lock:
        _selector_instance = None
