#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU碰撞引擎实际性能测试
测试真实GPU碰撞性能和稳定性
"""

import sys
import time
import os
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.collision.gpu.engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats


def main():
    """主函数"""
    print("=" * 80)
    print("  GPU碰撞引擎实际性能测试")  # 移除emoji避免Windows GBK编码问题
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 测试配置
    test_duration = 60  # 测试时长（秒）
    targets = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # 测试用地址
        "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",  # 测试用地址
    }

    # 统计数据
    stats_history = []
    max_speed = 0.0
    min_speed = float("inf")
    total_checked = 0

    def on_progress(stats: CollisionStats):
        """进度回调"""
        nonlocal max_speed, min_speed, total_checked

        current_speed = stats.speed
        total_checked = stats.total_checked

        # 更新统计数据
        if current_speed > 0:
            max_speed = max(max_speed, current_speed)
            min_speed = min(min_speed, current_speed)

        stats_history.append(
            {
                "time": stats.elapsed,
                "speed": current_speed,
                "total": stats.total_checked,
                "matches": len(stats.matches),
            }
        )

        # 格式化输出
        elapsed = stats.elapsed
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        # 进度条
        progress_pct = min(100, (elapsed / test_duration) * 100)
        bar_length = 40
        filled = int(bar_length * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        print(
            f"\r  [{bar}] {progress_pct:5.1f}% | "
            f"⏱️  {mins:02d}:{secs:02d} | "
            f"📊 {stats.total_checked:>12,} keys | "
            f"⚡ {current_speed:>12,.2f} keys/s",
            end="",
            flush=True,
        )

    def on_match(private_key: bytes, address: str, wif: str):
        """匹配回调"""
        print(f"\n\n  🎯 发现匹配!")
        print(f"     地址: {address}")
        print(f"     私钥: {private_key.hex()}")
        print(f"     WIF: {wif}")

    try:
        # 1. 初始化引擎
        print("  📋 步骤1: 初始化GPU碰撞引擎...")
        print()

        start_init = time.time()
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,  # 自动选择最佳GPU
            batch_size=262144,  # v2.2.1优化: 使用262K批次
            on_progress=on_progress,
            on_match=on_match,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True,
            gpu_pool_max_buffers=100,
            gpu_pool_max_memory_mb=512,
        )
        init_time = time.time() - start_init

        print(f"\n\n  ✅ GPU引擎初始化完成 (耗时: {init_time:.2f}秒)")
        print()

        # 获取设备信息
        device_info = engine._gpu_device.get_device_info()
        print(f"  📱 GPU设备信息:")
        print(f"     名称: {device_info.get('name', 'Unknown')}")
        print(f"     厂商: {device_info.get('vendor', 'Unknown')}")
        # 修复: 使用global_mem_size（字节）而非global_mem_gb
        global_mem_bytes = device_info.get("global_mem_size", 0)
        global_mem_gb = global_mem_bytes / (1024**3) if global_mem_bytes > 0 else 0
        print(f"     显存: {global_mem_gb:.2f} GB")
        print(f"     批次大小: {engine.batch_size:,}")
        print()

        # 2. 开始测试
        print(f"  🎯 目标地址: {len(targets)} 个")
        print(f"  ⏱️  测试时长: {test_duration}秒")
        print(f"  🚀 开始GPU碰撞测试...")
        print()
        print("  " + "─" * 78)

        # 启动引擎
        start_time = time.time()
        engine.start(mode="random")  # GPU引擎使用"random"模式

        # 运行指定时长
        try:
            while (time.time() - start_time) < test_duration:
                time.sleep(0.5)  # 更频繁的更新

                # 检查是否意外停止
                if not engine.is_running():
                    print(f"\n\n  ⚠️  引擎意外停止!")
                    break
        except KeyboardInterrupt:
            print(f"\n\n  ⚠️  收到中断信号，正在停止...")
        finally:
            engine.stop()

        elapsed = time.time() - start_time

        # 3. 打印结果
        print()
        print("  " + "─" * 78)
        print()
        print(f"  📊 测试完成!")
        print()
        print(f"  {'='*76}")
        print(f"  📈 性能统计")
        print(f"  {'='*76}")
        print(f"     总运行时间: {elapsed:.2f}秒")
        print(f"     总检查数:   {total_checked:>15,} keys")
        print(f"     平均速度:   {total_checked/elapsed:>15,.2f} keys/s")
        print(f"     峰值速度:   {max_speed:>15,.2f} keys/s")
        if min_speed != float("inf"):
            print(f"     最低速度:   {min_speed:>15,.2f} keys/s")
        print(f"     发现匹配:   {stats_history[-1]['matches'] if stats_history else 0}")
        print(f"  {'='*76}")

        # 4. 性能对比
        print()
        print(f"  📊 性能对比")
        print(f"  {'='*76}")

        cpu_speed = 88  # CPU模式参考速度
        gpu_speed = total_checked / elapsed
        speedup = gpu_speed / cpu_speed

        print(f"     CPU模式速度:  ~{cpu_speed:,} keys/s (参考值)")
        print(f"     GPU模式速度:  {gpu_speed:,.2f} keys/s (实测)")
        print(f"     加速倍数:     {speedup:,.1f}x")
        print()

        # 性能评级
        if speedup >= 5000:
            rating = "🏆 优秀"
        elif speedup >= 1000:
            rating = "✅ 良好"
        elif speedup >= 100:
            rating = "⚠️  一般"
        else:
            rating = "❌ 较差"

        print(f"     性能评级:     {rating}")
        print(f"  {'='*76}")

        # 5. 稳定性分析
        if len(stats_history) > 10:
            print()
            print(f"  📊 稳定性分析")
            print(f"  {'='*76}")

            speeds = [s["speed"] for s in stats_history if s["speed"] > 0]
            if speeds:
                avg_speed = sum(speeds) / len(speeds)
                speed_variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
                speed_stddev = speed_variance**0.5
                speed_cv = (speed_stddev / avg_speed * 100) if avg_speed > 0 else 0

                print(f"     速度样本数:   {len(speeds)}")
                print(f"     平均速度:     {avg_speed:,.2f} keys/s")
                print(f"     标准差:       {speed_stddev:,.2f} keys/s")
                print(f"     变异系数:     {speed_cv:.2f}%")
                print()

                if speed_cv < 10:
                    stability = "🏆 非常稳定"
                elif speed_cv < 20:
                    stability = "✅ 稳定"
                elif speed_cv < 30:
                    stability = "⚠️  波动较大"
                else:
                    stability = "❌ 不稳定"

                print(f"     稳定性评级:   {stability}")

            print(f"  {'='*76}")

        # 6. 资源使用
        print()
        print(f"  📊 资源使用")
        print(f"  {'='*76}")

        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent()

            print(f"     进程内存:     {memory_mb:,.1f} MB")
            print(f"     CPU使用率:    {cpu_percent:.1f}%")
        except Exception:
            print(f"     资源监控:     不可用")

        print(f"  {'='*76}")

        # 7. 总结
        print()
        print(f"  📝 测试总结")
        print(f"  {'='*76}")
        print(f"     GPU模式:      {'✅ 正常工作' if total_checked > 0 else '❌ 未运行'}")
        print(f"     性能达标:     {'✅ 是' if speedup >= 100 else '⚠️  低于预期'}")
        print(
            f"     稳定性:       {'✅ 良好' if min_speed != float('inf') and speed_cv < 30 else '⚠️  需优化'}"
        )
        print(
            f"     生产就绪:     {'✅ 是' if speedup >= 1000 and total_checked > 100000 else '❌ 否'}"
        )
        print(f"  {'='*76}")
        print()

        return 0 if total_checked > 0 else 1

    except Exception as e:
        print(f"\n\n  ❌ GPU测试失败: {e}")
        import traceback

        print()
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
