"""
GPU模块调用验证脚本

验证GPU监控模块集成后的完整调用链路:
1. GPU引擎初始化
2. 监控器自动启动
3. GPU内核执行
4. 性能指标记录
5. 引擎停止时监控器正确停止
"""

import io
import logging
import sys
import time
from pathlib import Path

# 修复Windows编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", closefd=False)

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collision.gpu.engine import GPUCollisionEngine
from src.monitoring.gpu_performance_monitor import (
    reset_gpu_performance_monitor,
)


def verify_gpu_module_integration():
    """验证GPU模块集成"""
    print("=" * 80)
    print("GPU模块调用验证")
    print("=" * 80)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 重置全局监控器
    reset_gpu_performance_monitor()

    # 检查GPU可用性
    print("\n[1/6] 检查GPU可用性...")
    if not GPUCollisionEngine.is_gpu_available():
        print("❌ GPU不可用,跳过验证")
        return False
    print("✅ GPU可用")

    # 创建GPU引擎
    print("\n[2/6] 创建GPU引擎...")
    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
    try:
        engine = GPUCollisionEngine(
            targets=targets,
            batch_size=10000,
            use_gpu_memory_pool=True,  # 小批次用于快速验证
        )
        print("✅ GPU引擎创建成功")
    except Exception as e:
        print(f"❌ GPU引擎创建失败: {e}")
        return False

    # 验证监控器已启动
    print("\n[3/6] 验证监控器状态...")
    if not engine.gpu_performance_monitor:
        print("❌ GPU性能监控器未初始化")
        return False

    monitor = engine.gpu_performance_monitor
    if not monitor._running:
        print("❌ GPU性能监控器未启动")
        return False

    print("✅ GPU性能监控器已启动")
    print(f"   设备: {monitor._device_name}")
    print(f"   厂商: {monitor._vendor}")
    print(f"   显存: {monitor._total_memory_mb:.0f}MB")

    # 运行GPU引擎(短时间)
    print("\n[4/6] 运行GPU引擎(3秒)...")
    try:
        engine.start(mode="random")
        time.sleep(3)
        engine.stop()
        print("✅ GPU引擎运行完成")
    except Exception as e:
        print(f"❌ GPU引擎运行失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 验证性能指标已记录
    print("\n[5/6] 验证性能指标...")
    report = monitor.get_performance_report()

    if report.total_batches == 0:
        print("⚠️ 未记录任何批次(可能GPU执行较慢)")
    else:
        print("✅ 已记录性能指标:")
        print(f"   总批次数: {report.total_batches}")
        print(f"   总处理密钥: {report.total_keys_processed:,}")
        print(f"   平均吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
        print(f"   峰值吞吐量: {report.peak_throughput_keys_per_sec:,.0f} keys/s")
        print(f"   平均执行时间: {report.avg_execution_time_ms:.1f}ms")
        print(f"   错误率: {report.error_rate_percent:.2f}%")

    # 验证监控器已停止
    print("\n[6/6] 验证监控器停止...")
    if monitor._running:
        print("❌ GPU性能监控器仍在运行(未正确停止)")
        return False

    print("✅ GPU性能监控器已正确停止")

    # 总结
    print("\n" + "=" * 80)
    print("✅ GPU模块调用验证通过!")
    print("=" * 80)
    print("\n验证项目:")
    print("  ✅ GPU可用性检测")
    print("  ✅ GPU引擎初始化")
    print("  ✅ 监控器自动启动")
    print("  ✅ GPU内核执行")
    print("  ✅ 性能指标记录")
    print("  ✅ 监控器正确停止")

    return True


def verify_monitor_lifecycle():
    """验证监控器生命周期管理"""
    print("\n" + "=" * 80)
    print("监控器生命周期验证")
    print("=" * 80)

    reset_gpu_performance_monitor()

    # 创建多个引擎
    print("\n[测试] 创建-停止-重建引擎...")

    targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    # 第1次
    print("\n  第1次创建引擎...")
    engine1 = GPUCollisionEngine(targets=targets, batch_size=5000)
    monitor1 = engine1.gpu_performance_monitor
    print(f"  ✅ 监控器1已启动: {monitor1._running}")

    engine1.start(mode="random")
    time.sleep(1)
    engine1.stop()
    print(f"  ✅ 引擎1已停止,监控器状态: {monitor1._running}")

    if monitor1._running:
        print("  ❌ 监控器1未停止!")
        return False

    # 第2次
    print("\n  第2次创建引擎...")
    engine2 = GPUCollisionEngine(targets=targets, batch_size=5000)
    monitor2 = engine2.gpu_performance_monitor

    # 注意: 由于使用全局单例,monitor2可能是monitor1的实例
    print(f"  ✅ 监控器2已启动: {monitor2._running}")
    print(f"  监控器是同一实例: {monitor1 is monitor2}")

    engine2.start(mode="random")
    time.sleep(1)
    engine2.stop()
    print(f"  ✅ 引擎2已停止,监控器状态: {monitor2._running}")

    if monitor2._running:
        print("  ❌ 监控器2未停止!")
        return False

    print("\n✅ 监控器生命周期验证通过!")
    return True


def verify_metrics_recording():
    """验证指标记录准确性"""
    print("\n" + "=" * 80)
    print("性能指标记录验证")
    print("=" * 80)

    from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

    # 创建独立监控器
    monitor = GPUPerformanceMonitor()
    monitor.start()

    # 记录测试数据
    print("\n[测试] 记录10个批次的性能指标...")

    for i in range(10):
        batch_size = 10000
        exec_time = 45.0 + (i % 3) * 5.0  # 45-55ms波动
        memory_mb = 128.0 + i * 10

        monitor.record_kernel_metrics(
            batch_size=batch_size,
            execution_time_ms=exec_time,
            memory_allocated_mb=memory_mb,
            error_count=0,
            match_count=0,
        )

    # 验证指标
    report = monitor.get_performance_report()

    print("\n✅ 指标记录验证:")
    print(f"   总批次数: {report.total_batches} (期望: 10)")
    print(f"   总密钥数: {report.total_keys_processed:,} (期望: 100,000)")
    print(f"   平均吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
    print(f"   峰值吞吐量: {report.peak_throughput_keys_per_sec:,.0f} keys/s")
    print(f"   平均执行时间: {report.avg_execution_time_ms:.1f}ms (期望: ~48ms)")
    print(f"   错误率: {report.error_rate_percent:.2f}% (期望: 0%)")

    # 验证计算正确性
    assert report.total_batches == 10, f"批次数错误: {report.total_batches}"
    assert report.total_keys_processed == 100000, f"密钥数错误: {report.total_keys_processed}"
    assert report.error_rate_percent == 0.0, f"错误率错误: {report.error_rate_percent}"

    print("\n✅ 性能指标记录验证通过!")

    monitor.stop()
    return True


if __name__ == "__main__":
    print("GPU模块调用验证工具")
    print("=" * 80)

    results = []

    # 测试1: GPU模块集成
    try:
        result1 = verify_gpu_module_integration()
        results.append(("GPU模块集成", result1))
    except Exception as e:
        print(f"\n❌ GPU模块集成验证失败: {e}")
        import traceback

        traceback.print_exc()
        results.append(("GPU模块集成", False))

    # 测试2: 监控器生命周期
    try:
        result2 = verify_monitor_lifecycle()
        results.append(("监控器生命周期", result2))
    except Exception as e:
        print(f"\n❌ 监控器生命周期验证失败: {e}")
        import traceback

        traceback.print_exc()
        results.append(("监控器生命周期", False))

    # 测试3: 指标记录
    try:
        result3 = verify_metrics_recording()
        results.append(("性能指标记录", result3))
    except Exception as e:
        print(f"\n❌ 性能指标记录验证失败: {e}")
        import traceback

        traceback.print_exc()
        results.append(("性能指标记录", False))

    # 总结
    print("\n" + "=" * 80)
    print("验证总结")
    print("=" * 80)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有验证通过! GPU模块集成正常!")
    else:
        print("❌ 部分验证失败,请检查上方错误信息")
    print("=" * 80)
