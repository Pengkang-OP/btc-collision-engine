"""优化模块集成示例
展示如何在碰撞引擎中使用新增的性能优化模块
"""

import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.address_generator import P2PKHAddressGenerator
from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator


def example_1_basic_usage():
    """示例1: 基本使用"""
    print("\n" + "=" * 80)
    print("示例1: 优化版地址生成器 - 基本使用")
    print("=" * 80)

    # 创建优化版生成器(默认启用所有优化)
    generator = OptimizedP2PKHAddressGenerator()

    # 生成单个地址
    import secrets

    private_key = secrets.token_bytes(32)

    start = time.perf_counter()
    address = generator.generate_from_private_key(private_key)
    elapsed = time.perf_counter() - start

    print(f"  私钥: {private_key.hex()[:16]}...")
    print(f"  地址: {address}")
    print(f"  耗时: {elapsed * 1000:.2f}ms")

    # 查看优化配置
    info = generator.get_optimization_info()
    print("\n  优化配置:")
    print(
        f"    预计算表: {info['precomputed_table']['enabled']}, window_size={info['precomputed_table']['window_size']}"
    )
    print(f"    SIMD哈希: {info['simd_hash']['enabled']}, backend={info['simd_hash']['backend']}")
    print(f"    内存池: {info['memory_pool']['enabled']}")


def example_2_batch_generation():
    """示例2: 批量生成"""
    print("\n" + "=" * 80)
    print("示例2: 批量地址生成 - 高性能模式")
    print("=" * 80)

    generator = OptimizedP2PKHAddressGenerator()

    # 生成100个私钥
    import secrets

    private_keys = [secrets.token_bytes(32) for _ in range(100)]

    # 批量生成
    start = time.perf_counter()
    addresses = generator.batch_generate(private_keys)
    elapsed = time.perf_counter() - start

    print(f"  生成数量: {len(addresses)}")
    print(f"  耗时: {elapsed:.4f}s")
    print(f"  速度: {len(addresses) / elapsed:.0f} 地址/秒")
    print(f"  示例地址: {addresses[0]}")


def example_3_comparison():
    """示例3: 性能对比"""
    print("\n" + "=" * 80)
    print("示例3: 优化版 vs 标准版 - 性能对比")
    print("=" * 80)

    import secrets

    # 准备测试数据
    num_keys = 50
    private_keys = [secrets.token_bytes(32) for _ in range(num_keys)]

    # 标准版
    std_generator = P2PKHAddressGenerator()
    start = time.perf_counter()
    for pk in private_keys:
        std_generator.generate_address(pk)
    elapsed_std = time.perf_counter() - start

    # 优化版
    opt_generator = OptimizedP2PKHAddressGenerator()
    start = time.perf_counter()
    for pk in private_keys:
        opt_generator.generate_from_private_key(pk)
    elapsed_opt = time.perf_counter() - start

    speedup = elapsed_std / elapsed_opt

    print(f"  测试数量: {num_keys}个地址")
    print(f"  标准版: {elapsed_std:.4f}s ({elapsed_std / num_keys * 1000:.2f}ms/个)")
    print(f"  优化版: {elapsed_opt:.4f}s ({elapsed_opt / num_keys * 1000:.2f}ms/个)")
    print(f"  性能提升: {speedup:.2f}x")


def example_4_custom_config():
    """示例4: 自定义配置"""
    print("\n" + "=" * 80)
    print("示例4: 自定义优化配置")
    print("=" * 80)

    # 只启用预计算表,禁用其他优化
    gen1 = OptimizedP2PKHAddressGenerator(
        use_precomputed_table=True, use_simd_hash=False, use_memory_pool=False, window_size=6
    )
    print("  配置1: 仅预计算表(w=6)")
    print(f"    {gen1.get_optimization_info()}")

    # 只启用SIMD哈希
    gen2 = OptimizedP2PKHAddressGenerator(
        use_precomputed_table=False, use_simd_hash=True, use_memory_pool=False
    )
    print("\n  配置2: 仅SIMD哈希")
    print(f"    {gen2.get_optimization_info()}")

    # 全部启用
    gen3 = OptimizedP2PKHAddressGenerator(
        use_precomputed_table=True, use_simd_hash=True, use_memory_pool=True, window_size=8
    )
    print("\n  配置3: 全部优化(w=8)")
    print(f"    {gen3.get_optimization_info()}")


def example_5_integration_with_engine():
    """示例5: 集成到碰撞引擎"""
    print("\n" + "=" * 80)
    print("示例5: 集成到碰撞引擎的伪代码示例")
    print("=" * 80)

    print("""
    # 在KeyCollisionEngine中使用优化版生成器
    
    from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator
    
    class OptimizedKeyCollisionEngine:
        def __init__(self, targets):
            self.targets = set(targets)
            # 使用优化版生成器替代标准版
            self.generator = OptimizedP2PKHAddressGenerator(
                use_precomputed_table=True,
                use_simd_hash=True,
                use_memory_pool=True,
                window_size=8
            )
        
        def check_private_key(self, private_key):
            # 生成地址(自动使用所有优化)
            address = self.generator.generate_from_private_key(private_key)
            
            # 检查碰撞
            if address in self.targets:
                return (private_key, address)
            return None
    
    # 使用示例
    engine = OptimizedKeyCollisionEngine(targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'])
    engine.check_private_key(secrets.token_bytes(32))
    """)


def main():
    """运行所有示例"""
    print("\n" + "=" * 80)
    print("BTC碰撞引擎 - 优化模块集成示例")
    print("=" * 80)

    try:
        example_1_basic_usage()
    except Exception as e:
        print(f"  示例1失败: {e}")

    try:
        example_2_batch_generation()
    except Exception as e:
        print(f"  示例2失败: {e}")

    try:
        example_3_comparison()
    except Exception as e:
        print(f"  示例3失败: {e}")

    try:
        example_4_custom_config()
    except Exception as e:
        print(f"  示例4失败: {e}")

    try:
        example_5_integration_with_engine()
    except Exception as e:
        print(f"  示例5失败: {e}")

    print("\n" + "=" * 80)
    print("所有示例运行完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
