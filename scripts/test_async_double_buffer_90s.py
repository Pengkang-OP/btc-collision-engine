#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步双缓冲60秒性能对比测试 v4 - 修复停止阻塞问题

关键修复:
- 不使用engine.stop()避免阻塞
- 直接设置_stop_event强制线程退出
- 使用后台线程监控测试时长,超时自动退出
"""

import sys
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加项目根目录到路径
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats


class AsyncDoubleBufferTest:
    """异步双缓冲性能对比测试器"""

    def __init__(self, test_duration: int = 90, analysis_duration: int = 60):
        """
        初始化测试器

        Args:
            test_duration: 每个模式的测试时长(秒),默认90秒
            analysis_duration: 数据分析时长(秒),默认60秒(截取前60秒稳定数据)
        """
        self.test_duration = test_duration
        self.analysis_duration = analysis_duration
        self.targets = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # 中本聪地址
            "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S",  # 早期地址
        ]

    def test_sync_mode(self) -> Dict[str, Any]:
        """测试同步模式(单缓冲)"""
        print("\n" + "=" * 80)
        print("  测试模式: 同步(单缓冲)")
        print("=" * 80)
        print(f"  测试时长: {self.test_duration}秒")
        print(f"  数据分析: 前{self.analysis_duration}秒")
        print(f"  批次大小: 1,048,576")
        print()

        stats_history = []
        total_keys = 0
        start_time = time.time()
        engine = None

        def on_progress(stats: CollisionStats):
            """进度回调"""
            elapsed = time.time() - start_time
            if elapsed >= self.test_duration:
                return

            # 只记录前analysis_duration秒的数据
            if elapsed <= self.analysis_duration:
                stats_history.append(
                    {
                        "timestamp": time.time(),
                        "elapsed": elapsed,
                        "total_checked": stats.total_checked,
                        "speed": stats.speed,
                        "matches": len(stats.matches),
                    }
                )

            # 打印进度(每5秒)
            if len(stats_history) % 10 == 0 and elapsed <= self.analysis_duration:
                print(
                    f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                    f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}"
                )

        try:
            # 初始化引擎(同步模式 - 禁用异步执行器)
            print("  [初始化] 创建GPU引擎(同步模式)...")
            init_start = time.time()

            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,
                batch_size=1048576,
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False,
            )

            # 禁用异步执行器(强制同步模式)
            if hasattr(engine, "_async_executor") and engine._async_executor:
                print("  [配置] 检测到异步执行器,正在禁用...")
                engine._async_executor = None
                print("  [配置] ✓ 异步执行器已禁用(同步模式)")

            init_time = time.time() - init_start
            device_name = (
                engine._gpu_device.device_info.get("name", "Unknown")
                if engine._gpu_device
                else "Unknown"
            )
            print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
            print(f"  [设备] {device_name}")
            print()

            # 启动碰撞检测
            print("  [启动] 开始同步模式测试...")
            engine.start()

            # 后台线程: 90秒后强制退出整个进程
            def force_exit():
                time.sleep(self.test_duration)
                print(f"\n  ⏰ [90秒倒计时结束] 强制退出进程...")
                os._exit(0)  # 强制退出,不等待线程

            exit_thread = threading.Thread(target=force_exit, daemon=True)
            exit_thread.start()

            # 等待测试完成
            while time.time() - start_time < self.test_duration + 3:  # 额外3秒缓冲
                time.sleep(0.5)
                stats = engine.get_stats()
                if stats:
                    total_keys = stats.total_checked

                # 检查线程是否已退出
                if hasattr(engine, "_thread") and engine._thread and not engine._thread.is_alive():
                    print("  [完成] 引擎线程已退出")
                    break

            elapsed = time.time() - start_time
            print(f"  [停止] 测试结束 (总耗时: {elapsed:.2f}秒)")

            # 计算前60秒的平均速度
            if stats_history:
                speed_samples = [s["speed"] for s in stats_history if s["speed"] > 0]
                avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0

                # 找到60秒时的总密钥数
                keys_at_60s = 0
                for s in sorted(stats_history, key=lambda x: x["elapsed"], reverse=True):
                    if s["elapsed"] <= self.analysis_duration:
                        keys_at_60s = s["total_checked"]
                        break

                if keys_at_60s == 0 and stats_history:
                    keys_at_60s = stats_history[-1]["total_checked"]
            else:
                avg_speed = 0
                keys_at_60s = total_keys
                speed_samples = []

            result = {
                "mode": "sync",
                "device": device_name,
                "test_duration": self.test_duration,
                "analysis_duration": self.analysis_duration,
                "duration": elapsed,
                "total_keys": keys_at_60s,
                "avg_speed": avg_speed,
                "init_time": init_time,
                "samples": len(stats_history),
                "speed_samples": speed_samples,
            }

            if speed_samples:
                result["max_speed"] = max(speed_samples)
                result["min_speed"] = min(speed_samples)
                result["speed_std"] = (
                    sum((s - avg_speed) ** 2 for s in speed_samples) / len(speed_samples)
                ) ** 0.5

            return result

        except Exception as e:
            print(f"\n  [错误] 同步模式测试失败: {e}")
            import traceback

            traceback.print_exc()
            return {"mode": "sync", "error": str(e), "duration": time.time() - start_time}

    def test_async_mode(self) -> Dict[str, Any]:
        """测试异步模式(双缓冲)"""
        print("\n" + "=" * 80)
        print("  测试模式: 异步(双缓冲)")
        print("=" * 80)
        print(f"  测试时长: {self.test_duration}秒")
        print(f"  数据分析: 前{self.analysis_duration}秒")
        print(f"  批次大小: 1,048,576")
        print()

        stats_history = []
        total_keys = 0
        start_time = time.time()
        engine = None

        def on_progress(stats: CollisionStats):
            """进度回调"""
            elapsed = time.time() - start_time
            if elapsed >= self.test_duration:
                return

            # 只记录前analysis_duration秒的数据
            if elapsed <= self.analysis_duration:
                stats_history.append(
                    {
                        "timestamp": time.time(),
                        "elapsed": elapsed,
                        "total_checked": stats.total_checked,
                        "speed": stats.speed,
                        "matches": len(stats.matches),
                    }
                )

            # 打印进度(每5秒)
            if len(stats_history) % 10 == 0 and elapsed <= self.analysis_duration:
                print(
                    f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                    f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}"
                )

        try:
            # 初始化引擎(异步模式 - 使用默认配置)
            print("  [初始化] 创建GPU引擎(异步模式)...")
            init_start = time.time()

            engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=-1,
                batch_size=1048576,
                on_progress=on_progress,
                checkpoint_enabled=False,
                dedup_enabled=False,
            )

            # 确认异步执行器已启用
            if hasattr(engine, "_async_executor") and engine._async_executor:
                queue_depth = getattr(engine._async_executor, "queue_depth", "N/A")
                print(f"  [配置] ✓ 异步执行器已启用 (队列深度: {queue_depth})")
            else:
                print("  [错误] ✗ 异步执行器未启用,测试无效!")
                return {
                    "mode": "async",
                    "error": "异步执行器未启用",
                    "duration": time.time() - start_time,
                }

            init_time = time.time() - init_start
            device_name = (
                engine._gpu_device.device_info.get("name", "Unknown")
                if engine._gpu_device
                else "Unknown"
            )
            print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
            print(f"  [设备] {device_name}")
            print()

            # 启动碰撞检测
            print("  [启动] 开始异步模式测试...")
            engine.start()

            # 后台线程: 90秒后强制退出整个进程
            def force_exit():
                time.sleep(self.test_duration)
                print(f"\n  ⏰ [90秒倒计时结束] 强制退出进程...")
                os._exit(0)  # 强制退出,不等待线程

            exit_thread = threading.Thread(target=force_exit, daemon=True)
            exit_thread.start()

            # 等待测试完成
            while time.time() - start_time < self.test_duration + 3:
                time.sleep(0.5)
                stats = engine.get_stats()
                if stats:
                    total_keys = stats.total_checked

                # 检查线程是否已退出
                if hasattr(engine, "_thread") and engine._thread and not engine._thread.is_alive():
                    print("  [完成] 引擎线程已退出")
                    break

            elapsed = time.time() - start_time
            print(f"  [停止] 测试结束 (总耗时: {elapsed:.2f}秒)")

            # 计算前60秒的平均速度
            if stats_history:
                speed_samples = [s["speed"] for s in stats_history if s["speed"] > 0]
                avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0

                keys_at_60s = 0
                for s in sorted(stats_history, key=lambda x: x["elapsed"], reverse=True):
                    if s["elapsed"] <= self.analysis_duration:
                        keys_at_60s = s["total_checked"]
                        break

                if keys_at_60s == 0 and stats_history:
                    keys_at_60s = stats_history[-1]["total_checked"]
            else:
                avg_speed = 0
                keys_at_60s = total_keys
                speed_samples = []

            result = {
                "mode": "async",
                "device": device_name,
                "test_duration": self.test_duration,
                "analysis_duration": self.analysis_duration,
                "duration": elapsed,
                "total_keys": keys_at_60s,
                "avg_speed": avg_speed,
                "init_time": init_time,
                "samples": len(stats_history),
                "speed_samples": speed_samples,
            }

            if speed_samples:
                result["max_speed"] = max(speed_samples)
                result["min_speed"] = min(speed_samples)
                result["speed_std"] = (
                    sum((s - avg_speed) ** 2 for s in speed_samples) / len(speed_samples)
                ) ** 0.5

            return result

        except Exception as e:
            print(f"\n  [错误] 异步模式测试失败: {e}")
            import traceback

            traceback.print_exc()
            return {"mode": "async", "error": str(e), "duration": time.time() - start_time}

    def run_comparison(self) -> Dict[str, Any]:
        """运行完整对比测试"""
        print("=" * 80)
        print("  异步双缓冲性能对比测试 v4 (修复停止阻塞)")
        print("=" * 80)
        print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  测试时长: {self.test_duration}秒/模式")
        print(f"  数据分析: 前{self.analysis_duration}秒(稳定数据)")
        print(f"  目标地址: {len(self.targets)}个")
        print()

        # 测试同步模式
        sync_result = self.test_sync_mode()

        if "error" in sync_result:
            print("\n[错误] 同步模式测试失败,中止测试")
            return {
                "sync": sync_result,
                "async": {"error": "未执行"},
                "error": True,
                "timestamp": datetime.now().isoformat(),
            }

        # 等待3秒冷却
        print("\n" + "=" * 80)
        print("  冷却中...(3秒)")
        print("=" * 80)
        time.sleep(3)

        # 测试异步模式
        async_result = self.test_async_mode()

        # 生成对比报告
        comparison = self.generate_comparison(sync_result, async_result)

        return comparison

    def generate_comparison(self, sync: Dict, async_mode: Dict) -> Dict[str, Any]:
        """生成对比报告"""
        print("\n" + "=" * 80)
        print("  性能对比报告")
        print("=" * 80)

        if "error" not in sync and "error" not in async_mode:
            sync_speed = sync.get("avg_speed", 0)
            async_speed = async_mode.get("avg_speed", 0)

            print(f"\n  同步模式(单缓冲):")
            print(f"    平均速度: {sync_speed:,.0f} keys/s")
            print(f"    峰值速度: {sync.get('max_speed', 0):,.0f} keys/s")
            print(f"    最低速度: {sync.get('min_speed', 0):,.0f} keys/s")
            print(
                f"    稳定性: ±{sync.get('speed_std', 0)/sync_speed*100 if sync_speed > 0 else 0:.1f}%"
            )
            print(f"    60秒总计: {sync.get('total_keys', 0):,} keys")

            print(f"\n  异步模式(双缓冲):")
            print(f"    平均速度: {async_speed:,.0f} keys/s")
            print(f"    峰值速度: {async_mode.get('max_speed', 0):,.0f} keys/s")
            print(f"    最低速度: {async_mode.get('min_speed', 0):,.0f} keys/s")
            print(
                f"    稳定性: ±{async_mode.get('speed_std', 0)/async_speed*100 if async_speed > 0 else 0:.1f}%"
            )
            print(f"    60秒总计: {async_mode.get('total_keys', 0):,} keys")

            improvement = ((async_speed - sync_speed) / sync_speed * 100) if sync_speed > 0 else 0

            print(f"\n  性能提升: {improvement:+.1f}%")
            if improvement > 0:
                print(f"  ✅ 异步双缓冲带来 {improvement:.1f}% 性能提升")
            else:
                print(f"  ⚠️  异步双缓冲性能变化: {improvement:.1f}%")

            print("=" * 80)

            return {
                "sync": sync,
                "async": async_mode,
                "improvement_pct": improvement,
                "test_duration": self.test_duration,
                "timestamp": datetime.now().isoformat(),
                "device": sync.get("device", "Unknown"),
            }
        else:
            print("\n  ⚠️  测试出现错误，无法生成完整对比")
            return {
                "sync": sync,
                "async": async_mode,
                "error": True,
                "timestamp": datetime.now().isoformat(),
            }

    def save_results(self, comparison: Dict[str, Any]):
        """保存测试结果"""
        output_dir = os.path.join(project_root, "test_results")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"async_double_buffer_comparison_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)

        print(f"\n  结果已保存: {filepath}")


if __name__ == "__main__":
    duration = 90
    analysis_duration = 60

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的测试时长 '{sys.argv[1]}', 使用默认值90秒")

    if len(sys.argv) > 2:
        try:
            analysis_duration = int(sys.argv[2])
        except ValueError:
            print(f"警告: 无效的分析时长 '{sys.argv[2]}', 使用默认值60秒")

    print(f"测试时长设置为: {duration}秒")
    print(f"数据分析时长: {analysis_duration}秒")

    tester = AsyncDoubleBufferTest(test_duration=duration, analysis_duration=analysis_duration)
    comparison = tester.run_comparison()
    tester.save_results(comparison)

    print("\n✅ 测试完成！")
