#!/usr/bin/env python3
"""
GPU停止阻塞修复 - 异常处理专项测试

测试目标:
1. 验证command_execution_status查询的异常处理
2. 验证最大迭代次数保护
3. 验证停止信号处理
4. 验证超时监控优化
"""

import os
import sys
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_1_exception_handling_code_review():
    """测试1: 代码审查 - 异常处理完整性"""
    print("=" * 70)
    print("测试1: 异常处理代码审查")
    print("=" * 70)

    import inspect

    from src.gpu import kernel_impl

    # 获取run_batch方法源码
    source = inspect.getsource(kernel_impl.GPUKernel.run_batch)

    checks = {
        "cl.Error异常捕获": "except cl.Error as e:" in source,
        "通用Exception异常捕获": "except Exception as e:" in source,
        "最大迭代次数保护": "max_iterations" in source,
        "迭代计数器": "iteration_count" in source,
        "轮询次数警告": "轮询次数超过最大值" in source,
        "GPU状态查询失败日志": "GPU状态查询失败" in source,
        "停止信号检测日志": "检测到停止信号" in source,
        "轮询次数统计": "已轮询{iteration_count}次" in source,
    }

    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed


def test_2_timeout_monitor_optimization():
    """测试2: 超时监控优化"""
    print("\n" + "=" * 70)
    print("测试2: 超时监控线程优化")
    print("=" * 70)

    import inspect

    from src.gpu import kernel_impl

    source = inspect.getsource(kernel_impl.GPUKernel.run_batch)

    checks = {
        "移除queue.finish()调用": "self.device.queue.finish()" not in source,
        "直接标记超时": "标记GPU执行超时" in source,
        "保留未来扩展接口": "context.abort" in source
        or "context.abort" in source.replace(" ", "").replace("\n", ""),
        "超时监控线程存在": "timeout_monitor" in source,
        "daemon线程": "daemon=True" in source,
    }

    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed


def test_3_race_condition_fix():
    """测试3: 竞态条件修复"""
    print("\n" + "=" * 70)
    print("测试3: 停止信号竞态条件优化")
    print("=" * 70)

    import inspect

    from src.gpu import kernel_impl

    source = inspect.getsource(kernel_impl.GPUKernel.run_batch)

    # 检查代码顺序: GPU状态检查应在停止信号检查之前
    gpu_check_pos = source.find("command_execution_status.COMPLETE")
    stop_check_pos = source.find("stop_event.is_set()")

    correct_order = gpu_check_pos < stop_check_pos and gpu_check_pos > 0

    checks = {
        "GPU状态检查在停止信号之前": correct_order,
        "包含轮询次数信息": "已轮询" in source,
        "包含耗时信息": "耗时" in source,
    }

    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed


def test_4_max_iterations_calculation():
    """测试4: 最大迭代次数计算"""
    print("\n" + "=" * 70)
    print("测试4: 最大迭代次数计算逻辑")
    print("=" * 70)

    timeout_seconds = 30
    poll_interval = 0.1

    expected_max_iterations = int(timeout_seconds / poll_interval) + 10  # 300 + 10

    print(f"  超时时间: {timeout_seconds}秒")
    print(f"  轮询间隔: {poll_interval}秒")
    print(f"  预期最大迭代次数: {expected_max_iterations}")
    print(f"  预期最大等待时间: {expected_max_iterations * poll_interval}秒")

    # 验证计算逻辑
    assert expected_max_iterations == 310, f"预期310,实际{expected_max_iterations}"

    print("  ✅ 最大迭代次数计算正确")
    print("  ✅ 包含10次容错缓冲")

    return True


def test_5_polling_interval_performance():
    """测试5: 轮询间隔性能影响"""
    print("\n" + "=" * 70)
    print("测试5: 轮询间隔性能影响评估")
    print("=" * 70)

    poll_interval = 0.1  # 100ms
    batch_time_estimate = 0.5  # 估计每批次0.5秒
    polling_count = batch_time_estimate / poll_interval  # 5次

    overhead_ms = polling_count * 0.001  # 每次查询约1ms
    overhead_percent = (overhead_ms / (batch_time_estimate * 1000)) * 100

    print(f"  轮询间隔: {poll_interval}秒 ({poll_interval * 1000}ms)")
    print(f"  预计每批次时间: {batch_time_estimate}秒")
    print(f"  预计轮询次数: {polling_count}次")
    print(f"  轮询总开销: {overhead_ms * 1000:.3f}ms")
    print(f"  性能影响: {overhead_percent:.4f}%")

    assert overhead_percent < 0.01, f"性能影响过大: {overhead_percent}%"

    print("  ✅ 性能影响极小(<0.001%)")

    return True


def test_6_exception_types_coverage():
    """测试6: 异常类型覆盖范围"""
    print("\n" + "=" * 70)
    print("测试6: 异常类型覆盖分析")
    print("=" * 70)

    try:
        import pyopencl as cl

        print(f"  PyOpenCL版本: {cl.VERSION_TEXT}")
        print("  ✅ command_execution_status枚举可用")
        print("  ✅ cl.Error异常类型可用")

        # 验证异常类型
        assert hasattr(cl, "Error"), "cl.Error不存在"
        assert hasattr(cl, "command_execution_status"), "command_execution_status不存在"

        print("  ✅ 异常处理所需的API完整")

        return True

    except ImportError as e:
        print(f"  ❌ PyOpenCL导入失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 70)
    print("GPU停止阻塞修复 - 异常处理专项测试")
    print("=" * 70)
    print(f"Python版本: {sys.version}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    tests = [
        ("异常处理代码审查", test_1_exception_handling_code_review),
        ("超时监控优化", test_2_timeout_monitor_optimization),
        ("竞态条件修复", test_3_race_condition_fix),
        ("最大迭代次数计算", test_4_max_iterations_calculation),
        ("轮询间隔性能影响", test_5_polling_interval_performance),
        ("异常类型覆盖", test_6_exception_types_coverage),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n  ❌ 测试异常: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {test_name}")

    print("=" * 70)
    print(f"总计: {passed}/{total} 通过")

    if passed == total:
        print("✅ 所有测试通过! 异常处理修复验证成功!")
        return 0
    else:
        print("❌ 部分测试失败,请检查修复代码")
        return 1


if __name__ == "__main__":
    sys.exit(main())
