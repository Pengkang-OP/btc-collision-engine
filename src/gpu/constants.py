"""GPU引擎全局常量定义.

统一管理GPU模块中的硬编码参数，避免重复定义，提升可维护性.
"""

# ===== 内存相关常量 =====
PER_KEY_MEMORY_BYTES = 36  # 每密钥GPU内存占用（32字节私钥 + 4字节匹配标志）
BYTES_PER_MB = 1024 * 1024  # 1 MiB

# ===== 批次大小相关常量 =====
BATCH_SIZE_ALIGNMENT = 1024  # 批次大小对齐值
MIN_BATCH_SIZE = 1024  # 最小批次大小
MAX_BATCH_SIZE = 16777216  # 最大批次大小 (16M，与配置层保持一致)
DEFAULT_BATCH_SIZE = 262144  # 默认批次大小 (256K)

# ===== 显存效率相关常量 =====
MEMORY_EFFICIENCY_MIN = 0.1  # 最低显存使用效率
MEMORY_EFFICIENCY_MAX = 0.9  # 最高显存使用效率
DEFAULT_MEMORY_EFFICIENCY = 0.6  # 默认显存使用效率

# ===== OpenCL 版本兼容相关常量 (COMP-2) =====
OPENCL_MIN_REQUIRED_VERSION = 1.2  # 最低要求 OpenCL 版本
OPENCL_RECOMMENDED_VERSION = 2.0  # 推荐的最低版本
OPENCL_OPTIMAL_VERSION = 3.0  # 最佳版本（支持所有高级特性）
OPENCL_VERSION_UNKNOWN = 0.0  # 无法获取版本时的默认值

# OpenCL 版本对应的编译 CL 标准字符串
OPENCL_CL_STANDARDS: dict[str, str] = {
    "1.2": "CL1.2",
    "2.0": "CL2.0",
    "3.0": "CL2.0",  # CL3.0 兼容 CL2.0 标准
}

# OpenCL 版本升级建议（按厂商分类）
OPENCL_UPGRADE_ADVICE: dict[str, dict[str, str]] = {
    "nvidia": {
        "description": "NVIDIA GPU",
        "advice": (
            "请从 NVIDIA 官网下载最新 Game Ready 或 Studio 驱动:\n"
            "  https://www.nvidia.com/download/\n"
            "当前驱动可能过旧，无法提供足够的 OpenCL 支持。"
        ),
    },
    "amd": {
        "description": "AMD GPU",
        "advice": (
            "请从 AMD 官网下载最新 Adrenalin 驱动:\n"
            "  https://www.amd.com/support\n"
            "建议安装 ROCm 或 AMD APP SDK 以获得完整 OpenCL 支持。"
        ),
    },
    "intel": {
        "description": "Intel GPU",
        "advice": (
            "请从 Intel 官网下载最新 GPU 驱动:\n"
            "  https://www.intel.com/content/www/us/en/download/\n"
            "对于 Arc 系列 GPU，建议使用驱动版本 31.0.101.4500+。\n"
            "对于核显 (HD/UHD Graphics)，OpenCL 支持有限，建议使用独立 GPU。"
        ),
    },
    "unknown": {
        "description": "未知厂商 GPU",
        "advice": ("请访问 GPU 制造商官网下载最新驱动。\n确保驱动包含 OpenCL 运行时支持。"),
    },
}


def align_batch_size(batch_size: int, alignment: int = BATCH_SIZE_ALIGNMENT) -> int:
    """将批次大小向下对齐到指定值的倍数.

    Args:
        batch_size: 原始批次大小
        alignment: 对齐值（默认1024）

    Returns:
        对齐后的批次大小，最小为 MIN_BATCH_SIZE

    """
    aligned = (batch_size // alignment) * alignment
    return max(aligned, MIN_BATCH_SIZE)


def clamp_batch_size(batch_size: int) -> int:
    """将批次大小限制在有效范围内.

    Args:
        batch_size: 原始批次大小

    Returns:
        限制在 [MIN_BATCH_SIZE, MAX_BATCH_SIZE] 范围内的值

    """
    return max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
