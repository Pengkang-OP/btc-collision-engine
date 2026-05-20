#!/usr/bin/env python
"""
为长文档自动添加目录

为超过50行的文档自动生成并添加目录（TOC）

使用方法:
    python tools/add_table_of_contents.py [--dry-run] [--min-lines 50]
"""

import re
import sys
from pathlib import Path

# 修复Windows控制台编码问题 - 使用共享模块
from tools.utf8_helper import setup_windows_utf8

setup_windows_utf8()


def extract_headings(content: str) -> list[tuple[int, int, str]]:
    """提取文档标题

    Returns:
        List of (level, line_number, title_text)
    """
    headings = []
    lines = content.split('\n')

    for i, line in enumerate(lines, 1):
        match = re.match(r'^(#{1,6})\s+(.+)', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append((level, i, text))

    return headings


def generate_toc(headings: list[tuple[int, int, str]]) -> str:
    """生成目录Markdown文本"""
    if not headings:
        return ""

    toc_lines = ["## 目录\n"]

    for level, line_num, title in headings:
        # 跳过主标题（level 1）
        if level == 1:
            continue

        # 生成锚点链接
        anchor = title.lower()
        anchor = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', anchor)  # 移除特殊字符
        anchor = anchor.replace(' ', '-')

        # 缩进
        indent = '  ' * (level - 2)  # level 2 开始无缩进

        toc_lines.append(f"{indent}- [{title}](#{anchor})")

    return '\n'.join(toc_lines)


def has_toc(content: str) -> bool:
    """检查文档是否已有目录"""
    # 查找"目录"标题
    return bool(re.search(r'^##\s+目录\s*$', content, re.MULTILINE))


def add_toc_to_file(content: str, min_headings: int = 3) -> tuple[str, bool]:
    """为文档添加目录

    Returns:
        (新内容, 是否已添加)
    """
    if has_toc(content):
        return content, False

    headings = extract_headings(content)

    # 过滤掉level 1的主标题
    sub_headings = [h for h in headings if h[0] > 1]

    if len(sub_headings) < min_headings:
        return content, False

    # 生成目录
    toc = generate_toc(headings)

    if not toc:
        return content, False

    # 找到插入位置（在第一个##标题之前，或版本信息块之后）
    lines = content.split('\n')
    insert_idx = 0

    # 查找第一个##标题或版本信息块结束位置
    for i, line in enumerate(lines):
        # 跳过主标题
        if i == 0 and line.startswith('# '):
            insert_idx = i + 1
            continue

        # 跳过版本信息块
        if line.startswith('> **版本**:'):
            # 找到版本信息块结束
            j = i
            while j < len(lines) and (lines[j].startswith('> ') or lines[j].strip() == ''):
                j += 1
            insert_idx = j
            break

        # 找到第一个##标题
        if line.startswith('## '):
            insert_idx = i
            break

    # 插入目录
    lines.insert(insert_idx, toc)
    lines.insert(insert_idx, '')  # 空行

    return '\n'.join(lines), True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='为长文档自动添加目录')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示添加计划，不实际修改文件'
    )
    parser.add_argument(
        '--min-lines',
        type=int,
        default=50,
        help='最小行数 (默认: 50)'
    )
    parser.add_argument(
        '--min-headings',
        type=int,
        default=3,
        help='最小标题数 (默认: 3)'
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

    print("🔧 开始为长文档添加目录...\n")

    if args.dry_run:
        print("⚠️  模拟运行模式 - 不会修改文件\n")

    md_files = list(docs_dir.glob("*.md"))
    md_files = [f for f in md_files if 'archive' not in str(f)]

    total_added = 0
    total_skipped = 0
    file_stats = []

    for md_file in sorted(md_files):
        content = md_file.read_text(encoding='utf-8')
        line_count = len(content.split('\n'))

        # 跳过长文档
        if line_count < args.min_lines:
            total_skipped += 1
            continue

        new_content, added = add_toc_to_file(content, args.min_headings)

        if added:
            total_added += 1
            headings_count = len([h for h in extract_headings(content) if h[0] > 1])
            file_stats.append((md_file.name, line_count, headings_count))

            if not args.dry_run:
                md_file.write_text(new_content, encoding='utf-8')
                print(f"✅ {md_file.name}: 添加目录 ({line_count}行, {headings_count}个标题)")
            else:
                print(f"📄 {md_file.name}: 将添加目录 ({line_count}行, {headings_count}个标题)")

    print(f"\n{'=' * 60}")
    print("📊 目录添加报告")
    print(f"{'=' * 60}")

    print(f"\n📁 扫描文件: {len(md_files)}")
    print(f"⏭️  跳过(行数不足): {total_skipped}")
    print(f"✨ 添加目录: {total_added}")

    if file_stats:
        print("\n添加详情:")
        for file_name, lines, headings in sorted(file_stats, key=lambda x: -x[1]):
            print(f"  📄 {file_name}: {lines}行, {headings}个标题")

    print(f"\n{'=' * 60}")

    if args.dry_run:
        print("\n💡 这是模拟运行。移除 --dry-run 参数以实际添加。")
    else:
        print(f"\n✅ 添加完成！共为 {total_added} 个文档添加目录。")

    return total_added


if __name__ == "__main__":
    main()
