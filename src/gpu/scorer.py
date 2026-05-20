"""统一GPU设备评分器

提供统一的GPU设备评分算法，消除 selector.py、load_balancer.py、device.py
三处评分公式的不一致性。

评分公式:
    raw_score = memory_score + compute_score + cache_bonus + local_mem_bonus + generation_bonus
    final_score = raw_score * vendor_factor

评分等级:
    S  (>100):  旗舰 (RTX 4090, RX 7900 XTX)
    A  (60-100): 高端 (RTX 4080, RX 7800 XT)
    B  (30-60):  中端 (RTX 3060, RX 6600)
    C  (10-30):  入门 (GTX 1050, RX 550)
    D  (0-10):   低端/核显
"""

from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("GPUDeviceScorer")


class GPUDeviceScorer:
    """统一GPU设备评分器

    用途:
    1. 设备选择 (selector.py) - 选择最佳GPU
    2. 负载均衡 (load_balancer.py) - 计算性能权重
    3. 设备检测 (device.py) - 自动选择最佳设备

    使用示例:
        scorer = GPUDeviceScorer()

        # 评分单个设备
        score = scorer.score(device_info)
        tier = scorer.get_tier(score)

        # 按分数排序
        ranked = scorer.rank_devices(devices)
    """

    # === 评分权重 ===
    # 显存: 主要因素，每GB 10分
    WEIGHT_MEMORY = 10.0
    # 计算单元: 次要因素，每CU 0.05分
    WEIGHT_COMPUTE_UNITS = 0.05
    # 全局缓存: 辅助因素，每KB 0.001分
    WEIGHT_CACHE = 0.001
    # 本地内存: 辅助因素，每KB 0.01分
    WEIGHT_LOCAL_MEM = 0.01

    # === 厂商系数 (乘法因子) ===
    VENDOR_FACTORS = {
        "nvidia": 1.0,  # NVIDIA基准
        "amd": 0.95,  # AMD略低
        "intel": 0.9,  # Intel Arc需workarounds
        "unknown": 0.8,  # 未知厂商保守
    }

    # === GPU世代附加分 ===
    # 基于已知GPU型号的近似世代加分
    GENERATION_BONUS: dict[str, dict[str, float]] = {
        "nvidia": {
            "rtx50": 25.0,  # RTX 5090/5080 (Blackwell)
            "rtx40": 15.0,  # RTX 4090/4080/4070/4060 (Ada Lovelace)
            "rtx30": 10.0,  # RTX 3090/3080/3070/3060 (Ampere)
            "rtx20": 5.0,  # RTX 2080/2070/2060 (Turing)
            "gtx16": 2.0,  # GTX 1660/1650 (Turing, no RT)
            "gtx10": 0.0,  # GTX 1080/1070/1060 (Pascal)
            "titan": 12.0,  # Titan series
            "tesla": 8.0,  # Tesla/Data Center
            "quadro": 6.0,  # Quadro/Pro
        },
        "amd": {
            "rx9000": 25.0,  # RX 9070 XT (RDNA 4)
            "rx7000": 12.0,  # RX 7900/7800/7700 (RDNA 3)
            "rx6000": 8.0,  # RX 6900/6800/6700/6600 (RDNA 2)
            "rx5000": 4.0,  # RX 5700/5600/5500 (RDNA 1)
            "rx500": 1.0,  # RX 580/570/560 (GCN 4)
            "vega": 2.0,  # Vega series
            "instinct": 10.0,  # Instinct/Data Center
        },
        "intel": {
            "arc_bmg": 12.0,  # Arc Battlemage (B580/B570)
            "arc": 5.0,  # Arc Alchemist (A770/A750/A380)
            "iris": 1.0,  # Iris Xe
        },
    }

    # === 评分等级阈值 ===
    TIER_THRESHOLDS: list[tuple[str, float, str]] = [
        ("S", 100.0, "旗舰 (Flagship)"),
        ("A", 60.0, "高端 (High-end)"),
        ("B", 30.0, "中端 (Mid-range)"),
        ("C", 10.0, "入门 (Entry-level)"),
        ("D", 0.0, "低端 (Low-end)"),
    ]

    def __init__(self) -> None:
        """初始化GPU评分器"""
        self._model_cache: dict[str, str] = {}

    def score(self, device: dict[str, Any]) -> float:
        """计算GPU设备统一评分

        评分公式:
            raw_score = memory_gb * 10 + cu * 0.05
                        + cache_kb * 0.001 + local_mem_kb * 0.01
                        + generation_bonus
            final_score = raw_score * vendor_factor

        Args:
            device: 设备信息字典，需包含:
                - global_mem_gb (float): 显存大小(GB)
                - max_compute_units (int): 计算单元数
                - vendor (str): 厂商 ('nvidia'/'amd'/'intel'/'unknown')
                - name (str, optional): 设备名称，用于识别世代
                - global_mem_cache_kb (float, optional): 全局缓存(KB)
                - local_mem_kb (float, optional): 本地内存(KB)
                - model (str, optional): 预识别的GPU型号

        Returns:
            评分(越高越好)
        """
        # 1. 显存分数 (主因素)
        memory_gb = device.get("global_mem_gb", 0.0)
        memory_score = memory_gb * self.WEIGHT_MEMORY

        # 2. 计算单元分数 (次因素)
        compute_units = device.get("max_compute_units", 0)
        cu_score = float(compute_units) * self.WEIGHT_COMPUTE_UNITS

        # 3. 缓存加分 (辅助)
        cache_kb = device.get("global_mem_cache_kb", 0.0)
        cache_bonus = float(cache_kb) * self.WEIGHT_CACHE

        # 4. 本地内存加分 (辅助)
        local_mem_kb = device.get("local_mem_kb", 0.0)
        local_mem_bonus = float(local_mem_kb) * self.WEIGHT_LOCAL_MEM

        # 5. GPU世代加分
        vendor = device.get("vendor", "unknown")
        name = device.get("name", "")
        model = device.get("model", "")
        generation_bonus = self._get_generation_bonus(vendor, name, model)

        # 6. 原始总分
        raw_score = memory_score + cu_score + cache_bonus + local_mem_bonus + generation_bonus

        # 7. 厂商系数
        vendor_factor = self.VENDOR_FACTORS.get(vendor, 0.8)

        # 8. 最终评分
        final_score = float(raw_score * vendor_factor)

        # 详细日志 (debug级别)
        logger.debug(
            f"GPU评分 [{device.get('name', 'Unknown')}]: "
            f"mem={memory_score:.1f} + cu={cu_score:.1f} + "
            f"cache={cache_bonus:.1f} + lmem={local_mem_bonus:.1f} + "
            f"gen={generation_bonus:.1f} = {raw_score:.1f}, "
            f"vendor_factor={vendor_factor:.2f}, "
            f"final={final_score:.1f} (Tier: {self.get_tier(final_score)})"
        )

        return final_score

    def score_relative(self, device: dict[str, Any]) -> float:
        """计算相对性能权重 (用于负载均衡)

        使用更平衡的 memory:compute ≈ 60:1 权重比，与旧版 _calculate_performance_weights
        行为保持一致，使任务分配在显存和计算单元之间更均衡。

        与 score() 的区别:
        - score(): 权重比 200:1，偏向显存，用于设备评级排名
        - score_relative(): 权重比 60:1，更平衡，用于负载均衡归一化权重

        仍会乘以 vendor_factor，由调用方 calculate_performance_weights() 归一化。

        Args:
            device: 设备信息字典

        Returns:
            相对性能权重值 (含厂商系数)
        """
        # 负载均衡专用权重：memory:compute ≈ 6.0 : 0.1 = 60:1
        # 与旧版 load_balancer._calculate_performance_weights 保持一致
        _balance_memory = 6.0
        _balance_compute = 0.1

        memory_gb = device.get("global_mem_gb", 0.0)
        compute_units = device.get("max_compute_units", 0)
        vendor = device.get("vendor", "unknown")
        name = device.get("name", "")
        model = device.get("model", "")
        cache_kb = device.get("global_mem_cache_kb", 0.0)
        local_mem_kb = device.get("local_mem_kb", 0.0)

        memory_score = memory_gb * _balance_memory
        cu_score = float(compute_units) * _balance_compute
        # cache/local_mem/generation_bonus 保持与 score() 一致
        cache_bonus = float(cache_kb) * self.WEIGHT_CACHE
        local_mem_bonus = float(local_mem_kb) * self.WEIGHT_LOCAL_MEM
        generation_bonus = self._get_generation_bonus(vendor, name, model)

        raw_score = memory_score + cu_score + cache_bonus + local_mem_bonus + generation_bonus
        vendor_factor = self.VENDOR_FACTORS.get(vendor, 0.8)

        return float(raw_score * vendor_factor)

    def get_tier(self, score: float) -> str:
        """获取评分等级

        Args:
            score: 设备评分

        Returns:
            等级标识 ('S'/'A'/'B'/'C'/'D')
        """
        for tier, threshold, _ in self.TIER_THRESHOLDS:
            if score >= threshold:
                return tier
        return "D"

    def get_tier_description(self, score: float) -> str:
        """获取评分等级描述

        Args:
            score: 设备评分

        Returns:
            等级描述字符串
        """
        for tier, threshold, desc in self.TIER_THRESHOLDS:
            if score >= threshold:
                return f"{tier} ({desc})"
        return "D (低端)"

    def rank_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按评分降序排列设备

        Args:
            devices: 设备信息列表

        Returns:
            按评分降序排列的设备列表 (会添加 'score' 和 'tier' 字段)
        """
        for device in devices:
            score = self.score(device)
            device["score"] = score
            device["tier"] = self.get_tier(score)

        return sorted(devices, key=lambda d: d.get("score", 0), reverse=True)

    def select_best(self, devices: list[dict[str, Any]]) -> dict[str, Any] | None:
        """选择评分最高的设备

        Args:
            devices: 设备信息列表

        Returns:
            最佳设备信息，无设备时返回 None
        """
        if not devices:
            return None

        ranked = self.rank_devices(devices)
        return ranked[0]

    def calculate_performance_weights(self, devices: list[dict[str, Any]]) -> dict[int, float]:
        """计算归一化的性能权重 (用于负载均衡)

        Args:
            devices: 设备信息列表

        Returns:
            设备索引 -> 归一化权重 (总和为1.0)
        """
        raw_weights: dict[int, float] = {}

        for device in devices:
            idx = device.get("global_index", 0)
            raw_weights[idx] = self.score_relative(device)

        # 归一化
        total = sum(raw_weights.values())
        if total > 0:
            return {idx: w / total for idx, w in raw_weights.items()}
        else:
            # 降级为平均分配
            n = len(raw_weights)
            return {idx: 1.0 / n for idx in raw_weights}

    def compare_devices(self, device_a: dict[str, Any], device_b: dict[str, Any]) -> str:
        """比较两个设备的性能

        Args:
            device_a: 设备A信息
            device_b: 设备B信息

        Returns:
            比较结果字符串
        """
        score_a = self.score(device_a)
        score_b = self.score(device_b)

        name_a = device_a.get("name", "Unknown")
        name_b = device_b.get("name", "Unknown")

        if score_a > score_b:
            ratio = score_a / max(score_b, 0.01)
            return f"{name_a} 优于 {name_b} ({ratio:.1f}x)"
        elif score_b > score_a:
            ratio = score_b / max(score_a, 0.01)
            return f"{name_b} 优于 {name_a} ({ratio:.1f}x)"
        else:
            return f"{name_a} 与 {name_b} 性能相当"

    def format_score_report(self, device: dict[str, Any]) -> str:
        """格式化单个设备的评分报告

        Args:
            device: 设备信息字典

        Returns:
            格式化报告字符串
        """
        name = device.get("name", "Unknown")
        vendor = device.get("vendor", "unknown").upper()
        memory_gb = device.get("global_mem_gb", 0)
        compute_units = device.get("max_compute_units", 0)
        cache_kb = device.get("global_mem_cache_kb", 0)
        local_mem_kb = device.get("local_mem_kb", 0)

        score = self.score(device)
        tier = self.get_tier_description(score)
        model = device.get("model", self._identify_model(device.get("name", ""), vendor))

        lines = [
            f"GPU: {name}",
            f"  厂商: {vendor}",
            f"  型号: {model or '未知'}",
            f"  显存: {memory_gb:.1f} GB",
            f"  计算单元: {compute_units}",
            f"  全局缓存: {cache_kb:.0f} KB",
            f"  本地内存: {local_mem_kb:.0f} KB",
            f"  评分: {score:.1f} ({tier})",
        ]

        return "\n".join(lines)

    # === 内部方法 ===

    def _get_generation_bonus(self, vendor: str, device_name: str, model: str = "") -> float:
        """根据GPU型号获取世代附加分

        Args:
            vendor: 厂商标识
            device_name: 设备名称
            model: 预识别的GPU型号标识

        Returns:
            世代附加分
        """
        # 优先使用预识别的 model
        if model and vendor in self.GENERATION_BONUS:
            bonus_map = self.GENERATION_BONUS[vendor]
            if model in bonus_map:
                return bonus_map[model]

        # 从设备名称自动识别
        if not device_name:
            return 0.0

        identified_model = self._identify_model(device_name, vendor)

        if vendor in self.GENERATION_BONUS and identified_model:
            bonus_map = self.GENERATION_BONUS[vendor]
            return bonus_map.get(identified_model, 0.0)

        return 0.0

    def identify_model(self, device_name: str, vendor: str) -> str | None:
        """识别GPU型号 (公开接口)

        Args:
            device_name: 设备名称
            vendor: 厂商标识 (nvidia/amd/intel)

        Returns:
            型号标识字符串或 None
        """
        return self._identify_model(device_name, vendor)

    @staticmethod
    def _identify_nvidia_model(name_lower: str) -> str:
        """从设备名称识别 NVIDIA GPU 型号"""
        if "rtx 50" in name_lower:
            return "rtx50"
        if "rtx 40" in name_lower:
            return "rtx40"
        if "rtx 30" in name_lower:
            return "rtx30"
        if "rtx 20" in name_lower:
            return "rtx20"
        if "gtx 16" in name_lower:
            return "gtx16"
        if "gtx 10" in name_lower:
            return "gtx10"
        if "titan" in name_lower:
            return "titan"
        if "tesla" in name_lower:
            return "tesla"
        if "quadro" in name_lower:
            return "quadro"
        return "nvidia_other"

    @staticmethod
    def _identify_amd_model(name_lower: str) -> str:
        """从设备名称识别 AMD GPU 型号"""
        if "rx 90" in name_lower:
            return "rx9000"
        if "rx 7" in name_lower:
            return "rx7000"
        if "rx 6" in name_lower:
            return "rx6000"
        if "rx 5700" in name_lower or "rx 5600" in name_lower or "rx 5500" in name_lower:
            return "rx5000"
        _rx500_patterns = [
            "rx 590", "rx 580", "rx 570", "rx 560", "rx 550",
            "rx 480", "rx 470", "rx 460", "rx 540", "rx 530",
        ]
        if any(x in name_lower for x in _rx500_patterns):
            return "rx500"
        if "vega" in name_lower:
            return "vega"
        if "instinct" in name_lower:
            return "instinct"
        return "amd_other"

    @staticmethod
    def _identify_intel_model(name_lower: str) -> str:
        """从设备名称识别 Intel GPU 型号"""
        if "arc b" in name_lower or "battlemage" in name_lower:
            return "arc_bmg"
        if "arc" in name_lower:
            return "arc"
        if "iris" in name_lower:
            return "iris"
        return "intel_other"

    def _identify_model(self, device_name: str, vendor: str) -> str | None:
        """从设备名称自动识别GPU型号

        Args:
            device_name: 设备名称
            vendor: 厂商标识

        Returns:
            型号标识字符串，无法识别时返回 None
        """
        cache_key = f"{vendor}:{device_name}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        name_lower = device_name.lower()
        vendor_lower = vendor.lower()

        _identifiers = {
            "nvidia": self._identify_nvidia_model,
            "amd": self._identify_amd_model,
            "intel": self._identify_intel_model,
        }
        identifier = _identifiers.get(vendor_lower)
        model = identifier(name_lower) if identifier else None

        if model:
            self._model_cache[cache_key] = model

        return model


# 模块级单例
_scorer_instance: GPUDeviceScorer | None = None


def get_gpu_scorer() -> GPUDeviceScorer:
    """获取GPUDeviceScorer单例

    Returns:
        GPUDeviceScorer实例
    """
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = GPUDeviceScorer()
    return _scorer_instance


def reset_gpu_scorer() -> None:
    """重置GPUDeviceScorer单例 (用于测试)"""
    global _scorer_instance
    _scorer_instance = None
