#!/usr/bin/env python3
import sys

sys.path.insert(0, ".")

from src.gpu.auto_config import GPUAutoConfigurator  # noqa: E402

ac = GPUAutoConfigurator()
ac.clear_cache()

device = {
    "global_mem_size": 15933 * 1024 * 1024,
    "global_mem_gb": 15.56,
    "vendor": "intel",
    "name": "Intel(R) Arc(TM) A770 Graphics",
}

config = ac.configure_for_device(device)
print(f"batch_size: {config['batch_size']:,}")
print(f"memory_usage_ratio: {config['memory_usage_ratio']}")
