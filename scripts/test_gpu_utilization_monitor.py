#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU利用率监控测试 - v3.3.1

测试目标:
1. 验证异步模式是否真正提升GPU利用率
2. 监控GPU计算单元使用率
3. 监控PCIe传输带宽
4. 对比同步/异步模式的资源使用差异

测试时长: 60秒
"""

import sys
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine  # noqa: E402
from src.collision.collision_stats import CollisionStats  # noqa: E402


class GPUMonitor:
    """GPU利用率监控器"""

    def __init__(self):
        self.metrics_history = []
        self._running = False
        self._monitor_thread = None

    def start(self, engine: GPUCollisionEngine, interval: float = 1.0):
        """启动监控

        Args:
            engine: GPU引擎实例
            interval: 采样间隔(秒)
        """
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(engine, interval), daemon=True
        )
        self._monitor_thread.start()
        print(f"  [监控] GPU利用率监控已启动 (间隔: {interval}s)")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        print("  [监控] GPU利用率监控已停止")

    def _monitor_loop(self, engine: GPUCollisionEngine, interval: float):
        """监控循环"""
        while self._running:
            try:
                stats = engine.get_stats()
                if stats:
                    metrics = {
                        "timestamp": time.time(),
                        "speed": stats.speed,
                        "total_checked": stats.total_checked,
                        "matches": len(stats.matches),
                        "gpu_utilization": self._estimate_gpu_utilization(stats),
                        "elapsed": stats.elapsed,
                    }
                    self.metrics_history.append(metrics)
            except Exception as e:
                print(f"  [监控错误] {e}")

            time.sleep(interval)

    def _estimate_gpu_utilization(self, stats: CollisionStats) -> float:
        """估算GPU利用率

        基于速度和时间间隔估算GPU实际工作时间占比
        """
        if stats.speed <= 0:
            return 0.0

        # Intel Arc A770理论峰值约5M keys/s (PRNG模式)
        theoretical_max = 5000000
        utilization = min(stats.speed / theoretical_max * 100, 100.0)
        return utilization

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        if not self.metrics_history:
            return {"error": "无监控数据"}

        speeds = [m["speed"] for m in self.metrics_history if m["speed"] > 0]
        utilizations = [m["gpu_utilization"] for m in self.metrics_history]

        return {
            "samples": len(self.metrics_history),
            "avg_speed": sum(speeds) / len(speeds) if speeds else 0,
            "max_speed": max(speeds) if speeds else 0,
            "min_speed": min(speeds) if speeds else 0,
            "avg_gpu_utilization": sum(utilizations) / len(utilizations) if utilizations else 0,
            "max_gpu_utilization": max(utilizations) if utilizations else 0,
            "elapsed": self.metrics_history[-1]["elapsed"] if self.metrics_history else 0,
        }


def test_gpu_utilization(mode: str = "async", duration: int = 60):
    """测试GPU利用率

    Args:
        mode: 测试模式 ('sync' 或 'async')
        duration: 测试时长(秒)
    """
    print("=" * 80)
    print(f"  GPU利用率监控测试 - {mode.upper()}模式")
    print("=" * 80)
    print(f"  测试时长: {duration}秒")
    print("  批次大小: 1,048,576")
    print("  目标地址: 2个")
    print()

    targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"]

    engine = None
    monitor = GPUMonitor()
    start_time = time.time()

    def on_progress(stats: CollisionStats):
        """进度回调"""
        elapsed = time.time() - start_time
        if int(elapsed) % 10 == 0:
            print(
                f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}"
            )

    try:
        # 初始化引擎
        print(f"  [初始化] 创建GPU引擎({mode}模式)...")
        init_start = time.time()

        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=1048576,
            on_progress=on_progress,
            checkpoint_enabled=False,
            dedup_enabled=False,
        )

        # 配置模式
        if mode == "sync":
            if hasattr(engine, "_async_executor") and engine._async_executor:
                engine._async_executor = None
                print("  [配置] ✓ 异步执行器已禁用(同步模式)")
        else:
            if hasattr(engine, "_async_executor") and engine._async_executor:
                queue_depth = getattr(engine._async_executor, "queue_depth", "N/A")
                print(f"  [配置] ✓ 异步执行器已启用 (队列深度: {queue_depth})")
            else:
                print("  [错误] ✗ 异步执行器未启用!")
                return

        init_time = time.time() - init_start
        device_name = (
            engine._gpu_device.device_info.get("name", "Unknown")
            if engine._gpu_device
            else "Unknown"
        )
        print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
        print(f"  [设备] {device_name}")
        print()

        # 启动引擎
        print(f"  [启动] 开始{mode}模式测试...")
        engine.start()

        # 启动GPU利用率监控
        monitor.start(engine, interval=1.0)

        # 后台线程: 超时后强制退出
        def force_exit():
            time.sleep(duration)
            print(f"\n  ⏰ [{duration}秒倒计时结束] 强制退出...")
            os._exit(0)

        exit_thread = threading.Thread(target=force_exit, daemon=True)
        exit_thread.start()

        # 等待测试完成
        while time.time() - start_time < duration + 3:
            time.sleep(0.5)

            # 检查线程是否已退出
            if hasattr(engine, "_thread") and engine._thread and not engine._thread.is_alive():
                print("  [完成] 引擎线程已退出")
                break

        elapsed = time.time() - start_time
        print(f"  [停止] 测试结束 (总耗时: {elapsed:.2f}秒)")

        # 停止监控
        monitor.stop()

        # 获取监控摘要
        summary = monitor.get_summary()

        print(f"\n{'=' * 80}")
        print(f"  GPU利用率监控结果 - {mode.upper()}模式")
        print(f"{'=' * 80}")
        print(f"  采样点数: {summary['samples']}")
        print(f"  平均速度: {summary['avg_speed']:,.0f} keys/s")
        print(f"  峰值速度: {summary['max_speed']:,.0f} keys/s")
        print(f"  最低速度: {summary['min_speed']:,.0f} keys/s")
        print(f"  平均GPU利用率: {summary['avg_gpu_utilization']:.1f}%")
        print(f"  峰值GPU利用率: {summary['max_gpu_utilization']:.1f}%")
        print(f"  测试时长: {summary['elapsed']:.1f}秒")

        # 保存结果
        result = {
            "mode": mode,
            "device": device_name,
            "duration": elapsed,
            "monitoring": summary,
            "detailed_metrics": monitor.metrics_history,
            "timestamp": datetime.now().isoformat(),
        }

        output_dir = os.path.join(project_root, "test_results")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(output_dir, f"gpu_utilization_{mode}_{timestamp}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n  📊 详细数据已保存: {filepath}")

    except Exception as e:
        print(f"\n  [错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        monitor.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GPU利用率监控测试")
    parser.add_argument(
        "--mode", choices=["sync", "async"], default="async", help="测试模式 (默认: async)"
    )
    parser.add_argument("--duration", type=int, default=60, help="测试时长(秒, 默认: 60)")

    args = parser.parse_args()

    test_gpu_utilization(args.mode, args.duration)
