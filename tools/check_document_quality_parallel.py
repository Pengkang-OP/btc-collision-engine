#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文档质量并行检查工具

使用多进程加速文档质量检查，适用于大规模文档项目

使用方法:
    python tools/check_document_quality_parallel.py [--workers 4]
"""

import sys
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
from multiprocessing import BrokenProcessPool
from typing import List, Dict

# 修复Windows控制台编码问题
from utf8_helper import setup_windows_utf8
setup_windows_utf8()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.check_document_quality import DocumentScore


def check_single_doc(args) -> DocumentScore:
    """检查单个文档(用于多进程)

    Args:
        args: (file_path, docs_dir, config_dict)
    """
    file_path, docs_dir, config_dict = args

    from tools.check_document_quality import (
        DocumentQualityChecker,
        ScoringConfig,
    )

    # 创建检查器实例
    config = ScoringConfig(**config_dict)
    checker = DocumentQualityChecker(str(docs_dir), config)

    # 检查单个文档
    return checker.check_document(Path(file_path))


def parallel_check(docs_dir: str, workers: int = None, config_dict: Dict = None) -> List[DocumentScore]:
    """并行检查所有文档

    Args:
        docs_dir: 文档目录
        workers: 工作进程数(默认: CPU核心数)
        config_dict: 配置字典

    Returns:
        评分结果列表
    """
    if workers is None:
        workers = cpu_count()

    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    # 获取所有.md文件
    md_files = list(docs_path.glob("*.md"))
    md_files = [f for f in md_files if 'archive' not in str(f)]

    if not md_files:
        print("❌ 没有找到文档文件")
        sys.exit(1)

    print(f"🔍 开始并行检查文档质量...")
    print(f"📁 文档目录: {docs_dir}")
    print(f"📝 文档总数: {len(md_files)}")
    print(f"⚡ 工作进程: {workers}")
    print()

    # 默认配置
    if config_dict is None:
        from tools.check_document_quality import ScoringConfig
        config_dict = ScoringConfig().__dict__

    # 准备参数
    tasks = [(str(f), docs_dir, config_dict) for f in md_files]

    # 并行执行
    start_time = time.time()

    try:
        with Pool(processes=workers) as pool:
            scores = pool.map(check_single_doc, tasks, chunksize=1)
    except BrokenProcessPool as e:
        print(f"\n❌ 进程池损坏: {e}")
        print(f"💡 建议: 尝试减少工作进程数 (--workers 4)")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断并行检查")
        sys.exit(130)
    except RuntimeError as e:
        # 捕获其他运行时错误（如资源不足）
        print(f"\n❌ 并行检查运行时错误: {e}")
        print(f"💡 建议: 检查系统资源或减少工作进程数")
        sys.exit(1)

    elapsed = time.time() - start_time

    # 打印结果
    if elapsed > 0:
        print(f"\n✅ 检查完成! 耗时: {elapsed:.2f}秒")
        print(f"⚡ 平均速度: {len(md_files)/elapsed:.1f} 文档/秒")
    else:
        print(f"\n✅ 检查完成! 耗时: <0.01秒")

    return scores


def print_summary(scores: List[DocumentScore]):
    """打印评分摘要"""
    if not scores:
        return

    avg_score = sum(s.score for s in scores) / len(scores)

    print(f"\n{'=' * 60}")
    print(f"📊 文档质量检查报告")
    print(f"{'=' * 60}")

    print(f"\n核心文档总数: {len(scores)}")
    print(f"平均质量评分: {avg_score:.1f}/10")

    # 质量分布
    excellent = sum(1 for s in scores if s.score >= 8.5)
    good = sum(1 for s in scores if 7.0 <= s.score < 8.5)
    needs_improvement = sum(1 for s in scores if s.score < 7.0)

    print(f"\n质量分布:")
    print(f"  ✅ 优秀 (≥8.5): {excellent} 个 ({excellent/len(scores)*100:.1f}%)")
    print(f"  ⚠️  良好 (7.0-8.4): {good} 个 ({good/len(scores)*100:.1f}%)")
    print(f"  ❌ 需改进 (<7.0): {needs_improvement} 个 ({needs_improvement/len(scores)*100:.1f}%)")

    # 需改进的文档
    if needs_improvement > 0:
        print(f"\n⚠️  需要改进的文档:")
        for score in sorted(scores, key=lambda s: s.score):
            if score.score < 7.0:
                print(f"  - {Path(score.file).name}: {score.score}/10")

    # 总体评价
    if avg_score >= 8.5:
        print(f"\n总体评价: ✅ 优秀")
    elif avg_score >= 7.0:
        print(f"\n总体评价: ⚠️  良好")
    else:
        print(f"\n总体评价: ❌ 需要改进")

    print(f"{'=' * 60}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='文档质量并行检查工具')
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='工作进程数 (默认: CPU核心数)'
    )
    parser.add_argument(
        '--config',
        default=None,
        help='评分配置文件路径 (JSON格式)'
    )

    args = parser.parse_args()

    # 加载配置
    config_dict = None
    if args.config:
        import json
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            print(f"📝 使用配置文件: {config_path}")
        else:
            print(f"⚠️  配置文件不存在: {config_path}，使用默认配置")

    # 并行检查
    scores = parallel_check(args.docs_dir, args.workers, config_dict)

    # 打印摘要
    print_summary(scores)


if __name__ == "__main__":
    main()
