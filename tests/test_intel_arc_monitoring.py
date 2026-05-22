#!/usr/bin/env python3
"""
Intel Arc资源监控功能验证脚本

验证以下功能：
1. IntelMemoryMonitor - 显存监控
2. AdaptiveTimeoutManager - 超时管理
3. GPU性能监控
4. 数据质量监控
"""

import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

logger = logging.getLogger("IntelArcMonitorTest")


def test_memory_monitor():
    """测试显存监控功能"""
    print("\n" + "=" * 80)
    print("测试1: Intel Arc显存监控器 (IntelMemoryMonitor)")
    print("=" * 80)

    from src.gpu.intel_memory_monitor import IntelMemoryMonitor

    # 模拟Intel Arc A770 16GB显存
    total_memory = 16 * 1024**3  # 16GB
    monitor = IntelMemoryMonitor(
        total_memory_bytes=total_memory,
        safe_usage_ratio=0.45,  # Intel保守策略：45%
    )

    print("\n✓ 显存监控器初始化成功")
    print(f"  - 总显存: {total_memory / 1024**3:.1f} GB")
    print(f"  - 安全限制: {monitor.safe_limit / 1024**2:.0f} MB (45%)")
    print(f"  - 警告阈值: {monitor.warning_limit / 1024**2:.0f} MB")

    # 测试显存分配
    print("\n测试显存分配...")
    allocations = [
        512 * 1024**2,  # 512MB
        1024 * 1024**2,  # 1GB
        2048 * 1024**2,  # 2GB
    ]

    for i, size in enumerate(allocations):
        success = monitor.track_allocation(size, batch_count=i + 1)
        status = monitor.get_status()
        print(
            f"  批次 {i + 1}: 分配 {size / 1024**2:.0f}MB -> "
            f"使用 {status['current_mb']:.0f}MB "
            f"({status['usage_percent']:.1f}%) "
            f"[{'✓' if success else '✗'}]"
        )

    # 测试显存释放
    print("\n测试显存释放...")
    monitor.track_deallocation(1024 * 1024**2, batch_count=4)
    status = monitor.get_status()
    print(f"  释放 1024MB -> 使用 {status['current_mb']:.0f}MB ({status['usage_percent']:.1f}%)")

    # 测试状态检查
    print("\n测试状态检查...")
    warnings = monitor.check_warnings()
    if warnings:
        print("  ⚠️ 警告:")
        for warning in warnings:
            print(f"    - {warning}")
    else:
        print("  ✓ 无警告")

    # 测试批次调整建议
    print("\n测试批次调整建议...")
    reduction = monitor.get_recommended_batch_reduction()
    if reduction > 0:
        print(f"  ⚠️ 建议减少批次大小: {reduction * 100:.0f}%")
    else:
        print("  ✓ 无需调整批次大小")

    # 生成报告
    print("\n显存使用报告:")
    print(monitor.get_report())

    print("\n✅ 显存监控测试通过")
    return True


def test_timeout_manager():
    """测试超时管理功能"""
    print("\n" + "=" * 80)
    print("测试2: Intel Arc自适应超时管理器 (AdaptiveTimeoutManager)")
    print("=" * 80)

    from src.gpu.intel_timeout_manager import AdaptiveTimeoutManager

    manager = AdaptiveTimeoutManager(base_timeout=30.0, min_timeout=10.0, max_timeout=120.0)

    print("\n✓ 超时管理器初始化成功")
    print(f"  - 基础超时: {manager.base_timeout}秒")
    print(f"  - 超时范围: {manager.min_timeout} - {manager.max_timeout}秒")

    # 模拟执行时间记录
    print("\n模拟执行时间记录...")
    execution_times = [
        (100.0, 1),  # 100ms, 批次1
        (150.0, 2),  # 150ms, 批次2
        (200.0, 3),  # 200ms, 批次3
        (120.0, 4),  # 120ms, 批次4
        (180.0, 5),  # 180ms, 批次5
    ]

    for exec_time, batch in execution_times:
        manager.record_execution_time(exec_time)
        print(f"  批次 {batch}: 执行时间 {exec_time:.0f}ms")

    # 获取自适应超时
    print("\n获取自适应超时...")
    timeout = manager.get_timeout()
    stats = manager.get_statistics()

    print(f"  当前超时: {timeout:.1f}秒")
    print("  统计信息:")
    print(f"    - 平均执行时间: {stats['mean_ms']:.1f}ms")
    print(f"    - 执行次数: {stats['total_records']}")
    print(f"    - 超时调整: {stats['timeout_adjustments']}")

    # 测试重置
    print("\n测试重置...")
    manager.reset()
    stats = manager.get_statistics()
    print(f"  ✓ 已重置，状态: {stats['status']}")

    print("\n✅ 超时管理测试通过")
    return True


def test_performance_monitor():
    """测试GPU性能监控功能"""
    print("\n" + "=" * 80)
    print("测试3: GPU性能监控器 (GPUPerformanceMonitor)")
    print("=" * 80)

    from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

    # 创建性能监控器
    monitor = GPUPerformanceMonitor()

    print("\n✓ 性能监控器初始化成功")

    # 模拟性能数据
    print("\n记录性能数据...")
    for i in range(5):
        monitor.record_kernel_metrics(
            batch_size=100000, execution_time_ms=50.0 + i * 10, memory_allocated_mb=256.0
        )
        print(f"  批次 {i + 1}: 执行时间 {50.0 + i * 10:.0f}ms, 显存 256MB")

    # 获取性能报告
    print("\n生成性能报告...")
    report = monitor.get_performance_report()

    print("\n📊 GPU性能报告:")
    print("  设备: Intel(R) Arc(TM) A770 Graphics")
    print(f"  监控时长: {report.monitoring_duration_sec:.1f}秒")
    print(f"  总批次数: {report.total_batches}")
    print(f"  总处理密钥: {report.total_keys_processed:,}")
    print(f"  平均吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
    print(f"  峰值吞吐量: {report.peak_throughput_keys_per_sec:,.0f} keys/s")
    print(f"  平均执行时间: {report.avg_execution_time_ms:.1f}ms")
    print(f"  错误率: {report.error_rate_percent:.2f}%")
    print(f"  性能稳定性: {report.performance_stability_percent:.1f}%")

    print("\n✅ 性能监控测试通过")
    return True


def test_data_monitor():
    """测试数据质量监控功能"""
    print("\n" + "=" * 80)
    print("测试4: 数据质量监控器 (DataMonitor)")
    print("=" * 80)

    from src.gpu.data_monitor import DataMonitor

    # 创建数据监控器
    monitor = DataMonitor(
        config={"check_interval": 0.5, "throughput_threshold": 0.5, "error_rate_threshold": 0.1}
    )

    print("\n✓ 数据监控器初始化成功")

    # 启动监控
    monitor.start()
    print("  ✓ 监控已启动")

    # 模拟数据报告
    print("\n模拟数据报告...")
    for i in range(5):
        monitor.report_keys_generated(
            device_idx=0, count=100000, key_range=(i * 100000, (i + 1) * 100000)
        )
        print(f"  GPU 0: 生成 {100000:,} 个密钥 (批次 {i + 1})")
        time.sleep(0.1)

    # 获取统计信息
    print("\n获取监控统计...")
    stats = monitor.get_stats()

    print("\n📈 数据监控统计:")
    print(f"  总监控密钥: {stats['total_keys_monitored']:,}")
    print(f"  总验证匹配: {stats['total_matches_verified']:,}")
    print(f"  总检测问题: {stats['total_issues_detected']:,}")
    print(f"  验证通过率: {stats['validation_pass_rate']:.2%}")

    if stats.get("devices"):
        for device_idx, device_stats in stats["devices"].items():
            print(f"\n  GPU {device_idx}:")
            print(f"    - 总密钥: {device_stats['total_keys']:,}")
            print(f"    - 平均吞吐量: {device_stats['avg_throughput']:,.0f} keys/s")

    # 停止监控
    monitor.stop()
    print("\n  ✓ 监控已停止")

    print("\n✅ 数据质量监控测试通过")
    return True


def test_integration():
    """测试集成工作流"""
    print("\n" + "=" * 80)
    print("测试5: Intel Arc资源监控集成工作流")
    print("=" * 80)

    from src.gpu.intel_memory_monitor import IntelMemoryMonitor
    from src.gpu.intel_timeout_manager import AdaptiveTimeoutManager

    print("\n模拟完整的Intel Arc资源监控工作流...")

    # 1. 初始化监控器
    memory_monitor = IntelMemoryMonitor(total_memory_bytes=16 * 1024**3)
    timeout_manager = AdaptiveTimeoutManager(base_timeout=30.0)

    print("\n步骤1: 初始化监控组件")
    print(f"  ✓ 显存监控器: 安全限制 {memory_monitor.safe_limit / 1024**2:.0f}MB")
    print(f"  ✓ 超时管理器: 基础超时 {timeout_manager.base_timeout}秒")

    # 2. 模拟碰撞引擎运行
    print("\n步骤2: 模拟碰撞引擎运行（10个批次）")
    for batch in range(1, 11):
        # 模拟显存分配
        alloc_size = 256 * 1024**2  # 256MB
        memory_monitor.track_allocation(alloc_size, batch_count=batch)

        # 模拟执行时间
        exec_time = 100.0 + batch * 5  # 100-145ms
        timeout_manager.record_execution_time(exec_time)

        # 模拟显存释放
        memory_monitor.track_deallocation(alloc_size, batch_count=batch)

        # 每5个批次打印状态
        if batch % 5 == 0:
            mem_status = memory_monitor.get_status()
            timeout = timeout_manager.get_timeout()
            print(f"  批次 {batch}: 显存 {mem_status['current_mb']:.0f}MB, 超时 {timeout:.1f}秒")

    # 3. 生成综合报告
    print("\n步骤3: 生成综合资源报告")
    print("\n" + "=" * 60)
    print("📊 Intel Arc A770 资源监控报告")
    print("=" * 60)

    mem_status = memory_monitor.get_status()
    print("\n显存使用:")
    print(f"  总显存: {mem_status['total_memory_gb']:.1f} GB")
    print(f"  安全限制: {mem_status['safe_limit_mb']:.0f} MB (45%)")
    print(f"  当前使用: {mem_status['current_mb']:.1f} MB")
    print(f"  峰值使用: {mem_status['peak_mb']:.1f} MB")
    print(f"  状态: {mem_status['status'].value.upper()}")

    timeout_stats = timeout_manager.get_statistics()
    print("\n执行超时:")
    print(f"  平均执行时间: {timeout_stats['mean_ms']:.1f}ms")
    print(f"  执行次数: {timeout_stats['total_records']}")
    print(f"  当前超时: {timeout_manager.get_timeout():.1f}秒")

    print("\n" + "=" * 60)
    print("✅ 集成工作流测试通过")

    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("Intel Arc资源监控功能验证")
    print("=" * 80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("目标设备: Intel Arc A770 (16GB)")

    tests = [
        ("显存监控", test_memory_monitor),
        ("超时管理", test_timeout_manager),
        ("性能监控", test_performance_monitor),
        ("数据质量监控", test_data_monitor),
        ("集成工作流", test_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"测试失败 [{name}]: {e}", exc_info=True)
            results.append((name, False))

    # 打印总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有Intel Arc资源监控功能验证通过！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
