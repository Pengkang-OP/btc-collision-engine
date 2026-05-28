"""Performance benchmark utility.

Tests performance improvements of various optimization strategies:
- SIMD vectorization
- Multi-process parallel
- Bloom Filter deduplication
- GPU acceleration (if available)

使用方法:
    python -m src.utils.performance_benchmark
"""

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime
from typing import Any, cast

from . import get_configured_logger

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("PerformanceBenchmark")


class BenchmarkResult:
    """基准测试结果."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        """初始化基准测试结果。.

        Args:
            name: 测试名称
            config: 配置字典
        """
        self.name = name
        self.config = config
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.total_processed = 0
        self.matches_found = 0
        self.avg_speed = 0.0
        self.peak_speed = 0.0
        self.memory_usage_mb = 0.0

    def start(self) -> None:
        """开始测试."""
        self.start_time = time.time()

    def stop(self) -> None:
        """停止测试."""
        self.end_time = time.time()

        if self.end_time is not None and self.start_time is not None:
            elapsed = self.end_time - self.start_time
        else:
            elapsed = 0.0
        self.avg_speed = self.total_processed / elapsed if elapsed > 0 else 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "name": self.name,
            "config": self.config,
            "elapsed_seconds": (
                (self.end_time - self.start_time)
                if self.end_time is not None and self.start_time is not None
                else 0
            ),
            "total_processed": self.total_processed,
            "matches_found": self.matches_found,
            "avg_keys_per_second": self.avg_speed,
            "peak_keys_per_second": self.peak_speed,
            "memory_usage_mb": self.memory_usage_mb,
        }


class PerformanceBenchmark:
    """性能基准测试器."""

    def __init__(self) -> None:
        """初始化基准测试器."""
        self.results: list[BenchmarkResult] = []

    def benchmark_simd_optimization(self, batch_sizes: list[int] | None = None) -> None:
        """测试SIMD优化性能.

        Args:
            batch_sizes: 要测试的批次大小列表

        """
        if batch_sizes is None:
            batch_sizes = [10000, 50000, 100000, 500000]

        print("\n" + "=" * 70)
        print("SIMD向量化优化基准测试")
        print("=" * 70)

        from src.core.simd_optimizer import SIMDVectorizedOperations

        for batch_size in batch_sizes:
            print(f"\n测试批次大小: {batch_size:,}")

            # 创建优化器
            optimizer = SIMDVectorizedOperations(batch_size=batch_size)

            # 生成测试数据
            test_data = [os.urandom(32) for _ in range(batch_size)]

            # 测试批量SHA256
            result = BenchmarkResult(
                f"SIMD_SHA256_{batch_size}",
                {"batch_size": batch_size, "operation": "SHA256"},
            )
            result.start()

            optimizer.batch_sha256(test_data)
            result.total_processed = batch_size
            result.stop()

            print(
                f"  SHA256: {result.avg_speed:,.0f} keys/s, "
                f"耗时: {cast('float', result.end_time) - cast('float', result.start_time):.3f}s",
            )
            self.results.append(result)

            # 测试批量Hash160
            result = BenchmarkResult(
                f"SIMD_HASH160_{batch_size}",
                {"batch_size": batch_size, "operation": "Hash160"},
            )
            result.start()

            optimizer.batch_hash160(test_data)
            result.total_processed = batch_size
            result.stop()

            print(
                f"  Hash160: {result.avg_speed:,.0f} keys/s, "
                f"耗时: {cast('float', result.end_time) - cast('float', result.start_time):.3f}s",
            )
            self.results.append(result)

    def benchmark_multiprocess(self, worker_counts: list[int] | None = None) -> None:
        """测试多进程性能.

        Args:
            worker_counts: 要测试的工作进程数量列表

        """
        import multiprocessing as mp

        if worker_counts is None:
            worker_counts = [1, 2, 4, 8, mp.cpu_count()]

        print("\n" + "=" * 70)
        print("多进程并行基准测试")
        print("=" * 70)

        for num_workers in worker_counts:
            if num_workers > mp.cpu_count():
                print(f"\n跳过 {num_workers} 个工作进程（超过CPU核心数）")
                continue

            print(f"\n测试工作进程数: {num_workers}")

            from src.collision.multiprocess_engine import MultiProcessCollisionEngine

            # 创建引擎
            engine = MultiProcessCollisionEngine(
                num_workers=num_workers,
                batch_size=10000,
                target_addresses=["test_address"],  # 假地址
            )

            # 定义私钥生成函数
            def generate_keys(batch_size: int) -> list[bytes]:
                return [os.urandom(32) for _ in range(batch_size)]

            # 简化的地址生成器
            class MockAddressGenerator:
                def generate_from_private_key(self, pk: bytes) -> str:
                    # 模拟地址生成
                    import hashlib

                    return hashlib.sha256(pk).hexdigest()[:34]

            # 启动引擎
            cast("Any", engine).start(
                generator_func=generate_keys,
                address_generator=MockAddressGenerator(),
            )

            # 提交任务并测试
            result = BenchmarkResult(
                f"Multiprocess_{num_workers}",
                {"num_workers": num_workers, "batch_size": 10000},
            )
            result.start()

            # 提交10个任务
            for _ in range(10):
                engine.submit_task()
                time.sleep(0.1)

            # 获取统计
            time.sleep(2)
            stats = engine.get_stats()
            result.total_processed = stats.get("total_checked", 0)
            result.stop()

            print(f"  速度: {result.avg_speed:,.0f} keys/s, 总检测: {result.total_processed:,}")
            self.results.append(result)

            # 清理
            engine.stop()
            engine.cleanup()

    def benchmark_bloom_filter(self, sizes: list[int] | None = None) -> None:
        """测试Bloom Filter性能.

        Args:
            sizes: 要测试的元素数量列表

        """
        if sizes is None:
            sizes = [100000, 1000000, 10000000]

        print("\n" + "=" * 70)
        print("Bloom Filter去重基准测试 - 模块已移除，跳过")
        print("=" * 70)

    def benchmark_comparison(self) -> None:
        """对比测试：优化前 vs 优化后."""
        print("\n" + "=" * 70)
        print("性能对比测试")
        print("=" * 70)

        import hashlib

        batch_size = 100000
        test_data = [os.urandom(32) for _ in range(batch_size)]

        # 测试1: 传统方式（循环）
        print(f"\n传统方式（循环）- {batch_size:,}个元素")
        result_traditional = BenchmarkResult(
            "Traditional_Loop",
            {"method": "loop", "batch_size": batch_size},
        )
        result_traditional.start()

        traditional_results = []
        for data in test_data:
            traditional_results.append(hashlib.sha256(data).digest())

        result_traditional.total_processed = batch_size
        result_traditional.stop()

        print(f"  速度: {result_traditional.avg_speed:,.0f} keys/s")
        self.results.append(result_traditional)

        # 测试2: SIMD优化（列表推导式）
        print(f"\nSIMD优化（列表推导式）- {batch_size:,}个元素")
        result_simd = BenchmarkResult(
            "SIMD_ListComp",
            {"method": "list_comprehension", "batch_size": batch_size},
        )
        result_simd.start()

        [hashlib.sha256(data).digest() for data in test_data]
        result_simd.total_processed = batch_size
        result_simd.stop()

        print(f"  速度: {result_simd.avg_speed:,.0f} keys/s")
        self.results.append(result_simd)

        # 计算加速比
        speedup = (
            result_simd.avg_speed / result_traditional.avg_speed
            if result_traditional.avg_speed > 0
            else 0
        )
        print(f"\n加速比: {speedup:.2f}x")

    def run_all_benchmarks(self) -> None:
        """运行所有基准测试."""
        print("=" * 70)
        print("BTC碰撞引擎 - 性能基准测试套件")
        print("=" * 70)
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 运行各项测试
        self.benchmark_simd_optimization()
        self.benchmark_multiprocess()
        self.benchmark_bloom_filter()
        self.benchmark_comparison()

        # 输出总结
        self.print_summary()

    def print_summary(self) -> None:
        """打印测试总结."""
        print("\n" + "=" * 70)
        print("基准测试总结")
        print("=" * 70)

        for result in self.results:
            d = result.to_dict()
            print(f"\n{d['name']}:")
            print(f"  速度: {d['avg_keys_per_second']:,.0f} keys/s")
            print(f"  耗时: {d['elapsed_seconds']:.3f}s")
            print(f"  处理量: {d['total_processed']:,}")

    def save_results(self, filepath: str = "benchmark_results.json") -> None:
        """保存测试结果到文件.

        Args:
            filepath: 输出文件路径

        """
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "results": [r.to_dict() for r in self.results],
        }

        with pathlib.Path(filepath).open("w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        print(f"\n测试结果已保存到: {filepath}")

    def _get_system_info(self) -> dict[str, Any]:
        """获取系统信息."""
        import multiprocessing as mp

        import psutil

        return {
            "cpu_count": mp.cpu_count(),
            "cpu_frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "total_memory_gb": psutil.virtual_memory().total / (1024**3),
            "python_version": sys.version,
            "platform": sys.platform,
        }


def main() -> None:
    """主函数."""
    parser = argparse.ArgumentParser(description="性能基准测试工具")
    parser.add_argument(
        "--test",
        type=str,
        choices=["simd", "multiprocess", "bloom", "comparison", "all"],
        default="all",
        help="选择要运行的测试",
    )
    parser.add_argument("--output", type=str, default="benchmark_results.json", help="结果输出文件路径")

    args = parser.parse_args()

    benchmark = PerformanceBenchmark()

    if args.test == "simd":
        benchmark.benchmark_simd_optimization()
    elif args.test == "multiprocess":
        benchmark.benchmark_multiprocess()
    elif args.test == "bloom":
        benchmark.benchmark_bloom_filter()
    elif args.test == "comparison":
        benchmark.benchmark_comparison()
    else:
        benchmark.run_all_benchmarks()

    # 保存结果
    benchmark.save_results(args.output)


if __name__ == "__main__":
    main()
