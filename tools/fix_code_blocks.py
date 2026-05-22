#!/usr/bin/env python
"""
自动修复代码块语言类型

将所有未指定语言的代码块添加语言类型（python/bash/markdown等）

使用方法:
    python tools/fix_code_blocks.py [--dry-run]
"""

import re
import sys
from pathlib import Path
from typing import Tuple

# 修复Windows控制台编码问题 - 使用共享模块`nfrom tools.utf8_helper import setup_windows_utf8`nsetup_windows_utf8()


def detect_language(code_content: str, context: str) -> str:
    """根据代码内容和上下文检测语言类型"""
    code_content = code_content.strip()

    # Python代码特征
    python_patterns = [
        r"^import\s+\w+",
        r"^from\s+\w+\s+import",
        r"^def\s+\w+",
        r"^class\s+\w+",
        r"print\(.*\)",
        r"if\s+__name__\s*==",
        r"self\.",
        r"@\w+",  # 装饰器
    ]

    for pattern in python_patterns:
        if re.search(pattern, code_content, re.MULTILINE):
            return "python"

    # Bash/Shell脚本特征
    bash_patterns = [
        r"^#!/bin/bash",
        r"^#!/bin/sh",
        r"^sudo\s+",
        r"^apt-get\s+",
        r"^pip\s+install",
        r"^git\s+",
        r"^cd\s+",
        r"^python\s+",
        r"export\s+\w+",
        r"\$\w+",  # 变量
    ]

    for pattern in bash_patterns:
        if re.search(pattern, code_content, re.MULTILINE):
            return "bash"

    # YAML特征
    yaml_patterns = [
        r"^\w+:\s*\w+",
        r"^\s+-\s+\w+",
        r"github-actions",
    ]

    for pattern in yaml_patterns:
        if re.search(pattern, code_content, re.MULTILINE):
            return "yaml"

    # JSON特征
    if code_content.startswith("{") or code_content.startswith("["):
        return "json"

    # Markdown特征
    if code_content.startswith("#") or code_content.startswith("##"):
        return "markdown"

    # 检查上下文
    context_lower = context.lower()
    if "python" in context_lower:
        return "python"
    if "bash" in context_lower or "shell" in context_lower:
        return "bash"

    # 默认为python（项目主要语言）
    return "python"


def fix_code_blocks_in_file(file_path: Path, dry_run: bool = False) -> Tuple[int, int]:
    """修复单个文件中的代码块

    Returns:
        (修复数量, 文件行数)
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    fixed_count = 0
    in_code_block = False
    code_block_start = 0
    code_content = []
    context_lines = []

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_code_block:
                # 代码块开始
                in_code_block = True
                code_block_start = i

                # 检查是否已经有语言类型
                if line.strip() == "```":
                    # 需要修复
                    pass
                else:
                    # 已有语言类型，跳过
                    in_code_block = False
            else:
                # 代码块结束
                in_code_block = False
                code_text = "\n".join(code_content)

                # 检测语言类型
                context = "\n".join(context_lines[-5:])  # 前5行上下文
                language = detect_language(code_text, context)

                # 修复代码块开始标记
                if lines[code_block_start].strip() == "```":
                    lines[code_block_start] = f"```{language}"
                    fixed_count += 1

                code_content = []
        elif in_code_block:
            code_content.append(line)
        else:
            context_lines.append(line)

    if fixed_count > 0 and not dry_run:
        new_content = "\n".join(lines)
        file_path.write_text(new_content, encoding="utf-8")

    return fixed_count, len(lines)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="自动修复代码块语言类型")
    parser.add_argument("--dry-run", action="store_true", help="仅显示修复计划，不实际修改文件")
    parser.add_argument("--docs-dir", default="docs", help="文档目录路径 (默认: docs)")

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    print("🔧 开始修复代码块语言类型...\n")

    if args.dry_run:
        print("⚠️  模拟运行模式 - 不会修改文件\n")

    md_files = list(docs_dir.glob("*.md"))
    # 排除archive目录
    md_files = [f for f in md_files if "archive" not in str(f)]

    total_fixed = 0
    total_files = 0
    file_stats = []

    for md_file in sorted(md_files):
        fixed, lines = fix_code_blocks_in_file(md_file, args.dry_run)

        if fixed > 0:
            total_fixed += fixed
            total_files += 1
            file_stats.append((md_file.name, fixed, lines))

    # 打印统计信息
    print("=" * 60)
    print("📊 代码块修复报告")
    print("=" * 60)

    if not file_stats:
        print("\n✅ 所有代码块都已指定语言类型！")
    else:
        print(f"\n📁 扫描文件数: {len(md_files)}")
        print(f"🔧 修复文件数: {total_files}")
        print(f"✨ 修复代码块数: {total_fixed}")
        print("\n修复详情:")

        for file_name, fixed, lines in sorted(file_stats, key=lambda x: -x[1]):
            percentage = (fixed / lines * 100) if lines > 0 else 0
            print(f"  📄 {file_name}")
            print(f"     修复: {fixed}个代码块 ({percentage:.1f}%的行数)")

    print("\n" + "=" * 60)

    if args.dry_run:
        print("\n💡 这是模拟运行。移除 --dry-run 参数以实际修复。")
    else:
        print(f"\n✅ 修复完成！共修复 {total_fixed} 个代码块。")

    return total_fixed


if __name__ == "__main__":
    main()
