#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心模块性能基准测试

测试内容:
1. secp256k1 椭圆曲线运算性能
2. 日志系统性能（同步 vs 异步）
3. ThreadSafeLogger vs 原生logger性能对比
"""
import sys
import os
import time
import statistics

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.secp256k1 import Secp256k1, ECPoint, EllipticCurve
from src.utils import init_logging, get_configured_logger
from src.utils.logger import (
    ThreadSafeLogger, SampledLogger,
    AsyncLogger, AsyncFileHandler
)
import logging
import warnings


def benchmark_secp256k1_scalar_multiply(iterations=100):
    """基准测试: 标量乘法性能"""
    print("\n" + "="*60)
    print("基准测试 1: secp256k1 标量乘法性能")
    print("="*60)

    ec = EllipticCurve()
    G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    # 测试旧版标量乘法（带弃用警告）
    print("\n[测试1a] 旧版 scalar_multiply() (双倍-加法)")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        times = []
        for i in range(iterations):
            k = 123456789 + i
            start = time.perf_counter()
            result = ec.scalar_multiply(k, G)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

    avg_time = statistics.mean(times)
    median_time = statistics.median(times)
    print(f"  平均时间: {avg_time:.2f}ms")
    print(f"  中位数: {median_time:.2f}ms")
    print(f"  最小值: {min(times):.2f}ms")
    print(f"  最大值: {max(times):.2f}ms")

    # 测试新版恒定时间标量乘法
    print("\n[测试1b] 新版 scalar_multiply_const_time() (Montgomery Ladder)")
    times = []
    for i in range(iterations):
        k = 123456789 + i
        start = time.perf_counter()
        result = ec.scalar_multiply_const_time(k, G)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg_time = statistics.mean(times)
    median_time = statistics.median(times)
    print(f"  平均时间: {avg_time:.2f}ms")
    print(f"  中位数: {median_time:.2f}ms")
    print(f"  最小值: {min(times):.2f}ms")
    print(f"  最大值: {max(times):.2f}ms")

    # 验证结果正确性（使用k=2）
    result_2g = ec.scalar_multiply_const_time(2, G)
    expected_x = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    assert result_2g.x == expected_x, f"X坐标不匹配: {result_2g.x:#x} != {expected_x:#x}"
    print(f"\n  [PASS] 计算结果正确 (2G.x = {result_2g.x:#x})")


def benchmark_logger_performance(iterations=1000):
    """基准测试: 日志系统性能"""
    print("\n" + "="*60)
    print("基准测试 2: 日志系统性能对比")
    print("="*60)

    # 初始化日志
    init_logging()

    # 测试1: 原生logger
    print("\n[测试2a] 原生 logging.Logger")
    logger1 = get_configured_logger("Benchmark_Native", thread_safe=False)
    native_times = []
    for i in range(iterations):
        start = time.perf_counter()
        logger1.debug(f"Test message {i}")
        elapsed = (time.perf_counter() - start) * 1000
        native_times.append(elapsed)

    native_avg = statistics.mean(native_times)
    native_total = sum(native_times)
    print(f"  总时间: {native_total:.2f}ms")
    print(f"  平均时间: {native_avg:.4f}ms/条")
    print(f"  吞吐量: {iterations/native_total*1000:.0f} 条/秒")

    # 测试2: ThreadSafeLogger (已弃用)
    print("\n[测试2b] ThreadSafeLogger (已弃用)")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logger2_base = get_configured_logger("Benchmark_ThreadSafe", thread_safe=False)
        logger2 = ThreadSafeLogger(logger2_base)

        ts_times = []
        for i in range(iterations):
            start = time.perf_counter()
            logger2.debug(f"Test message {i}")
            elapsed = (time.perf_counter() - start) * 1000
            ts_times.append(elapsed)

    ts_avg = statistics.mean(ts_times)
    ts_total = sum(ts_times)
    print(f"  总时间: {ts_total:.2f}ms")
    print(f"  平均时间: {ts_avg:.4f}ms/条")
    print(f"  吞吐量: {iterations/ts_total*1000:.0f} 条/秒")

    # 性能对比（使用独立变量名避免覆盖）
    slowdown = (ts_total / native_total - 1) * 100 if native_total > 0 else 0
    print(f"\n  [WARNING] ThreadSafeLogger 比原生logger慢约 {slowdown:.1f}%")

    # 测试3: 异步日志
    print("\n[测试2c] AsyncFileHandler (异步日志)")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name

    try:
        async_handler = AsyncFileHandler(log_file, max_bytes=10*1024*1024)
        logger3 = get_configured_logger("Benchmark_Async", thread_safe=False)
        logger3.addHandler(async_handler)

        times = []
        for i in range(iterations):
            start = time.perf_counter()
            logger3.debug(f"Test message {i}")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = statistics.mean(times)
        total_time = sum(times)
        print(f"  总时间: {total_time:.2f}ms (非阻塞)")
        print(f"  平均时间: {avg_time:.4f}ms/条")
        print(f"  吞吐量: {iterations/total_time*1000:.0f} 条/秒 (理论值)")

        # 等待队列清空
        async_handler.close()

        stats = async_handler._async_logger.get_stats()
        print(f"  队列状态: {stats}")

    finally:
        if os.path.exists(log_file):
            os.remove(log_file)


def benchmark_sampled_logger(iterations=10000):
    """基准测试: 采样日志性能"""
    print("\n" + "="*60)
    print("基准测试 3: SampledLogger 性能")
    print("="*60)

    init_logging()

    # 测试不同采样率
    sample_rates = [1, 10, 100, 1000]

    for rate in sample_rates:
        logger_base = get_configured_logger(f"Benchmark_Sampled_{rate}", thread_safe=False)
        sampled_logger = SampledLogger(logger_base, sample_rate=rate)

        times = []
        for i in range(iterations):
            start = time.perf_counter()
            sampled_logger.debug(f"Test message {i}")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        total_time = sum(times)
        actual_logs = iterations // rate
        print(f"\n  采样率 1/{rate}:")
        print(f"    总时间: {total_time:.2f}ms")
        print(f"    实际记录: {actual_logs} 条")
        print(f"    平均时间: {statistics.mean(times):.4f}ms/条")


def benchmark_concurrent_logging(thread_count=5, messages_per_thread=100):
    """基准测试: 并发日志性能"""
    print("\n" + "="*60)
    print("基准测试 4: 并发日志性能")
    print("="*60)

    init_logging()

    import threading

    # 测试原生logger
    print(f"\n[测试4a] 原生logger ({thread_count}线程, {messages_per_thread}条/线程)")
    logger = get_configured_logger("Benchmark_Concurrent", thread_safe=False)
    messages = []

    def log_messages(thread_id):
        for i in range(messages_per_thread):
            logger.debug(f"Thread-{thread_id} message-{i}")
            messages.append(f"Thread-{thread_id}-{i}")

    threads = []
    for i in range(thread_count):
        t = threading.Thread(target=log_messages, args=(i,))
        threads.append(t)

    start_time = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = (time.perf_counter() - start_time) * 1000

    total_messages = thread_count * messages_per_thread
    print(f"  总消息数: {len(messages)}/{total_messages}")
    print(f"  总时间: {elapsed:.2f}ms")
    print(f"  吞吐量: {total_messages/elapsed*1000:.0f} 条/秒")
    print(f"  无竞态条件: {'[PASS]' if len(messages) == total_messages else '[FAIL]'}")


def main():
    """运行所有基准测试"""
    print("\n" + "="*60)
    print("BTC碰撞引擎核心模块性能基准测试")
    print("="*60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行测试
    try:
        benchmark_secp256k1_scalar_multiply(iterations=50)
        benchmark_logger_performance(iterations=1000)
        benchmark_sampled_logger(iterations=10000)
        benchmark_concurrent_logging(thread_count=5, messages_per_thread=100)

        print("\n" + "="*60)
        print("所有基准测试完成！")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 基准测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
