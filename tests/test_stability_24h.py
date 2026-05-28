#!/usr/bin/env python3
"""GPU碰撞引擎24小时稳定性测试.

测试目标:
1. 验证长时间运行无内存泄漏
2. 验证性能稳定性(无显著下降)
3. 验证错误率为0
4. 记录性能趋势

运行时间: 24小时(可配置)
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# 添加项目根目录到路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
from src.collision.gpu.engine import GPUCollisionEngine
from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor


class StabilityTestRunner:
    """稳定性测试运行器."""

    def __init__(self, duration_hours: int = 24, check_interval: int = 300):
        """初始化稳定性测试.

        Args:
            duration_hours: 测试时长(小时),默认24小时
            check_interval: 检查间隔(秒),默认5分钟

        """
        self.duration_hours = duration_hours
        self.check_interval = check_interval
        self.duration_seconds = duration_hours * 3600
        self.engine = None
        self.metrics_history: list[dict[str, Any]] = []
        self.start_time = None
        self.test_data_dir = _PROJECT_ROOT / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)
        self._monitor = None  # GPUPerformanceMonitor 实例

    def print_header(self, title: str):
        """打印标题."""
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")

    def log_metrics(self, metrics: dict[str, Any]):
        """记录性能指标."""
        timestamp = datetime.now().isoformat()
        record = {
            "timestamp": timestamp,
            "elapsed_hours": (time.time() - self.start_time) / 3600,
            **metrics,
        }
        self.metrics_history.append(record)

        # 打印当前指标
        print(
            f"  [{record['elapsed_hours']:.2f}h] "
            f"吞吐量: {metrics['throughput']:>10,.0f} keys/s | "
            f"错误率: {metrics['error_rate']:>6.2f}% | "
            f"显存: {metrics['memory_mb']:>8.2f} MB | "
            f"批次: {metrics['total_batches']:>6}",
        )

    def save_intermediate_report(self):
        """保存中间报告."""
        report = {
            "test_start": self.start_time,
            "test_duration_hours": self.duration_hours,
            "current_elapsed_hours": (time.time() - self.start_time) / 3600,
            "check_interval_seconds": self.check_interval,
            "total_checks": len(self.metrics_history),
            "metrics_history": self.metrics_history,
        }

        report_path = self.test_data_dir / "stability_test_intermediate.json"
        with Path(report_path).open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def check_memory_leak(self) -> bool:
        """检查内存泄漏."""
        if len(self.metrics_history) < 2:
            return True

        # 比较初始和当前显存使用
        initial_memory = self.metrics_history[0]["memory_mb"]
        current_memory = self.metrics_history[-1]["memory_mb"]

        # 防止除零: 初始显存为0时视为无泄漏（监控未采集到数据）
        if initial_memory <= 0:
            return True

        # 显存增长超过10%视为内存泄漏
        growth_rate = (current_memory - initial_memory) / initial_memory * 100
        has_leak = growth_rate > 10.0

        if has_leak:
            print("\nWARN  警告: 检测到显存泄漏!")
            print(f"   初始显存: {initial_memory:.2f} MB")
            print(f"   当前显存: {current_memory:.2f} MB")
            print(f"   增长率: {growth_rate:.2f}%")

        return not has_leak

    def check_performance_stability(self) -> bool:
        """检查性能稳定性."""
        if len(self.metrics_history) < 2:
            return True

        # 计算吞吐量下降率
        initial_throughput = self.metrics_history[0]["throughput"]
        current_throughput = self.metrics_history[-1]["throughput"]

        if initial_throughput == 0:
            return True

        decline_rate = (initial_throughput - current_throughput) / initial_throughput * 100
        is_stable = decline_rate < 10.0  # 下降超过10%视为不稳定

        if not is_stable:
            print("\nWARN  警告: 检测到性能下降!")
            print(f"   初始吞吐量: {initial_throughput:,.0f} keys/s")
            print(f"   当前吞吐量: {current_throughput:,.0f} keys/s")
            print(f"   下降率: {decline_rate:.2f}%")

        return is_stable

    def check_error_rate(self) -> bool:
        """检查错误率."""
        if not self.metrics_history:
            return True

        latest_error_rate = self.metrics_history[-1]["error_rate"]
        is_ok = latest_error_rate == 0.0

        if not is_ok:
            print("\nERR 错误: 检测到错误率 > 0!")
            print(f"   当前错误率: {latest_error_rate:.2f}%")

        return is_ok

    def generate_final_report(self) -> dict[str, Any]:
        """生成最终报告."""
        if not self.metrics_history:
            return {}

        throughputs = [m["throughput"] for m in self.metrics_history]
        error_rates = [m["error_rate"] for m in self.metrics_history]
        memory_usages = [m["memory_mb"] for m in self.metrics_history]

        report = {
            "test_info": {
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_hours": self.duration_hours,
                "total_checks": len(self.metrics_history),
                "check_interval_seconds": self.check_interval,
            },
            "performance_summary": {
                "avg_throughput": sum(throughputs) / len(throughputs),
                "max_throughput": max(throughputs),
                "min_throughput": min(throughputs),
                "throughput_std": (
                    sum((x - sum(throughputs) / len(throughputs)) ** 2 for x in throughputs)
                    / len(throughputs)
                )
                ** 0.5,
            },
            "error_summary": {
                "avg_error_rate": sum(error_rates) / len(error_rates),
                "max_error_rate": max(error_rates),
                "zero_error_checks": sum(1 for e in error_rates if e == 0.0),
            },
            "memory_summary": {
                "avg_memory_mb": sum(memory_usages) / len(memory_usages),
                "max_memory_mb": max(memory_usages),
                "min_memory_mb": min(memory_usages),
                "memory_growth_mb": memory_usages[-1] - memory_usages[0],
                "memory_growth_percent": (memory_usages[-1] - memory_usages[0]) / memory_usages[0] * 100,
            },
            "stability_checks": {
                "memory_leak_detected": not self.check_memory_leak(),
                "performance_unstable": not self.check_performance_stability(),
                "errors_detected": not self.check_error_rate(),
            },
            "metrics_history": self.metrics_history,
        }

        return report

    def run(self):
        """运行稳定性测试."""
        self.print_header("GPU碰撞引擎24小时稳定性测试")

        print("测试配置:")
        print(f"  测试时长: {self.duration_hours} 小时")
        print(f"  检查间隔: {self.check_interval} 秒")
        print("  批次大小: 262,144")
        print("  目标地址: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"预计结束: {(datetime.now() + timedelta(hours=self.duration_hours)).strftime('%Y-%m-%d %H:%M:%S')}",
        )

        # 初始化引擎
        print("\n初始化GPU引擎...")
        test_targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

        self.engine = GPUCollisionEngine(
            targets=test_targets,
            device_index=-1,  # 自动选择最佳GPU
            batch_size=262144,
            use_gpu_memory_pool=True,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 初始化 GPU 性能监控器 (引擎默认不初始化)
        self._monitor = GPUPerformanceMonitor(engine=self.engine)
        # 注入到引擎，确保引擎的 record_kernel_metrics() 能向监控器推送数据
        self.engine.gpu_performance_monitor = self._monitor
        self._monitor.start()

        self.start_time = time.time()

        # 启动引擎
        def run_engine():
            self.engine.start()

        thread = threading.Thread(target=run_engine, daemon=True)
        thread.start()

        print("\n引擎已启动,开始监控...\n")
        print(f"  {'时间':>8} | {'吞吐量':>15} | {'错误率':>8} | {'显存':>10} | {'批次':>6}")
        print(f"  {'(小时)':>8} | {'(keys/s)':>15} | {'(%)':>8} | {'(MB)':>10} | {'':>6}")
        print(f"  {'-' * 8}-+-{'-' * 15}-+-{'-' * 8}-+-{'-' * 10}-+-{'-' * 6}")

        try:
            # 主循环
            elapsed = 0
            while elapsed < self.duration_seconds:
                # 等待检查间隔
                time.sleep(self.check_interval)
                elapsed = time.time() - self.start_time

                # 获取性能报告
                monitor = self._monitor
                report = monitor.get_performance_report()

                # 记录指标
                metrics = {
                    "throughput": report.avg_throughput_keys_per_sec,
                    "error_rate": report.error_rate_percent,
                    "memory_mb": report.memory_usage_avg_mb,
                    "total_batches": report.total_batches,
                    "total_keys": report.total_keys_processed,
                }

                self.log_metrics(metrics)

                # 保存中间报告
                self.save_intermediate_report()

                # 检查异常
                if not self.check_memory_leak():
                    print("ERR 测试失败: 检测到内存泄漏")
                    break

                if not self.check_performance_stability():
                    print("WARN  警告: 性能下降,继续观察...")

                if not self.check_error_rate():
                    print("ERR 测试失败: 检测到错误")
                    break

            # 停止引擎
            print("\n停止引擎...")
            self.engine.stop()
            thread.join(timeout=10)

            # 停止监控器
            if self._monitor:
                try:
                    self._monitor.stop()
                except (RuntimeError, OSError):
                    pass  # 监控器已停止或清理失败，不影响测试报告

            # 生成最终报告
            print("\n生成最终报告...")
            final_report = self.generate_final_report()

            report_path = self.test_data_dir / "stability_test_final_report.json"
            with Path(report_path).open("w", encoding="utf-8") as f:
                json.dump(final_report, f, indent=2, ensure_ascii=False)

            # 打印总结
            self.print_header("测试总结")

            perf = final_report["performance_summary"]
            mem = final_report["memory_summary"]
            err = final_report["error_summary"]
            checks = final_report["stability_checks"]

            print("性能指标:")
            print(f"  平均吞吐量: {perf['avg_throughput']:,.0f} keys/s")
            print(f"  峰值吞吐量: {perf['max_throughput']:,.0f} keys/s")
            print(f"  最低吞吐量: {perf['min_throughput']:,.0f} keys/s")
            print(f"  标准差: {perf['throughput_std']:,.0f} keys/s")

            print("\n错误率:")
            print(f"  平均错误率: {err['avg_error_rate']:.4f}%")
            print(f"  最大错误率: {err['max_error_rate']:.4f}%")
            print(
                f"  零错误检查: {err['zero_error_checks']}/{final_report['test_info']['total_checks']}",
            )

            print("\n显存使用:")
            print(f"  平均显存: {mem['avg_memory_mb']:.2f} MB")
            print(f"  峰值显存: {mem['max_memory_mb']:.2f} MB")
            print(f"  显存增长: {mem['memory_growth_mb']:.2f} MB ({mem['memory_growth_percent']:.2f}%)")

            print("\n稳定性检查:")
            print(
                f"  内存泄漏: {'[FAIL] 检测到' if checks['memory_leak_detected'] else '[PASS] 未检测到'}",
            )
            print(f"  性能稳定: {'[FAIL] 不稳定' if checks['performance_unstable'] else '[PASS] 稳定'}")
            print(f"  错误检测: {'[FAIL] 有错误' if checks['errors_detected'] else '[PASS] 无错误'}")

            # 总体评估
            all_passed = not any(checks.values())
            print(f"\n{'=' * 80}")
            if all_passed:
                print("  [PASS] 24小时稳定性测试通过!")
            else:
                print("  [WARN] 24小时稳定性测试未完全通过,请检查上述警告")
            print(f"{'=' * 80}")

            print(f"\n详细报告已保存: {report_path}")
            print(f"中间数据已保存: {self.test_data_dir / 'stability_test_intermediate.json'}")

        except KeyboardInterrupt:
            print("\n\nWARN  用户中断测试")
            if self.engine:
                self.engine.stop()
            if self._monitor:
                try:
                    self._monitor.stop()
                except (RuntimeError, OSError):
                    pass  # 中断路径下监控器清理

            # 保存已收集的数据
            self.save_intermediate_report()
            print(f"已保存中间数据到: {self.test_data_dir / 'stability_test_intermediate.json'}")

        except Exception as e:
            print(f"\n\n[ERROR] 测试异常: {e}")
            import traceback

            traceback.print_exc()

            if self.engine:
                self.engine.stop()
            if self._monitor:
                try:
                    self._monitor.stop()
                except (RuntimeError, OSError):
                    pass  # 异常路径下监控器清理


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="GPU碰撞引擎24小时稳定性测试")
    parser.add_argument("--hours", type=float, default=24, help="测试时长(小时),默认24")
    parser.add_argument("--interval", type=int, default=300, help="检查间隔(秒),默认300")

    args = parser.parse_args()

    runner = StabilityTestRunner(duration_hours=args.hours, check_interval=args.interval)

    runner.run()


if __name__ == "__main__":
    main()
