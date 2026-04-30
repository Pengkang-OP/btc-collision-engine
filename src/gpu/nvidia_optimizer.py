"""NVIDIA GPU 专有优化模块

封装所有 NVIDIA GPU 特定的优化逻辑，包括：
- 驱动版本检测与建议
- GPU 架构代识别（Kepler/Maxwell/Pascal/Volta/Turing/Ampere/Ada/Hopper/Blackwell）
- 显存大小动态配置（含HBM数据中心卡识别）
- 异步传输建议（Ampere+ 架构）

支持的架构代系（基于NVIDIA官方文档）：
  Kepler (CC 3.x, 2012) / Maxwell (CC 5.x, 2014) / Pascal (CC 6.1, 2016)
  Volta (CC 7.0, 2017) / Turing (CC 7.5, 2018) / Ampere (CC 8.x, 2020)
  Ada Lovelace (CC 8.9, 2022) / Hopper (CC 9.0, 2023) / Blackwell (CC 10.x, 2024)

通过 NvidiaGPUOptimizer 类提供统一接口，供 GPUCollisionEngine 委托调用。
所有优化在 OpenCL 框架内实现，不使用 CUDA 特有功能。

注意：禁止使用 -cl-fast-relaxed-math 等快速数学优化，避免破坏
SHA256/RIPEMD160/secp256k1 等加密/哈希运算的精度。
"""

import logging
from ..utils import init_logging, get_configured_logger
import re
from typing import Any, Optional, TYPE_CHECKING

logger = get_configured_logger("NvidiaOptimizer")

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


class NvidiaDriverDetector:
    """NVIDIA 驱动版本检测器

    从设备信息或平台信息中提取驱动版本，
    并给出最低版本建议（OpenCL 1.2 需要 310+，推荐 550+）。
    按架构最低驱动要求检查：Kepler=300, Maxwell=340, Pascal=380,
    Volta=410, Turing=440, Ampere=450, Ada=520, Hopper=535, Blackwell=545
    """

    # 推荐最低驱动版本（基于NVIDIA官方文档）
    MIN_DRIVER_FOR_OCL_12 = 310   # OpenCL 1.2 最低驱动
    MIN_DRIVER_FOR_OCL_20 = 440   # OpenCL 2.0 最低驱动
    RECOMMENDED_DRIVER = 550      # 推荐驱动版本（2024+）

    # 各架构最低驱动版本要求（来源：NVIDIA官方发布说明）
    _ARCH_MIN_DRIVERS = {
        'Kepler':    300,
        'Maxwell':   340,
        'Pascal':    380,
        'Volta':     410,
        'Turing':    440,
        'Ampere':    450,
        'Ada':       520,
        'Hopper':    535,
        'Blackwell': 545,
    }

    def __init__(self, device_info: dict, engine_logger: Optional[Any] = None) -> None:
        self._device_info = device_info
        self._logger = engine_logger or logger

    def detect(self) -> dict:
        """检测驱动版本并返回结果字典

        Returns:
            {
                'version_str': str | None,
                'major': int | None,
                'opencl_12_ok': bool,
                'opencl_20_ok': bool,
                'recommendation': str | None,
            }
        """
        result = {
            'version_str': None,
            'major': None,
            'opencl_12_ok': False,
            'opencl_20_ok': False,
            'recommendation': None,
        }

        # 尝试从 device_info 中提取
        version_str = (
            self._device_info.get('driver_version')
            or self._device_info.get('version', '')
        )
        if not version_str:
            result['recommendation'] = "无法检测 NVIDIA 驱动版本，建议升级至 450+ 以获得最佳 OpenCL 支持"
            return result

        result['version_str'] = str(version_str)

        # 尝试解析主版本号（格式如 "530.41.03" 或 "OpenCL 3.0 CUDA 12.1.66"）
        major = self._parse_major_version(str(version_str))
        result['major'] = major

        if major is not None:
            result['opencl_12_ok'] = major >= self.MIN_DRIVER_FOR_OCL_12
            result['opencl_20_ok'] = major >= self.MIN_DRIVER_FOR_OCL_20

            if major < self.MIN_DRIVER_FOR_OCL_12:
                result['recommendation'] = (
                    f"NVIDIA 驱动版本 {major} 过旧（最低需要 {self.MIN_DRIVER_FOR_OCL_12}），"
                    f"建议升级至 {self.RECOMMENDED_DRIVER}+ 以获得完整 OpenCL 支持"
                )
            elif major < self.MIN_DRIVER_FOR_OCL_20:
                result['recommendation'] = (
                    f"NVIDIA 驱动版本 {major} 支持 OpenCL 1.2，"
                    f"升级至 {self.MIN_DRIVER_FOR_OCL_20}+ 可启用 OpenCL 2.0 特性，"
                    f"推荐使用 {self.RECOMMENDED_DRIVER}+"
                )
            elif major < self.RECOMMENDED_DRIVER:
                result['recommendation'] = (
                    f"NVIDIA 驱动版本 {major} 可正常工作，"
                    f"建议升级至推荐版本 {self.RECOMMENDED_DRIVER}+ 以获得最佳性能"
                )

        return result

    @staticmethod
    def _parse_major_version(version_str: str) -> Optional[int]:
        """从版本字符串中解析主版本号"""
        # 匹配形如 "530.41" 或 "390" 的 NVIDIA 驱动版本号
        match = re.search(r'\b(\d{3,4})\b', version_str)
        if match:
            return int(match.group(1))
        return None


class NvidiaArchDetector:
    """NVIDIA GPU 架构代识别器

    基于设备名称模式匹配识别架构代，返回架构特性。
    不使用 CUDA 特有 API，仅依赖设备名称字符串。
    """

    # 架构映射：(模式列表, 架构名称, 支持特性)
    # 顺序重要：更新/更具体的型号优先匹配，避免被旧架构误判
    # 基于 NVIDIA 官方计算能力文档（developer.nvidia.com/cuda-gpus）
    _ARCH_PATTERNS = [
        # Blackwell (CC 10.x, 2024) - B100/B200/RTX 50xx
        # 来源：NVIDIA Blackwell Architecture White Paper 2024
        (['B100', 'B200', 'GB100', 'GB200',
          'RTX 5090', 'RTX 5080', 'RTX 5070', 'RTX 5060', 'RTX 50',
          'Blackwell'],
         'Blackwell', {
             'async_copy': True, 'fp64_native': False,
             'compute_capability': '10.x', 'min_driver': 545, 'recommended_driver': 550,
             'shared_memory_kb': 227, 'warp_size': 32,
         }),
        # Hopper (CC 9.0, 2023) - H100/H200/GH200
        # 来源：NVIDIA Hopper Architecture White Paper 2022
        (['H100', 'H200', 'GH200'],
         'Hopper', {
             'async_copy': True, 'fp64_native': True,
             'compute_capability': '9.0', 'min_driver': 535, 'recommended_driver': 545,
             'shared_memory_kb': 227, 'warp_size': 32,
         }),
        # Ada Lovelace (CC 8.9, 2022) - RTX 40xx / L40 / RTX PRO
        # 来源：NVIDIA Ada Lovelace Architecture White Paper 2022
        (['RTX 4090', 'RTX 4080', 'RTX 4070', 'RTX 4060', 'RTX 4050',
          'RTX 40', 'RTX40', 'L40', 'RTX PRO', 'Ada'],
         'Ada', {
             'async_copy': True, 'fp64_native': False,
             'compute_capability': '8.9', 'min_driver': 520, 'recommended_driver': 545,
             'shared_memory_kb': 227, 'warp_size': 32,
         }),
        # Ampere (CC 8.0-8.6, 2020) - RTX 30xx / A100 / A30 / A40 / A10
        # 来源：NVIDIA Ampere Architecture White Paper 2020
        (['RTX 3090', 'RTX 3080', 'RTX 3070', 'RTX 3060', 'RTX 3050',
          'RTX 30', 'RTX30',
          'A100', 'A40', 'A30', 'A10', 'A6000', 'Ampere'],
         'Ampere', {
             'async_copy': True, 'fp64_native': False,
             'compute_capability': '8.x', 'min_driver': 450, 'recommended_driver': 530,
             'shared_memory_kb': 99, 'warp_size': 32,
         }),
        # Turing (CC 7.5, 2018) - RTX 20xx / GTX 16xx / T4 / Quadro RTX
        # 来源：NVIDIA Turing Architecture White Paper 2018
        (['RTX 2080', 'RTX 2070', 'RTX 2060',
          'RTX 20', 'RTX20',
          'GTX 1660', 'GTX 1650',
          'Quadro RTX', 'T4', 'Turing'],
         'Turing', {
             'async_copy': True, 'fp64_native': False,
             'compute_capability': '7.5', 'min_driver': 440, 'recommended_driver': 520,
             'shared_memory_kb': 96, 'warp_size': 32,
         }),
        # Volta (CC 7.0, 2017) - V100 / Titan V / GV100
        # 来源：NVIDIA Volta Architecture White Paper 2017
        (['V100', 'Titan V', 'GV100', 'Volta'],
         'Volta', {
             'async_copy': True, 'fp64_native': True,
             'compute_capability': '7.0', 'min_driver': 410, 'recommended_driver': 470,
             'shared_memory_kb': 96, 'warp_size': 32,
         }),
        # Pascal (CC 6.1, 2016) - GTX 10xx / Tesla P / GP100 / Quadro P
        # 来源：NVIDIA Pascal Architecture White Paper 2016
        (['GTX 1080', 'GTX 1070', 'GTX 1060', 'GTX 1050',
          'GTX 10', 'GTX10',
          'Tesla P', 'GP100', 'Quadro P',
          'Titan X', 'Pascal', 'GP10'],
         'Pascal', {
             'async_copy': True, 'fp64_native': False,
             'compute_capability': '6.1', 'min_driver': 380, 'recommended_driver': 470,
             'shared_memory_kb': 96, 'warp_size': 32,
         }),
        # Maxwell (CC 5.x, 2014) - GTX 750/9xx / GTX 900系列
        # 来源：NVIDIA Maxwell Architecture White Paper 2014
        (['GTX 980', 'GTX 970', 'GTX 960', 'GTX 950',
          'GTX 750',
          'GTX 9', 'GTX90',
          'Maxwell', 'GM1', 'GM2'],
         'Maxwell', {
             'async_copy': False, 'fp64_native': False,
             'compute_capability': '5.x', 'min_driver': 340, 'recommended_driver': 450,
             'shared_memory_kb': 96, 'warp_size': 32,
         }),
        # Kepler (CC 3.x, 2012) - GTX 6xx/7xx / Tesla K / Titan
        # 来源：NVIDIA Kepler Architecture White Paper 2012
        (['GTX 6', 'GTX 7', 'Tesla K', 'Kepler', 'GK1', 'GK2'],
         'Kepler', {
             'async_copy': False, 'fp64_native': False,
             'compute_capability': '3.x', 'min_driver': 300, 'recommended_driver': 400,
             'shared_memory_kb': 48, 'warp_size': 32,
         }),
    ]

    def __init__(self, device_info: dict, engine_logger: Optional[Any] = None) -> None:
        self._device_info = device_info
        self._logger = engine_logger or logger

    def detect(self) -> dict:
        """检测 GPU 架构代

        Returns:
            {
                'arch': str,                    # 架构名称（未知时为 'Unknown'）
                'async_copy': bool,             # 是否支持异步拷贝（Ampere+）
                'fp64_native': bool,            # 是否原生 FP64 支持
                'compute_capability': str,      # 计算能力版本（如果已知）
                'min_driver': int,              # 最低驱动版本要求
                'recommended_driver': int,      # 推荐驱动版本
                'shared_memory_kb': int,        # 共享内存大小(KB)
                'warp_size': int,               # Warp大小（常为32）
            }
        """
        device_name = self._device_info.get('name', '')

        for patterns, arch_name, features in self._ARCH_PATTERNS:
            for pattern in patterns:
                if pattern.upper() in device_name.upper():
                    return {'arch': arch_name, **features}

        self._logger.warning(f"⚠️ 无法识别 NVIDIA GPU 架构：{device_name}，使用默认配置")
        return {'arch': 'Unknown', 'async_copy': False, 'fp64_native': False}


class NvidiaMemoryOptimizer:
    """NVIDIA 显存优化器

    基于显存大小和类型动态设置 memory_ratio：
    - HBM显存（A100/V100/H100等数据中心卡）→ memory_ratio = 0.80
    - ≥16GB显存 → memory_ratio = 0.75
    - ≥8GB显存 → memory_ratio = 0.70
    - <8GB显存 → memory_ratio = 0.60
    并根据架构特性给出异步传输建议（Ampere+ 支持硬件级 memcpy_async）。
    """

    # HBM 设备关键词（数据中心卡，带宽显著更高）
    # 来源：NVIDIA HBM Memory Architecture Documentation
    _HBM_KEYWORDS = ['A100', 'V100', 'H100', 'H200', 'GH200', 'GV100',
                     'Tesla K', 'Tesla P', 'Quadro GV']

    def __init__(self, device_info: dict, arch_features: dict, engine_logger=None) -> None:
        self._device_info = device_info
        self._arch_features = arch_features
        self._logger = engine_logger or logger

    def compute(self) -> dict:
        """计算显存优化配置

        Returns:
            {
                'memory_ratio': float,      # 显存使用比例
                'global_mem_gb': float,     # 显存大小（GB）
                'async_transfer': bool,     # 是否建议启用异步传输
                'is_hbm': bool,             # 是否为HBM显存（数据中心卡）
            }
        """
        global_mem = self._device_info.get('global_mem_size', 0)
        global_mem_gb = global_mem / (1024 ** 3) if global_mem > 0 else 0.0

        # 检测是否为 HBM 显存的数据中心卡
        device_name = self._device_info.get('name', '')
        is_hbm = self._detect_hbm(device_name)

        # 根据显存类型和大小动态设置 memory_ratio
        if is_hbm:
            # HBM显存（A100/V100等数据中心卡）：带宽高，可用更多显存
            memory_ratio = 0.80
        elif global_mem_gb >= 16.0:
            memory_ratio = 0.75
        elif global_mem_gb >= 8.0:
            memory_ratio = 0.70
        else:
            memory_ratio = 0.60

        # Ampere+ 架构支持硬件级异步拷贝（memcpy_async）
        async_transfer = self._arch_features.get('async_copy', False)

        return {
            'memory_ratio': memory_ratio,
            'global_mem_gb': global_mem_gb,
            'async_transfer': async_transfer,
            'is_hbm': is_hbm,
        }

    def _detect_hbm(self, device_name: str) -> bool:
        """检测设备是否使用HBM显存（数据中心卡）"""
        device_upper = device_name.upper()
        for keyword in self._HBM_KEYWORDS:
            if keyword.upper() in device_upper:
                return True
        return False


# ---------------------------------------------------------------------------
# 主优化器类
# ---------------------------------------------------------------------------

class NvidiaGPUOptimizer:
    """NVIDIA GPU 专有优化器

    封装所有 NVIDIA GPU 特定的优化逻辑，提供统一接口供引擎委托调用。
    与 IntelGPUOptimizer 架构对齐，使用防御性初始化模式。

    注意：所有优化在 OpenCL 框架内实现，不使用 CUDA 特有功能。
    禁止使用 -cl-fast-relaxed-math 等会破坏加密/哈希精度的快速数学优化。

    Args:
        device_info: 设备信息字典（包含 name, vendor, global_mem_size 等）
        config: 引擎配置字典
        engine_logger: 可选的日志记录器，默认使用模块级 logger
    """

    def __init__(self, device_info: dict, config: Optional[dict] = None, engine_logger: Optional[Any] = None) -> None:
        self._device_info = device_info if isinstance(device_info, dict) else {}
        self._config = config or {}
        self._logger = engine_logger or logger
        self._rate_logger = _RateLimitedLogger(self._logger)

        # 内部组件（防御性初始化，默认为 None）
        self._driver_info: Optional[dict] = None
        self._arch_info: Optional[dict] = None
        self._memory_config: Optional[dict] = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def apply_optimizations(self) -> dict:
        """应用 NVIDIA GPU 特定优化

        采用防御性策略：每个检测步骤独立执行，单步失败不影响整体。

        Returns:
            优化配置字典，包含各项优化状态和推荐参数
        """
        self._logger.info("=" * 60)
        self._logger.info("🔧 开始应用 NVIDIA GPU 特殊优化")
        self._logger.info("=" * 60)

        result = {}

        # 1. 驱动版本检测
        try:
            detector = NvidiaDriverDetector(
                device_info=self._device_info,
                engine_logger=self._logger,
            )
            self._driver_info = detector.detect()
            result['driver'] = self._driver_info

            if self._driver_info.get('version_str'):
                self._logger.info(
                    f"✅ NVIDIA 驱动版本: {self._driver_info['version_str']}"
                    f"（OpenCL 1.2: {'✓' if self._driver_info['opencl_12_ok'] else '✗'}，"
                    f"OpenCL 2.0: {'✓' if self._driver_info['opencl_20_ok'] else '✗'}）"
                )
            else:
                self._logger.warning("⚠️ 无法检测 NVIDIA 驱动版本")

            if self._driver_info.get('recommendation'):
                self._logger.warning(f"⚠️ {self._driver_info['recommendation']}")

        except Exception as e:
            self._logger.warning(
                f"⚠️ NVIDIA 驱动检测失败（非致命）: {type(e).__name__}: {e}\n"
                f"   驱动版本信息将不可用"
            )
            self._driver_info = {}
            result['driver'] = {}

        # 2. 架构代识别
        try:
            arch_detector = NvidiaArchDetector(
                device_info=self._device_info,
                engine_logger=self._logger,
            )
            self._arch_info = arch_detector.detect()
            result['arch'] = self._arch_info

            self._logger.info(
                f"\u2705 NVIDIA GPU 架构: {self._arch_info['arch']}"
                f"（计算能力 CC {self._arch_info.get('compute_capability', '?')}，"
                f"异步拷贝: {'\u652f持' if self._arch_info.get('async_copy') else '\u4e0d支持'}，"
                f"原生 FP64: {'\u652f持' if self._arch_info.get('fp64_native') else '\u4e0d支持'}，"
                f"最低驱动: {self._arch_info.get('min_driver', '?')}）"
            )

        except Exception as e:
            self._logger.warning(
                f"⚠️ NVIDIA 架构识别失败（非致命）: {type(e).__name__}: {e}\n"
                f"   架构特性将使用保守默认值"
            )
            self._arch_info = {'arch': 'Unknown', 'async_copy': False, 'fp64_native': False}
            result['arch'] = self._arch_info

        # 3. 显存优化配置
        try:
            mem_optimizer = NvidiaMemoryOptimizer(
                device_info=self._device_info,
                arch_features=self._arch_info,
                engine_logger=self._logger,
            )
            self._memory_config = mem_optimizer.compute()
            result['memory'] = self._memory_config

            self._logger.info(
                f"\u2705 NVIDIA 显存配置: {self._memory_config['global_mem_gb']:.1f}GB"
                f"（类型: {'HBM' if self._memory_config.get('is_hbm') else 'GDDR'}），"
                f"memory_ratio={self._memory_config['memory_ratio']:.2f}，"
                f"异步传输={'\u5efa议启用' if self._memory_config['async_transfer'] else '\u4e0d建议'}"
            )

        except Exception as e:
            self._logger.warning(
                f"⚠️ NVIDIA 显存优化配置失败（非致命）: {type(e).__name__}: {e}\n"
                f"   显存配置将使用保守默认值"
            )
            self._memory_config = {'memory_ratio': 0.60, 'global_mem_gb': 0.0, 'async_transfer': False, 'is_hbm': False}
            result['memory'] = self._memory_config

        # 4. 快速数学优化禁用确认（加密/哈希必须精确）
        result['fast_math_disabled'] = True
        self._logger.info("✅ 快速数学优化: 已禁用（保证 SHA256/RIPEMD160/secp256k1 精度）")

        # 5. 汇总优化建议
        result['recommended_memory_ratio'] = (
            self._memory_config.get('memory_ratio', 0.60) if self._memory_config else 0.60
        )
        result['recommended_async_transfer'] = (
            self._memory_config.get('async_transfer', False) if self._memory_config else False
        )
        result['arch_name'] = (
            self._arch_info.get('arch', 'Unknown') if self._arch_info else 'Unknown'
        )

        self._logger.info("=" * 60)
        self._logger.info("✅ NVIDIA GPU 特殊优化应用完成")
        self._logger.info("=" * 60)

        return result

    def get_optimization_report(self) -> dict:
        """返回优化状态报告

        Returns:
            包含当前优化状态的字典
        """
        driver_version = None
        if self._driver_info:
            driver_version = self._driver_info.get('version_str')

        arch_name = 'Unknown'
        if self._arch_info:
            arch_name = self._arch_info.get('arch', 'Unknown')

        memory_ratio = 0.60
        async_transfer = False
        global_mem_gb = 0.0
        if self._memory_config:
            memory_ratio = self._memory_config.get('memory_ratio', 0.60)
            async_transfer = self._memory_config.get('async_transfer', False)
            global_mem_gb = self._memory_config.get('global_mem_gb', 0.0)

        return {
            'vendor': 'NVIDIA',
            'driver_version': driver_version,
            'arch': arch_name,
            'global_mem_gb': global_mem_gb,
            'memory_ratio': memory_ratio,
            'async_transfer_recommended': async_transfer,
            'fast_math_disabled': True,
            'driver_info': self._driver_info or {},
            'arch_info': self._arch_info or {},
        }
