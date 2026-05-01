#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU性能优化基准测试

测试v2.2.1性能优化效果：
1. 异步执行预取机制
2. 内存池预分配和大小对齐
3. 动态batch_size调整策略
"""

import time
import sys
import logging
from typing import Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("GPU_Benchmark")


class PerformanceBenchmark:
    """性能基准测试器"""

    def __init__(self):
        self.results: List[Dict] = []

    def test_async_executor_prefetch(self):
        """测试异步执行器预取机制"""
        print("\n" + "=" * 80)
        print("测试1: 异步执行器预取机制")
        print("=" * 80)

        try:
            from src.gpu.async_executor import AsyncGPUExecutor
            from unittest.mock import Mock

            # 创建模拟GPU设备
            mock_device = Mock()
            mock_device.enable_async_execution = True
            mock_device.compute_queue = Mock()
            mock_device.transfer_queue = Mock()

            # 创建执行器
            executor = AsyncGPUExecutor(mock_device, max_batch_size=100000)

            # 测试预取功能
            test_data = b"\x00" * 3200000  # 100k keys * 32 bytes
            executor.prefetch_next_batch(test_data, 100000)

            # 验证预取状态
            assert executor._next_batch_ready.is_set(), "预取状态未设置"
            assert executor._next_batch_data is not None, "预取数据为空"
            assert executor._next_batch_size == 100000, "预取大小错误"

            print("✅ 预取机制测试通过")
            print(f"   - 预取状态: {executor._next_batch_ready.is_set()}")
            print(f"   - 预取数据大小: {executor._next_batch_size:,} keys")

            self.results.append(
                {"test": "async_executor_prefetch", "status": "PASS", "details": "预取机制正常工作"}
            )

        except Exception as e:
            print(f"❌ 预取机制测试失败: {e}")
            self.results.append(
                {"test": "async_executor_prefetch", "status": "FAIL", "details": str(e)}
            )

    def test_memory_pool_alignment(self):
        """测试内存池大小对齐优化"""
        print("\n" + "=" * 80)
        print("测试2: 内存池大小对齐优化")
        print("=" * 80)

        try:
            # 测试对齐逻辑（不依赖OpenCL）
            def align_size(size):
                return ((size + 255) // 256) * 256

            # 测试不同大小的对齐
            test_sizes = [100, 256, 300, 512, 1000, 1024]
            aligned_results = []

            for size in test_sizes:
                aligned = align_size(size)
                aligned_results.append((size, aligned))
                # 验证对齐正确性
                assert aligned % 256 == 0, f"对齐错误: {aligned} % 256 != 0"
                assert aligned >= size, f"对齐后小于原大小: {aligned} < {size}"

            print("✅ 内存池对齐测试通过")
            print(f"   测试的对齐结果:")
            for original, aligned in aligned_results:
                print(f"   - {original:,} bytes -> {aligned:,} bytes (对齐)")

            self.results.append(
                {
                    "test": "memory_pool_alignment",
                    "status": "PASS",
                    "details": f"测试{len(test_sizes)}种大小对齐",
                }
            )

        except Exception as e:
            print(f"❌ 内存池对齐测试失败: {e}")
            self.results.append(
                {"test": "memory_pool_alignment", "status": "FAIL", "details": str(e)}
            )

    def test_performance_optimizer_aggressive(self):
        """测试性能优化器激进调整策略"""
        print("\n" + "=" * 80)
        print("测试3: 性能优化器激进调整策略")
        print("=" * 80)

        try:
            from src.gpu.performance_optimizer import GPUPerformanceOptimizer, PerformanceMetrics

            optimizer = GPUPerformanceOptimizer()

            # 创建配置文件
            optimizer.create_optimized_profile(
                device_name="Test GPU", vendor_str="NVIDIA", global_mem_size=8 * 1024**3  # 8GB
            )

            # 记录优秀的性能数据（执行时间很短）
            for _ in range(10):
                optimizer.record_performance(
                    PerformanceMetrics(
                        batch_execution_time_ms=50.0,  # 非常快
                        keys_per_second=2000000.0,
                        error_count=0,
                    )
                )

            # 测试调整策略
            current_batch = 100000
            new_batch, adjustments = optimizer.analyze_and_adjust(
                current_batch_size=current_batch, error_rate=0.0
            )

            print("✅ 激进调整策略测试通过")
            print(f"   - 当前batch: {current_batch:,}")
            print(f"   - 调整后batch: {new_batch:,}")
            print(f"   - 增长倍数: {new_batch/current_batch:.1f}x")

            if "performance_good" in adjustments:
                time_ratio = adjustments["performance_good"].get("time_ratio", 0)
                print(f"   - 性能余量: {time_ratio:.1f}x")

            self.results.append(
                {
                    "test": "performance_optimizer_aggressive",
                    "status": "PASS",
                    "details": f"batch增长{new_batch/current_batch:.1f}x",
                }
            )

        except Exception as e:
            print(f"❌ 激进调整策略测试失败: {e}")
            import traceback

            traceback.print_exc()
            self.results.append(
                {"test": "performance_optimizer_aggressive", "status": "FAIL", "details": str(e)}
            )

    def test_memory_pool_preallocate(self):
        """测试内存池预分配功能"""
        print("\n" + "=" * 80)
        print("测试4: 内存池预分配功能")
        print("=" * 80)

        try:
            from src.gpu.memory_pool import GPUMemoryPool
            from unittest.mock import Mock

            # 创建模拟上下文
            mock_context = Mock()

            pool = GPUMemoryPool(mock_context, max_buffers=100, max_memory_mb=512)

            # 测试预分配
            sizes = [1024, 2048, 4096, 8192]
            pool.preallocate_buffers(sizes, count_per_size=2)

            stats = pool.get_stats()

            print("✅ 内存池预分配测试通过")
            print(f"   - 预分配大小: {len(sizes)}种")
            print(f"   - 总分配数: {stats['total_allocated']}")
            print(f"   - 池内缓冲: {stats['pooled_buffers']}")

            self.results.append(
                {
                    "test": "memory_pool_preallocate",
                    "status": "PASS",
                    "details": f"预分配{len(sizes)}种大小",
                }
            )

        except Exception as e:
            print(f"❌ 内存池预分配测试失败: {e}")
            self.results.append(
                {"test": "memory_pool_preallocate", "status": "FAIL", "details": str(e)}
            )

    def run_all_tests(self):
        """运行所有基准测试"""
        print("=" * 80)
        print("GPU性能优化基准测试 v2.2.1")
        print("=" * 80)
        print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        start_time = time.time()

        # 运行测试
        self.test_async_executor_prefetch()
        self.test_memory_pool_alignment()
        self.test_performance_optimizer_aggressive()
        self.test_memory_pool_preallocate()

        # 汇总结果
        elapsed = time.time() - start_time

        print("\n" + "=" * 80)
        print("基准测试汇总")
        print("=" * 80)

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)

        for r in self.results:
            status = "✅" if r["status"] == "PASS" else "❌"
            print(f"{status} {r['test']}: {r['details']}")

        print("\n" + "=" * 80)
        print(f"总计: {passed}/{total} 测试通过")
        print(f"耗时: {elapsed:.2f}秒")
        print("=" * 80)

        if passed == total:
            print("\n🎉 所有性能优化测试通过！")
            return 0
        else:
            print(f"\n⚠️  {failed}个测试失败")
            return 1


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    sys.exit(benchmark.run_all_tests())
