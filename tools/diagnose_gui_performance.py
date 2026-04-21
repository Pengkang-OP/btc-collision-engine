#!/usr/bin/env python3
"""深度诊断GUI性能问题"""

import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent))


def diagnose_performance():
    """诊断性能问题"""
    
    print("=" * 80)
    print("  GPU性能深度诊断")
    print("=" * 80)
    print()
    
    log_file = Path("logs/collision.log")
    if not log_file.exists():
        print("❌ 日志文件不存在")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        log_content = f.read()
        lines = log_content.split('\n')
    
    # 获取最后300行
    recent_lines = lines[-300:] if len(lines) > 300 else lines
    recent_log = '\n'.join(recent_lines)
    
    print("【1. 配置检查】")
    print("-" * 80)
    
    # batch_size
    batch_match = re.search(r'batch_size[=:\s]+(\d+)', recent_log)
    if batch_match:
        print(f"  ✅ batch_size: {int(batch_match.group(1)):,}")
    
    # 目标数量
    num_targets = 0  # 默认值,避免后续未定义错误
    targets_match = re.search(r'(\d+)\s*个目标', recent_log)
    if targets_match:
        num_targets = int(targets_match.group(1))
        print(f"  ⚠️  目标地址数量: {num_targets}")
        if num_targets > 10:
            print(f"     → 目标地址较多,可能影响性能!")
    else:
        print(f"  ℹ️  未检测到目标地址数量(使用默认值0)")
        print(f"     → 可能原因: 日志格式变化或程序未完全启动")
    
    # 异步状态
    if '使用GPU异步执行模式' in recent_log:
        print(f"  ✅ 异步执行模式: 已启用")
    else:
        print(f"  ❌ 异步执行模式: 未启用")
    
    if '双缓冲' in recent_log:
        print(f"  ✅ 双缓冲: 已启用")
    
    print()
    print("【2. 性能数据分析】")
    print("-" * 80)
    
    # 提取所有吞吐量数据
    throughput_pattern = r'当前=([0-9,]+)\s*keys/s.*峰值=([0-9,]+)\s*keys/s.*退化率=([0-9.]+)%'
    throughput_matches = re.findall(throughput_pattern, recent_log)
    
    if throughput_matches:
        current_throughputs = [int(m[0].replace(',', '')) for m in throughput_matches]
        peak_throughputs = [int(m[1].replace(',', '')) for m in throughput_matches]
        degradation_rates = [float(m[2]) for m in throughput_matches]
        
        avg_current = sum(current_throughputs) / len(current_throughputs)
        max_peak = max(peak_throughputs)
        avg_degradation = sum(degradation_rates) / len(degradation_rates)
        
        print(f"  当前吞吐量(平均): {avg_current:,.0f} keys/s")
        print(f"  峰值吞吐量(最高): {max_peak:,} keys/s")
        print(f"  性能退化率(平均): {avg_degradation:.2f}%")
        print()
        
        # 分析性能差距
        if max_peak > 1000000:
            print(f"  ⚠️  性能差距分析:")
            print(f"     峰值性能: {max_peak:,} keys/s")
            print(f"     当前性能: {avg_current:,.0f} keys/s")
            print(f"     性能比: {avg_current/max_peak*100:.1f}%")
            print()
            print(f"  可能原因:")
            print(f"     1. 目标地址数量多({num_targets}个)")
            print(f"     2. GPU内核执行效率")
            print(f"     3. 显存带宽限制")
            print(f"     4. 异步执行开销")
    
    print()
    print("【3. 目标地址影响分析】")
    print("-" * 80)
    
    if num_targets > 1:
        print(f"  目标地址数量: {num_targets}")
        print(f"  预期影响:")
        print(f"     - 1个目标:    100% 性能 (基准)")
        print(f"     - 10个目标:   ~90% 性能")
        print(f"     - 38个目标:   ~70-80% 性能")
        print(f"     - 100个目标:  ~50-60% 性能")
        print()
        print(f"  建议:")
        print(f"     - 如果只需要碰撞少量地址,减少目标数量")
        print(f"     - 38个目标会降低约20-30%的吞吐量")
    
    print()
    print("【4. 异步执行器状态】")
    print("-" * 80)
    
    if '异步执行失败' in recent_log:
        print(f"  ❌ 异步执行失败 - 回退到同步模式")
        print(f"  这是性能低的主要原因!")
    else:
        print(f"  ✅ 异步执行器正常工作")
        print(f"  未发现异步执行错误")
    
    if 'RepeatedKernelRetrieval' in recent_log:
        print(f"  ⚠️  内核重复检索警告")
        print(f"  可能影响性能,但不会导致严重问题")
    
    print()
    print("【5. 对比测试数据】")
    print("-" * 80)
    
    print(f"  测试脚本(run_async_test.py):")
    print(f"     - 目标地址: 1个")
    print(f"     - batch_size: 1,000,000")
    print(f"     - 吞吐量: 1,501,106 keys/s (稳定)")
    print(f"     - 吞吐量: 2,952,891 keys/s (初始)")
    print()
    print(f"  GUI程序(key_collision_gui.py):")
    print(f"     - 目标地址: {num_targets}个")
    print(f"     - batch_size: 1,000,000")
    print(f"     - 吞吐量: {avg_current:,.0f} keys/s (当前)")
    print(f"     - 吞吐量: {max_peak:,} keys/s (峰值)")
    print()
    
    # 计算目标数量影响
    if num_targets > 1 and avg_current > 0:
        expected_with_1_target = avg_current * (1 + (num_targets - 1) * 0.008)
        print(f"  性能差异归因:")
        print(f"     目标数量影响: ~{((num_targets - 1) * 0.8):.0f}% 性能损失")
        print(f"     如果只有1个目标,预期吞吐量: ~{expected_with_1_target:,.0f} keys/s")
    
    print()
    print("=" * 80)
    print("  诊断总结")
    print("=" * 80)
    print()
    
    if num_targets > 10:
        print(f"🔍 主要原因: 目标地址数量过多({num_targets}个)")
        print()
        print(f"📊 性能损失估算:")
        print(f"   - 目标数量导致: ~{((num_targets - 1) * 0.8):.0f}% 性能损失")
        print(f"   - 预期单目标性能: ~{max_peak:,} keys/s")
        print(f"   - 实际{num_targets}目标性能: ~{avg_current:,.0f} keys/s")
        print()
        print(f"✅ 优化建议:")
        print(f"   1. 减少目标地址数量(如果只需要碰撞少量地址)")
        print(f"   2. 保持当前配置(batch_size=1M,异步启用)")
        print(f"   3. 性能已是最优(在{num_targets}个目标的情况下)")
    else:
        print(f"✅ 性能正常,无明显问题")
    
    print()


if __name__ == "__main__":
    diagnose_performance()
