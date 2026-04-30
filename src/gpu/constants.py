"""GPU引擎全局常量定义

统一管理GPU模块中的硬编码参数，避免重复定义，提升可维护性。
"""

# ===== 内存相关常量 =====
PER_KEY_MEMORY_BYTES = 36  # 每密钥GPU内存占用（32字节私钥 + 4字节匹配标志）
BYTES_PER_MB = 1024 * 1024  # 1 MiB

# ===== 批次大小相关常量 =====
BATCH_SIZE_ALIGNMENT = 1024  # 批次大小对齐值
MIN_BATCH_SIZE = 1024  # 最小批次大小
MAX_BATCH_SIZE = 4194304  # 最大批次大小 (4M)
DEFAULT_BATCH_SIZE = 262144  # 默认批次大小 (256K)

# ===== 显存效率相关常量 =====
MEMORY_EFFICIENCY_MIN = 0.1  # 最低显存使用效率
MEMORY_EFFICIENCY_MAX = 0.9  # 最高显存使用效率
DEFAULT_MEMORY_EFFICIENCY = 0.6  # 默认显存使用效率


def align_batch_size(batch_size: int, alignment: int = BATCH_SIZE_ALIGNMENT) -> int:
    """将批次大小向下对齐到指定值的倍数

    Args:
        batch_size: 原始批次大小
        alignment: 对齐值（默认1024）

    Returns:
        对齐后的批次大小，最小为 MIN_BATCH_SIZE
    """
    aligned = (batch_size // alignment) * alignment
    return max(aligned, MIN_BATCH_SIZE)


def clamp_batch_size(batch_size: int) -> int:
    """将批次大小限制在有效范围内

    Args:
        batch_size: 原始批次大小

    Returns:
        限制在 [MIN_BATCH_SIZE, MAX_BATCH_SIZE] 范围内的值
    """
    return max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
