#!/usr/bin/env python3
"""Fix MD012: 修复版本行后和文件开头附近的多个连续空行问题。"""
import os


def fix_md012(content: str):
    """将 3 个连续空行缩减为 1 个连续空行。"""
    lines = content.split('\n')
    result = []
    blank_count = 0
    changes = 0
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count >= 2:
                changes += 1
                continue
            result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return '\n'.join(result), changes


def collect_md_files(root: str):
    """递归收集 root 下所有 .md 文件。"""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith('.md'):
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_fix = collect_md_files(root)
    total = 0
    fixed_count = 0
    for fp in files_to_fix:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content, c = fix_md012(content)
        if c > 0:
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(new_content)
            total += c
            fixed_count += 1
            print(f"  OK {os.path.relpath(fp, root)}: {c} changes")
    print(f"\nDone: {total} MD012 fixes across {fixed_count}/{len(files_to_fix)} files")


if __name__ == '__main__':
    main()
