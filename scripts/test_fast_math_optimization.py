#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证Intel Arc快速数学优化效果
对比启用/禁用fast-math的性能差异
"""

import sys
import os
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.collision.gpu_collision_engine import GPUCollisionEngine


def test_fast_math_optimization(test_duration=30):
    """测试快速数学优化效果"""
    print("=" * 80)
    print("  Intel Arc 快速数学优化验证测试")
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    targets = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
    }
    
    stats_history = []
    
    def on_progress(stats):
        stats_history.append({
            'timestamp': time.time(),
            'total_checked': stats.total_checked,
            'speed': stats.speed,
            'matches': len(stats.matches) if hasattr(stats.matches, '__len__') else stats.matches
        })
    
    def on_match(match_info):
        print(f"  [MATCH] 发现匹配!")
    
    try:
        # 初始化引擎
        print("  初始化GPU引擎 (batch_size=262144)...")
        print("  配置: use_fast_math=True, compiler_flags=-cl-fast-relaxed-math")
        print()
        
        start_init = time.time()
        
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=-1,
            batch_size=262144,
            on_progress=on_progress,
            on_match=on_match,
            use_enhanced_monitoring=True,
            use_gpu_memory_pool=True
        )
        
        init_time = time.time() - start_init
        
        device_info = engine._gpu_device.get_device_info()
        print(f"  GPU设备: {device_info.get('name', 'Unknown')}")
        print(f"  显存: {device_info.get('global_mem_size', 0) / (1024**3):.2f} GB")
        print(f"  批次大小: {engine.batch_size:,}")
        print(f"  初始化时间: {init_time:.2f}秒")
        print()
        
        # 开始测试
        print(f"  开始测试 ({test_duration} 秒)...")
        print()
        
        engine.start(mode="random")
        
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            time.sleep(5)
            if stats_history:
                latest = stats_history[-1]
                elapsed = time.time() - start_time
                print(f"  [{elapsed:5.1f}s] {latest['total_checked']:>12,} keys | "
                      f"{latest['speed']:>10.2f} keys/s")
        
        engine.stop()
        
        # 统计结果
        if stats_history:
            speeds = [s['speed'] for s in stats_history if s['speed'] > 0]
            total_keys = stats_history[-1]['total_checked']
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            max_speed = max(speeds) if speeds else 0
            min_speed = min(speeds) if speeds else 0
            
            # 计算稳定性
            if avg_speed > 0:
                std_dev = (sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)) ** 0.5
                cv = (std_dev / avg_speed) * 100
            else:
                cv = 0
            
            print(f"\n{'='*80}")
            print("  测试结果 (快速数学优化已启用)")
            print(f"{'='*80}")
            print(f"    总运行时间:   {time.time() - start_time:.2f}秒")
            print(f"    总检查数:     {total_keys:,} keys")
            print(f"    平均速度:     {avg_speed:,.2f} keys/s")
            print(f"    峰值速度:     {max_speed:,.2f} keys/s")
            print(f"    最低速度:     {min_speed:,.2f} keys/s")
            print(f"    稳定性:       变异系数 {cv:.2f}%")
            print()
            
            # 与历史数据对比
            print(f"{'='*80}")
            print("  性能对比历史数据")
            print(f"{'='*80}")
            print(f"    优化前(65K):     44,096 keys/s (基线)")
            print(f"    优化1(262K):     47,799 keys/s (+8.4%)")
            print(f"    快速数学(262K):  {avg_speed:,.2f} keys/s ({((avg_speed - 47799) / 47799 * 100):+.1f}%)")
            print()
            
            # 评估优化效果
            improvement = ((avg_speed - 47799) / 47799 * 100)
            
            print(f"{'='*80}")
            print("  快速数学优化评估")
            print(f"{'='*80}")
            
            if improvement > 5:
                print(f"    效果: ✅ 显著提升 (+{improvement:.1f}%)")
                print(f"    建议: 保留快速数学优化")
            elif improvement > 0:
                print(f"    效果: ⚠️  轻微提升 (+{improvement:.1f}%)")
                print(f"    建议: 可以保留，继续观察")
            elif improvement > -3:
                print(f"    效果: ⚠️  轻微下降 ({improvement:.1f}%)")
                print(f"    建议: 在统计误差范围内，可保留")
            else:
                print(f"    效果: ❌ 显著下降 ({improvement:.1f}%)")
                print(f"    建议: 考虑禁用快速数学")
            
            print(f"{'='*80}")
            
            return {
                'batch_size': 262144,
                'fast_math': True,
                'total_keys': total_keys,
                'avg_speed': avg_speed,
                'max_speed': max_speed,
                'min_speed': min_speed,
                'cv': cv,
                'improvement': improvement
            }
        
    except Exception as e:
        print(f"\n  错误: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    result = test_fast_math_optimization(test_duration=60)
    
    if result:
        print(f"\n{'='*80}")
        print("  测试完成!")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print("  测试失败!")
        print(f"{'='*80}")
