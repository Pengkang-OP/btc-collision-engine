"""Project-wide constants — single source of truth.

Merged from:
- src/cli/constants.py
- src/collision/constants.py
- src/collision/_engine_constants.py
- src/gpu/constants.py

All original modules now re-export from here for backward compatibility.
"""

# ============================================================================
# CLI constants (from src/cli/constants.py)
# ============================================================================

# Exit codes
EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1
EXIT_INVALID_CONFIG: int = 2
EXIT_GPU_ERROR: int = 3

# Output formatting
PROGRESS_BAR_WIDTH: int = 40
DEFAULT_PAGE_SIZE: int = 20

# Config file paths
CONFIG_FILE_NAME: str = "config.json"
CONFIG_EXAMPLE_FILE: str = "config.example.json"
WIZARD_MARKER_PATH: str = ".wizard_completed"

# Required config sections
REQUIRED_CONFIG_SECTIONS: list[str] = [
    "collision",
    "engine",
    "logging",
    "monitoring",
    "gpu",
    "crypto",
    "security",
]

# Separator lines for CLI output
SEPARATOR_EQUAL: str = "=" * 64
SEPARATOR_DASHED: str = "-" * 64
SEPARATOR_DASHED_SHORT: str = "-" * 40


# ============================================================================
# Collision constants (from src/collision/constants.py)
# ============================================================================

# Search mode constants
RANDOM_SEARCH: str = "random"
SEQUENTIAL_SEARCH: str = "sequential"
HYBRID_SEARCH: str = "hybrid"

# Address type constants
P2PKH: str = "p2pkh"
P2SH: str = "p2sh"
BECH32: str = "bech32"
TAPROOT: str = "taproot"

# Default configuration (collision domain)
COLLISION_DEFAULT_BATCH_SIZE: int = 100000
COLLISION_DEFAULT_MAX_WORKERS: int = 4
DEFAULT_CHECKPOINT_INTERVAL: int = 60
MATCH_BATCH_FLUSH_THRESHOLD: int = 10

# Performance targets
TARGET_THROUGHPUT_KEYS_PER_SEC: int = 1000
MIN_THROUGHPUT_WARNING: int = 100

# Timeouts
WORKER_JOIN_TIMEOUT: int = 30
GPU_KERNEL_TIMEOUT: int = 300


# ============================================================================
# Engine constants (from src/collision/_engine_constants.py)
# ============================================================================

# 每批处理的私钥数量
BATCH_SIZE: int = 1000

# 进度回调最小间隔（秒）
PROGRESS_INTERVAL_SEC: float = 0.5

# 每N次检测触发一次进度回调
PROGRESS_INTERVAL_COUNT: int = 1000
PROGRESS_INTERVAL_COUNT_DEFAULT: int = PROGRESS_INTERVAL_COUNT

# 每N次记录保存一次数据日志
DATA_LOG_SAVE_FREQUENCY: int = 3

# 错误日志记录间隔（秒）
ERROR_LOG_INTERVAL_SEC: float = 5.0

# CPU使用率缓存更新间隔（秒）
CPU_CACHE_INTERVAL_SEC: float = 1.0

# P3-9: Batch自动调优参数
BATCH_TUNE_1_2_CORE: int = 500
BATCH_TUNE_4_CORE: int = 1000
BATCH_TUNE_8_CORE: int = 2000
BATCH_TUNE_16_CORE: int = 4000
BATCH_TUNE_32_CORE: int = 6000
BATCH_TUNE_64_PLUS_CORE: int = 8000

# 内存监控降级参数 (P1-6)
MEMORY_HIGH_THRESHOLD_MB: int = 2048
MEMORY_CRITICAL_THRESHOLD_MB: int = 3072
MEMORY_DOWNGRADE_COOLDOWN_SEC: float = 30.0

# 去重缓存参数
DEDUP_MAX_RECENT_SIZE: int = 10000
COMPRESSION_AUTO_THRESHOLD: int = 10000
COMPRESSION_FORCE_SINGLE_THRESHOLD: int = 50000


# ============================================================================
# GPU constants (from src/gpu/constants.py)
# ============================================================================

# 内存相关常量
PER_KEY_MEMORY_BYTES: int = 36
BYTES_PER_MB: int = 1024 * 1024

# 批次大小相关常量
BATCH_SIZE_ALIGNMENT: int = 1024
MIN_BATCH_SIZE: int = 1024
MAX_BATCH_SIZE: int = 16777216
GPU_DEFAULT_BATCH_SIZE: int = 262144

# 显存效率相关常量
MEMORY_EFFICIENCY_MIN: float = 0.1
MEMORY_EFFICIENCY_MAX: float = 0.9
DEFAULT_MEMORY_EFFICIENCY: float = 0.6

# OpenCL 版本兼容相关常量 (COMP-2)
OPENCL_MIN_REQUIRED_VERSION: float = 1.2
OPENCL_RECOMMENDED_VERSION: float = 2.0
OPENCL_OPTIMAL_VERSION: float = 3.0
OPENCL_VERSION_UNKNOWN: float = 0.0

# OpenCL 版本对应的编译 CL 标准字符串
OPENCL_CL_STANDARDS: dict[str, str] = {
    "1.2": "CL1.2",
    "2.0": "CL2.0",
    "3.0": "CL2.0",
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
