#!/usr/bin/env python3
"""快速验证work_group_size优化是否生效"""

import sys
from pathlib import Path

from src.gpu.auto_config import GPUAutoConfigurator

# 创建模拟设备信息
mock_device = {
    "name": "Intel(R) Arc(TM) A770 Graphics",
    "global_mem_gb": 15.56,
    "max_compute_units": 512,
}

# 获取配置
auto_config = GPUAutoConfigurator()
config = auto_config.get_intel_config(mock_device)

print("=" * 70)
print("Intel Arc A770 配置验证")
print("=" * 70)
print(f"batch_size: {config['batch_size']:,}")
print(f"work_group_size: {config['work_group_size']}")
print(f"memory_usage_ratio: {config['memory_usage_ratio']}")
print(f"enable_async: {config['enable_async']}")
print(f"use_fast_math: {config['use_fast_math']}")
print("=" * 70)

# 验证
if config["work_group_size"] == 512:
    print("✅ work_group_size优化已生效 (256 → 512)")
else:
    print(f"❌ work_group_size未优化: {config['work_group_size']} (期望512)")

if config["batch_size"] == 262144:
    print("✅ batch_size配置正确 (262K)")
else:
    print(f"❌ batch_size错误: {config['batch_size']} (期望262144)")
