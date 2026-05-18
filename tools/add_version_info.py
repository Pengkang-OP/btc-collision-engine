#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量添加版本信息到文档

为缺少版本信息的文档添加标准版本标识

使用方法:
    python tools/add_version_info.py [--dry-run] [--version v4.2.2]
"""

import re
import sys
from pathlib import Path
from typing import Tuple
from datetime import datetime

# 修复Windows控制台编码问题 - 使用共享模块`nfrom tools.utf8_helper import setup_windows_utf8`nsetup_windows_utf8()


def check_has_version(content: str) -> bool:
    """检查文档是否已有版本信息"""
    # 检查前20行是否有版本信息
    first_20_lines = '\n'.join(content.split('\n')[:20])
    return bool(re.search(r'[*]*[*]版本[*]*[*]:\s*v?\d+\.\d+', first_20_lines))


def add_version_info(content: str, version: str, target_audience: str = "用户/开发者") -> Tuple[str, bool]:
    """添加版本信息到文档

    Returns:
        (新内容, 是否已添加)
    """
    if check_has_version(content):
        return content, False

    lines = content.split('\n')

    # 找到第一个标题行
    title_line_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('# ') and not line.startswith('##'):
            title_line_idx = i
            break

    # 在标题后插入版本信息
    version_block = f"\n> **版本**: {version} | **最后更新**: {datetime.now().strftime('%Y-%m-%d')}  \n> **面向**: {target_audience}\n"

    # 插入到标题后
    insert_idx = title_line_idx + 1
    lines.insert(insert_idx, version_block)

    return '\n'.join(lines), True


def determine_target_audience(file_name: str) -> str:
    """根据文件名确定目标读者"""
    audience_map = {
        'README': '所有用户',
        'getting-started': '新用户',
        'user-interface': '用户',
        'troubleshooting': '用户',
        'api-reference': '开发者',
        'architecture': '开发者/架构师',
        'performance-optimization': '开发者',
        'security': '开发者/安全工程师',
        'CONTRIBUTING': '贡献者',
        'config': '开发者/运维',
        'monitoring': '运维/开发者',
        'logging': '开发者',
        'gpu': '开发者',
        'intel': '开发者',
        'checkpoint': '用户',
        'address-import': '用户',
        'bech32': '开发者',
        'workflow': '开发者',
        'review': '审查者',
        'quality': '维护者',
        'improvement': '维护者',
    }

    for key, audience in audience_map.items():
        if key.lower() in file_name.lower():
            return audience

    return '用户/开发者'


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='批量添加版本信息到文档')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示添加计划，不实际修改文件'
    )
    parser.add_argument(
        '--version',
        default='v4.2.3',
        help='版本号 (默认: v4.2.3)'
    )
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='文档目录路径 (默认: docs)'
    )

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    print("🔧 开始添加版本信息...\n")

    if args.dry_run:
        print(f"⚠️  模拟运行模式 - 不会修改文件\n")

    md_files = list(docs_dir.glob("*.md"))
    # 排除archive目录
    md_files = [f for f in md_files if 'archive' not in str(f)]

    total_added = 0
    total_skipped = 0
    file_stats = []

    for md_file in sorted(md_files):
        content = md_file.read_text(encoding='utf-8')

        if check_has_version(content):
            total_skipped += 1
            continue

        audience = determine_target_audience(md_file.name)
        new_content, added = add_version_info(content, args.version, audience)

        if added:
            total_added += 1
            file_stats.append((md_file.name, audience))

            if not args.dry_run:
                md_file.write_text(new_content, encoding='utf-8')

    # 打印统计信息
    print("=" * 60)
    print("📊 版本信息添加报告")
    print("=" * 60)

    print(f"\n📁 扫描文件数: {len(md_files)}")
    print(f"✅ 已有版本信息: {total_skipped}")
    print(f"✨ 添加版本信息: {total_added}")

    if file_stats:
        print(f"\n添加详情:")
        for file_name, audience in sorted(file_stats):
            print(f"  📄 {file_name}")
            print(f"     面向: {audience}")

    print("\n" + "=" * 60)

    if args.dry_run:
        print(f"\n💡 这是模拟运行。发现 {total_added} 个文档需要添加版本信息。")
        print(f"   移除 --dry-run 参数以实际添加。")
    else:
        print(f"\n✅ 添加完成！共为 {total_added} 个文档添加版本信息。")
        print(f"   版本号: {args.version}")
        print(f"   日期: {datetime.now().strftime('%Y-%m-%d')}")

    print("=" * 60)

    return total_added


if __name__ == "__main__":
    main()
