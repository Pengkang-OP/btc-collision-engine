#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步模式90秒性能测试 - 自动退出

测试策略:
- 运行90秒后自动停止并清理资源
- 采集前60秒稳定数据
- 结果保存到JSON文件
- 使用 threading.Event 进行受控退出，确保 GPU 资源正确释放
"""

import sys
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.collision.gpu_collision_engine import GPUCollisionEngine  # noqa: E402
from src.collision.collision_stats import CollisionStats  # noqa: E402

# 输出目录
_TEST_OUTPUT_DIR = _PROJECT_ROOT / "test_results"
os.makedirs(_TEST_OUTPUT_DIR, exist_ok=True)


def test_async_mode(test_duration: int = 90, analysis_duration: int = 60):
    """测试异步模式"""
    print("=" * 80)
    print("  异步模式(双缓冲)性能测试")
    print("=" * 80)
    print(f"  测试时长: {test_duration}秒 (含 {test_duration - analysis_duration}s 缓冲)")
    print(f"  数据分析: 前{analysis_duration}秒")
    print("  批次大小: 1,048,576")
    print("  目标地址: 2个")
    print()

    targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"]

    stats_history = []
    total_keys = 0
    start_time = time.time()
    engine = None

    # 受控停止信号 (替代 os._exit)
    _stop_event = threading.Event()

    def on_progress(stats: CollisionStats):
        """进度回调"""
        elapsed = time.time() - start_time
        if elapsed >= test_duration:
            return

        # 只记录前analysis_duration秒的数据
        if elapsed <= analysis_duration:
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
        if len(stats_history) % 10 == 0 and elapsed <= analysis_duration:
            print(
                f"  [{elapsed:5.1f}s] 速度: {stats.speed:,.0f} keys/s | "
                f"总计: {stats.total_checked:,} | 匹配: {len(stats.matches)}"
            )

    try:
        # 初始化引擎
        print("  [初始化] 创建GPU引擎(异步模式)...")
        init_start = time.time()

        engine = GPUCollisionEngine(
            targets=targets,
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
            print("  [配置] 异步执行器未启用")

        init_time = time.time() - init_start
        device_info = engine._gpu_device.get_device_info() if engine._gpu_device else {}
        device_name = device_info.get("name", "Unknown")
        print(f"  [完成] 初始化耗时: {init_time:.2f}秒")
        print(f"  [设备] {device_name}")
        print()

        # 启动引擎
        print("  [启动] 开始测试...")
        engine.start()

        # 后台线程: 到时间后发出停止信号 (替代 os._exit)
        def timer_stop():
            time.sleep(test_duration)
            print(f"\n  ⏰ [{test_duration}秒倒计时结束] 发出停止信号...")
            _stop_event.set()

        timer_thread = threading.Thread(target=timer_stop, daemon=True)
        timer_thread.start()

        # 等待测试完成或停止信号
        while not _stop_event.is_set():
            time.sleep(0.5)
            stats = engine.get_stats()
            if stats:
                total_keys = stats.total_checked

            # 检查引擎线程是否异常退出
            if hasattr(engine, "_thread") and engine._thread and not engine._thread.is_alive():
                print("  [完成] 引擎线程已退出")
                break

        elapsed = time.time() - start_time
        print(f"  [停止] 测试结束 (总耗时: {elapsed:.2f}秒)")

        # 停止引擎 (确保资源释放)
        if engine:
            engine.stop()

        # 计算统计数据
        if stats_history:
            speed_samples = [s["speed"] for s in stats_history if s["speed"] > 0]
            avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0

            keys_at_60s = 0
            for s in sorted(stats_history, key=lambda x: x["elapsed"], reverse=True):
                if s["elapsed"] <= analysis_duration:
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
            "test_duration": test_duration,
            "analysis_duration": analysis_duration,
            "duration": elapsed,
            "total_keys": keys_at_60s,
            "avg_speed": avg_speed,
            "init_time": init_time,
            "samples": len(stats_history),
            "speed_samples": speed_samples,
            "timestamp": datetime.now().isoformat(),
        }

        if speed_samples:
            result["max_speed"] = max(speed_samples)
            result["min_speed"] = min(speed_samples)
            n = len(speed_samples)
            if n > 1:
                result["speed_std"] = (sum((s - avg_speed) ** 2 for s in speed_samples) / n) ** 0.5

        # 保存结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = _TEST_OUTPUT_DIR / f"async_mode_{timestamp}.json"

        with open(str(filepath), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n  📊 结果已保存: {filepath}")
        print(f"\n  平均速度: {avg_speed:,.0f} keys/s")
        print(f"  60秒总计: {keys_at_60s:,} keys")

        # 触发资源完全释放
        if hasattr(engine, "_gpu_device") and engine._gpu_device:
            try:
                engine._gpu_device.cleanup()
            except Exception:
                pass

    except Exception as e:
        print(f"\n  [错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        # 确保异常路径下也清理资源
        if engine:
            try:
                engine.stop()
            except Exception:
                pass


if __name__ == "__main__":
    test_async_mode(90, 60)
