#!/usr/bin/env python3
"""
验证Intel Arc配置修复
确保batch_size不会被降级
"""

import sys

sys.path.insert(0, ".")

from src.gpu.auto_config import GPUAutoConfigurator  # noqa: E402

print("=" * 80)
print("  Intel Arc配置修复验证")
print("=" * 80)
print()

# 模拟Intel Arc A770设备
device = {
    "global_mem_size": 15933 * 1024 * 1024,  # 15.56 GB
    "global_mem_gb": 15.56,
    "vendor": "Intel(R) Corporation",
    "name": "Intel(R) Arc(TM) A770 Graphics",
}

# 测试Intel Arc默认配置
print("测试1: Intel Arc默认配置")
print("-" * 80)

ac = GPUAutoConfigurator()
config = ac.configure_for_device(device)

print(f"  设备: {device['name']}")
print(f"  显存: {device['global_mem_gb']} GB")
print(f"  batch_size: {config['batch_size']:,}")
print(f"  memory_usage_ratio: {config['memory_usage_ratio']}")
print(f"  use_fast_math: {config['use_fast_math']}")
print()

if config["batch_size"] == 262144:
    print("  ✅ batch_size正确: 262,144")
else:
    print(f"  ❌ batch_size错误: {config['batch_size']:,} (期望: 262,144)")

print()

# 测试显存调整逻辑
print("测试2: 显存调整逻辑")
print("-" * 80)

test_config = {"batch_size": 262144, "memory_usage_ratio": 0.70}

ac2 = GPUAutoConfigurator()
result = ac2._adjust_for_memory(device, test_config)

print("  请求batch_size: 262,144")
print(f"  调整后batch_size: {test_config['batch_size']:,}")

if test_config["batch_size"] == 262144:
    print("  ✅ 未被降级")
else:
    print(f"  ❌ 被降级到 {test_config['batch_size']:,}")

print()
print("=" * 80)

if config["batch_size"] == 262144 and test_config["batch_size"] == 262144:
    print("✅ 所有测试通过! Intel Arc配置修复成功")
else:
    print("❌ 测试失败，需要进一步检查")

print("=" * 80)
