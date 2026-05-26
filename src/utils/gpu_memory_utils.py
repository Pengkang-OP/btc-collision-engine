"""GPU内存优化相关的共享工具函数

提取GPU显存计算的公共逻辑，消除代码重复，遵循DRY原则。

默认值:
    - memory_usage_ratio: 0.5 (50%显存)
    - min_batch_size: 1024
    - max_batch_size: 8388608 (8M)
    - memory_alignment: 1024
    - per_key_memory: 36 (32+4)

性能考虑:
    - 延迟导入: 函数内导入避免循环依赖，每次调用有微小开销(<0.1ms)
    - 对于碰撞引擎，该函数只在初始化时调用一次，性能影响可忽略
"""

from dataclasses import dataclass
from typing import Any, Protocol

from .logging_config import get_configured_logger

logger = get_configured_logger(__name__)


@dataclass
class BatchSizeConfig:
    """batch_size计算配置

    用于封装calculate_optimal_batch_size的配置参数，简化函数签名。

    Attributes:
        memory_usage_ratio: 显存使用比例（0.0-1.0），默认0.5（50%）
        min_batch_size: 最小batch_size，默认1024
        max_batch_size: 最大batch_size，默认8388608 (8M)
        memory_alignment: 内存对齐字节数，默认1024
        per_key_memory: 每个私钥的内存占用（字节），默认36 (32+4)

    """

    memory_usage_ratio: float = 0.5
    min_batch_size: int = 1024
    max_batch_size: int = 8388608
    memory_alignment: int = 1024
    per_key_memory: int = 36

    def validate(self) -> None:
        """验证配置有效性

        Raises:
            ValueError: 当配置参数无效时

        """
        if not (0 < self.memory_usage_ratio <= 1.0):
            raise ValueError(f"memory_usage_ratio必须在(0, 1]范围内: {self.memory_usage_ratio}")

        if self.min_batch_size <= 0:
            raise ValueError(f"min_batch_size必须为正数: {self.min_batch_size}")

        if self.max_batch_size < self.min_batch_size:
            raise ValueError(
                f"max_batch_size({self.max_batch_size})必须>=min_batch_size({self.min_batch_size})",
            )

        if self.memory_alignment <= 0:
            raise ValueError(f"memory_alignment必须为正数: {self.memory_alignment}")

        if self.per_key_memory <= 0:
            raise ValueError(f"per_key_memory必须为正数: {self.per_key_memory}")

    def __post_init__(self) -> None:
        """初始化后自动验证配置

        在dataclass初始化完成后自动调用validate()，确保配置始终有效。
        """
        self.validate()


class GPUDeviceProtocol(Protocol):
    """GPU设备协议，定义calculate_optimal_batch_size所需的接口"""

    class DeviceObject(Protocol):
        """设备对象协议"""

        global_mem_size: int

    device: DeviceObject
    device_info: dict[str, Any]


# 模块级常量
MIN_GPU_MEMORY = 1 * 1024 * 1024  # 1MB
DEFAULT_BATCH_SIZE = 65536


def calculate_optimal_batch_size(
    device: GPUDeviceProtocol,
    target_buffer_size: int = 0,
    config: BatchSizeConfig | None = None,
    verbose: bool = True,
) -> int:
    """根据GPU显存大小计算最优batch_size

    Args:
        device: GPUDevice实例，包含device和device_info属性
        target_buffer_size: 目标地址缓冲区大小（字节），默认为0
        config: batch_size计算配置，默认使用BatchSizeConfig()的默认值
        verbose: 是否输出详细日志，默认True

    Returns:
        最优batch_size值

    Raises:
        ValueError: 当参数无效时

    计算逻辑:
        1. 验证参数有效性
        2. 获取GPU全局内存大小
        3. 验证显存有效性（至少1MB）
        4. 计算可用内存 = 总显存 * 使用比例 - 目标缓冲区
        5. 计算理论最大batch_size = 可用内存 / 每私钥内存
        6. 限制在[min_batch_size, max_batch_size]范围内
        7. 向下对齐到memory_alignment的倍数

    Example:
        >>> from src.utils.gpu_memory_utils import calculate_optimal_batch_size
        >>> # device = GPUDevice() # 已初始化的GPU设备
        >>> # device.initialize(0)
        >>> # batch_size = calculate_optimal_batch_size(device)
        >>> # print(batch_size)
        8388608

        >>> # 使用自定义配置
        >>> from src.utils.gpu_memory_utils import BatchSizeConfig
        >>> config = BatchSizeConfig(memory_usage_ratio=0.7, min_batch_size=2048)
        >>> batch_size = calculate_optimal_batch_size(device, config=config)

    """
    # 使用默认配置
    if config is None:
        config = BatchSizeConfig()

    # 验证配置
    config.validate()

    # 验证其他参数
    if target_buffer_size < 0:
        raise ValueError(f"target_buffer_size不能为负数: {target_buffer_size}")

    try:
        # 获取GPU全局内存大小（字节）
        global_mem = device.device.global_mem_size

        # 优先使用device_info中的缓存值
        if hasattr(device, "device_info") and "global_mem_size" in device.device_info:
            global_mem = device.device_info["global_mem_size"]

        # 检查显存有效性（至少1MB）
        if global_mem < MIN_GPU_MEMORY:
            if verbose:
                logger.warning(
                    "GPU显存过小: %.2f MB，使用最小batch_size: %d",
                    global_mem / (1024**2),
                    config.min_batch_size,
                )
            return config.min_batch_size

        # 计算可用内存 = 总显存 * 使用比例 - 目标缓冲区
        total_available = int(global_mem * config.memory_usage_ratio)
        available_mem = total_available - target_buffer_size

        # 如果可用内存不足，使用最小batch_size
        if available_mem <= 0:
            if verbose:
                logger.warning(
                    "GPU显存不足以分配缓冲区: 总显存=%.2fGB, 目标缓冲区=%.2fMB, 使用最小batch_size: %d",
                    global_mem / (1024**3),
                    target_buffer_size / (1024**2),
                    config.min_batch_size,
                )
            return config.min_batch_size

        # 计算理论最大batch_size（使用整数除法保持精度）
        theoretical_max = available_mem // config.per_key_memory

        # 限制范围
        optimal_batch = max(config.min_batch_size, min(config.max_batch_size, theoretical_max))

        # 向下取整到对齐字节数的倍数（内存对齐优化）
        optimal_batch = (optimal_batch // config.memory_alignment) * config.memory_alignment

        # 验证对齐正确性（仅在调试模式）
        if __debug__:
            assert optimal_batch % config.memory_alignment == 0, (
                f"batch_size未对齐: {optimal_batch} % {config.memory_alignment} != 0"
            )

        # 计算实际内存占用和比例
        total_buffer = optimal_batch * config.per_key_memory + target_buffer_size
        usage_percent = (total_buffer / global_mem) * 100

        if verbose:
            logger.info(
                "GPU显存优化: batch_size=%d, 占用=%.1fMB (%.1f%%)",
                optimal_batch,
                total_buffer / (1024**2),
                usage_percent,
            )

        return optimal_batch

    except AttributeError as e:
        logger.error("GPU设备对象结构错误: %s", str(e))
        return DEFAULT_BATCH_SIZE
    except (TypeError, ValueError) as e:
        logger.error("GPU显存值错误: %s", str(e))
        return DEFAULT_BATCH_SIZE
    except Exception as e:
        logger.warning("计算最优batch_size失败，使用默认值%d: %s", DEFAULT_BATCH_SIZE, str(e))
        return DEFAULT_BATCH_SIZE
