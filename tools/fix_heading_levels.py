#!/usr/bin/env python
"""自动修复标题层级跳跃.

检测并修复Markdown文档中的标题层级跳跃问题
例如：从 # 直接跳到 ###，缺少 ##

使用方法:
    python tools/fix_heading_levels.py [--dry-run]
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# 修复Windows控制台编码问题 - 使用共享模块`nfrom tools.utf8_helper import setup_windows_utf8`nsetup_windows_utf8()


@dataclass
class HeadingInfo:
    """标题信息."""

    line_num: int
    level: int  # 1-6
    text: str
    original_line: str


def extract_headings(content: str) -> list[HeadingInfo]:
    """提取文档中的所有标题."""
    headings = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append(HeadingInfo(line_num=i, level=level, text=text, original_line=line))

    return headings


def detect_heading_jumps(headings: list[HeadingInfo]) -> list[tuple[int, int, int]]:
    """检测标题层级跳跃.

    Returns:
        List of (from_level, to_level, line_num)
    """
    jumps = []

    for i in range(1, len(headings)):
        prev_level = headings[i - 1].level
        curr_level = headings[i].level

        # 如果层级跳跃超过1级
        if curr_level > prev_level + 1:
            jumps.append((prev_level, curr_level, headings[i].line_num))

    return jumps


def fix_heading_jumps(content: str, dry_run: bool = False) -> tuple[str, int]:
    """修复标题层级跳跃.

    Returns:
        (修复后的内容, 修复数量)
    """
    lines = content.split("\n")
    headings = extract_headings(content)
    jumps = detect_heading_jumps(headings)

    fixed_count = 0

    # 从后向前修复，避免行号变化影响
    for prev_level, curr_level, line_num in reversed(jumps):
        # 需要插入缺失的层级
        list(range(prev_level + 1, curr_level))

        if not dry_run:
            # 获取当前标题行
            current_line_idx = line_num - 1
            current_line = lines[current_line_idx]

            # 提取标题文本
            match = re.match(r"^(#{1,6})\s+(.+)", current_line)
            if match:
                title_text = match.group(2).strip()

                # 修改当前标题为正确的层级（只降低一级）
                new_level = prev_level + 1
                new_heading = "#" * new_level + " " + title_text
                lines[current_line_idx] = new_heading

                fixed_count += 1

    if not dry_run:
        return "\n".join(lines), fixed_count
    return content, len(jumps)


def analyze_file(file_path: Path) -> dict:
    """分析单个文件的标题层级问题."""
    content = file_path.read_text(encoding="utf-8")
    headings = extract_headings(content)
    jumps = detect_heading_jumps(headings)

    return {
        "file": file_path.name,
        "total_headings": len(headings),
        "total_jumps": len(jumps),
        "jumps": jumps,
        "headings": headings,
    }


def main():
    """主函数."""
    import argparse

    parser = argparse.ArgumentParser(description="自动修复标题层级跳跃")
    parser.add_argument("--dry-run", action="store_true", help="仅显示修复计划，不实际修改文件")
    parser.add_argument("--docs-dir", default="docs", help="文档目录路径 (默认: docs)")

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    print("🔧 开始检查标题层级...\n")

    md_files = list(docs_dir.glob("*.md"))
    # 排除archive目录
    md_files = [f for f in md_files if "archive" not in str(f)]

    total_files_with_jumps = 0
    total_jumps = 0
    file_analyses = []

    # 先分析所有文件
    for md_file in sorted(md_files):
        analysis = analyze_file(md_file)
        if analysis["total_jumps"] > 0:
            total_files_with_jumps += 1
            total_jumps += analysis["total_jumps"]
            file_analyses.append(analysis)

    # 打印分析结果
    print("=" * 60)
    print("📊 标题层级分析报告")
    print("=" * 60)

    print(f"\n📁 扫描文件数: {len(md_files)}")
    print(f"⚠️  有问题的文件: {total_files_with_jumps}")
    print(f"🔢 总跳跃数: {total_jumps}")

    if file_analyses:
        print("\n问题详情:")
        for analysis in sorted(file_analyses, key=lambda x: -x["total_jumps"]):
            print(f"\n📄 {analysis['file']}")
            print(f"   标题总数: {analysis['total_headings']}")
            print(f"   跳跃次数: {analysis['total_jumps']}")

            # 显示前5个跳跃
            for i, (from_level, to_level, line_num) in enumerate(analysis["jumps"][:5]):
                missing = ", ".join(["#" * i for i in range(from_level + 1, to_level)])
                print(f"   ⚠️  行 {line_num}: {'#' * from_level} → {'#' * to_level} (缺少 {missing})")

            if len(analysis["jumps"]) > 5:
                print(f"   ... 还有 {len(analysis['jumps']) - 5} 个跳跃")

    # 执行修复
    if total_jumps > 0:
        print(f"\n{'=' * 60}")

        if args.dry_run:
            print(f"\n💡 这是模拟运行。发现 {total_jumps} 个标题层级跳跃。")
            print("   移除 --dry-run 参数以实际修复。")
        else:
            print("\n🔧 开始修复标题层级跳跃...\n")

            total_fixed = 0
            for md_file in sorted(md_files):
                content = md_file.read_text(encoding="utf-8")
                new_content, fixed = fix_heading_jumps(content, args.dry_run)

                if fixed > 0:
                    if not args.dry_run:
                        md_file.write_text(new_content, encoding="utf-8")
                    total_fixed += fixed
                    print(f"✅ {md_file.name}: 修复 {fixed} 个跳跃")

            print(f"\n{'=' * 60}")
            print("📊 修复报告")
            print(f"{'=' * 60}")
            print(f"\n✅ 修复完成！共修复 {total_fixed} 个标题层级跳跃。")

    print(f"\n{'=' * 60}")

    return total_jumps


if __name__ == "__main__":
    main()
