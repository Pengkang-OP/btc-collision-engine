# -*- coding: utf-8 -*-
"""
BTC碰撞引擎性能优化基准测试
验证所有优化模块的性能提升效果
"""
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.precomputed_table import get_precomputed_table
from src.core.bigint_optimizer import get_bigint_optimizer
from src.core.simd_hash import get_simd_hash_optimizer
from src.core.memory_pool import get_pool_manager
from src.core.secp256k1 import Secp256k1, ECPoint
import hashlib


def benchmark_precomputed_table(iterations=100):
    """基准测试: 预计算点表性能"""
    print("\n" + "="*80)
    print("基准测试1: 预计算点表优化")
    print("="*80)
    
    table = get_precomputed_table(window_size=8)
    ec = table.ec
    G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
    
    k = 12345678901234567890123456789012345678
    
    # 测试预计算表方法
    start = time.perf_counter()
    for _ in range(iterations):
        _ = table.scalar_multiply_with_table(k)
    elapsed_table = time.perf_counter() - start
    
    # 测试标准方法
    start = time.perf_counter()
    for _ in range(iterations):
        _ = ec.scalar_multiply(k, G)
    elapsed_standard = time.perf_counter() - start
    
    speedup = elapsed_standard / elapsed_table
    
    print(f"  迭代次数: {iterations}")
    print(f"  预计算表: {elapsed_table:.4f}s ({elapsed_table/iterations*1000:.4f}ms/次)")
    print(f"  标准方法: {elapsed_standard:.4f}s ({elapsed_standard/iterations*1000:.4f}ms/次)")
    print(f"  性能提升: {speedup:.2f}x")
    print(f"  内存占用: {table.get_memory_usage()/1024:.1f}KB")
    
    return speedup


def benchmark_bigint_optimizer(iterations=10000):
    """基准测试: 大整数优化性能"""
    print("\n" + "="*80)
    print("基准测试2: 大整数优化")
    print("="*80)
    
    optimizer = get_bigint_optimizer()
    
    a = 12345678901234567890123456789012345678
    b = 98765432109876543210987654321098765432
    m = Secp256k1.P
    
    # 模乘法
    start = time.perf_counter()
    for _ in range(iterations):
        _ = optimizer.mod_mul(a, b, m)
    elapsed_opt = time.perf_counter() - start
    
    # 纯Python对比
    start = time.perf_counter()
    for _ in range(iterations):
        _ = (a * b) % m
    elapsed_python = time.perf_counter() - start
    
    speedup = elapsed_python / elapsed_opt
    
    print(f"  后端: {optimizer.get_backend_name()}")
    print(f"  迭代次数: {iterations}")
    print(f"  优化版本: {elapsed_opt:.4f}s")
    print(f"  纯Python: {elapsed_python:.4f}s")
    print(f"  性能提升: {speedup:.2f}x", flush=True)
    
    return speedup


def benchmark_simd_hash(iterations=10000):
    """基准测试: SIMD哈希性能"""
    print("\n" + "="*80)
    print("基准测试3: SIMD哈希优化")
    print("="*80)
    
    optimizer = get_simd_hash_optimizer()
    
    # 准备测试数据
    data_list = [f'data{i}'.encode() * 100 for i in range(iterations)]
    
    # pycryptodome
    start = time.perf_counter()
    results_crypto = optimizer.batch_sha256(data_list)
    elapsed_crypto = time.perf_counter() - start
    
    # hashlib
    start = time.perf_counter()
    results_hashlib = [hashlib.sha256(data).digest() for data in data_list]
    elapsed_hashlib = time.perf_counter() - start
    
    # 验证结果一致性
    assert results_crypto == results_hashlib, "结果不一致!"
    
    speedup = elapsed_hashlib / elapsed_crypto
    
    print(f"  后端: {optimizer.get_backend_name()}")
    print(f"  数据量: {len(data_list)}条")
    print(f"  pycryptodome: {elapsed_crypto:.4f}s")
    print(f"  hashlib: {elapsed_hashlib:.4f}s")
    print(f"  性能提升: {speedup:.2f}x", flush=True)
    
    return speedup


def benchmark_memory_pool(iterations=1000):
    """基准测试: 内存池性能"""
    print("\n" + "="*80)
    print("基准测试4: 内存池优化")
    print("="*80)
    
    from src.core.secp256k1 import Secp256k1
    
    # 使用内存池
    pool_mgr = get_pool_manager()
    pool_mgr.initialize()
    ec_pool = pool_mgr.get_ecpoint_pool()
    
    # 不使用内存池(直接创建)
    start = time.perf_counter()
    for _ in range(iterations):
        point = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        point.x = None
        point.y = None
    elapsed_direct = time.perf_counter() - start
    
    # 使用内存池
    start = time.perf_counter()
    for _ in range(iterations):
        point = ec_pool.acquire(x=Secp256k1.Gx, y=Secp256k1.Gy)
        ec_pool.release(point)
    elapsed_pool = time.perf_counter() - start
    
    speedup = elapsed_direct / elapsed_pool
    
    print(f"  迭代次数: {iterations}")
    print(f"  直接创建: {elapsed_direct:.4f}s")
    print(f"  内存池: {elapsed_pool:.4f}s")
    print(f"  性能提升: {speedup:.2f}x", flush=True)
    
    stats = ec_pool.get_stats()
    print(f"  池统计: 创建={stats['created_count']}, 获取={stats['acquire_count']}, 归还={stats['release_count']}")
    
    return speedup


def benchmark_batch_hash160(iterations=10000):
    """基准测试: 批量Hash160性能"""
    print("\n" + "="*80)
    print("基准测试5: 批量Hash160优化")
    print("="*80)
    
    optimizer = get_simd_hash_optimizer()
    
    # 模拟压缩公钥(33字节)
    pubkeys = [bytes([0x02 + i % 2]) + bytes([i % 256] * 32) for i in range(iterations)]
    
    # 批量处理
    start = time.perf_counter()
    addresses_batch = optimizer.batch_hash160(pubkeys)
    elapsed_batch = time.perf_counter() - start
    
    # 逐个处理
    start = time.perf_counter()
    addresses_single = []
    for pubkey in pubkeys:
        sha256 = hashlib.sha256(pubkey).digest()
        ripemd160 = hashlib.new('ripemd160', sha256).digest()
        addresses_single.append(ripemd160)
    elapsed_single = time.perf_counter() - start
    
    # 验证结果
    assert addresses_batch == addresses_single
    
    speedup = elapsed_single / elapsed_batch
    
    print(f"  公钥数量: {len(pubkeys)}")
    print(f"  批量处理: {elapsed_batch:.4f}s")
    print(f"  逐个处理: {elapsed_single:.4f}s")
    print(f"  性能提升: {speedup:.2f}x", flush=True)
    
    return speedup


def main():
    """运行所有基准测试"""
    import sys
    import io
    
    # 修复Windows终端编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "="*80)
    print("BTC碰撞引擎性能优化基准测试套件")
    print("="*80)
    print(f"Python版本: {sys.version}")
    print(f"平台: {sys.platform}")
    
    results = {}
    
    try:
        results['precomputed_table'] = benchmark_precomputed_table(100)
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        results['precomputed_table'] = 0
    
    try:
        results['bigint_optimizer'] = benchmark_bigint_optimizer(10000)
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        results['bigint_optimizer'] = 0
    
    try:
        results['simd_hash'] = benchmark_simd_hash(10000)
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        results['simd_hash'] = 0
    
    try:
        results['memory_pool'] = benchmark_memory_pool(1000)
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        results['memory_pool'] = 0
    
    try:
        results['batch_hash160'] = benchmark_batch_hash160(10000)
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        results['batch_hash160'] = 0
    
    # 汇总结果
    print("\n" + "="*80)
    print("📊 性能优化汇总")
    print("="*80)
    
    test_names = {
        'precomputed_table': '预计算点表',
        'bigint_optimizer': '大整数优化',
        'simd_hash': 'SIMD哈希',
        'memory_pool': '内存池',
        'batch_hash160': '批量Hash160'
    }
    
    total_speedup = 0
    count = 0
    
    for key, name in test_names.items():
        speedup = results[key]
        if speedup > 0:
            print(f"  {name:15s}: {speedup:.2f}x")
            total_speedup += speedup
            count += 1
        else:
            print(f"  {name:15s}: 跳过")
    
    if count > 0:
        avg_speedup = total_speedup / count
        print(f"\n  平均性能提升: {avg_speedup:.2f}x")
    
    print("\n" + "="*80)
    print("基准测试完成!")
    print("="*80)


if __name__ == '__main__':
    main()
