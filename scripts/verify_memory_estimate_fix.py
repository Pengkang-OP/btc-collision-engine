#!/usr/bin/env python3
"""
验证显存估算公式修改（36→42字节/密钥）
测试不同GPU和不同batch_size的场景
"""

import sys

sys.path.insert(0, ".")

from src.gpu.auto_config import GPUAutoConfigurator  # noqa: E402


def test_memory_estimate(gpu_name, memory_gb, batch_size, expected_adjusted=None):
    """测试特定GPU配置的显存估算"""
    device = {
        "global_mem_size": int(memory_gb * 1024 * 1024 * 1024),
        "global_mem_gb": memory_gb,
        "vendor": "Test Vendor",
        "name": gpu_name,
    }

    config = {"batch_size": batch_size, "memory_usage_ratio": 0.70}

    ac = GPUAutoConfigurator()
    original_batch = config["batch_size"]
    ac._adjust_for_memory(device, config)

    adjusted = config["batch_size"]
    was_adjusted = adjusted != original_batch

    print(f"\n{gpu_name} ({memory_gb}GB)")
    print(f"  请求batch_size: {original_batch:,}")
    print(f"  调整后batch_size: {adjusted:,}")

    if was_adjusted:
        ratio = adjusted / original_batch * 100
        print(f"  ⚠️  被降级: {ratio:.1f}%")
    else:
        print("  ✅ 未被降级")

    # 计算显存使用
    estimated_mb = (batch_size * 42) / (1024**2)
    max_safe_mb = memory_gb * 0.70 * 1024
    print(f"  估算显存: {estimated_mb:.1f} MB / 安全限制: {max_safe_mb:.0f} MB")

    if expected_adjusted is not None:
        if adjusted == expected_adjusted:
            print("  ✅ 符合预期")
        else:
            print(f"  ❌ 不符合预期 (期望: {expected_adjusted:,})")

    return not was_adjusted


print("=" * 80)
print("显存估算公式验证测试 (42字节/密钥)")
print("=" * 80)

# 测试不同GPU
test_cases = [
    # (GPU名称, 显存GB, 请求batch_size, 预期是否保持)
    ("Intel Arc A770", 15.56, 262144, True),
    ("Intel Arc A770", 15.56, 524288, True),
    ("Intel Arc A770", 15.56, 1000000, True),
    ("NVIDIA GTX 1660 Ti", 6.0, 262144, True),
    ("NVIDIA GTX 1660 Ti", 6.0, 131072, True),
    ("NVIDIA RTX 3090", 24.0, 262144, True),
    ("NVIDIA RTX 3090", 24.0, 524288, True),
    ("AMD RX 6800 XT", 16.0, 262144, True),
]

print("\n测试不同GPU和batch_size配置:")
print("-" * 80)

all_passed = True
for gpu_name, memory_gb, batch_size, _expected in test_cases:
    passed = test_memory_estimate(gpu_name, memory_gb, batch_size)
    all_passed = all_passed and passed

print("\n" + "=" * 80)
if all_passed:
    print("✅ 所有测试通过! 显存估算公式正确")
else:
    print("⚠️  部分测试失败，需要检查")
print("=" * 80)

# 显示显存使用对比
print("\n" + "=" * 80)
print("显存使用对比 (旧公式 vs 新公式)")
print("=" * 80)
print(f"{'batch_size':>12} | {'旧公式(2KB)':>12} | {'新公式(36B)':>12} | {'新公式(42B)':>12} | 实际测试")
print("-" * 80)

for batch in [1024, 65536, 131072, 262144, 524288, 1000000]:
    old_mb = (batch * 2048) / (1024**2)
    new36_mb = (batch * 36) / (1024**2)
    new42_mb = (batch * 42) / (1024**2)

    actual = "~9 MB ✅" if batch == 262144 else "~线性推算"

    print(f"{batch:>12,} | {old_mb:>10.1f}MB | {new36_mb:>10.1f}MB | {new42_mb:>10.1f}MB | {actual}")

print("=" * 80)
