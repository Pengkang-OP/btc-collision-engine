#!/usr/bin/env python3
"""
性能基线测试工具

建立性能基线,检测性能回归。

功能:
- CPU地址生成性能测试
- GPU碰撞引擎性能测试
- 内存池性能测试
- 预计算表性能测试

使用方法:
    # 运行完整性能测试
    python tools/performance_baseline.py

    # 仅测试CPU性能
    python tools/performance_baseline.py --cpu-only

    # 仅测试GPU性能
    python tools/performance_baseline.py --gpu-only

    # 保存到基线文件
    python tools/performance_baseline.py --save-baseline

    # 与基线对比
    python tools/performance_baseline.py --compare-baseline
"""

import json
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

class PerformanceBaseline:
    """性能基线管理器"""

    BASELINE_FILE = Path("performance_baseline.json")

    def __init__(self):
        self.baseline = self.load_baseline()
        self.results = {}

    def load_baseline(self) -> dict:
        """加载性能基线"""
        if self.BASELINE_FILE.exists():
            try:
                with open(self.BASELINE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def save_baseline(self):
        """保存性能基线"""
        with open(self.BASELINE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"✅ 基线已保存: {self.BASELINE_FILE}")

    def compare_with_baseline(self) -> dict:
        """与基线对比"""
        if not self.baseline:
            print("⚠️  无基线数据,请先运行 --save-baseline")
            return {}

        comparison = {}
        for test_name, result in self.results.items():
            if test_name in self.baseline:
                baseline_value = self.baseline[test_name].get("throughput", 0)
                current_value = result.get("throughput", 0)

                if baseline_value > 0:
                    change = ((current_value - baseline_value) / baseline_value) * 100
                    comparison[test_name] = {
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change,
                        "status": "✅ 提升" if change >= 0 else "❌ 下降",
                    }

        return comparison

    def test_cpu_address_generation(self, iterations=10000) -> dict:
        """测试CPU地址生成性能"""
        from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator

        print("\n🔍 测试CPU地址生成性能...")
        generator = OptimizedP2PKHAddressGenerator()

        # 预热
        for _ in range(100):
            pk = secrets.token_bytes(32)
            generator.generate_address(pk)

        # 正式测试
        start_time = time.time()
        for _ in range(iterations):
            pk = secrets.token_bytes(32)
            generator.generate_address(pk)
        elapsed = time.time() - start_time

        throughput = iterations / elapsed

        result = {
            "test_name": "CPU地址生成",
            "iterations": iterations,
            "elapsed_seconds": round(elapsed, 2),
            "throughput": round(throughput, 2),
            "unit": "keys/s",
        }

        print(f"  ✅ 完成: {throughput:,.0f} keys/s")
        return result

    def test_memory_pool_performance(self, iterations=50000) -> dict:
        """测试内存池性能"""
        from src.core.memory_pool import get_pool_manager

        print("\n🔍 测试内存池性能...")
        pool_manager = get_pool_manager()
        pool_manager.initialize()
        ecpoint_pool = pool_manager.get_ecpoint_pool()

        # 测试带池性能
        start_time = time.time()
        for _ in range(iterations):
            ecpoint_pool.acquire()
            # 不使用release,让池自动管理
        elapsed_with_pool = time.time() - start_time

        # 测试不带池性能(直接创建对象)
        from src.core.secp256k1 import ECPoint, Secp256k1

        start_time = time.time()
        for _ in range(iterations):
            ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        elapsed_without_pool = time.time() - start_time

        speedup = elapsed_without_pool / elapsed_with_pool if elapsed_with_pool > 0 else 1.0

        result = {
            "test_name": "内存池性能",
            "iterations": iterations,
            "with_pool_seconds": round(elapsed_with_pool, 3),
            "without_pool_seconds": round(elapsed_without_pool, 3),
            "speedup": round(speedup, 2),
            "unit": "x加速",
        }

        print(f"  ✅ 完成: {speedup:.2f}x加速")
        return result

    def test_precomputed_table_performance(self, iterations=5000) -> dict:
        """测试预计算表性能"""
        from src.core.precomputed_table import get_precomputed_table
        from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1

        print("\n🔍 测试预计算表性能...")
        ec = EllipticCurve(Secp256k1)
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

        # 测试不带预计算表
        start_time = time.time()
        for _ in range(iterations):
            k = int.from_bytes(secrets.token_bytes(32), "big") % Secp256k1.N
            ec.scalar_multiply(k, G)
        elapsed_standard = time.time() - start_time

        # 测试带预计算表
        table = get_precomputed_table(window_size=8)
        start_time = time.time()
        for _ in range(iterations):
            k = int.from_bytes(secrets.token_bytes(32), "big") % Secp256k1.N
            table.scalar_multiply_with_table(k, ec)
        elapsed_optimized = time.time() - start_time

        speedup = elapsed_standard / elapsed_optimized if elapsed_optimized > 0 else 1.0

        result = {
            "test_name": "预计算表性能",
            "iterations": iterations,
            "standard_seconds": round(elapsed_standard, 3),
            "optimized_seconds": round(elapsed_optimized, 3),
            "speedup": round(speedup, 2),
            "unit": "x加速",
        }

        print(f"  ✅ 完成: {speedup:.2f}x加速")
        return result

    def test_gpu_performance(self, batch_size=10000, duration=10) -> dict | None:
        """测试GPU性能"""
        try:
            from src.gpu.collision_engine import GPUCollisionEngine

            from src.gpu.device import GPUDeviceDetector

            print("\n🔍 测试GPU性能...")

            # 检测GPU
            devices = GPUDeviceDetector.detect_devices()
            if not devices:
                print("  ⚠️  未检测到GPU,跳过GPU测试")
                return None

            # 初始化GPU引擎
            engine = GPUCollisionEngine()
            engine.initialize(device_index=0, batch_size=batch_size)

            # 预热
            print("  预热GPU...")
            engine.start()
            time.sleep(2)

            # 正式测试
            print(f"  运行{duration}秒...")
            engine.reset_stats()
            time.sleep(duration)

            # 获取统计
            report = engine.get_performance_report()

            # 停止引擎
            engine.stop()
            engine.cleanup()

            throughput = report.get("avg_throughput_keys_per_sec", 0)

            result = {
                "test_name": "GPU碰撞引擎",
                "gpu_name": devices[0]["name"],
                "batch_size": batch_size,
                "duration_seconds": duration,
                "throughput": round(throughput, 2),
                "unit": "keys/s",
            }

            print(f"  ✅ 完成: {throughput:,.0f} keys/s")
            return result

        except Exception as e:
            print(f"  ⚠️  GPU测试失败: {e}")
            return None

    def run_all_tests(self, cpu_only=False, gpu_only=False):
        """运行所有测试"""
        print("=" * 80)
        print("🚀 性能基线测试")
        print("=" * 80)

        if not gpu_only:
            # CPU测试
            self.results["cpu_address_generation"] = self.test_cpu_address_generation()
            self.results["memory_pool"] = self.test_memory_pool_performance()
            self.results["precomputed_table"] = self.test_precomputed_table_performance()

        if not cpu_only:
            # GPU测试
            gpu_result = self.test_gpu_performance()
            if gpu_result:
                self.results["gpu_collision"] = gpu_result

        # 打印总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 80)
        print("📊 性能测试总结")
        print("=" * 80)

        for test_name, result in self.results.items():
            print(f"\n{result['test_name']}:")
            print(f"  吞吐量: {result['throughput']:,.2f} {result['unit']}")

        # 与基线对比
        if self.baseline:
            print("\n" + "=" * 80)
            print("📈 与基线对比")
            print("=" * 80)

            comparison = self.compare_with_baseline()
            for test_name, comp in comparison.items():
                print(f"\n{test_name}:")
                print(f"  基线: {comp['baseline']:,.2f}")
                print(f"  当前: {comp['current']:,.2f}")
                print(f"  变化: {comp['change_percent']:+.2f}% {comp['status']}")

        print("\n" + "=" * 80)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="性能基线测试工具")
    parser.add_argument("--cpu-only", action="store_true", help="仅测试CPU性能")
    parser.add_argument("--gpu-only", action="store_true", help="仅测试GPU性能")
    parser.add_argument("--save-baseline", action="store_true", help="保存为基线")
    parser.add_argument("--compare-baseline", action="store_true", help="与基线对比")

    args = parser.parse_args()

    baseline = PerformanceBaseline()
    baseline.run_all_tests(cpu_only=args.cpu_only, gpu_only=args.gpu_only)

    if args.save_baseline:
        baseline.results["timestamp"] = datetime.now().isoformat()
        baseline.save_baseline()

    if args.compare_baseline:
        comparison = baseline.compare_with_baseline()
        if comparison:
            # 检查是否有性能下降
            regressions = [k for k, v in comparison.items() if v["change_percent"] < -5]
            if regressions:
                print(f"\n⚠️  发现性能下降的测试: {', '.join(regressions)}")
                sys.exit(1)


if __name__ == "__main__":
    main()
