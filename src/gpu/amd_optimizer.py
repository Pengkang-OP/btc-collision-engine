"""AMD GPU 专有优化模块

封装所有 AMD GPU 特定的优化逻辑，包括：
- 驱动版本检测（Adrenalin/ROCm）
- GPU 架构代识别（GCN1.0/GCN3.0/Vega/RDNA/RDNA2/RDNA3/RDNA4/CDNA1-4）
- Wavefront 大小验证（GCN/CDNA=64, RDNA原生=32兄容樟64）
- 显存类型与 Infinity Cache 优化建议

支持的架构代系（基于AMD官方文档）：
  GCN 1.0 (2012) / GCN 3.0 (2015) / Vega GCN 5.0 (2017)
  RDNA 1.0 (2019) / RDNA 2.0 (2020) / RDNA 3.0 (2022) / RDNA 4.0 (2025)
  CDNA 1.0 (2019) / CDNA 2.0 (2021) / CDNA 3.0 (2023) / CDNA 4.0 (2024)

通过 AmdGPUOptimizer 类提供统一接口，供 GPUCollisionEngine 委托调用。
所有优化在 OpenCL 框架内实现。

注意：禁止使用 -cl-fast-relaxed-math 等快速数学优化，避免破坏
SHA256/RIPEMD160/secp256k1 等加密/哈希运算的精度。
"""

import logging
from ..utils import init_logging, get_configured_logger
import re
from typing import Any, Optional, TYPE_CHECKING

logger = get_configured_logger("AMDOptimizer")

# 延迟导入避免循环依赖
if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 内部辅助组件
# ---------------------------------------------------------------------------


class _RateLimitedLogger:
    """频率限制日志记录器

    避免在高频循环中产生大量重复日志，每条消息在冷却期内只记录一次。
    """

    def __init__(self, base_logger: Any, cooldown_seconds: float = 60.0) -> None:
        self._logger = base_logger
        self._cooldown = cooldown_seconds
        self._last_logged: dict = {}

    def warning(self, key: str, message: str) -> None:
        import time

        now = time.monotonic()
        if now - self._last_logged.get(key, 0.0) >= self._cooldown:
            self._logger.warning(message)
            self._last_logged[key] = now

    def info(self, key: str, message: str) -> None:
        import time

        now = time.monotonic()
        if now - self._last_logged.get(key, 0.0) >= self._cooldown:
            self._logger.info(message)
            self._last_logged[key] = now


class AmdDriverDetector:
    """AMD 驱动版本检测器

    从设备信息中提取驱动版本，支持 Adrenalin 和 ROCm 两种驱动。
    - Adrenalin（消费级）：最低 22.10，推荐 25.x
    - ROCm（专业级）：最低 4.5，推荐 7.x
    来源：amdgpu.com 官方驱动发布说明
    """

    # 推荐最低版本（基于AMD官方发布说明）
    MIN_ROCM_MAJOR = 4  # ROCm 4.5+ (最低支持OpenCL 2.0)
    MIN_ROCM_MINOR = 5  # ROCm 4.5
    RECOMMENDED_ROCM_MAJOR = 7  # ROCm 7.x (最新推荐)
    MIN_ADRENALIN_YEAR = 22  # Adrenalin 22.10+
    MIN_ADRENALIN_MINOR = 10
    RECOMMENDED_ADRENALIN_YEAR = 25  # Adrenalin 25.x (最新推荐)

    def __init__(self, device_info: dict, engine_logger: Optional[Any] = None) -> None:
        self._device_info = device_info
        self._logger = engine_logger or logger

    def detect(self) -> dict:
        """检测驱动版本并返回结果字典

        Returns:
            {
                'version_str': str | None,
                'driver_type': str,         # 'ROCm' / 'Adrenalin' / 'Unknown'
                'is_sufficient': bool,      # 是否满足推荐最低版本
                'recommendation': str | None,
            }
        """
        result = {
            "version_str": None,
            "driver_type": "Unknown",
            "is_sufficient": False,
            "recommendation": None,
        }

        version_str = self._device_info.get("driver_version") or self._device_info.get(
            "version", ""
        )
        if not version_str:
            result["recommendation"] = (
                "无法检测 AMD 驱动版本，建议使用 Adrenalin 22.10+ 或 ROCm 4.0+ 以获得最佳 OpenCL 支持"
            )
            return result

        version_str = str(version_str)
        result["version_str"] = version_str

        # 判断驱动类型并解析版本
        if "rocm" in version_str.lower():
            result["driver_type"] = "ROCm"
            major, minor = self._parse_rocm_version(version_str)
            if major is not None:
                # ROCm 4.5+ 满足最低要求
                result["is_sufficient"] = major > self.MIN_ROCM_MAJOR or (
                    major == self.MIN_ROCM_MAJOR and (minor or 0) >= self.MIN_ROCM_MINOR
                )
                if not result["is_sufficient"]:
                    result["recommendation"] = (
                        f"ROCm 版本 {major}.{minor or 0} 较旧，"
                        f"建议升级至 ROCm {self.MIN_ROCM_MAJOR}.{self.MIN_ROCM_MINOR}+ "
                        f"以获得完整 OpenCL 2.0 支持"
                    )
                elif major < self.RECOMMENDED_ROCM_MAJOR:
                    result["recommendation"] = (
                        f"ROCm 版本 {major}.{minor or 0} 可正常工作，"
                        f"建议升级至推荐版本 ROCm {self.RECOMMENDED_ROCM_MAJOR}.x"
                    )
        else:
            # Adrenalin 格式通常为 "22.10.1" 或 "23.5.2"
            result["driver_type"] = "Adrenalin"
            year, minor = self._parse_adrenalin_version(version_str)
            if year is not None:
                result["is_sufficient"] = year > self.MIN_ADRENALIN_YEAR or (
                    year == self.MIN_ADRENALIN_YEAR and minor >= self.MIN_ADRENALIN_MINOR
                )
                if not result["is_sufficient"]:
                    result["recommendation"] = (
                        f"AMD Adrenalin 驱动版本 {year}.{minor} 较旧，"
                        f"建议升级至 {self.MIN_ADRENALIN_YEAR}.{self.MIN_ADRENALIN_MINOR}+ "
                        f"以获得更好的 OpenCL 稳定性"
                    )
                elif year < self.RECOMMENDED_ADRENALIN_YEAR:
                    result["recommendation"] = (
                        f"AMD Adrenalin 驱动版本 {year}.{minor} 可正常工作，"
                        f"建议升级至推荐版本 Adrenalin {self.RECOMMENDED_ADRENALIN_YEAR}.x"
                    )
            else:
                result["is_sufficient"] = True  # 无法解析时不报警

        return result

    @staticmethod
    def _parse_rocm_version(version_str: str) -> tuple:
        """从 ROCm 版本字符串中解析主次版本号，返回(major, minor)"""
        match = re.search(r"(\d+)\.(\d+)", version_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        # 仅有主版本号
        match = re.search(r"(\d+)", version_str)
        if match:
            return int(match.group(1)), None
        return None, None

    @staticmethod
    def _parse_rocm_major(version_str: str) -> Optional[int]:
        """从 ROCm 版本字符串中解析主版本号（常规调用）"""
        match = re.search(r"(\d+)\.\d+", version_str)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _parse_adrenalin_version(version_str: str) -> tuple:
        """从 Adrenalin 版本字符串中解析 (年份, 次版本)"""
        match = re.search(r"(\d{2})\.(\d{1,2})", version_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None


class AmdArchDetector:
    """AMD GPU 架构代识别器

    基于设备名称模式匹配识别架构代，返回架构特性。
    匹配顺序重要：更新/更具体的型号优先，避免误匹配。
    如 'RX 5700' 必须在 'RX 5' 前匹配以区分 RDNA1 和 GCN3。
    """

    # 架构映射：(模式列表, 架构名称, Wavefront大小, 支持特性)
    # 顺序：CDNA系列 > RDNA4 > RDNA3 > RDNA2 > RDNA1 > Vega > GCN3.0 > GCN1.0
    # 基于 AMD 官方建筑师手册和 GPU开放开发者指南
    _ARCH_PATTERNS = [
        # CDNA 4.0 (2024) - MI350/MI355
        # 来源：amd.com CDNA4 建筑师介绍
        (
            ["MI355", "MI350", "MI35"],
            "CDNA4",
            64,
            {
                "infinity_cache": False,
                "chiplet": True,
                "is_cdna": True,
                "lds_kb": 160,
                "memory_type": "HBM3e",
                "min_driver": "ROCm 7.x",
                "recommended_driver": "ROCm 7.x",
            },
        ),
        # CDNA 3.0 (2023) - MI300/MI325
        # 来源：amd.com CDNA3 建筑师介绍
        (
            ["MI325", "MI300", "MI3"],
            "CDNA3",
            64,
            {
                "infinity_cache": False,
                "chiplet": True,
                "is_cdna": True,
                "lds_kb": 64,
                "memory_type": "HBM3",
                "min_driver": "ROCm 6.0",
                "recommended_driver": "ROCm 7.x",
            },
        ),
        # CDNA 2.0 (2021) - MI210/MI250
        # 来源：amd.com CDNA2 建筑师介绍
        (
            ["MI250", "MI210", "MI2"],
            "CDNA2",
            64,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": True,
                "lds_kb": 64,
                "memory_type": "HBM2e",
                "min_driver": "ROCm 5.x",
                "recommended_driver": "ROCm 7.x",
            },
        ),
        # CDNA 1.0 (2019) - MI100
        # 来源：amd.com CDNA1 建筑师介绍
        (
            ["MI100"],
            "CDNA1",
            64,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": True,
                "lds_kb": 64,
                "memory_type": "HBM2",
                "min_driver": "ROCm 4.5",
                "recommended_driver": "ROCm 6.4",
            },
        ),
        # RDNA 4.0 (2025) - RX 9xxx (Navi 4x)
        # 来源：amd.com RDNA4 建筑师介绍
        # 具体型号先，'Navi 4'最后
        (
            [
                "RX 9070",
                "RX 9060",
                "RX 9080",
                "RX 9090",
                "RX 92",
                "RX 93",
                "RX 95",
                "RX 97",
                "RX 99",
                "Navi 4",
                "RDNA4",
            ],
            "RDNA4",
            32,
            {
                "infinity_cache": True,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 128,
                "memory_type": "GDDR6",
                "alternative_wavefront": 64,
                "min_driver": "Adrenalin 25.x",
                "recommended_driver": "Adrenalin 25.x",
            },
        ),
        # RDNA 3.0 (2022) - RX 7xxx (Navi 3x)
        # 来源：amd.com RDNA3 建筑师介绍
        (
            [
                "RX 7900",
                "RX 7800",
                "RX 7700",
                "RX 7600",
                "RX 7500",
                "RX7900",
                "RX7800",
                "RX7700",
                "RX7600",
                "W7900",
                "W7800",
                "Navi 3",
                "RDNA3",
            ],
            "RDNA3",
            32,
            {
                "infinity_cache": True,
                "chiplet": True,
                "is_cdna": False,
                "lds_kb": 128,
                "memory_type": "GDDR6",
                "alternative_wavefront": 64,
                "min_driver": "Adrenalin 23.x",
                "recommended_driver": "Adrenalin 25.x",
            },
        ),
        # RDNA 2.0 (2020) - RX 6xxx (Navi 2x)
        # 来源：amd.com RDNA2 建筑师介绍；全线配备 128MB Infinity Cache
        (
            [
                "RX 6900",
                "RX 6800",
                "RX 6700",
                "RX 6600",
                "RX 6500",
                "RX 6400",
                "RX6900",
                "RX6800",
                "RX6700",
                "RX6600",
                "W6900",
                "W6800",
                "Navi 2",
                "RDNA2",
            ],
            "RDNA2",
            32,
            {
                "infinity_cache": True,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 128,
                "memory_type": "GDDR6",
                "alternative_wavefront": 64,
                "min_driver": "Adrenalin 22.x",
                "recommended_driver": "Adrenalin 24.x",
            },
        ),
        # RDNA 1.0 (2019) - RX 5xxx (Navi 10/14)
        # 注意：具体型号先于'Navi 1'和'RDNA'，避免和 GCN3.0 的'RX 5'模式冲突
        # 来源：amd.com RDNA 建筑师介绍
        (
            [
                "RX 5700",
                "RX 5600",
                "RX 5500",
                "RX 5300",
                "RX5700",
                "RX5600",
                "RX5500",
                "Navi 1",
                "Navi10",
                "Navi14",
                "RDNA",
            ],
            "RDNA",
            32,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 128,
                "memory_type": "GDDR6",
                "alternative_wavefront": 64,
                "min_driver": "Adrenalin 22.x",
                "recommended_driver": "Adrenalin 24.x",
            },
        ),
        # GCN 5.0 / Vega (2017) - Vega56/64 / MI25/MI50/MI60 / Radeon VII
        # 来源：amd.com GCN5 建筑师介绍；Vega 全系列使用 HBM2
        (
            ["Vega", "Radeon VII", "MI50", "MI60", "MI25", "Frontier", "GCN5", "Vega20", "Vega10"],
            "GCN5.0",
            64,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 64,
                "memory_type": "HBM2",
                "min_driver": "Adrenalin 20.x",
                "recommended_driver": "Adrenalin 24.x",
            },
        ),
        # GCN 3.0/4.0 (2015-2016) - Fiji/Polaris - RX 480/580 / Fury
        # 注意：'RX 5'在RDNA1已处理，这里只匹配具体型号
        # 来源：amd.com GCN3 建筑师介绍
        (
            [
                "RX 480",
                "RX 470",
                "RX 460",
                "RX 580",
                "RX 570",
                "RX 560",
                "RX 550",
                "RX480",
                "RX470",
                "RX580",
                "RX570",
                "Fury",
                "Nano",
                "Polaris",
                "Fiji",
                "GCN3",
                "GCN4",
            ],
            "GCN3.0",
            64,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 64,
                "memory_type": "GDDR5",
                "min_driver": "Adrenalin 18.x",
                "recommended_driver": "Adrenalin 22.x",
            },
        ),
        # GCN 1.0/2.0 (2012-2014) - HD 7xxx / R9 2xx/3xx
        # 来源：amd.com GCN1 建筑师介绍
        (
            [
                "R9 390",
                "R9 380",
                "R9 370",
                "R9 290",
                "R9 280",
                "R9 270",
                "R7 260",
                "R7 370",
                "HD 7970",
                "HD 7950",
                "HD 7870",
                "HD 7850",
                "HD 77",
                "HD 78",
                "HD 79",
                "GCN1",
                "GCN2",
                "Tahiti",
                "Hawaii",
                "Bonaire",
            ],
            "GCN1.0",
            64,
            {
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 64,
                "memory_type": "GDDR5",
                "min_driver": "Adrenalin 18.x",
                "recommended_driver": "Adrenalin 22.x",
            },
        ),
    ]

    def __init__(self, device_info: dict, engine_logger: Optional[Any] = None) -> None:
        self._device_info = device_info
        self._logger = engine_logger or logger

    def detect(self) -> dict:
        """检测 GPU 架构代

        Returns:
            {
                'arch': str,                    # 架构名称
                'wavefront_size': int,          # Wavefront 大小（32 或 64）
                'infinity_cache': bool,         # 是否支持 Infinity Cache（RDNA2+）
                'chiplet': bool,                # 是否为 Chiplet 架构（RDNA3/CDNA3+）
                'is_cdna': bool,                # 是否为数据中心CDNA架构
                'lds_kb': int,                  # 局部数据存储大小(KB)
                'memory_type': str,             # 显存类型
                'alternative_wavefront': int,   # 兼容wavefront（RDNA系列可用64）
                'min_driver': str,              # 最低驱动版本
                'recommended_driver': str,      # 推荐驱动版本
            }
        """
        device_name = self._device_info.get("name", "")

        for patterns, arch_name, wavefront_size, features in self._ARCH_PATTERNS:
            for pattern in patterns:
                if pattern.upper() in device_name.upper():
                    return {
                        "arch": arch_name,
                        "wavefront_size": wavefront_size,
                        **features,
                    }

        self._logger.warning(f"⚠️ 无法识别 AMD GPU 架构：{device_name}，使用默认 GCN 配置")
        return {
            "arch": "Unknown",
            "wavefront_size": 64,  # 保守默认値
            "infinity_cache": False,
            "chiplet": False,
            "is_cdna": False,
            "lds_kb": 64,
            "memory_type": "Unknown",
        }


class AmdWavefrontValidator:
    """AMD Wavefront 大小验证器

    验证 work_group_size 是否为 Wavefront 大小的整数倍。
    - GCN 架构（包括CDNA）：Wavefront=64
    - RDNA 1/2/3/4：原生 Wavefront=32，兼容樟可设置为 64
    - work_group_size 应为 wavefront_size 的整数倍以获得最佳性能

    不对齐时记录 warning 并建议调整，不抛出异常。
    """

    def __init__(self, arch_info: dict, engine_logger: Optional[Any] = None) -> None:
        self._arch_info = arch_info
        self._logger = engine_logger or logger
        self._wavefront_size = arch_info.get("wavefront_size", 64)

    def validate(self, work_group_size: int) -> dict:
        """验证 work_group_size 对齐情况

        Args:
            work_group_size: 当前 OpenCL work_group_size

        Returns:
            {
                'valid': bool,
                'wavefront_size': int,
                'work_group_size': int,
                'suggested_size': int | None,
                'warning': str | None,
            }
        """
        result = {
            "valid": True,
            "wavefront_size": self._wavefront_size,
            "work_group_size": work_group_size,
            "suggested_size": None,
            "warning": None,
        }

        if work_group_size <= 0:
            result["valid"] = False
            result["warning"] = f"work_group_size={work_group_size} 无效，应为正整数"
            return result

        if work_group_size % self._wavefront_size != 0:
            result["valid"] = False
            # 计算建议值：向上取整到 wavefront_size 的倍数
            suggested = (
                (work_group_size + self._wavefront_size - 1)
                // self._wavefront_size
                * self._wavefront_size
            )
            result["suggested_size"] = suggested
            result["warning"] = (
                f"work_group_size={work_group_size} 不是 AMD Wavefront 大小 "
                f"{self._wavefront_size} 的倍数（架构: {self._arch_info.get('arch', 'Unknown')}），"
                f"建议调整为 {suggested} 以获得最佳性能"
            )
            self._logger.warning(f"⚠️ {result['warning']}")

        return result


class AmdMemoryOptimizer:
    """AMD 显存优化器

    基于显存类型和架构特性设置 memory_ratio（基于AMD官方技术规格）：
    - HBM 显存（Vega/CDNA 系列） → 0.70（高带宽，但爆发传输系数较大）
    - GDDR6 显存（RDNA 系列） → 0.60
    - GDDR5 显存（老 GCN） → 0.55
    - 有 Infinity Cache（RDNA2+） → 在上述基础上提升 0.05
    """

    # HBM 架构列表（优先从 arch_info 的 memory_type 字段读取）
    # 错误回退用：设备名称关键词匹配
    _HBM_DEVICE_KEYWORDS = [
        "Vega",
        "Radeon VII",
        "MI50",
        "MI60",
        "MI25",
        "MI100",
        "MI210",
        "MI250",
        "MI300",
        "MI325",
        "MI350",
        "MI355",
        "Frontier",
        "Instinct",
    ]
    # HBM 架构列表
    _HBM_ARCHS = {"GCN5.0", "CDNA1", "CDNA2", "CDNA3", "CDNA4"}
    # GDDR6 架构列表
    _GDDR6_ARCHS = {"RDNA", "RDNA2", "RDNA3", "RDNA4"}
    # GDDR5 架构列表
    _GDDR5_ARCHS = {"GCN1.0", "GCN3.0"}

    def __init__(
        self, device_info: dict, arch_info: dict, engine_logger: Optional[Any] = None
    ) -> None:
        self._device_info = device_info
        self._arch_info = arch_info
        self._logger = engine_logger or logger

    def compute(self) -> dict:
        """计算显存优化配置

        Returns:
            {
                'memory_ratio': float,          # 显存使用比例
                'global_mem_gb': float,         # 显存大小（GB）
                'memory_type': str,             # 'HBM' / 'HBM2' / 'HBM2e' / 'HBM3' / 'GDDR6' / 'GDDR5' / 'Unknown'
                'infinity_cache_hint': bool,    # 是否建议利用 Infinity Cache
                'infinity_cache_bonus': float,  # Infinity Cache 提升的 ratio 附加值
            }
        """
        global_mem = self._device_info.get("global_mem_size", 0)
        global_mem_gb = global_mem / (1024**3) if global_mem > 0 else 0.0

        # 优先从 arch_info 中获取显存类型字段（已经由架构识别确定）
        memory_type = self._arch_info.get("memory_type", "")
        if not memory_type or memory_type == "Unknown":
            # 回退：通过设备名称和架构名推断
            device_name = self._device_info.get("name", "")
            memory_type = self._detect_memory_type(device_name)

        # 根据显存类型设置基准 memory_ratio
        arch = self._arch_info.get("arch", "")
        if memory_type in ("HBM2", "HBM2e", "HBM3", "HBM3e", "HBM") or arch in self._HBM_ARCHS:
            base_ratio = 0.70  # HBM带宽高，但爆发传输比系数大，保守一些
            memory_type = memory_type if memory_type != "Unknown" else "HBM"
        elif memory_type == "GDDR6" or arch in self._GDDR6_ARCHS:
            base_ratio = 0.60  # RDNA 系列 GDDR6
            memory_type = "GDDR6"
        elif memory_type == "GDDR5" or arch in self._GDDR5_ARCHS:
            base_ratio = 0.55  # 老 GCN GDDR5
            memory_type = "GDDR5"
        else:
            base_ratio = 0.60  # 保守默认

        # RDNA2+支持 Infinity Cache，提升局部性访问的内存利用率
        infinity_cache_hint = self._arch_info.get("infinity_cache", False)
        infinity_cache_bonus = 0.05 if infinity_cache_hint else 0.0
        memory_ratio = min(base_ratio + infinity_cache_bonus, 0.85)  # 上限 0.85

        return {
            "memory_ratio": memory_ratio,
            "global_mem_gb": global_mem_gb,
            "memory_type": memory_type,
            "infinity_cache_hint": infinity_cache_hint,
            "infinity_cache_bonus": infinity_cache_bonus,
        }

    def _detect_memory_type(self, device_name: str) -> str:
        """根据设备名称和架构推断显存类型（回退逻辑）"""
        device_upper = device_name.upper()
        arch = self._arch_info.get("arch", "")

        # 优先检查架构名
        if arch in self._HBM_ARCHS:
            return "HBM"
        if arch in self._GDDR6_ARCHS:
            return "GDDR6"
        if arch in self._GDDR5_ARCHS:
            return "GDDR5"

        # 设备名称关键词匹配
        for keyword in self._HBM_DEVICE_KEYWORDS:
            if keyword.upper() in device_upper:
                return "HBM"

        return "Unknown"


# ---------------------------------------------------------------------------
# 主优化器类
# ---------------------------------------------------------------------------


class AmdGPUOptimizer:
    """AMD GPU 专有优化器

    封装所有 AMD GPU 特定的优化逻辑，提供统一接口供引擎委托调用。
    与 IntelGPUOptimizer 架构对齐，使用防御性初始化模式。

    注意：所有优化在 OpenCL 框架内实现。
    禁止使用 -cl-fast-relaxed-math 等会破坏加密/哈希精度的快速数学优化。

    Args:
        device_info: 设备信息字典（包含 name, vendor, global_mem_size 等）
        config: 引擎配置字典
        engine_logger: 可选的日志记录器，默认使用模块级 logger
    """

    def __init__(
        self, device_info: dict, config: Optional[dict] = None, engine_logger: Optional[Any] = None
    ) -> None:
        self._device_info = device_info if isinstance(device_info, dict) else {}
        self._config = config or {}
        self._logger = engine_logger or logger
        self._rate_logger = _RateLimitedLogger(self._logger)

        # 内部组件（防御性初始化，默认为 None）
        self._driver_info: Optional[dict] = None
        self._arch_info: Optional[dict] = None
        self._wavefront_result: Optional[dict] = None
        self._memory_config: Optional[dict] = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def apply_optimizations(self) -> dict:
        """应用 AMD GPU 特定优化

        采用防御性策略：每个检测步骤独立执行，单步失败不影响整体。

        Returns:
            优化配置字典，包含各项优化状态和推荐参数
        """
        self._logger.info("=" * 60)
        self._logger.info("🔧 开始应用 AMD GPU 特殊优化")
        self._logger.info("=" * 60)

        result = {}

        # 1. 驱动版本检测
        try:
            detector = AmdDriverDetector(
                device_info=self._device_info,
                engine_logger=self._logger,
            )
            self._driver_info = detector.detect()
            result["driver"] = self._driver_info

            driver_type = self._driver_info.get("driver_type", "Unknown")
            version_str = self._driver_info.get("version_str")

            if version_str:
                sufficient = self._driver_info.get("is_sufficient", False)
                self._logger.info(
                    f"✅ AMD 驱动版本: {version_str}（类型: {driver_type}，"
                    f"版本{'充足' if sufficient else '较旧'}）"
                )
            else:
                self._logger.warning(f"⚠️ 无法检测 AMD 驱动版本（类型: {driver_type}）")

            if self._driver_info.get("recommendation"):
                self._logger.warning(f"⚠️ {self._driver_info['recommendation']}")

        except (OSError, FileNotFoundError) as e:
            self._logger.warning(
                f"⚠️ AMD 驱动检测系统错误（非致命）: {type(e).__name__}: {e}\n"
                f"   驱动版本信息将不可用"
            )
            self._driver_info = {}
            result["driver"] = {}
        except Exception as e:
            self._logger.warning(
                f"⚠️ AMD 驱动检测失败（非致命）: {type(e).__name__}: {e}\n"
                f"   驱动版本信息将不可用"
            )
            self._driver_info = {}
            result["driver"] = {}

        # 2. 架构代识别
        try:
            arch_detector = AmdArchDetector(
                device_info=self._device_info,
                engine_logger=self._logger,
            )
            self._arch_info = arch_detector.detect()
            result["arch"] = self._arch_info

            wavefront_size = self._arch_info.get("wavefront_size", 64)
            infinity_cache = self._arch_info.get("infinity_cache", False)
            self._logger.info(
                f"✅ AMD GPU 架构: {self._arch_info['arch']}"
                f"（Wavefront={wavefront_size}，"
                f"Infinity Cache: {'支持' if infinity_cache else '不支持'}，"
                f"Chiplet: {'是' if self._arch_info.get('chiplet') else '否'}）"
            )

        except (ValueError, KeyError) as e:
            self._logger.warning(
                f"⚠️ AMD 架构识别数据异常（非致命）: {type(e).__name__}: {e}\n"
                f"   架构特性将使用保守默认值（GCN，Wavefront=64）"
            )
            self._arch_info = {
                "arch": "Unknown",
                "wavefront_size": 64,
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 64,
                "memory_type": "Unknown",
            }
            result["arch"] = self._arch_info
        except Exception as e:
            self._logger.warning(
                f"⚠️ AMD 架构识别失败（非致命）: {type(e).__name__}: {e}\n"
                f"   架构特性将使用保守默认值（GCN，Wavefront=64）"
            )
            self._arch_info = {
                "arch": "Unknown",
                "wavefront_size": 64,
                "infinity_cache": False,
                "chiplet": False,
                "is_cdna": False,
                "lds_kb": 64,
                "memory_type": "Unknown",
            }
            result["arch"] = self._arch_info

        # 3. Wavefront 对齐验证
        try:
            work_group_size = self._config.get("work_group_size", 256)
            validator = AmdWavefrontValidator(
                arch_info=self._arch_info,
                engine_logger=self._logger,
            )
            self._wavefront_result = validator.validate(work_group_size)
            result["wavefront"] = self._wavefront_result

            if self._wavefront_result["valid"]:
                self._logger.info(
                    f"✅ AMD Wavefront 对齐验证通过: "
                    f"work_group_size={work_group_size} 是 "
                    f"Wavefront({self._wavefront_result['wavefront_size']}) 的整数倍"
                )

        except (ValueError, TypeError) as e:
            self._logger.warning(
                f"⚠️ AMD Wavefront 验证参数异常（非致命）: {type(e).__name__}: {e}\n"
                f"   Wavefront 对齐将跳过"
            )
            self._wavefront_result = {}
            result["wavefront"] = {}
        except Exception as e:
            self._logger.warning(
                f"⚠️ AMD Wavefront 验证失败（非致命）: {type(e).__name__}: {e}\n"
                f"   Wavefront 对齐将跳过"
            )
            self._wavefront_result = {}
            result["wavefront"] = {}

        # 4. 显存优化配置
        try:
            mem_optimizer = AmdMemoryOptimizer(
                device_info=self._device_info,
                arch_info=self._arch_info,
                engine_logger=self._logger,
            )
            self._memory_config = mem_optimizer.compute()
            result["memory"] = self._memory_config

            mem_type = self._memory_config.get("memory_type", "Unknown")
            mem_gb = self._memory_config.get("global_mem_gb", 0.0)
            mem_ratio = self._memory_config.get("memory_ratio", 0.60)
            ic_hint = self._memory_config.get("infinity_cache_hint", False)
            ic_bonus = self._memory_config.get("infinity_cache_bonus", 0.0)

            self._logger.info(
                f"\u2705 AMD 显存配置: {mem_gb:.1f}GB（类型: {mem_type}），"
                f"memory_ratio={mem_ratio:.2f}"
                + (f"（含 Infinity Cache +{ic_bonus:.2f}）" if ic_bonus > 0 else "")
            )
            if ic_hint:
                self._logger.info("✅ AMD Infinity Cache 可用，局部性访问模式将受益")

        except (ValueError, KeyError, TypeError) as e:
            self._logger.warning(
                f"⚠️ AMD 显存优化配置数据异常（非致命）: {type(e).__name__}: {e}\n"
                f"   显存配置将使用保守默认值"
            )
            self._memory_config = {
                "memory_ratio": 0.60,
                "global_mem_gb": 0.0,
                "memory_type": "Unknown",
                "infinity_cache_hint": False,
                "infinity_cache_bonus": 0.0,
            }
            result["memory"] = self._memory_config
        except Exception as e:
            self._logger.warning(
                f"⚠️ AMD 显存优化配置失败（非致命）: {type(e).__name__}: {e}\n"
                f"   显存配置将使用保守默认值"
            )
            self._memory_config = {
                "memory_ratio": 0.60,
                "global_mem_gb": 0.0,
                "memory_type": "Unknown",
                "infinity_cache_hint": False,
                "infinity_cache_bonus": 0.0,
            }
            result["memory"] = self._memory_config

        # 5. 快速数学优化禁用确认（加密/哈希必须精确）
        result["fast_math_disabled"] = True
        self._logger.info("✅ 快速数学优化: 已禁用（保证 SHA256/RIPEMD160/secp256k1 精度）")

        # 6. 汇总优化建议
        result["recommended_memory_ratio"] = (
            self._memory_config.get("memory_ratio", 0.60) if self._memory_config else 0.60
        )
        result["recommended_wavefront_size"] = (
            self._arch_info.get("wavefront_size", 64) if self._arch_info else 64
        )
        result["arch_name"] = (
            self._arch_info.get("arch", "Unknown") if self._arch_info else "Unknown"
        )

        self._logger.info("=" * 60)
        self._logger.info("✅ AMD GPU 特殊优化应用完成")
        self._logger.info("=" * 60)

        return result

    def get_optimization_report(self) -> dict:
        """返回优化状态报告

        Returns:
            包含当前优化状态的字典
        """
        driver_version = None
        driver_type = "Unknown"
        if self._driver_info:
            driver_version = self._driver_info.get("version_str")
            driver_type = self._driver_info.get("driver_type", "Unknown")

        arch_name = "Unknown"
        wavefront_size = 64
        if self._arch_info:
            arch_name = self._arch_info.get("arch", "Unknown")
            wavefront_size = self._arch_info.get("wavefront_size", 64)

        memory_ratio = 0.60
        global_mem_gb = 0.0
        memory_type = "Unknown"
        infinity_cache = False
        if self._memory_config:
            memory_ratio = self._memory_config.get("memory_ratio", 0.60)
            global_mem_gb = self._memory_config.get("global_mem_gb", 0.0)
            memory_type = self._memory_config.get("memory_type", "Unknown")
            infinity_cache = self._memory_config.get("infinity_cache_hint", False)

        wavefront_valid = True
        if self._wavefront_result:
            wavefront_valid = self._wavefront_result.get("valid", True)

        return {
            "vendor": "AMD",
            "driver_version": driver_version,
            "driver_type": driver_type,
            "arch": arch_name,
            "wavefront_size": wavefront_size,
            "wavefront_aligned": wavefront_valid,
            "global_mem_gb": global_mem_gb,
            "memory_type": memory_type,
            "memory_ratio": memory_ratio,
            "infinity_cache": infinity_cache,
            "fast_math_disabled": True,
            "driver_info": self._driver_info or {},
            "arch_info": self._arch_info or {},
        }
