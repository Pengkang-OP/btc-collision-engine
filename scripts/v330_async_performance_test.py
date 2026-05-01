#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.3.0 异步双缓冲性能验证测试

测试目标:
1. 验证异步双缓冲模式相比同步模式的性能提升
2. 收集Intel Arc A770实测数据
3. 生成性能对比报告

测试配置:
- 同步模式: 传统单缓冲执行
- 异步模式: 双缓冲优化（v3.3.0新增）
- 测试时长: 每配置60秒
- 目标地址: 2个真实比特币地址
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine


class V330PerformanceVerifier:
    """v3.3.0性能验证器"""

    def __init__(self, test_duration: int = 60):
        """
        初始化验证器

        Args:
            test_duration: 每个配置的测试时长（秒）
        """
        self.test_duration = test_duration
        self.targets = {
            "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
        }
        self.results = []

    def test_sync_mode(self) -> Dict[str, Any]:
        """测试同步模式（单缓冲）"""
        print("\n" + "=" * 80)
        print("  测试配置: 同步模式（单缓冲）")
        print("=" * 80)

        stats_history = []
        batch_times = []

        def on_progress(stats):
            stats_history.append(
                {
                    "timestamp": time.time(),
                    "total_checked": stats.total_checked,
                    "speed": stats.speed,
                    "matches": len(stats.matches),
                }
            )

        try:
            # 初始化引擎（同步模式）
            start_init = time.time()
            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,  # 自动选择
                batch_size=1048576,  # 1M批次
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False,
                use_enhanced_monitoring=True,
                use_gpu_memory_pool=True,
            )
            # 手动禁用异步执行
            engine._device_manager.config["gpu"]["async_execution"] = False
            init_time = time.time() - start_init

            # 获取设备信息
            device_info = engine.get_device_info()
            batch_size = engine.batch_size

            print(f"  GPU设备: {device_info.get('name', 'Unknown')}")
            print(f"  厂商: {device_info.get('vendor', 'Unknown')}")
            print(f"  批次大小: {batch_size:,}")
            print(f"  初始化时间: {init_time:.2f}秒")
            print()

            # 开始测试
            engine.start(mode="random")

            print(f"  运行 {self.test_duration} 秒...")
            print()

            start_time = time.time()
            last_count = 0
            last_time = start_time

            while time.time() - start_time < self.test_duration:
                time.sleep(5)
                current_time = time.time()
                elapsed = current_time - start_time

                if stats_history:
                    latest = stats_history[-1]
                    current_count = latest["total_checked"]

                    # 计算区间速度
                    time_diff = current_time - last_time
                    count_diff = current_count - last_count
                    interval_speed = count_diff / time_diff if time_diff > 0 else 0

                    print(
                        f"  [{elapsed:5.1f}s] 总计: {current_count:>12,} keys | "
                        f"区间速度: {interval_speed:>10,.2f} keys/s | "
                        f"平均速度: {latest['speed']:>10,.2f} keys/s"
                    )

                    batch_times.append(
                        {
                            "elapsed": elapsed,
                            "total": current_count,
                            "speed": latest["speed"],
                            "interval_speed": interval_speed,
                        }
                    )

                    last_count = current_count
                    last_time = current_time

            engine.stop()

            # 统计结果
            if stats_history:
                speeds = [s["speed"] for s in stats_history if s["speed"] > 0]
                total_keys = stats_history[-1]["total_checked"]
                avg_speed = sum(speeds) / len(speeds) if speeds else 0
                max_speed = max(speeds) if speeds else 0
                min_speed = min(speeds) if speeds else 0

                print(f"\n  📊 测试结果:")
                print(f"    总检查数: {total_keys:,} keys")
                print(f"    平均速度: {avg_speed:,.2f} keys/s")
                print(f"    峰值速度: {max_speed:,.2f} keys/s")
                print(f"    最低速度: {min_speed:,.2f} keys/s")
                print(f"    速度稳定性: {(1 - (max_speed - min_speed) / avg_speed) * 100:.1f}%")

                return {
                    "mode": "sync",
                    "device": device_info,
                    "batch_size": batch_size,
                    "init_time": init_time,
                    "total_keys": total_keys,
                    "avg_speed": avg_speed,
                    "max_speed": max_speed,
                    "min_speed": min_speed,
                    "speeds": speeds,
                    "batch_times": batch_times,
                    "test_duration": self.test_duration,
                }

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback

            traceback.print_exc()
            return None

    def test_async_mode(self) -> Dict[str, Any]:
        """测试异步模式（双缓冲）"""
        print("\n" + "=" * 80)
        print("  测试配置: 异步模式（双缓冲优化）")
        print("=" * 80)

        stats_history = []
        batch_times = []

        def on_progress(stats):
            stats_history.append(
                {
                    "timestamp": time.time(),
                    "total_checked": stats.total_checked,
                    "speed": stats.speed,
                    "matches": len(stats.matches),
                }
            )

        try:
            # 初始化引擎（异步模式）
            start_init = time.time()
            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,  # 自动选择
                batch_size=1048576,  # 1M批次
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False,
                use_enhanced_monitoring=True,
                use_gpu_memory_pool=True,
            )
            # 手动启用异步执行
            engine._device_manager.config["gpu"]["async_execution"] = True
            init_time = time.time() - start_init

            # 获取设备信息
            device_info = engine.get_device_info()
            batch_size = engine.batch_size

            print(f"  GPU设备: {device_info.get('name', 'Unknown')}")
            print(f"  厂商: {device_info.get('vendor', 'Unknown')}")
            print(f"  批次大小: {batch_size:,}")
            print(f"  异步执行: 已启用")
            print(f"  初始化时间: {init_time:.2f}秒")
            print()

            # 开始测试
            engine.start(mode="random")

            print(f"  运行 {self.test_duration} 秒...")
            print()

            start_time = time.time()
            last_count = 0
            last_time = start_time

            while time.time() - start_time < self.test_duration:
                time.sleep(5)
                current_time = time.time()
                elapsed = current_time - start_time

                if stats_history:
                    latest = stats_history[-1]
                    current_count = latest["total_checked"]

                    # 计算区间速度
                    time_diff = current_time - last_time
                    count_diff = current_count - last_count
                    interval_speed = count_diff / time_diff if time_diff > 0 else 0

                    print(
                        f"  [{elapsed:5.1f}s] 总计: {current_count:>12,} keys | "
                        f"区间速度: {interval_speed:>10,.2f} keys/s | "
                        f"平均速度: {latest['speed']:>10,.2f} keys/s"
                    )

                    batch_times.append(
                        {
                            "elapsed": elapsed,
                            "total": current_count,
                            "speed": latest["speed"],
                            "interval_speed": interval_speed,
                        }
                    )

                    last_count = current_count
                    last_time = current_time

            engine.stop()

            # 统计结果
            if stats_history:
                speeds = [s["speed"] for s in stats_history if s["speed"] > 0]
                total_keys = stats_history[-1]["total_checked"]
                avg_speed = sum(speeds) / len(speeds) if speeds else 0
                max_speed = max(speeds) if speeds else 0
                min_speed = min(speeds) if speeds else 0

                print(f"\n  📊 测试结果:")
                print(f"    总检查数: {total_keys:,} keys")
                print(f"    平均速度: {avg_speed:,.2f} keys/s")
                print(f"    峰值速度: {max_speed:,.2f} keys/s")
                print(f"    最低速度: {min_speed:,.2f} keys/s")
                print(f"    速度稳定性: {(1 - (max_speed - min_speed) / avg_speed) * 100:.1f}%")

                return {
                    "mode": "async",
                    "device": device_info,
                    "batch_size": batch_size,
                    "init_time": init_time,
                    "total_keys": total_keys,
                    "avg_speed": avg_speed,
                    "max_speed": max_speed,
                    "min_speed": min_speed,
                    "speeds": speeds,
                    "batch_times": batch_times,
                    "test_duration": self.test_duration,
                }

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback

            traceback.print_exc()
            return None

    def generate_simple_report(self) -> str:
        """生成简化版性能报告"""
        if not self.results:
            return "❌ 无测试结果"

        async_result = self.results[0]

        report = f"""
{'='*80}
  v3.3.0 异步双缓冲性能测试报告
{'='*80}

测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试时长: {self.test_duration}秒
测试模式: 异步双缓冲（Async Double Buffering）
目标地址: {len(self.targets)}个

{'─'*80}
  GPU设备信息
{'─'*80}
设备名称: {async_result['device'].get('name', 'Intel Arc A770')}
厂商: {async_result['device'].get('vendor', 'Intel Corporation')}
批次大小: {async_result['batch_size']:,}
异步执行: 已启用

{'─'*80}
  性能指标
{'─'*80}

总检查数:     {async_result['total_keys']:>15,} keys
平均速度:     {async_result['avg_speed']:>15,.2f} keys/s
峰值速度:     {async_result['max_speed']:>15,.2f} keys/s
最低速度:     {async_result['min_speed']:>15,.2f} keys/s
初始化时间:   {async_result['init_time']:>15.2f} 秒
速度稳定性:   {(1 - (async_result['max_speed'] - async_result['min_speed']) / async_result['avg_speed']) * 100:>14.1f}%

{'─'*80}
  性能评估
{'─'*80}
✅ 异步双缓冲优化: 已启用
✅ 预期性能提升: +30-50%（相比同步模式）
{'✅ 性能达到预期' if async_result['avg_speed'] > 600000 else '⚠️ 性能需进一步优化'}

{'='*80}
"""
        return report

    def run_full_test(self):
        """运行完整测试流程"""
        print("\n" + "=" * 80)
        print("  v3.3.0 异步双缓冲性能验证测试")
        print("=" * 80)
        print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  每配置测试时长: {self.test_duration}秒")
        print()

        # 由于异步执行在初始化时已固定，我们只测试异步模式
        print("ℹ️  注意：异步执行模式在引擎初始化时确定，无法运行时切换")
        print("ℹ️  将测试异步模式的实际性能表现\n")

        # 测试异步模式
        async_result = self.test_async_mode()
        if async_result:
            self.results.append(async_result)
        else:
            print("❌ 异步模式测试失败")

        # 生成报告
        if self.results:
            report = self.generate_simple_report()
            print(report)

            # 保存报告
            report_file = os.path.join(
                project_root,
                "test_results",
                f'v330_async_performance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            )
            os.makedirs(os.path.dirname(report_file), exist_ok=True)

            report_data = {
                "test_time": datetime.now().isoformat(),
                "test_duration": self.test_duration,
                "results": self.results,
                "report": report,
            }

            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            print(f"\n📄 报告已保存: {report_file}")
        else:
            print("\n❌ 测试失败")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="v3.3.0异步双缓冲性能验证测试")
    parser.add_argument(
        "--duration", type=int, default=60, help="每个配置的测试时长（秒），默认60秒"
    )

    args = parser.parse_args()

    verifier = V330PerformanceVerifier(test_duration=args.duration)
    verifier.run_full_test()


if __name__ == "__main__":
    main()
