#!/usr/bin/env python3
"""
性能基准测试 - 验证 pycryptodome 安装后的性能提升
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import secrets

print("=" * 80)
print("性能基准测试 - pycryptodome 性能验证")
print("=" * 80)

# 检查依赖
print("\n[1] 依赖库检查")
print("-" * 80)

libs = {
    "coincurve": "secp256k1曲线",
    "gmpy2": "大整数优化",
    "pycryptodome": "哈希优化",
}

for lib, purpose in libs.items():
    try:
        mod = __import__(lib)
        version = getattr(mod, "__version__", "已安装")
        print(f"  ✓ {lib:15s} - {version} ({purpose})")
    except ImportError:
        print(f"  ✗ {lib:15s} - 未安装 ({purpose})")

# 性能测试
print("\n[2] 性能基准测试")
print("-" * 80)

from src.core.multi_format_generator import MultiFormatAddressGenerator

gen = MultiFormatAddressGenerator()

# 测试不同规模
test_sizes = [100, 500, 1000]

for size in test_sizes:
    print(f"\n测试规模: {size} iterations")

    start = time.time()
    for _ in range(size):
        key = secrets.token_bytes(32)
        gen.generate_all_formats(key)
    elapsed = time.time() - start

    rate = size / elapsed
    print(f"  耗时: {elapsed:.3f}s")
    print(f"  速度: {rate:.1f} sets/s")

# 性能评估
print("\n[3] 性能评估")
print("-" * 80)

iterations = 1000
start = time.time()
for _ in range(iterations):
    key = secrets.token_bytes(32)
    gen.generate_all_formats(key)
elapsed = time.time() - start

rate = iterations / elapsed

print(f"基准测试 ({iterations} iterations):")
print(f"  总耗时: {elapsed:.3f}s")
print(f"  平均速度: {rate:.1f} sets/s")

if rate > 2000:
    performance = "优秀"
    rating = "★★★★★"
elif rate > 1500:
    performance = "良好"
    rating = "★★★★☆"
elif rate > 1000:
    performance = "中等"
    rating = "★★★☆☆"
else:
    performance = "一般"
    rating = "★★☆☆☆"

print(f"\n性能评价: {performance} {rating}")

print("\n[4] SIMD加速检查")
print("-" * 80)

try:
    from src.utils.sha256_simd import is_simd_available, get_sha256_implementation

    if is_simd_available():
        impl = get_sha256_implementation()
        print("  ✓ SIMD加速已启用")
        print(f"  实现: {impl}")
        print("  ✓ pycryptodome SIMD哈希优化已启用 (AES-NI加速)")
    else:
        print("  ⚠ SIMD加速未启用")
        print("  建议: 安装pycryptodome以启用AES-NI加速")
except Exception as e:
    print(f"  ⚠ 无法检查SIMD状态: {e}")

# 批量性能测试
print("\n[5] 批量处理性能")
print("-" * 80)

batch_sizes = [10, 50, 100]

for batch_size in batch_sizes:
    start = time.time()
    keys = [secrets.token_bytes(32) for _ in range(batch_size)]
    for key in keys:
        gen.generate_all_formats(key)
    elapsed = time.time() - start

    rate = batch_size / elapsed
    print(f"  批量{batch_size:3d}: {elapsed:.3f}s ({rate:.1f} sets/s)")

print("\n" + "=" * 80)
print("性能测试总结")
print("=" * 80)

# 根据实际检测结果输出（而非无条件打印成功）
pycryptodome_ok = False
simd_ok = False
try:
    __import__("pycryptodome")
    pycryptodome_ok = True
except ImportError:
    pass
try:
    from src.utils.sha256_simd import is_simd_available
    simd_ok = is_simd_available()
except Exception:
    pass

print(f"\n{'✓' if pycryptodome_ok else '✗'} pycryptodome {'已安装并启用' if pycryptodome_ok else '未安装'}")
print(f"{'✓' if simd_ok else '✗'} SIMD哈希优化{'已启用 (AES-NI加速)' if simd_ok else '未启用'}")
print(f"{'✓' if pycryptodome_ok or simd_ok else '✗'} 当前性能: {rate:.1f} sets/s ({performance})")

print("\n优化建议:")
print("  • 如果性能不足，可考虑:")
print("    1. 使用GPU加速")
print("    2. 批量生成多个私钥")
print("    3. 减少同时支持的格式数量")
print("    4. 使用更快的哈希库")

print("\n" + "=" * 80)
