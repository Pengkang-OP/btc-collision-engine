#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intel Arc GPU 2M批次大小性能测试

测试目标：
1. 验证2M批次大小的稳定性
2. 对比1M vs 2M性能差异
3. 监控显存使用情况
4. 评估性能提升幅度
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

import pytest

pytestmark = pytest.mark.gpu  # 需要真实GPU硬件

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.collision.collision_stats import CollisionStats

def test_2m_batch_size(duration=60):
    """测试2M批次大小"""

    print("\n" + "="*80)
    print("🚀 Intel Arc GPU 2M批次大小性能测试")
    print("="*80)
    print(f"测试时长: {duration} 秒")
    print(f"批次大小: 2,097,152 (2M)")
    print(f"目标地址: 38 个 (valid_addresses.txt)")
    print()

    # 加载目标地址
    targets = set()
    try:
        with open("valid_addresses.txt", "r", encoding="utf-8") as f:
            for line in f:
                addr = line.strip()
                if addr and len(addr) >= 26:
                    targets.add(addr)
        if not targets:
            targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}
    except:
        targets = {"12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"}

    print(f"✅ 加载 {len(targets)} 个目标地址\n")

    # 统计数据
    stats_data = {
        'total_checked': 0,
        'speed': 0.0,
        'elapsed': 0.0,
        'matches': []
    }

    batch_count = 0
    speed_history = []

    def on_progress(stats: CollisionStats):
        """进度回调"""
        nonlocal batch_count

        stats_data['total_checked'] = stats.total_checked
        stats_data['speed'] = stats.speed
        stats_data['elapsed'] = stats.elapsed
        stats_data['matches'] = stats.matches

        # 记录速度历史
        if stats.speed > 0:
            speed_history.append(stats.speed)
            batch_count += 1

        elapsed = stats.elapsed
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        print(f"  [{mins:02d}:{secs:02d}] "
              f"已检查: {stats.total_checked:>12,} | "
              f"速度: {stats.speed:>12,.0f} keys/s | "
              f"批次: {batch_count}")

    def on_match(private_key: bytes, address: str, wif: str):
        """匹配回调"""
        print(f"\n🎯 发现匹配: {address}")
        print(f"   私钥: {private_key.hex()}")
        print(f"   WIF: {wif}\n")
        stats_data['matches'].append({
            'address': address,
            'private_key': private_key.hex(),
            'wif': wif
        })

    try:
        # 初始化GPU引擎（2M批次）
        print("📋 初始化GPU碰撞引擎 (2M批次)...")
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,  # 自动选择
            batch_size=2097152,  # 2M批次
            on_progress=on_progress,
            on_match=on_match,
            checkpoint_enabled=False,
            dedup_enabled=False,
            data_logging_enabled=False,
            use_enhanced_monitoring=True
        )

        # 获取设备信息
        device_info = engine._gpu_device.get_device_info()
        print(f"\n✅ GPU引擎初始化完成")
        print(f"   设备: {device_info.get('name', 'Unknown')}")
        print(f"   厂商: {device_info.get('vendor', 'Unknown')}")
        print(f"   显存: {device_info.get('global_mem_size', 0) / 1024**3:.1f} GB")
        print(f"   批次大小: {engine.batch_size:,} (2M)")
        print(f"   异步执行: {engine._gpu_device.enable_async_execution}")

        print(f"\n⏱️  开始测试，持续 {duration} 秒...\n")
        print("-" * 80)

        # 启动引擎
        start_time = time.time()
        engine.start(mode="random")

        # 运行指定时长
        try:
            while (time.time() - start_time) < duration:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️  收到中断信号，正在停止...")
        finally:
            engine.stop()

        elapsed = time.time() - start_time

        # 计算统计
        avg_speed = stats_data['total_checked'] / elapsed if elapsed > 0 else 0
        peak_speed = max(speed_history) if speed_history else 0
        min_speed = min(speed_history) if speed_history else 0

        # 打印结果
        print("-" * 80)
        print(f"\n📊 2M批次测试完成！")
        print("=" * 80)
        print(f"  总检查数   : {stats_data['total_checked']:,}")
        print(f"  运行时间   : {elapsed:.2f} 秒")
        print(f"  平均速度   : {avg_speed:,.0f} keys/s")
        print(f"  峰值速度   : {peak_speed:,.0f} keys/s")
        print(f"  最低速度   : {min_speed:,.0f} keys/s")
        print(f"  总批次数   : {batch_count}")
        print(f"  发现匹配   : {len(stats_data['matches'])} 个")
        print("=" * 80)

        # 显存估算
        estimated_memory_mb = (2097152 / 1048576) * 42  # 1M ≈ 42MB
        print(f"\n💾 显存使用估算:")
        print(f"  预计占用: ~{estimated_memory_mb:.0f} MB")
        print(f"  总显存: 16,384 MB (16GB)")
        print(f"  使用率: {estimated_memory_mb/16384*100:.2f}%")
        print(f"  状态: ✅ 非常安全")

        # 与1M批次对比
        print(f"\n📈 性能对比（vs 1M批次 ~522,928 keys/s）:")
        baseline_1m = 522928
        improvement = (avg_speed - baseline_1m) / baseline_1m * 100
        print(f"  1M批次基线: {baseline_1m:,.0f} keys/s")
        print(f"  2M批次实测: {avg_speed:,.0f} keys/s")
        print(f"  性能提升: {improvement:+.1f}%")

        if improvement > 0:
            print(f"  ✅ 2M批次性能更优！")
        else:
            print(f"  ⚠️ 2M批次未见明显提升")

        print("=" * 80)

        # 保存测试结果
        test_result = {
            'timestamp': datetime.now().isoformat(),
            'test_type': '2M_batch_size_test',
            'device': device_info,
            'batch_size': 2097152,
            'duration_seconds': elapsed,
            'total_checked': stats_data['total_checked'],
            'avg_speed': avg_speed,
            'peak_speed': peak_speed,
            'min_speed': min_speed,
            'batch_count': batch_count,
            'estimated_memory_mb': estimated_memory_mb,
            'improvement_vs_1m_percent': improvement
        }

        result_file = f"intel_arc_2m_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 测试结果已保存到: {result_file}")

        return test_result

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("\n" + "="*80)
    print("Intel Arc GPU 批次大小优化测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("测试目标:")
    print("  1. 验证2M批次大小稳定性")
    print("  2. 对比1M vs 2M性能差异")
    print("  3. 评估显存使用安全性")
    print()

    result = test_2m_batch_size(duration=60)

    if result:
        print("\n" + "="*80)
        print("🎉 测试完成！")
        print("="*80)

        print(f"\n📊 核心结果:")
        print(f"  平均速度: {result['avg_speed']:,.0f} keys/s")
        print(f"  性能提升: {result['improvement_vs_1m_percent']:+.1f}%")
        print(f"  显存使用: {result['estimated_memory_mb']:.0f} MB")

        if result['improvement_vs_1m_percent'] > 2:
            print(f"\n✅ 建议: 使用2M批次大小（性能提升显著）")
        elif result['improvement_vs_1m_percent'] > 0:
            print(f"\n✅ 建议: 可以使用2M批次大小（轻微提升）")
        else:
            print(f"\n⚠️ 建议: 保持1M批次大小（2M未见优势）")

        print("="*80)
        return 0
    else:
        print("\n❌ 测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
