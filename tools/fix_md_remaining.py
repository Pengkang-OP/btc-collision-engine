#!/usr/bin/env python3
"""修复 MD022/MD026/MD032 问题。

MD022: 标题前后需要空行
MD026: 标题末尾不要标点符号（中文：）
MD032: 列表前后需要空行
"""
import re
import os


def fix_all(content: str):
    lines = content.split('\n')
    result = []
    changes = {'MD022': 0, 'MD026': 0, 'MD032': 0}
    i = 0
    n = len(lines)
    in_code_block = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Detect fenced code blocks (```/~~~), toggle state and process as fence
        is_fence = bool(re.match(r'^(```+|~~~+)\w*\s*$', stripped))

        if is_fence:
            in_code_block = not in_code_block
            # Only need blank before the opening fence (after a closing fence the
            # next real heading/list will handle its own blank line check)
            if i > 0 and lines[i -1].strip() != '' and lines[i -1].strip() != '---':
                result.append('')
                changes['MD022'] += 1

            result.append(line)
            i += 1
            continue

        # Inside code block: skip all fix logic, output as-is
        if in_code_block:
            result.append(line)
            i += 1
            continue

        # MD026: Remove trailing colon from headings
        heading_match = re.match(r'^(#{1,6}\s+)(.+?)([：:])\s*$', stripped)
        if heading_match:
            prefix = heading_match.group(1)
            text = heading_match.group(2)
            new_line = f"{' ' * (len(line) - len(stripped))}{prefix}{text}"
            result.append(new_line)
            changes['MD026'] += 1
            i += 1
            continue

        # Check if this is a heading or list
        is_heading = bool(re.match(r'^#{1,6}\s+\S', stripped))
        is_list = bool(re.match(r'^[\s]*[-*+]\s', stripped)) or bool(
            re.match(r'^[\s]*\d+[.)]\s', stripped))

        if is_heading or is_list:
            # Check previous line
            prev_is_blank = (i > 0 and lines[i -1].strip() == '')
            prev_is_hr = (i > 0 and lines[i -1].strip() == '---')

            if is_heading and i > 0 and not prev_is_blank and not prev_is_hr:
                # Add blank before heading
                before = lines[i -1].strip()
                before_is_heading = bool(re.match(r'^#{1,6}\s+\S', before))
                before_is_list = bool(re.match(r'^[\s]*[-*+]\s', before)) or bool(
                    re.match(r'^[\s]*\d+[.)]\s', before))
                if not before_is_heading and not before_is_list:
                    result.append('')
                    changes['MD022'] += 1

            if is_list and i > 0 and not prev_is_blank:
                before = lines[i -1].strip()
                before_is_heading = bool(re.match(r'^#{1,6}\s+\S', before))
                before_is_hr = before == '---'
                before_is_table = '|' in before
                if not before_is_heading and not before_is_hr and not before_is_table:
                    result.append('')
                    changes['MD032'] += 1

            result.append(line)
            i += 1

            # Check next line for MD022/MD032
            if i < n:
                next_stripped = lines[i].strip()
                next_is_blank = next_stripped == ''
                next_is_hr = next_stripped == '---'
                next_is_heading = bool(re.match(r'^#{1,6}\s+\S', next_stripped))
                next_is_list = bool(re.match(r'^[\s]*[-*+]\s', next_stripped)) or bool(
                    re.match(r'^[\s]*\d+[.)]\s', next_stripped))
                next_is_fence = bool(re.match(r'^(```+|~~~+)', next_stripped))
                next_is_table = '|' in next_stripped

                if is_heading and not next_is_blank and not next_is_hr:
                    if next_is_list or next_is_fence:
                        result.append('')
                        changes['MD022'] += 1
                    elif not next_is_heading:
                        result.append('')
                        changes['MD022'] += 1

                if is_list and not next_is_blank:
                    if not next_is_list and not next_is_fence and not next_is_heading \
                            and not next_is_hr and not next_is_table:
                        result.append('')
                        changes['MD032'] += 1
            continue

        result.append(line)
        i += 1

    return '\n'.join(result), changes


def main():
    docs_dir = 'f:/Qoder/btc-collision-engine/docs'
    project_root = 'f:/Qoder/btc-collision-engine'

    targets = []
    for root, dirs, files in os.walk(docs_dir):
        dirs[:] = [d for d in dirs if d != 'archive']
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, project_root)
                targets.append(rel)

    targets = sorted(set(targets))
    total = {'MD022': 0, 'MD026': 0, 'MD032': 0}
    fixed_files = 0
    error_files = 0

    for rel in targets:
        fp = os.path.join(project_root, rel)
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content, ch = fix_all(content)
            tc = sum(ch.values())
            if tc > 0:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed_files += 1
                parts = [f"{k}:{v}" for k, v in ch.items() if v > 0]
                print(f"  OK {rel} ({', '.join(parts)})")
                for k in total:
                    total[k] += ch[k]
        except Exception as e:
            error_files += 1
            print(f"  ERR {rel}: {e}")

    print(f'\nDone: fixed {fixed_files} files, {error_files} errors')
    print(f'MD022={total["MD022"]}, MD026={total["MD026"]}, MD032={total["MD032"]}')


if __name__ == '__main__':
    main()
