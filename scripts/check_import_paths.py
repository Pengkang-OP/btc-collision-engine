#!/usr/bin/env python3
"""导入路径检查脚本

检查项目中是否使用了已弃用的导入路径。

使用方法:
    python scripts/check_import_paths.py

返回值:
    0 - 所有导入路径正确
    1 - 发现使用旧路径的代码
"""

import os
import re
import sys
from pathlib import Path

# 已弃用的导入路径模式
DEPRECATED_PATTERNS = [
    r"from\s+src\.collision\.target_resolver\s+import",
    r"from\s+\.\.target_resolver\s+import",
    r"from\s+\.target_resolver\s+import",
]

# 允许使用旧路径的文件（用于测试向后兼容性）
ALLOWED_DEPRECATED_FILES = [
    "tests/test_import_paths.py",  # 导入路径测试（需要测试旧路径）
]

# 推荐的导入路径
RECOMMENDED_IMPORTS = [
    "from src.collision.targets.resolver import TargetResolver",
    "from src.collision.targets import TargetResolver",
]

# 需要检查的目录
CHECK_DIRS = ["src", "tests"]

# 忽略的目录
IGNORE_DIRS = ["__pycache__", ".git", ".pytest_cache", "node_modules", "venv", "env"]

# 文件扩展名
CHECK_EXTENSIONS = [".py"]


def is_ignored_dir(dirpath: str) -> bool:
    """检查目录是否应该被忽略"""
    dir_name = os.path.basename(dirpath)
    return dir_name in IGNORE_DIRS


def should_check_file(filepath: str) -> bool:
    """检查文件是否应该被检查"""
    return any(filepath.endswith(ext) for ext in CHECK_EXTENSIONS)


def check_file_for_deprecated_imports(filepath: str) -> list:
    """检查文件中的弃用导入路径"""
    issues = []

    # 检查是否是允许使用旧路径的文件
    rel_path = os.path.relpath(filepath, Path(__file__).parent.parent)
    rel_path_normalized = rel_path.replace("\\", "/")

    if any(rel_path_normalized.startswith(allowed) for allowed in ALLOWED_DEPRECATED_FILES):
        return []  # 跳过允许的文件

    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # 跳过注释
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # 检查是否包含弃用的导入路径
            for pattern in DEPRECATED_PATTERNS:
                if re.search(pattern, line):
                    issues.append(
                        {
                            "file": filepath,
                            "line": line_num,
                            "content": line.rstrip(),
                            "pattern": pattern,
                        }
                    )
                    break
    except Exception as e:
        print(f"[WARN] 读取文件失败 {filepath}: {e}", file=sys.stderr)

    return issues


def check_project() -> list:
    """检查整个项目"""
    all_issues = []
    project_root = Path(__file__).parent.parent

    for check_dir in CHECK_DIRS:
        dir_path = project_root / check_dir

        if not dir_path.exists():
            continue

        for root, dirs, files in os.walk(dir_path):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if not is_ignored_dir(d)]

            for file in files:
                filepath = os.path.join(root, file)

                if not should_check_file(filepath):
                    continue

                issues = check_file_for_deprecated_imports(filepath)
                all_issues.extend(issues)

    return all_issues


def print_report(issues: list) -> None:
    """打印检查报告"""
    if not issues:
        print("[PASS] 所有导入路径正确")
        print("\n推荐的导入方式:")
        for imp in RECOMMENDED_IMPORTS:
            print(f"  [OK] {imp}")
        return

    print("[FAIL] 发现使用已弃用导入路径的代码\n")
    print(f"共发现 {len(issues)} 个问题:\n")

    for i, issue in enumerate(issues, 1):
        # 计算相对路径
        rel_path = os.path.relpath(issue["file"], Path(__file__).parent.parent)
        print(f"{i}. [FILE] {rel_path}:{issue['line']}")
        print(f"   {issue['content']}")
        print()

    print("=" * 80)
    print("\n[TIP] 修复建议:")
    print("\n推荐的导入方式:")
    for imp in RECOMMENDED_IMPORTS:
        print(f"  [OK] {imp}")

    print("\n请替换所有使用旧路径的代码。")
    print("旧路径将在 v4.2.1 (2026-Q3) 中移除。\n")


def main():
    """主函数"""
    print("=" * 80)
    print("[INFO] 导入路径检查工具")
    print("=" * 80)
    print()

    issues = check_project()
    print_report(issues)

    if issues:
        print("=" * 80)
        print("[FAIL] 检查失败: 发现弃用的导入路径")
        print("=" * 80)
        sys.exit(1)
    else:
        print("=" * 80)
        print("[PASS] 检查通过: 所有导入路径正确")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
