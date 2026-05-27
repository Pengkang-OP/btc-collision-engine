"""GPU设备检测和管理.

提供GPU设备自动检测、过滤、选择功能。
复用现有gpu_engine.py的逻辑并保持API兼容。
"""

import re
import threading
from typing import TYPE_CHECKING, Any, cast, final

# 统一日志获取
from ..utils import get_configured_logger

if TYPE_CHECKING:
    import pyopencl as cl

from ._availability import PYOPENCL_AVAILABLE
from .constants import (
    OPENCL_MIN_REQUIRED_VERSION,
    OPENCL_OPTIMAL_VERSION,
    OPENCL_RECOMMENDED_VERSION,
    OPENCL_UPGRADE_ADVICE,
    OPENCL_VERSION_UNKNOWN,
)
from .driver_manager import DriverManager
from .profiles.loader import GPUProfileLoader
from .scorer import get_gpu_scorer

if PYOPENCL_AVAILABLE:
    import pyopencl as cl  # noqa: F811
else:
    cl = None  # type: ignore[assignment]


def _assert_opencl_available() -> None:
    """运行时检查 pyopencl 是否可用，不可用时抛出明确的 ImportError.

    Raises:
        ImportError: 当 pyopencl 未安装时

    """
    if not PYOPENCL_AVAILABLE:
        raise ImportError(
            "pyopencl 未安装。GPU 加速功能不可用。\n"
            "请运行: pip install pyopencl\n"
            "或在配置中禁用 GPU 加速。",
        )


logger = get_configured_logger("GPUDevice")


def _parse_opencl_version(version_str: str) -> float:
    """解析 OpenCL 版本字符串为浮点数.

    支持格式:
      - "OpenCL 3.0 NEO"
      - "OpenCL C 2.0 NEO"
      - "OpenCL 2.1 AMD-APP (3276.6)"
      - "OpenCL 1.2 CUDA 12.1.128"

    Args:
        version_str: OpenCL 版本字符串

    Returns:
        版本号浮点数, 如 3.0, 2.1, 1.2; 解析失败返回 OPENCL_VERSION_UNKNOWN

    """
    if not version_str or version_str == "Unknown":
        return OPENCL_VERSION_UNKNOWN
    match = re.search(r"OpenCL\s*(?:C\s*)?(\d+\.\d+)", str(version_str))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return OPENCL_VERSION_UNKNOWN


def identify_vendor(device_name: str, vendor_str: str = "") -> str:
    """识别GPU厂商.

    Args:
        device_name: 设备名称
        vendor_str: 厂商标识字符串

    Returns:
        厂商标识: 'nvidia', 'amd', 'intel', 或 'unknown'

    """
    name_lower = device_name.lower()
    vendor_lower = vendor_str.lower()

    # NVIDIA
    if (
        "nvidia" in vendor_lower
        or "nvidia" in name_lower
        or "geforce" in name_lower
        or "rtx" in name_lower
        or "gtx" in name_lower
        or "titan" in name_lower
        or "tesla" in name_lower
        or "quadro" in name_lower
    ):
        return "nvidia"

    # AMD
    if (
        "amd" in vendor_lower
        or "amd" in name_lower
        or "radeon" in name_lower
        or "radeon" in vendor_lower
        or "vega" in name_lower
        or "navi" in name_lower
        or "instinct" in name_lower
    ):
        return "amd"

    # Intel
    if "intel" in vendor_lower or "intel" in name_lower or "iris" in name_lower or "arc" in name_lower:
        return "intel"

    # 未知
    return "unknown"


def _identify_nvidia_model(name_lower: str) -> str:
    """识别 NVIDIA GPU 型号."""
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


def _identify_amd_model(name_lower: str) -> str:
    """识别 AMD GPU 型号."""
    if "rx 7" in name_lower:
        return "rx7000"
    if "rx 6" in name_lower:
        return "rx6000"
    if "rx 5700" in name_lower or "rx 5600" in name_lower or "rx 5500" in name_lower:
        return "rx5000"
    if "rx 580" in name_lower or "rx 570" in name_lower or "rx 560" in name_lower:
        return "rx500"
    if "vega" in name_lower:
        return "vega"
    if "instinct" in name_lower:
        return "instinct"
    return "amd_other"


def _identify_intel_model(name_lower: str) -> str:
    """识别 Intel GPU 型号."""
    if "arc" in name_lower:
        return "arc"
    if "iris" in name_lower:
        return "iris"
    if "hd graphics" in name_lower:
        return "hd_graphics"
    if "uhd graphics" in name_lower:
        return "uhd_graphics"
    return "intel_other"


def identify_gpu_model(device_name: str, vendor: str) -> str:
    """识别GPU型号.

    Args:
        device_name: 设备名称
        vendor: 厂商名称

    Returns:
        GPU型号标识

    """
    name_lower = device_name.lower()
    vendor_lower = vendor.lower()

    _identifiers = {
        "nvidia": _identify_nvidia_model,
        "amd": _identify_amd_model,
        "intel": _identify_intel_model,
    }
    identifier = _identifiers.get(vendor_lower)
    if identifier is not None:
        return identifier(name_lower)
    return "unknown"


class GPUDeviceDetector:
    """GPU设备检测器."""

    # 线程安全锁，保护类级缓存
    _cache_lock: threading.Lock = threading.Lock()

    # 可用性检测缓存
    _availability_cache: bool | None = None
    _cache_timestamp: float = 0.0
    _cache_ttl: int = 30  # 缓存有效期30秒(从60秒缩短,提高响应性)

    # 设备信息缓存（避免重复检测）
    _devices_cache: list[dict[str, Any]] | None = None
    _devices_cache_timestamp: float = 0.0
    _devices_cache_ttl: int = 30  # 设备缓存TTL(明确配置)

    @staticmethod
    def is_gpu_available() -> bool:
        """检查GPU是否可用.

        使用缓存机制避免频繁检测，缓存有效期60秒。

        Returns:
            True如果GPU可用

        """
        import time

        # 检查缓存是否有效
        now = time.time()
        with GPUDeviceDetector._cache_lock:
            if (
                GPUDeviceDetector._availability_cache is not None
                and now - GPUDeviceDetector._cache_timestamp < GPUDeviceDetector._cache_ttl
            ):
                logger.debug(f"使用GPU可用性缓存: {GPUDeviceDetector._availability_cache}")
                return GPUDeviceDetector._availability_cache

        if not PYOPENCL_AVAILABLE:
            logger.debug("pyopencl不可用，GPU检测跳过")
            with GPUDeviceDetector._cache_lock:
                GPUDeviceDetector._availability_cache = False
                GPUDeviceDetector._cache_timestamp = now
            return False

        try:
            devices = GPUDeviceDetector.detect_devices()
            available = len(devices) > 0
            if available:
                logger.debug(f"GPU可用，检测到 {len(devices)} 个设备")
                # 缓存设备信息供get_gpu_health_status()使用
                with GPUDeviceDetector._cache_lock:
                    GPUDeviceDetector._devices_cache = devices
                    GPUDeviceDetector._devices_cache_timestamp = time.time()
            else:
                logger.debug("GPU不可用，未检测到设备")

            # 更新缓存
            with GPUDeviceDetector._cache_lock:
                GPUDeviceDetector._availability_cache = available
                GPUDeviceDetector._cache_timestamp = now

            return available
        except (ImportError, RuntimeError, OSError) as e:
            # 预期的设备检测异常
            logger.debug(f"GPU检测失败: {type(e).__name__}: {e}")
            with GPUDeviceDetector._cache_lock:
                GPUDeviceDetector._availability_cache = False
                GPUDeviceDetector._cache_timestamp = now
            return False
        except Exception as e:
            # 未知错误：记录警告日志
            logger.warning(f"GPU检测未知错误: {type(e).__name__}: {e}")
            with GPUDeviceDetector._cache_lock:
                GPUDeviceDetector._availability_cache = False
                GPUDeviceDetector._cache_timestamp = now
            return False

    @staticmethod
    def get_gpu_health_status() -> dict[str, Any]:
        """获取GPU健康状态信息.

        用于监控系统和运维诊断，提供详细的GPU状态信息。
        复用is_gpu_available()的缓存，避免重复检测。

        Returns:
            Dict: 包含GPU健康状态的字典，字段包括：
                - available (bool): GPU是否可用
                - device_count (int): 检测到的设备数量
                - devices (List[str]): 设备名称列表
                - status (str): 健康状态 ('healthy'/'unavailable'/'error')
                - error (str, optional): 错误信息（仅在status='error'时存在）

        """
        import time

        try:
            available = GPUDeviceDetector.is_gpu_available()

            if available:
                # 复用缓存的设备信息，避免重复检测
                now = time.time()
                if (
                    GPUDeviceDetector._devices_cache is not None
                    and now - GPUDeviceDetector._devices_cache_timestamp < GPUDeviceDetector._cache_ttl
                ):
                    # 使用缓存的设备信息
                    devices = GPUDeviceDetector._devices_cache
                else:
                    # 缓存失效，重新检测
                    devices = GPUDeviceDetector.detect_devices()
                    GPUDeviceDetector._devices_cache = devices
                    GPUDeviceDetector._devices_cache_timestamp = now

                device_names = [dev["name"] for dev in devices]

                return {
                    "available": True,
                    "device_count": len(devices),
                    "devices": device_names,
                    "status": "healthy",
                }
            return {
                "available": False,
                "device_count": 0,
                "devices": [],
                "status": "unavailable",
            }
        except Exception as e:
            logger.error(f"GPU健康检查失败: {type(e).__name__}: {e}")
            return {
                "available": False,
                "device_count": 0,
                "devices": [],
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
            }

    @staticmethod
    def clear_availability_cache() -> None:
        """清除GPU可用性缓存和设备信息缓存.

        在GPU状态可能发生变化时调用（如驱动更新、设备插拔），
        强制下次is_gpu_available()重新检测。
        """
        GPUDeviceDetector._availability_cache = None
        GPUDeviceDetector._cache_timestamp = 0.0
        GPUDeviceDetector._devices_cache = None
        GPUDeviceDetector._devices_cache_timestamp = 0.0
        logger.debug("GPU可用性缓存和设备信息缓存已清除")

    @staticmethod
    def detect_devices() -> list[dict[str, Any]]:
        """检测所有可用的GPU设备.

        过滤规则:
        1. 跳过CPU设备
        2. 跳过Intel HD/UHD/Iris核显
        3. 只保留GPU设备

        Returns:
            设备信息列表

        """
        if not PYOPENCL_AVAILABLE:
            logger.warning("pyopencl不可用,无法检测设备")
            return []

        devices = []
        try:
            platforms = cl.get_platforms()

            for platform in platforms:
                try:
                    platform_devices = platform.get_devices()

                    for device in platform_devices:
                        device_type = device.get_info(cl.device_info.TYPE)

                        # 过滤掉CPU设备
                        if device_type == cl.device_type.CPU:
                            cpu_name = device.get_info(cl.device_info.NAME)
                            logger.debug("跳过CPU设备: %s", cpu_name)
                            continue

                        # 只保留GPU设备
                        if device_type != cl.device_type.GPU:
                            continue

                        device_name = device.get_info(cl.device_info.NAME)
                        device_name_lower = cast("str", device_name).lower()

                        # 过滤掉核显/亮机显卡
                        if "intel" in device_name_lower and (
                            "hd graphics" in device_name_lower
                            or "uhd graphics" in device_name_lower
                            or "iris" in device_name_lower
                        ):
                            logger.debug("跳过核显设备: %s", device_name)
                            continue

                        # COMP-2: 查询 OpenCL 版本信息
                        try:
                            opencl_version_str = device.get_info(cl.device_info.VERSION)
                        except (RuntimeError, OSError):
                            opencl_version_str = "Unknown"
                        try:
                            opencl_c_version_str = device.get_info(cl.device_info.OPENCL_C_VERSION)
                        except (RuntimeError, OSError):
                            opencl_c_version_str = "Unknown"

                        # 构建设备信息字典
                        device_info = {
                            "name": device_name,
                            "vendor": device.get_info(cl.device_info.VENDOR),
                            "platform": platform.get_info(cl.platform_info.NAME),
                            "device": device,
                            "platform_obj": platform,
                            "global_mem_size": device.global_mem_size,
                            "max_compute_units": device.max_compute_units,
                            "max_work_group_size": device.max_work_group_size,
                            "type": "GPU",
                            "opencl_version": opencl_version_str,
                            "opencl_c_version": opencl_c_version_str,
                        }

                        devices.append(device_info)

                except Exception as e:
                    logger.warning("获取平台设备时出错: %s", e)

        except Exception as e:
            logger.error("检测OpenCL设备失败: %s", e)

        logger.info(f"检测到 {len(devices)} 个GPU设备")
        return devices

    @staticmethod
    def select_best_device(devices: list[dict[str, Any]]) -> dict[str, Any]:
        """选择最佳GPU设备.

        v5.2.4: 由私有方法 `_select_best_device` 更名为公开方法，
        以消除基于类型检查器对保护成员跨类访问的警告。
        使用统一的 GPUDeviceScorer 进行评分和选择。
        优先级: NVIDIA > AMD > Intel Arc > Intel其他 > 其他GPU

        Args:
            devices: 设备列表

        Returns:
            最佳设备信息

        """
        if not devices:
            raise RuntimeError("没有可用的GPU设备")

        scorer = get_gpu_scorer()

        # 为每个设备计算评分
        for dev in devices:
            # 构建评分器所需的设备信息
            device_name = dev.get("name", "")
            vendor_str = dev.get("vendor", "")
            vendor = identify_vendor(device_name, vendor_str)

            score_info = {
                "name": device_name,
                "vendor": vendor,
                "model": scorer.identify_model(device_name, vendor),
                "global_mem_gb": dev.get("global_mem_size", 0) / (1024**3),
                "max_compute_units": dev.get("max_compute_units", 0),
            }

            dev["_score"] = scorer.score(score_info)

        # 按分数排序
        devices.sort(key=lambda d: d.get("_score", 0), reverse=True)
        best_device = devices[0]

        # 记录选择原因
        logger.info(
            f"自动选择最佳设备: {best_device['name']}\n"
            f"  - 显存: {best_device.get('global_mem_size', 0) / (1024**3):.1f} GB\n"
            f"  - 计算单元: {best_device.get('max_compute_units', 'N/A')}\n"
            f"  - 统一评分: {best_device.get('_score', 0):.1f}",
        )

        return best_device


@final
class GPUDevice:
    """GPU设备封装类.

    v5.2.4: 添加 ``@final`` 装饰器，消除基于 pyright
    ``reportUnannotatedClassAttribute`` 对 ``__slots__`` 类未注解属性的警告。
    保持与现有 gpu_engine.py 和 gpu_collision_engine.py 的 API 完全兼容。
    """

    __slots__: tuple[str, ...] = (
        "_opencl_version",
        "_opencl_version_str",
        "_supports_svm",
        "compute_queue",
        "context",
        "device",
        "device_info",
        "driver_health",
        "driver_optimization_flags",
        "driver_version",
        "enable_async_execution",
        "memory_efficiency",
        "profile",
        "profile_loader",
        "queue",
        "requires_uint32_workaround",
        "timeout_seconds",
        "transfer_queue",
        "vendor",
    )

    def __init__(self) -> None:
        """初始化GPU设备对象."""
        _assert_opencl_available()
        self.context = None
        self.queue = None  # 向后兼容: 默认队列
        self.compute_queue = None  # 计算队列(异步优化)
        self.transfer_queue = None  # 传输队列(异步优化)
        self.device = None
        self.device_info: dict[str, Any] = {}
        self.vendor = None
        self.profile: dict[str, Any] | None = None
        self.profile_loader = GPUProfileLoader()

        # 驱动相关
        self.driver_version = None
        self.driver_health = None
        self.driver_optimization_flags: dict[str, Any] = {}

        # 异步优化配置
        # PERF-2修复: 默认启用异步执行，提高GPU利用率
        self.enable_async_execution = True  # 是否启用异步执行（默认True）

        # COMP-2: OpenCL 版本兼容性
        self._opencl_version = OPENCL_VERSION_UNKNOWN
        self._opencl_version_str = "Unknown"
        self._supports_svm = False

        # Intel uint32 workaround标志
        # v4.2.1新增: 用于标记Intel Arc GPU需要特殊处理(避免global char* hang bug)
        self.requires_uint32_workaround = False

        # Intel超时保护配置
        # v4.2.1新增: 用于设置GPU操作的超时时间,防止内核hang
        self.timeout_seconds = 30  # 默认30秒超时

        # Intel显存效率配置
        # v4.3.0新增: 用于控制GPU显存使用率
        self.memory_efficiency = 0.70  # 默认70%

    def initialize(self, device_index: int = -1, enable_async: bool = True) -> None:
        """初始化GPU设备.

        Args:
            device_index: 设备索引
                         -1 = 自动选择最佳设备
                         >=0 = 使用指定索引的设备
            enable_async: 是否启用异步执行(双队列), 默认True开启双缓冲优化

        """
        # 设置异步标志
        self.enable_async_execution = enable_async
        if not PYOPENCL_AVAILABLE:
            raise RuntimeError("pyopencl不可用")

        # 检测所有设备
        devices = GPUDeviceDetector.detect_devices()
        if not devices:
            raise RuntimeError("未找到OpenCL设备")

        # 选择设备
        if device_index == -1:
            # 自动选择最佳设备
            device_info = GPUDeviceDetector.select_best_device(devices)
            logger.info(f"自动选择最佳GPU设备: {device_info['name']}")

        elif device_index >= 0:
            # 使用指定设备,严格模式(不静默回退)
            if device_index >= len(devices):
                # 抛出异常,提供可用设备列表
                available = [
                    f"  [{i}] {d['name']} ({d.get('global_mem_size', 0) / (1024**3):.1f}GB)"
                    for i, d in enumerate(devices)
                ]
                raise ValueError(
                    f"设备索引 {device_index} 超出范围 (0-{len(devices) - 1})\n可用设备:\n"
                    + "\n".join(available),
                )
            device_info = devices[device_index]
            logger.info(f"使用指定GPU设备 [{device_index}]: {device_info['name']}")

        else:
            # 其他负数索引,视为无效
            raise ValueError(
                f"无效的设备索引 {device_index}\n有效值: -1(自动选择) 或 0-{len(devices) - 1}(指定设备)",
            )

        # 保存设备对象
        self.device = device_info["device"]
        self.vendor = device_info.get("vendor", "Unknown")

        # COMP-2: 检测OpenCL版本并提供兼容性建议
        opencl_version_str = device_info.get("opencl_version", "Unknown")
        opencl_c_version_str = device_info.get("opencl_c_version", "Unknown")
        self._opencl_version_str = opencl_version_str

        # 优先使用 OPENCL_C_VERSION (设备级), 回退到 VERSION (平台级)
        version_source = (
            opencl_c_version_str if opencl_c_version_str != "Unknown" else opencl_version_str
        )
        self._opencl_version = _parse_opencl_version(version_source)

        logger.info(
            f"COMP-2: OpenCL 版本检测 — 平台: {opencl_version_str}, "
            f"设备: {opencl_c_version_str}, 解析: {self._opencl_version:.1f}",
        )

        # 按版本分级处理
        if self._opencl_version < OPENCL_MIN_REQUIRED_VERSION:
            # OpenCL < 1.2: 不兼容，给出明确提示但不崩溃
            vendor_for_advice = identify_vendor(device_info.get("name", ""), cast("str", self.vendor))
            upgrade_info = OPENCL_UPGRADE_ADVICE.get(
                vendor_for_advice,
                OPENCL_UPGRADE_ADVICE["unknown"],
            )
            logger.warning(
                f"COMP-2: OpenCL 版本不兼容 (当前: {self._opencl_version:.1f}, "
                f"最低要求: {OPENCL_MIN_REQUIRED_VERSION})\n"
                f"  当前版本: {self._opencl_version_str}\n"
                f"  最低要求: OpenCL {OPENCL_MIN_REQUIRED_VERSION}\n"
                f"  推荐版本: OpenCL {OPENCL_RECOMMENDED_VERSION}+\n"
                f"  升级建议 ({upgrade_info['description']}):\n"
                f"    {upgrade_info['advice']}",
            )
            self._supports_svm = False
        elif self._opencl_version < OPENCL_RECOMMENDED_VERSION:
            # OpenCL 1.2: 兼容但功能受限，使用标准 buffer 映射
            logger.info(
                f"COMP-2: OpenCL {self._opencl_version:.1f} — 兼容模式 (标准 buffer 映射)\n"
                f"  不支持 SVM 共享虚拟内存 (需 OpenCL {OPENCL_RECOMMENDED_VERSION}+)\n"
                f"  将使用标准 clCreateBuffer + clEnqueueMapBuffer 进行数据传输",
            )
            self._supports_svm = False
        elif self._opencl_version >= OPENCL_OPTIMAL_VERSION:
            # OpenCL 3.0+: 完全支持，可使用 SVM
            logger.info(
                f"COMP-2: OpenCL {self._opencl_version:.1f} — 完全兼容\n"
                f"  SVM 共享虚拟内存: [OK] 可用 (OpenCL 2.0+)\n"
                f"  Sub-groups (SIMD): [OK] 可用\n"
                f"  Generic Address Space: [OK] 可用\n"
                f"  Extended atomics: [OK] 可用",
            )
            self._supports_svm = True
        else:
            # OpenCL 2.0 - 2.x: 支持 SVM
            logger.info(
                f"COMP-2: OpenCL {self._opencl_version:.1f} — 完全兼容\n  SVM 共享虚拟内存: [OK] 可用",
            )
            self._supports_svm = True

        # 识别GPU型号
        vendor_identifier = identify_vendor(device_info.get("name", ""), cast("str", self.vendor))
        gpu_model = identify_gpu_model(device_info.get("name", ""), vendor_identifier)

        # 构建设备信息字典
        self.device_info = {
            "name": device_info.get("name", "Unknown"),
            "type": device_info.get("type", "GPU"),
            "vendor": self.vendor,
            "vendor_identifier": vendor_identifier,
            "model": gpu_model,
            "platform": device_info.get("platform", "Unknown"),
            "global_mem_size": device_info["device"].global_mem_size,
            "max_compute_units": device_info["device"].max_compute_units,
            "work_group_size": 256,  # v4.2.1优化: 默认值，会被auto_config覆盖
        }

        # 查询设备最大工作组大小
        try:
            max_wgs = device_info["device"].max_work_group_size
        except (AttributeError, Exception):
            max_wgs = 256  # 安全默认值
        self.device_info["max_work_group_size"] = max_wgs

        # 查询设备本地内存大小
        try:
            local_mem = device_info["device"].local_mem_size
        except (AttributeError, Exception):
            local_mem = 16384  # 16KB默认值
        self.device_info["local_mem_size"] = local_mem

        # 验证设备能力
        self._validate_device_capabilities(device_info)

        # 加载厂商配置
        self._load_vendor_profile(device_info["name"])

        # 检测和验证驱动
        self._detect_and_validate_driver()

        # 创建OpenCL上下文和命令队列
        self.context = cl.Context([self.device])

        # 异步优化: 创建命令队列
        if self.enable_async_execution:
            # ── v5.2.1: Intel Arc DG2 仅 1 个硬件 OOO 队列 ──────────────────
            # DG2 架构限制：单 Out-of-Order 队列（numQueues=1），无法并行化多队列。
            # 因此 Intel Arc 上 compute/transfer 共用同一队列，靠事件依赖保证顺序。
            #
            # ── v5.2.3 PERF-2 修复: Intel Arc profiling 导致的序列化 ─────────
            # Intel compute-runtime FAQ 确认：
            #   "Turning on profiling on out of order command queue serializes
            #    kernel execution."
            # 参考: https://github.com/intel/compute-runtime/blob/master/opencl/doc/FAQ.md
            #
            # 项目在创建 OOO 队列时默认附加了 PROFILING_ENABLE 标志（见下方 ooo_prop
            # 初始值），导致 Intel GPU 上所有内核被强制串行执行——表现为 GPU 利用率
            # 呈尖刺/齿轮状（每批次完成→等待→下一批次开始）。
            #
            # 修复: Intel Arc 路径移除 PROFILING_ENABLE，仅保留 OOO 模式。
            # 全项目无任何代码消费 profiling 数据（clGetEventProfilingInfo 零引用），
            # 此标志从未被实际使用，移除无功能影响。
            #
            # NVIDIA/AMD 不受此限制，保留 PROFILING_ENABLE + OOO 双队列模式。
            # ─────────────────────────────────────────────────────────────────
            vendor = identify_vendor(device_info.get("name", ""), cast("str", self.vendor))
            # 非 Intel 默认队列属性: profiling + OOO
            ooo_prop = (
                cl.command_queue_properties.PROFILING_ENABLE
                | cl.command_queue_properties.OUT_OF_ORDER_EXEC_MODE_ENABLE
            )
            if vendor == "intel":
                # Intel Arc: 移除 PROFILING_ENABLE，否则 OOO 队列被强制序列化（Intel 官方 FAQ 确认）
                # 参考: https://github.com/intel/compute-runtime/blob/master/opencl/doc/FAQ.md
                # "Turning on profiling on out of order command queue serializes kernel execution."
                ooo_prop = cl.command_queue_properties.OUT_OF_ORDER_EXEC_MODE_ENABLE
                logger.info(
                    "启用GPU异步执行: Intel Arc 单 Out-of-Order 队列（DG2 numQueues=1, profiling=OFF）",
                )
                self.queue = cl.CommandQueue(
                    self.context,
                    self.device,
                    properties=cast(cl.command_queue_properties, ooo_prop),
                )
                # Intel Arc: compute/transfer 共用同一 OOO 队列
                self.compute_queue = self.queue
                self.transfer_queue = self.queue
                logger.info("  - 单 OOO 队列: 已创建（内核+传输共用，事件依赖保证顺序）")
            else:
                logger.info("启用GPU异步执行: 创建双队列(计算+传输)")
                self.compute_queue = cl.CommandQueue(
                    self.context,
                    self.device,
                    properties=cast(cl.command_queue_properties, ooo_prop),
                )
                self.transfer_queue = cl.CommandQueue(
                    self.context,
                    self.device,
                    properties=cast(cl.command_queue_properties, ooo_prop),
                )
                self.queue = self.compute_queue
                logger.info("  - 计算队列: 已创建(支持性能分析)")
                logger.info("  - 传输队列: 已创建(支持异步传输)")
        else:
            # 传统模式: 单一队列
            self.queue = cl.CommandQueue(
                self.context,
                self.device,
            )
            logger.info("使用传统单队列模式(同步执行)")

        logger.debug(
            "GPU设备初始化成功: %s (%s) 显存=%.1fGB 计算单元=%d OpenCL=%s",
            self.device_info["name"],
            self.device_info["vendor"],
            self.device_info["global_mem_size"] / (1024**3),
            self.device_info["max_compute_units"],
            f"{self._opencl_version:.1f}",
        )

    def _validate_device_capabilities(self, device_info: dict[str, Any]) -> None:
        """验证设备能力是否满足最低要求.

        Args:
            device_info: 设备信息

        """
        min_compute_units = 2
        min_global_mem = 512 * 1024 * 1024  # 512MB

        compute_units = device_info["device"].max_compute_units
        global_mem = device_info["device"].global_mem_size

        # 检查计算单元
        if compute_units < min_compute_units:
            logger.warning(
                "设备计算单元过少: %s (建议 >= %s), 性能可能受限",
                compute_units,
                min_compute_units,
            )

        # 检查显存
        if global_mem < min_global_mem:
            logger.warning(
                f"设备显存过小: {global_mem / (1024**2):.0f} MB "
                f"(建议 >= {min_global_mem / (1024**2):.0f} MB), "
                "可能需要减小batch_size",
            )

        logger.debug(f"设备能力: 计算单元={compute_units}, 显存={global_mem / (1024**3):.2f} GB")

    def _load_vendor_profile(self, device_name: str) -> None:
        """加载厂商型号配置.

        Args:
            device_name: 设备名称

        """
        # 使用共享函数识别厂商
        vendor = identify_vendor(device_name, cast("str", self.vendor))

        # 加载配置
        self.profile = self.profile_loader.get_profile(vendor, device_name)

        if self.profile:
            logger.info(
                f"已加载GPU配置: {device_name} -> {vendor}, "
                f"recommended_batch_size={self.profile.get('recommended_batch_size', 'N/A')}",
            )
        else:
            logger.warning("未找到 %s 的配置,使用默认参数", device_name)

    def _detect_and_validate_driver(self) -> None:
        """检测驱动版本并验证健康状态."""
        # 1. 检测驱动版本
        self.driver_version = DriverManager.detect_driver_version(cast("str", self.vendor))

        if not self.driver_version:
            logger.warning("无法检测GPU驱动版本")
            return

        # 2. 检查驱动健康状态
        self.driver_health = DriverManager.check_driver_health(
            cast("str", self.vendor) if self.vendor else "",
            self.driver_version,
            self.profile,
        )

        # 3. 记录健康检查结果
        if self.driver_health["status"] == "critical":
            logger.error(f"GPU驱动健康检查失败: {self.driver_health['message']}")
            for rec in self.driver_health["recommendations"]:
                logger.error("  建议: %s", rec)
        elif self.driver_health["status"] == "warning":
            logger.warning(f"GPU驱动健康检查警告: {self.driver_health['message']}")
            for rec in self.driver_health["recommendations"]:
                logger.warning("  建议: %s", rec)
        else:
            logger.info(f"GPU驱动版本: {self.driver_version}, 状态: 正常")

        # 4. 获取驱动优化标志
        self.driver_optimization_flags = DriverManager.get_driver_optimization_flags(
            cast("str", self.vendor) if self.vendor else "",
            self.driver_version,
            self.profile,
        )

        logger.debug(f"驱动优化标志: {self.driver_optimization_flags}")

    def get_driver_info(self) -> dict[str, Any]:
        """获取驱动信息.

        Returns:
            驱动信息字典

        """
        return {
            "version": self.driver_version,
            "health": self.driver_health,
            "optimization_flags": self.driver_optimization_flags,
        }

    def get_device_info(self) -> dict[str, Any]:
        """获取设备信息.

        Returns:
            设备信息字典

        """
        return self.device_info.copy()

    @property
    def opencl_version(self) -> float:
        """获取解析后的 OpenCL 版本号 (如 1.2, 2.0, 3.0)."""
        return self._opencl_version

    @property
    def supports_svm(self) -> bool:
        """是否支持 SVM 共享虚拟内存 (OpenCL 2.0+)."""
        return self._supports_svm

    def cleanup(self) -> None:
        """释放GPU资源."""
        import time

        # 清理命令队列
        queues_to_cleanup: list[tuple[str, Any]] = []

        if self.compute_queue:
            queues_to_cleanup.append(("计算队列", self.compute_queue))
        if self.transfer_queue:
            queues_to_cleanup.append(("传输队列", self.transfer_queue))
        if self.queue and self.queue not in [self.compute_queue, self.transfer_queue]:
            queues_to_cleanup.append(("默认队列", self.queue))

        for name, q in queues_to_cleanup:
            try:
                start_time = time.time()
                q.finish()
                elapsed = time.time() - start_time
                logger.debug(f"{name}已完成所有命令 (耗时: {elapsed:.2f}秒)")
            except Exception as e:
                logger.warning("%s清理失败: %s", name, e)

        self.queue = None
        self.compute_queue = None
        self.transfer_queue = None

        # 清理上下文
        if self.context:
            try:
                # 确保所有命令完成（hasattr 已在运行时确认 finish 存在）
                if hasattr(self.context, "finish"):
                    start_time = time.time()
                    _ctx: Any = self.context
                    _ctx.finish()
                    elapsed = time.time() - start_time
                    logger.debug(f"GPU上下文已完成所有命令 (耗时: {elapsed:.2f}秒)")
            except Exception as e:
                logger.warning("GPU上下文完成失败: %s", e)
            finally:
                self.context = None

        # 显式清理设备引用
        self.device = None
        self.device_info = {}
        self.vendor = None
        self.profile = None

        logger.info("GPU资源已释放")
