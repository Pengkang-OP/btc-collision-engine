#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU加速模式快速测试脚本

直接启动GPU碰撞引擎进行性能测试
"""

import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats


def main():
    """主函数"""
    print("=" * 70)
    print("🚀 GPU加速碰撞测试")
    print("=" * 70)

    # 目标地址
    targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}

    # 统计数据
    stats_data = {"total_checked": 0, "speed": 0.0, "elapsed": 0.0, "matches": 0}

    def on_progress(stats: CollisionStats):
        """进度回调"""
        stats_data["total_checked"] = stats.total_checked
        stats_data["speed"] = stats.speed
        stats_data["elapsed"] = stats.elapsed  # 修复: 使用elapsed而非elapsed_time
        stats_data["matches"] = len(stats.matches)

        elapsed = stats.elapsed  # 修复: 使用elapsed而非elapsed_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        print(
            f"[{mins:02d}:{secs:02d}] 已检查: {stats.total_checked:>10,} | "
            f"速度: {stats.speed:>12,.2f} keys/s | "
            f"匹配: {len(stats.matches)}"
        )

    def on_match(private_key: bytes, address: str, wif: str):
        """匹配回调"""
        print(f"🎯 发现匹配: {address}")
        print(f"   私钥: {private_key.hex()}")
        print(f"   WIF: {wif}")

    try:
        # 创建GPU引擎
        print("\n📋 初始化GPU碰撞引擎...")
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,  # 自动选择最佳GPU
            batch_size=65536,
            on_progress=on_progress,
            on_match=on_match,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
            use_enhanced_monitoring=True,
        )

        print(f"✅ GPU引擎初始化完成")
        print(f"   设备: {engine._gpu_device.get_device_info().get('name', 'Unknown')}")
        print(f"   厂商: {engine._gpu_device.get_device_info().get('vendor', 'Unknown')}")
        print(f"   Batch Size: {engine.batch_size:,}")
        print(f"   显存: {engine._gpu_device.get_device_info().get('global_mem_gb', 0):.2f} GB")

        print(f"\n🎯 目标地址: {targets.pop()}")
        print(f"⏱️  测试时长: 30秒")
        print(f"\n开始GPU碰撞测试...\n")
        print("-" * 70)

        # 启动引擎
        start_time = time.time()
        engine.start(mode="random")

        # 运行30秒
        duration = 30
        try:
            while (time.time() - start_time) < duration:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️  收到中断信号，正在停止...")
        finally:
            engine.stop()

        elapsed = time.time() - start_time

        # 打印结果
        print("-" * 70)
        print(f"\n📊 GPU测试完成！")
        print("=" * 70)
        print(f"  总检查数 : {stats_data['total_checked']:,}")
        print(f"  运行时间 : {elapsed:.2f}秒")
        print(f"  平均速度 : {stats_data['total_checked']/elapsed:,.2f} keys/s")
        print(f"  峰值速度 : {stats_data['speed']:,.2f} keys/s")
        print(f"  发现匹配 : {stats_data['matches']} 个")
        print("=" * 70)

        # 性能对比
        print(f"\n📈 性能对比（vs CPU模式 ~88 keys/s）:")
        speedup = (stats_data["total_checked"] / elapsed) / 88
        print(f"  加速倍数 : {speedup:,.1f}x")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ GPU测试失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
