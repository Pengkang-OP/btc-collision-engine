"""GPU module constants and defaults."""

# Default batch sizes
DEFAULT_GPU_BATCH_SIZE = 1000000
DEFAULT_CPU_BATCH_SIZE = 100000

# Timeouts (seconds)
GPU_KERNEL_TIMEOUT = 300
GPU_DEVICE_TIMEOUT = 60

# Memory limits
GPU_MAX_MEMORY_USAGE = 0.8  # 80% of available GPU memory
GPU_MIN_MEMORY_FREE = 256 * 1024 * 1024  # 256MB

# Device management
MAX_GPU_DEVICES = 8
GPU_DEVICE_POLL_INTERVAL = 5.0
