#!/usr/bin/env python
"""
智能配置推荐系统

根据项目特征自动推荐最合适的评分配置

使用方法:
    python tools/recommend_config.py
"""

import json
import sys
from pathlib import Path

# 修复Windows控制台编码问题
from utf8_helper import setup_windows_utf8

setup_windows_utf8()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入重试工具
from retry_helper import read_with_retry


def analyze_project(docs_dir: str) -> dict:
    """分析项目特征

    Returns:
        项目特征字典
    """
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        return {'error': '文档目录不存在'}

    # 统计文档数量
    md_files = list(docs_path.glob("*.md"))
    md_files = [f for f in md_files if 'archive' not in str(f)]
    doc_count = len(md_files)

    # 统计平均文档大小
    total_size = sum(f.stat().st_size for f in md_files)
    avg_size = total_size / doc_count if doc_count > 0 else 0

    # 检查是否有目录
    has_toc_count = 0
    for f in md_files:
        content = read_with_retry(f)
        if content is None:
            print(f"⚠️  无法读取文件 {f.name} (重试3次后失败)")
            continue
        if '## 目录' in content or '## TOC' in content or '## Table of Contents' in content:
            has_toc_count += 1

    toc_ratio = has_toc_count / doc_count if doc_count > 0 else 0

    # 检查版本信息
    has_version_count = 0
    for f in md_files:
        content = read_with_retry(f)
        if content is None:
            continue
        if '版本' in content or 'version' in content.lower():
            has_version_count += 1

    version_ratio = has_version_count / doc_count if doc_count > 0 else 0

    # 检查代码块
    has_code_count = 0
    for f in md_files:
        content = read_with_retry(f)
        if content is None:
            continue
        if '```' in content:
            has_code_count += 1

    code_ratio = has_code_count / doc_count if doc_count > 0 else 0

    return {
        'doc_count': doc_count,
        'avg_size_kb': avg_size / 1024,
        'toc_ratio': toc_ratio,
        'version_ratio': version_ratio,
        'code_ratio': code_ratio,
    }


def recommend_config(features: dict) -> tuple[str, dict]:
    """根据项目特征推荐配置

    Args:
        features: 项目特征字典

    Returns:
        (推荐配置名称, 配置字典)
    """
    if 'error' in features:
        return '错误', {}

    doc_count = features['doc_count']
    toc_ratio = features['toc_ratio']
    version_ratio = features['version_ratio']
    code_ratio = features['code_ratio']

    # 评分逻辑
    score = 0

    # 文档数量少 -> 宽松
    if doc_count < 20:
        score -= 2
    elif doc_count < 50:
        score -= 1

    # 目录覆盖率高 -> 严格
    if toc_ratio > 0.8:
        score += 2
    elif toc_ratio > 0.5:
        score += 1

    # 版本信息覆盖率高 -> 严格
    if version_ratio > 0.8:
        score += 1

    # 代码块比例高 -> 严格(代码质量重要)
    if code_ratio > 0.7:
        score += 1

    # 推荐配置
    if score >= 2:
        return '严格模式', {
            'error_weight': 2.5,
            'code_block_weight': 0.3,
            'code_block_max': 1.5,
            'link_weight': 1.2,
            'link_max': 2.0,
            'other_warning_weight': 0.5,
            'info_weight': 0.2,
            'toc_bonus': 0.2,
            'version_bonus': 0.2
        }
    elif score <= -1:
        return '宽松模式', {
            'error_weight': 1.0,
            'code_block_weight': 0.1,
            'code_block_max': 3.0,
            'link_weight': 0.5,
            'link_max': 4.0,
            'other_warning_weight': 0.2,
            'info_weight': 0.05,
            'toc_bonus': 0.4,
            'version_bonus': 0.3
        }
    else:
        return '平衡模式', {
            'error_weight': 1.5,
            'code_block_weight': 0.2,
            'code_block_max': 2.0,
            'link_weight': 0.8,
            'link_max': 3.0,
            'other_warning_weight': 0.3,
            'info_weight': 0.1,
            'toc_bonus': 0.3,
            'version_bonus': 0.2
        }


def print_recommendation(features: dict, config_name: str, config: dict):
    """打印推荐结果"""
    print(f"\n{'=' * 60}")
    print("🤖 智能配置推荐系统")
    print(f"{'=' * 60}")

    print("\n📊 项目特征分析:")
    print(f"  文档数量: {features.get('doc_count', 0)} 个")
    print(f"  平均大小: {features.get('avg_size_kb', 0):.1f} KB")
    print(f"  目录覆盖率: {features.get('toc_ratio', 0)*100:.1f}%")
    print(f"  版本信息覆盖率: {features.get('version_ratio', 0)*100:.1f}%")
    print(f"  代码块比例: {features.get('code_ratio', 0)*100:.1f}%")

    print(f"\n🎯 推荐配置: {config_name}")

    if config:
        print("\n📝 配置详情:")
        for key, value in config.items():
            print(f"  {key}: {value}")

        print("\n💡 使用方式:")
        print(f"  python tools/check_document_quality.py --config tools/scoring_{config_name[:4].lower()}.json")

    print(f"\n{'=' * 60}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='智能配置推荐系统')
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='保存推荐配置到文件'
    )

    args = parser.parse_args()

    # 分析项目
    print("🔍 分析项目特征...")
    features = analyze_project(args.docs_dir)

    # 推荐配置
    config_name, config = recommend_config(features)

    # 打印推荐
    print_recommendation(features, config_name, config)

    # 保存配置
    if args.save and config:
        try:
            config_file = Path("tools/scoring_recommended.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"\n✅ 配置已保存到: {config_file}")
        except (OSError, PermissionError) as e:
            print(f"\n❌ 无法保存配置: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
