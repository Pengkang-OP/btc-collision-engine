#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU碰撞引擎综合性能测试

测试内容：
1. GPU设备信息和配置
2. 基准性能测试（30秒）
3. 压力测试（60秒）
4. 内存使用监控
5. 性能稳定性测试
6. 生成详细报告
"""

import sys
import os
import time
import json
import statistics
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.collision.gpu.engine import GPUCollisionEngine
from src.collision.targets.resolver import TargetResolver


class GPUPerformanceTester:
    """GPU性能测试器"""

    def __init__(self, test_duration_benchmark=30, test_duration_stress=60):
        """
        初始化测试器

        Args:
            test_duration_benchmark: 基准测试时长（秒）
            test_duration_stress: 压力测试时长（秒）
        """
        self.test_duration_benchmark = test_duration_benchmark
        self.test_duration_stress = test_duration_stress
        self.results = {
            "test_time": datetime.now().isoformat(),
            "device_info": {},
            "benchmark": {},
            "stress_test": {},
            "memory_usage": {},
            "stability": {},
        }

    def load_test_addresses(self, count=10):
        """加载测试地址"""
        print("\n" + "=" * 80)
        print("  步骤1: 加载测试地址")
        print("=" * 80)

        # 从文件加载
        address_file = project_root / "btc_addresses_sorted.txt.txt"
        resolver = TargetResolver(enable_cache=True)
        addresses = resolver.load_from_file(str(address_file))

        # 取前N个地址
        test_addresses = set(list(addresses)[:count])

        print(f"✓ 从文件加载 {len(addresses)} 个地址")
        print(f"✓ 使用 {len(test_addresses)} 个地址进行测试")

        return test_addresses

    def initialize_gpu_engine(self, targets, batch_size=None):
        """初始化GPU引擎"""
        print("\n" + "=" * 80)
        print("  步骤2: 初始化GPU引擎")
        print("=" * 80)

        stats_history = []

        def on_progress(stats):
            stats_history.append(
                {
                    "timestamp": time.time(),
                    "total_checked": stats.total_checked,
                    "speed": stats.speed,
                    "matches": len(stats.matches),
                }
            )

        def on_match(match_info):
            print(f"  🎯 发现匹配: {match_info.get('address', 'N/A')}")

        start_init = time.time()

        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,  # 自动选择最佳GPU
            batch_size=batch_size,  # None=自动计算
            on_progress=on_progress,
            on_match=on_match,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True,
        )

        init_time = time.time() - start_init

        # 获取设备信息
        device_info = engine._gpu_device.get_device_info()
        memory_efficiency = getattr(engine._gpu_device, "memory_efficiency", 0.70)

        self.results["device_info"] = {
            "name": device_info.get("name", "Unknown"),
            "vendor": device_info.get("vendor", "Unknown"),
            "global_mem_gb": device_info.get("global_mem_gb", 0),
            "compute_units": device_info.get("compute_units", 0),
            "memory_efficiency": memory_efficiency,
            "batch_size": engine.batch_size,
            "initialization_time": init_time,
        }

        print(f"✓ GPU设备: {device_info.get('name', 'Unknown')}")
        print(f"✓ 显存: {device_info.get('global_mem_gb', 0):.2f} GB")
        print(f"✓ 计算单元: {device_info.get('compute_units', 0)}")
        print(f"✓ 显存效率: {memory_efficiency*100:.0f}%")
        print(f"✓ 批次大小: {engine.batch_size:,}")
        print(f"✓ 初始化时间: {init_time:.2f}秒")

        return engine, stats_history

    def run_benchmark_test(self, engine, stats_history):
        """运行基准性能测试"""
        print("\n" + "=" * 80)
        print(f"  步骤3: 基准性能测试 ({self.test_duration_benchmark}秒)")
        print("=" * 80)

        engine.start(mode="random")

        start_time = time.time()
        speeds = []

        while time.time() - start_time < self.test_duration_benchmark:
            time.sleep(5)
            if stats_history:
                latest = stats_history[-1]
                elapsed = time.time() - start_time
                speed = latest["speed"]
                speeds.append(speed)

                print(
                    f"  [{elapsed:5.1f}s] {latest['total_checked']:>12,} keys | "
                    f"{speed:>10,.2f} keys/s"
                )

        engine.stop()

        # 统计结果
        if speeds:
            avg_speed = statistics.mean(speeds)
            max_speed = max(speeds)
            min_speed = min(speeds)
            total_keys = stats_history[-1]["total_checked"]

            # 计算稳定性（标准差/平均值）
            if avg_speed > 0:
                stability = (statistics.stdev(speeds) / avg_speed) * 100 if len(speeds) > 1 else 0
            else:
                stability = 0

            self.results["benchmark"] = {
                "duration": self.test_duration_benchmark,
                "total_keys": total_keys,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "min_speed": min_speed,
                "stability_percent": stability,
                "speed_samples": len(speeds),
            }

            print(f"\n  基准测试结果:")
            print(f"    总检查数: {total_keys:,} keys")
            print(f"    平均速度: {avg_speed:,.2f} keys/s")
            print(f"    峰值速度: {max_speed:,.2f} keys/s")
            print(f"    最低速度: {min_speed:,.2f} keys/s")
            print(f"    稳定性: {stability:.2f}% (越低越稳定)")

    def run_stress_test(self, engine, stats_history):
        """运行压力测试"""
        print("\n" + "=" * 80)
        print(f"  步骤4: 压力测试 ({self.test_duration_stress}秒)")
        print("=" * 80)

        # 清空历史记录
        stats_history.clear()

        engine.start(mode="random")

        start_time = time.time()
        speeds = []
        memory_samples = []

        while time.time() - start_time < self.test_duration_stress:
            time.sleep(5)
            if stats_history:
                latest = stats_history[-1]
                elapsed = time.time() - start_time
                speed = latest["speed"]
                speeds.append(speed)

                # 获取内存使用
                import psutil

                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / (1024 * 1024)
                memory_samples.append(memory_mb)

                print(
                    f"  [{elapsed:5.1f}s] {latest['total_checked']:>12,} keys | "
                    f"{speed:>10,.2f} keys/s | "
                    f"内存: {memory_mb:>8,.1f} MB"
                )

        engine.stop()

        # 统计结果
        if speeds:
            avg_speed = statistics.mean(speeds)
            max_speed = max(speeds)
            min_speed = min(speeds)
            total_keys = stats_history[-1]["total_checked"]

            # 内存统计
            if memory_samples:
                avg_memory = statistics.mean(memory_samples)
                max_memory = max(memory_samples)
            else:
                avg_memory = 0
                max_memory = 0

            self.results["stress_test"] = {
                "duration": self.test_duration_stress,
                "total_keys": total_keys,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "min_speed": min_speed,
                "avg_memory_mb": avg_memory,
                "max_memory_mb": max_memory,
            }

            print(f"\n  压力测试结果:")
            print(f"    总检查数: {total_keys:,} keys")
            print(f"    平均速度: {avg_speed:,.2f} keys/s")
            print(f"    峰值速度: {max_speed:,.2f} keys/s")
            print(f"    平均内存: {avg_memory:,.1f} MB")
            print(f"    峰值内存: {max_memory:,.1f} MB")

    def run_stability_test(self, engine, stats_history):
        """运行稳定性测试（短周期多次）"""
        print("\n" + "=" * 80)
        print("  步骤5: 稳定性测试 (5次×10秒)")
        print("=" * 80)

        test_count = 5
        test_duration = 10
        all_speeds = []

        for i in range(test_count):
            stats_history.clear()
            engine.start(mode="random")

            start_time = time.time()
            speeds = []

            while time.time() - start_time < test_duration:
                time.sleep(2)
                if stats_history:
                    speeds.append(stats_history[-1]["speed"])

            engine.stop()

            if speeds:
                avg = statistics.mean([s for s in speeds if s > 0])
                all_speeds.append(avg)
                print(f"  测试 {i+1}/{test_count}: {avg:,.2f} keys/s")
            else:
                all_speeds.append(0)
                print(f"  测试 {i+1}/{test_count}: 0.00 keys/s")

            time.sleep(1)  # 等待资源释放

        # 统计稳定性
        valid_speeds = [s for s in all_speeds if s > 0]
        if valid_speeds:
            overall_avg = statistics.mean(valid_speeds)
            if len(valid_speeds) > 1:
                std_dev = statistics.stdev(valid_speeds)
                cv = (std_dev / overall_avg) * 100  # 变异系数
            else:
                std_dev = 0
                cv = 0

            self.results["stability"] = {
                "test_count": test_count,
                "test_duration": test_duration,
                "overall_avg_speed": overall_avg,
                "std_dev": std_dev,
                "coefficient_of_variation": cv,
                "individual_results": all_speeds,
            }

            print(f"\n  稳定性结果:")
            print(f"    平均速度: {overall_avg:,.2f} keys/s")
            print(f"    标准差: {std_dev:,.2f}")
            print(f"    变异系数: {cv:.2f}% (越低越稳定)")

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 80)
        print("  GPU性能测试报告")
        print("=" * 80)

        # 设备信息
        print(f"\n📊 GPU设备信息:")
        print(f"  设备名称: {self.results['device_info'].get('name', 'N/A')}")
        print(f"  厂商: {self.results['device_info'].get('vendor', 'N/A')}")
        print(f"  显存: {self.results['device_info'].get('global_mem_gb', 0):.2f} GB")
        print(f"  计算单元: {self.results['device_info'].get('compute_units', 0)}")
        print(f"  批次大小: {self.results['device_info'].get('batch_size', 0):,}")

        # 基准测试
        if "avg_speed" in self.results.get("benchmark", {}):
            print(f"\n🏁 基准测试 ({self.results['benchmark']['duration']}秒):")
            print(f"  总检查数: {self.results['benchmark']['total_keys']:>12,} keys")
            print(f"  平均速度: {self.results['benchmark']['avg_speed']:>12,.2f} keys/s")
            print(f"  峰值速度: {self.results['benchmark']['max_speed']:>12,.2f} keys/s")
            print(f"  稳定性: {self.results['benchmark']['stability_percent']:>12.2f}%")

        # 压力测试
        if "avg_speed" in self.results.get("stress_test", {}):
            print(f"\n💪 压力测试 ({self.results['stress_test']['duration']}秒):")
            print(f"  总检查数: {self.results['stress_test']['total_keys']:>12,} keys")
            print(f"  平均速度: {self.results['stress_test']['avg_speed']:>12,.2f} keys/s")
            print(f"  峰值速度: {self.results['stress_test']['max_speed']:>12,.2f} keys/s")
            print(f"  平均内存: {self.results['stress_test']['avg_memory_mb']:>12,.1f} MB")
            print(f"  峰值内存: {self.results['stress_test']['max_memory_mb']:>12,.1f} MB")

        # 稳定性测试
        if "overall_avg_speed" in self.results.get("stability", {}):
            print(f"\n📈 稳定性测试:")
            print(f"  平均速度: {self.results['stability']['overall_avg_speed']:>12,.2f} keys/s")
            print(f"  变异系数: {self.results['stability']['coefficient_of_variation']:>12.2f}%")

        # 综合评估
        print(f"\n⭐ 综合评估:")

        benchmark_speed = self.results.get("benchmark", {}).get("avg_speed", 0)
        stress_speed = self.results.get("stress_test", {}).get("avg_speed", 0)
        stability_cv = self.results.get("stability", {}).get("coefficient_of_variation", 100)

        # 性能评级
        if benchmark_speed > 100000:
            perf_rating = "优秀 ⭐⭐⭐⭐⭐"
        elif benchmark_speed > 50000:
            perf_rating = "良好 ⭐⭐⭐⭐"
        elif benchmark_speed > 10000:
            perf_rating = "中等 ⭐⭐⭐"
        elif benchmark_speed > 1000:
            perf_rating = "一般 ⭐⭐"
        else:
            perf_rating = "较差 ⭐"

        print(f"  性能评级: {perf_rating}")
        print(f"  基准速度: {benchmark_speed:,.2f} keys/s")

        # 稳定性评级
        if stability_cv < 5:
            stab_rating = "非常稳定 ⭐⭐⭐⭐⭐"
        elif stability_cv < 10:
            stab_rating = "稳定 ⭐⭐⭐⭐"
        elif stability_cv < 20:
            stab_rating = "一般 ⭐⭐⭐"
        else:
            stab_rating = "不稳定 ⭐⭐"

        print(f"  稳定性评级: {stab_rating}")

        # 保存报告
        report_file = (
            project_root
            / "test_results"
            / f"gpu_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        os.makedirs(report_file.parent, exist_ok=True)

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n📄 详细报告已保存: {report_file}")
        print("=" * 80)

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("  GPU碰撞引擎综合性能测试")
        print("=" * 80)
        print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 步骤1: 加载地址
        test_addresses = self.load_test_addresses(count=10)

        # 步骤2: 初始化引擎
        engine, stats_history = self.initialize_gpu_engine(test_addresses)

        try:
            # 步骤3: 基准测试
            self.run_benchmark_test(engine, stats_history)
            time.sleep(2)  # 等待资源释放

            # 步骤4: 压力测试
            self.run_stress_test(engine, stats_history)
            time.sleep(2)

            # 步骤5: 稳定性测试
            self.run_stability_test(engine, stats_history)

            # 生成报告
            self.generate_report()

        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
        except Exception as e:
            print(f"\n\n❌ 测试过程出错: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # 清理资源
            if engine:
                engine.stop()
                if hasattr(engine, "_gpu_device"):
                    engine._gpu_device.cleanup()

            print("\n✓ 测试完成，资源已清理")


def main():
    """主函数"""
    tester = GPUPerformanceTester(
        test_duration_benchmark=30, test_duration_stress=60  # 基准测试30秒  # 压力测试60秒
    )

    tester.run_all_tests()


if __name__ == "__main__":
    main()
