#!/usr/bin/env python
"""增强的代码块修复工具 - 第2轮

专门处理第一轮修复遗漏的代码块问题
包括:
- 嵌套代码块
- 特殊格式代码块
- Mermaid图表块
- 表格中的代码

使用方法:
    python tools/fix_code_blocks_v2.py
"""

import re
import sys
from pathlib import Path

# 修复Windows控制台编码问题 - 使用共享模块
from tools.utf8_helper import setup_windows_utf8

setup_windows_utf8()


def detect_language_v2(code_content: str, context_before: str, context_after: str) -> str:
    """增强版语言类型检测"""
    code_content = code_content.strip()

    # 1. Mermaid图表
    if re.search(
        r"^(graph|sequenceDiagram|classDiagram|stateDiagram|gantt|pie)", code_content, re.MULTILINE
    ):
        return "mermaid"

    # 2. Python代码特征（增强）
    python_patterns = [
        r"^import\s+\w+",
        r"^from\s+\w+\s+import",
        r"^def\s+\w+",
        r"^class\s+\w+",
        r"print\(.*\)",
        r"self\.\w+",
        r"@\w+\.route",
        r"async\s+def",
        r"await\s+",
        r"logging\.\w+",
        r"logger\.\w+",
    ]

    for pattern in python_patterns:
        if re.search(pattern, code_content, re.MULTILINE):
            return "python"

    # 3. Bash/Shell脚本（增强）
    bash_patterns = [
        r"^#!/bin/bash",
        r"^#!/bin/sh",
        r"^pip\s+install",
        r"^git\s+",
        r"^cd\s+",
        r"^python\s+",
        r"^pytest\s+",
        r"^make\s+",
        r"^docker\s+",
        r"^chmod\s+",
        r"^export\s+\w+",
        r"^\$\(\w+",
    ]

    for pattern in bash_patterns:
        if re.search(pattern, code_content, re.MULTILINE):
            return "bash"

    # 4. YAML配置
    yaml_patterns = [
        r"^\w+:\s*\w+",
        r"^\s+-\s+\w+",
        r"^[\w_-]+:\s*$",
    ]

    yaml_match_count = sum(
        1 for pattern in yaml_patterns if re.search(pattern, code_content, re.MULTILINE)
    )
    if yaml_match_count >= 2:
        return "yaml"

    # 5. JSON数据
    if code_content.startswith("{") or code_content.startswith("["):
        try:
            import json

            json.loads(code_content)
            return "json"
        except Exception:
            pass

    # 6. Markdown（如果包含Markdown语法）
    markdown_patterns = [
        r"^#{1,6}\s+",
        r"^\*\*.*\*\*",
        r"^- \[.*?\]",
        r"^\|.*\|",
    ]

    md_match_count = sum(
        1 for pattern in markdown_patterns if re.search(pattern, code_content, re.MULTILINE)
    )
    if md_match_count >= 2:
        return "markdown"

    # 7. 配置文件
    if re.search(r"^[\w_-]+\s*=\s*.*$", code_content, re.MULTILINE):
        return "ini"

    # 8. 根据上下文推断
    if "yaml" in context_after.lower() or "yaml" in context_before.lower():
        return "yaml"
    if "json" in context_after.lower() or "json" in context_before.lower():
        return "json"
    if "python" in context_after.lower() or "python" in context_before.lower():
        return "python"
    if "bash" in context_after.lower() or "bash" in context_before.lower():
        return "bash"

    # 默认为text
    return "text"


def find_unlabeled_code_blocks(content: str) -> list[tuple[int, str]]:
    """查找所有未标注语言类型的代码块

    Returns:
        List of (line_number, opening_line)
    """
    lines = content.split("\n")
    unlabeled = []

    for i, line in enumerate(lines):
        # 匹配 ``` 但没有语言标注
        if re.match(r"^```\s*$", line):
            # 检查是否是关闭标签（前面有代码内容）
            if i > 0 and not lines[i - 1].startswith("```"):
                # 这是关闭标签，跳过
                continue
            # 检查下一个非空行是否也是```（空代码块）
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and lines[j].startswith("```"):
                # 空代码块，跳过
                continue
            # 这是一个未标注的开启标签
            unlabeled.append((i + 1, line))

    return unlabeled


def fix_code_blocks_v2(content: str) -> tuple[str, int]:
    """修复未标注的代码块

    Returns:
        (新内容, 修复数量)
    """
    lines = content.split("\n")
    fixed_count = 0

    # 找到所有未标注的代码块
    unlabeled = find_unlabeled_code_blocks(content)

    if not unlabeled:
        return content, 0

    # 从后向前修复，避免行号变化
    for line_num, _opening_line in reversed(unlabeled):
        line_idx = line_num - 1

        # 提取代码块内容
        code_lines = []
        j = line_idx + 1
        while j < len(lines) and not lines[j].startswith("```"):
            code_lines.append(lines[j])
            j += 1

        if j >= len(lines):
            # 没有关闭标签，跳过
            continue

        code_content = "\n".join(code_lines)

        # 获取上下文
        context_before = "\n".join(lines[max(0, line_idx - 5) : line_idx])
        context_after = "\n".join(lines[j + 1 : min(len(lines), j + 6)])

        # 检测语言类型
        language = detect_language_v2(code_content, context_before, context_after)

        # 如果是text或mermaid，也需要标注
        if language in ["text", "mermaid", "python", "bash", "yaml", "json", "markdown", "ini"]:
            lines[line_idx] = f"```{language}"
            fixed_count += 1

    return "\n".join(lines), fixed_count


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="增强版代码块修复工具 - 第2轮")
    parser.add_argument("--dry-run", action="store_true", help="仅显示修复计划，不实际修改文件")
    parser.add_argument("--docs-dir", default="docs", help="文档目录路径 (默认: docs)")

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"❌ 文档目录不存在: {docs_dir}")
        sys.exit(1)

    print("🔧 开始第2轮代码块修复...\n")

    md_files = list(docs_dir.glob("*.md"))
    md_files = [f for f in md_files if "archive" not in str(f)]

    total_fixed = 0
    file_stats = []

    for md_file in sorted(md_files):
        content = md_file.read_text(encoding="utf-8")
        new_content, fixed = fix_code_blocks_v2(content)

        if fixed > 0:
            file_stats.append((md_file.name, fixed))
            total_fixed += fixed

            if not args.dry_run:
                md_file.write_text(new_content, encoding="utf-8")
                print(f"✅ {md_file.name}: 修复 {fixed} 个代码块")
            else:
                print(f"📄 {md_file.name}: 将修复 {fixed} 个代码块")

    print(f"\n{'=' * 60}")
    print("📊 第2轮修复报告")
    print(f"{'=' * 60}")

    if file_stats:
        print(f"\n📁 扫描文件: {len(md_files)}")
        print(f"✨ 修复文件: {len(file_stats)}")
        print(f"🔧 修复代码块: {total_fixed} 个")
        print("\n修复详情:")
        for file_name, count in sorted(file_stats, key=lambda x: -x[1]):
            print(f"  📄 {file_name}: {count} 个")
    else:
        print("\n✅ 所有代码块已正确标注！")

    print(f"\n{'=' * 60}")

    if args.dry_run:
        print("\n💡 这是模拟运行。移除 --dry-run 参数以实际修复。")

    return total_fixed


if __name__ == "__main__":
    main()
