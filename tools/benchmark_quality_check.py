#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文档质量检查性能基准测试

测试不同规模文档目录的检查性能
帮助了解工具的性能特征和瓶颈

使用方法:
    python tools/benchmark_quality_check.py [--docs-dir docs] [--iterations 10]
"""

import sys
import io
import time
import statistics
from pathlib import Path
from typing import Dict, List

# 修复Windows控制台编码问题
from utf8_helper import setup_windows_utf8
setup_windows_utf8()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.check_document_quality import DocumentQualityChecker


def benchmark_check(docs_dir: str, iterations: int = 10) -> Dict:
    """性能基准测试
    
    Args:
        docs_dir: 文档目录路径
        iterations: 迭代次数
        
    Returns:
        性能统计字典
    """
    times = []
    doc_counts = []
    scores = []
    
    print(f"🔧 开始性能基准测试...")
    print(f"📁 文档目录: {docs_dir}")
    print(f"🔄 迭代次数: {iterations}\n")
    
    for i in range(1, iterations + 1):
        start = time.time()
        
        # 执行质量检查
        checker = DocumentQualityChecker(docs_dir)
        results = checker.check_all()
        
        elapsed = time.time() - start
        times.append(elapsed)
        
        # 统计信息
        doc_count = len(results)
        doc_counts.append(doc_count)
        
        avg_score = sum(r.score for r in results) / doc_count if doc_count > 0 else 0
        scores.append(avg_score)
        
        print(f"  迭代 {i:2d}: {elapsed:.2f}秒, {doc_count}个文档, 平均分{avg_score:.1f}")
    
    # 计算统计
    if not times:
        print("❌ 没有有效的测试数据")
        sys.exit(1)
    
    avg_time = statistics.mean(times)
    if avg_time == 0:
        print("⚠️  测试耗时为0，无法计算吞吐量")
        throughput = 0
    else:
        throughput = doc_counts[0] / avg_time if doc_counts else 0
    
    stats = {
        'iterations': iterations,
        'doc_count': statistics.mean(doc_counts) if doc_counts else 0,
        'time': {
            'avg': avg_time,
            'min': min(times),
            'max': max(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        },
        'score': {
            'avg': statistics.mean(scores) if scores else 0,
            'min': min(scores) if scores else 0,
            'max': max(scores) if scores else 0,
        },
        'throughput': throughput,
    }
    
    return stats


def print_report(stats: Dict):
    """打印性能报告"""
    print(f"\n{'=' * 60}")
    print(f"📊 性能基准测试报告")
    print(f"{'=' * 60}")
    
    print(f"\n📁 测试配置:")
    print(f"  迭代次数: {stats['iterations']}")
    print(f"  文档数量: {stats['doc_count']:.0f}个")
    
    print(f"\n⏱️  时间统计:")
    print(f"  平均: {stats['time']['avg']:.2f}秒")
    print(f"  中位数: {stats['time']['median']:.2f}秒")
    print(f"  最小: {stats['time']['min']:.2f}秒")
    print(f"  最大: {stats['time']['max']:.2f}秒")
    print(f"  标准差: {stats['time']['stdev']:.2f}秒")
    
    print(f"\n📈 评分统计:")
    print(f"  平均: {stats['score']['avg']:.1f}/10")
    print(f"  最小: {stats['score']['min']:.1f}/10")
    print(f"  最大: {stats['score']['max']:.1f}/10")
    
    print(f"\n⚡ 吞吐量:")
    print(f"  {stats['throughput']:.1f} 文档/秒")
    print(f"  {stats['throughput'] * 60:.1f} 文档/分钟")
    
    print(f"\n{'=' * 60}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='文档质量检查性能基准测试')
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=10,
        help='迭代次数 (默认: 10)'
    )
    
    args = parser.parse_args()
    
    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)
    
    # 运行基准测试
    stats = benchmark_check(str(docs_dir), args.iterations)
    
    # 打印报告
    print_report(stats)
    
    # 性能建议
    print(f"\n💡 性能建议:")
    avg_time = stats['time']['avg']
    if avg_time < 1.0:
        print(f"  ✅ 性能优秀！平均{avg_time:.2f}秒")
    elif avg_time < 5.0:
        print(f"  ✅ 性能良好，平均{avg_time:.2f}秒")
    elif avg_time < 10.0:
        print(f"  ⚠️  性能可接受，但可以考虑优化")
    else:
        print(f"  ❌ 性能较慢，建议优化")
        print(f"     - 检查文档数量是否过多")
        print(f"     - 考虑增量检查模式")
        print(f"     - 优化链接检查逻辑")
    
    print()


if __name__ == "__main__":
    main()
