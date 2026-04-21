# -*- coding: utf-8 -*-
"""
完整性能优化演示 - 使用优化后的碰撞引擎
包含: 性能监控、文档参考、测试验证
"""
import sys
import time
import secrets
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collision.key_collision_engine import KeyCollisionEngine
from src.monitoring.optimization_monitor import get_performance_monitor
from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator


def demo_1_basic_usage():
    """演示1: 基本使用 - 默认启用所有优化"""
    print("="*80)
    print("演示1: 基本使用 (默认启用所有优化)")
    print("="*80)
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    
    # 默认配置 - 自动启用所有优化
    engine = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True  # 默认启用
    )
    
    print(f"\n✅ 引擎初始化成功")
    print(f"   目标地址数: {len(targets)}")
    print(f"   优化状态: 已启用")
    print(f"   生成器类型: {type(engine.generator).__name__}")
    
    # 生成几个测试地址
    print(f"\n  生成测试地址:")
    for i in range(5):
        private_key = secrets.token_bytes(32)
        address = engine.generator.generate_from_private_key(private_key)
        print(f"   {i+1}. {address[:20]}...{address[-10:]}")
    
    print("\n✅ 基本使用演示完成!\n")


def demo_2_custom_config():
    """演示2: 自定义优化配置"""
    print("="*80)
    print("演示2: 自定义优化配置")
    print("="*80)
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    
    # 自定义配置
    engine = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True,
        precomputed_window_size=8,      # 最大预计算表
        use_simd_hash=True,             # SIMD加速
        use_memory_pool=True            # 内存池
    )
    
    print(f"\n✅ 自定义配置:")
    print(f"   预计算窗口: 8 (256个预计算点)")
    print(f"   SIMD哈希: 启用 (AES-NI)")
    print(f"   内存池: 启用")
    
    # 性能测试
    num_tests = 100
    start = time.perf_counter()
    
    for _ in range(num_tests):
        pk = secrets.token_bytes(32)
        engine.generator.generate_from_private_key(pk)
    
    elapsed = time.perf_counter() - start
    speed = num_tests / elapsed
    
    print(f"\n  性能测试:")
    print(f"   生成地址数: {num_tests}")
    print(f"   耗时: {elapsed:.2f}s")
    print(f"   速度: {speed:.0f} 地址/秒")
    
    print("\n✅ 自定义配置演示完成!\n")


def demo_3_performance_monitoring():
    """演示3: 实时性能监控"""
    print("="*80)
    print("演示3: 实时性能监控")
    print("="*80)
    
    # 获取全局性能监控器
    monitor = get_performance_monitor()
    monitor.start()
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    engine = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True
    )
    
    print(f"\n🔍 开始监控...")
    
    # 分批生成地址并监控
    total_addresses = 1000
    batch_size = 200
    
    for batch in range(total_addresses // batch_size):
        batch_start = time.perf_counter()
        
        for _ in range(batch_size):
            pk = secrets.token_bytes(32)
            engine.generator.generate_from_private_key(pk)
        
        batch_elapsed = time.perf_counter() - batch_start
        
        # 记录到监控器
        monitor.record_metrics(
            addresses_generated=batch_size,
            elapsed_time=batch_elapsed,
            optimization_enabled=True,
            precomputed_table=True,
            simd_hash=True,
            memory_pool=True
        )
        
        # 实时显示
        current = monitor.get_current_metrics()
        avg_speed = monitor.get_average_speed(window_seconds=60.0)
        
        print(f"  批次 {batch+1}: "
              f"速度={current.speed:.0f} addr/s, "
              f"平均={avg_speed:.0f} addr/s, "
              f"延迟={current.avg_generation_time_ms:.2f}ms")
    
    # 获取完整报告
    report = monitor.get_performance_report()
    
    print(f"\n📊 性能监控报告:")
    print(f"   总地址数: {report['summary']['total_addresses']:,}")
    print(f"   峰值速度: {report['summary']['peak_speed']:.0f} addr/s")
    print(f"   平均速度: {report['summary']['avg_speed']:.0f} addr/s")
    print(f"   最低速度: {report['summary']['min_speed']:.0f} addr/s")
    print(f"   稳定性: {report['summary']['stability']:.1f}%")
    print(f"   优化启用率: {report['optimization']['enabled_percentage']:.1f}%")
    print(f"   平均延迟: {report['latency']['avg_ms']:.2f}ms")
    
    # 导出JSON数据
    json_data = monitor.export_metrics(format='json')
    print(f"\n  📄 已导出JSON数据 ({len(json_data)} 字符)")
    
    monitor.stop()
    print("\n✅ 性能监控演示完成!\n")


def demo_4_comparison():
    """演示4: 优化版 vs 标准版对比"""
    print("="*80)
    print("演示4: 优化版 vs 标准版性能对比")
    print("="*80)
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    num_tests = 500
    
    # 测试优化版
    print(f"\n  测试优化版引擎...")
    engine_opt = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True,
        precomputed_window_size=8,
        use_simd_hash=True,
        use_memory_pool=True
    )
    
    start = time.perf_counter()
    for _ in range(num_tests):
        pk = secrets.token_bytes(32)
        engine_opt.generator.generate_from_private_key(pk)
    elapsed_opt = time.perf_counter() - start
    speed_opt = num_tests / elapsed_opt
    
    # 测试标准版
    print(f"  测试标准版引擎...")
    engine_std = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=False
    )
    
    start = time.perf_counter()
    for _ in range(num_tests):
        pk = secrets.token_bytes(32)
        engine_std.generator.generate_address(pk)
    elapsed_std = time.perf_counter() - start
    speed_std = num_tests / elapsed_std
    
    # 对比结果
    print(f"\n📊 性能对比结果:")
    print(f"   优化版: {speed_opt:.0f} 地址/秒 ({elapsed_opt:.2f}s)")
    print(f"   标准版: {speed_std:.0f} 地址/秒 ({elapsed_std:.2f}s)")
    
    if speed_opt > speed_std:
        improvement = (speed_opt / speed_std - 1) * 100
        print(f"   ✅ 优化版快 {improvement:.1f}%")
    else:
        ratio = speed_std / speed_opt
        print(f"   ℹ️ 标准版快 {ratio:.1f}x (使用coincurve C实现)")
    
    print("\n✅ 性能对比演示完成!\n")


def demo_5_different_configs():
    """演示5: 不同优化配置对比"""
    print("="*80)
    print("演示5: 不同优化配置对比")
    print("="*80)
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    num_tests = 200
    
    configs = [
        ("全优化 (w=8)", True, 8, True, True),
        ("仅预计算表", True, 8, False, False),
        ("小窗口 (w=6)", True, 6, True, True),
        ("无优化", False, 8, True, True),
    ]
    
    results = []
    
    for name, use_opt, window, simd, pool in configs:
        print(f"\n  测试配置: {name}")
        
        engine = KeyCollisionEngine(
            targets=targets,
            use_performance_optimization=use_opt,
            precomputed_window_size=window,
            use_simd_hash=simd,
            use_memory_pool=pool
        )
        
        start = time.perf_counter()
        for _ in range(num_tests):
            pk = secrets.token_bytes(32)
            if use_opt:
                engine.generator.generate_from_private_key(pk)
            else:
                engine.generator.generate_address(pk)
        elapsed = time.perf_counter() - start
        speed = num_tests / elapsed
        
        results.append((name, speed, elapsed))
        print(f"    速度: {speed:.0f} addr/s ({elapsed:.2f}s)")
    
    # 排序并显示
    results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 配置排名:")
    for i, (name, speed, elapsed) in enumerate(results, 1):
        print(f"   {i}. {name}: {speed:.0f} addr/s")
    
    print("\n✅ 配置对比演示完成!\n")


def demo_6_stress_test():
    """演示6: 压力测试 (10,000地址)"""
    print("="*80)
    print("演示6: 压力测试 (10,000地址)")
    print("="*80)
    
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    engine = KeyCollisionEngine(
        targets=targets,
        use_performance_optimization=True
    )
    
    monitor = get_performance_monitor()
    monitor.start()
    
    total = 10000
    batch_size = 1000
    
    print(f"\n🚀 开始压力测试: {total} 个地址")
    start_time = time.perf_counter()
    
    for batch in range(total // batch_size):
        batch_start = time.perf_counter()
        
        for _ in range(batch_size):
            pk = secrets.token_bytes(32)
            engine.generator.generate_from_private_key(pk)
        
        batch_elapsed = time.perf_counter() - batch_start
        
        monitor.record_metrics(
            addresses_generated=batch_size,
            elapsed_time=batch_elapsed,
            optimization_enabled=True
        )
        
        progress = (batch + 1) * batch_size
        percent = progress / total * 100
        elapsed_total = time.perf_counter() - start_time
        avg_speed = progress / elapsed_total
        
        print(f"  进度: {progress:,}/{total:,} ({percent:.0f}%) - "
              f"速度: {avg_speed:.0f} addr/s")
    
    total_elapsed = time.perf_counter() - start_time
    final_speed = total / total_elapsed
    
    report = monitor.get_performance_report()
    
    print(f"\n📊 压力测试结果:")
    print(f"   总地址数: {total:,}")
    print(f"   总耗时: {total_elapsed:.2f}s")
    print(f"   平均速度: {final_speed:.0f} addr/s")
    print(f"   峰值速度: {report['summary']['peak_speed']:.0f} addr/s")
    print(f"   稳定性: {report['summary']['stability']:.1f}%")
    
    monitor.stop()
    print("\n✅ 压力测试完成!\n")


def main():
    """运行所有演示"""
    print("\n" + "="*80)
    print("BTC碰撞引擎 v2.2.0 - 完整性能优化演示")
    print("="*80)
    
    try:
        # 演示1: 基本使用
        demo_1_basic_usage()
        
        # 演示2: 自定义配置
        demo_2_custom_config()
        
        # 演示3: 性能监控
        demo_3_performance_monitoring()
        
        # 演示4: 性能对比
        demo_4_comparison()
        
        # 演示5: 配置对比
        demo_5_different_configs()
        
        # 演示6: 压力测试
        demo_6_stress_test()
        
    except KeyboardInterrupt:
        print("\n\n  ⚠️ 演示被用户中断")
    except Exception as e:
        print(f"\n\n  ❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("="*80)
    print("✅ 所有演示完成!")
    print("="*80)
    print("\n📚 参考文档:")
    print("   - docs/performance-verification-report.md")
    print("   - docs/optimization-quick-reference.md")
    print("   - RELEASE_NOTES_v2.2.0.md")
    print("   - docs/v2.2.0-final-implementation-report.md")
    print("\n🧪 运行测试:")
    print("   pytest tests/test_optimization_*.py -v")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
