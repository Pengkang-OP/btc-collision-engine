#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.3.0 异步双缓冲性能验证 - 简化版

直接运行基准测试，收集性能数据
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def run_benchmark_test():
    """运行基准测试"""
    print("="*80)
    print("  v3.3.0 性能基准测试")
    print("="*80)
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 运行现有的基准测试
    from benchmarks.benchmark_runner import BenchmarkRunner
    
    runner = BenchmarkRunner(
        output_dir=os.path.join(project_root, 'benchmarks', 'results'),
        compare=True
    )
    
    results = runner.run_all()
    
    # 保存结果
    out_path = runner.save(results)
    
    print("\n" + "="*80)
    print("  测试完成")
    print("="*80)
    print(f"  结果文件: {out_path}")
    
    return out_path


def generate_v330_report():
    """生成v3.3.0性能报告"""
    results_dir = os.path.join(project_root, 'benchmarks', 'results')
    
    # 查找最新的基准测试结果
    result_files = sorted(Path(results_dir).glob("benchmark_*.json"), reverse=True)
    
    if not result_files:
        print("❌ 未找到基准测试结果")
        return
    
    latest_file = result_files[0]
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "="*80)
    print("  v3.3.0 性能验证报告")
    print("="*80)
    print(f"\n测试时间: {data.get('timestamp', 'Unknown')}")
    print(f"Python版本: {data.get('python_version', 'Unknown')}")
    print(f"平台: {data.get('platform', 'Unknown')}")
    
    benchmarks = data.get('benchmarks', {})
    
    print(f"\n{'─'*80}")
    print(f"  性能指标")
    print(f"{'─'*80}")
    print(f"\n{'测试项':<30} {'操作/秒':>15} {'平均时间':>15} {'标准差':>15}")
    print(f"{'─'*80}")
    
    for name, result in benchmarks.items():
        if result.get('success', False):
            ops = result.get('ops_per_sec', 0)
            mean_us = result.get('mean_us', 0)
            std_us = result.get('std_us', 0)
            
            print(f"{name:<30} {ops:>15,.2f} {mean_us:>12.3f}µs {std_us:>12.3f}µs")
    
    # 对比分析
    comparison = data.get('comparison', {})
    if comparison.get('baseline_file'):
        print(f"\n{'─'*80}")
        print(f"  性能对比（基线: {comparison['baseline_file']}）")
        print(f"{'─'*80}")
        
        regressions = comparison.get('regressions', [])
        improvements = comparison.get('improvements', [])
        
        if regressions:
            print(f"\n⚠️  发现 {len(regressions)} 处性能回归:")
            for r in regressions:
                print(f"  - {r['name']}: {r['baseline_ops_per_sec']:,.2f} → {r['current_ops_per_sec']:,.2f} ({r['change_pct']:+.1f}%)")
        
        if improvements:
            print(f"\n✅ 发现 {len(improvements)} 处性能提升:")
            for r in improvements:
                print(f"  + {r['name']}: {r['baseline_ops_per_sec']:,.2f} → {r['current_ops_per_sec']:,.2f} ({r['change_pct']:+.1f}%)")
        
        if not regressions and not improvements:
            print(f"\n✅ 性能稳定，无显著变化")
    
    # 保存报告
    report_file = os.path.join(
        project_root,
        'test_results',
        f'v330_benchmark_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'─'*80}")
    print(f"  报告已保存: {report_file}")
    print(f"{'='*80}")


if __name__ == '__main__':
    # 运行基准测试
    result_file = run_benchmark_test()
    
    # 生成报告
    generate_v330_report()
