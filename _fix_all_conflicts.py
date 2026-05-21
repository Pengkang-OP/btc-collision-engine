#!/usr/bin/env python3
"""批量修复项目中所有 Git 冲突标记 (保留 Updated upstream 版本)"""
import os
import re

# 排除目录
EXCLUDE_DIRS = {".history", ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
                ".ruff_cache", ".qoder", ".qodo", ".trae", ".vscode", ".codeartsdoer",
                ".codebuddy", "venv", "node_modules", ".benchmarks"}

# 冲突块: 保留第一个版本, 丢弃 Stashed changes 部分
RE_CONFLICT = re.compile(
    r'<<<<<<< Updated upstream\n(.*?)\n=======\n.*?\n>>>>>>> Stashed changes',
    re.DOTALL
)

files_fixed = 0

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

    for fname in files:
        if not fname.endswith(".py"):
            continue

        fpath = os.path.join(root, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        if "<<<<<<<" not in content:
            continue

        original = content
        content = RE_CONFLICT.sub(r'\1', content)

        if content != original:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            count = original.count("<<<<<<<")
            print(f"[OK] {count} conflicts resolved: {fpath}")
            files_fixed += 1
        else:
            # 可能模式不匹配, 打印上下文排查
            idx = content.find("<<<<<<<")
            snippet = content[idx:idx+200]
            print(f"[??] Unresolved pattern in {fpath}:")
            print(f"     {repr(snippet[:120])}")

print(f"\n=== Done: {files_fixed} files fixed ===")
