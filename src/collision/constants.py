#!/usr/bin/env python3
"""
Collision detection constants and configuration defaults.
"""

# Search mode constants
RANDOM_SEARCH = "random"
SEQUENTIAL_SEARCH = "sequential"
HYBRID_SEARCH = "hybrid"

# Address type constants
P2PKH = "p2pkh"
P2SH = "p2sh"
BECH32 = "bech32"
TAPROOT = "taproot"

# Default configuration
DEFAULT_BATCH_SIZE = 100000
DEFAULT_MAX_WORKERS = 4
DEFAULT_CHECKPOINT_INTERVAL = 60
MATCH_BATCH_FLUSH_THRESHOLD = 10

# Performance targets
TARGET_THROUGHPUT_KEYS_PER_SEC = 1000
MIN_THROUGHPUT_WARNING = 100

# Timeouts
WORKER_JOIN_TIMEOUT = 30
GPU_KERNEL_TIMEOUT = 300
