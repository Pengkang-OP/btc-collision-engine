#!/usr/bin/env python3
"""Check MD022/MD026/MD032 issues across all markdown files (dry-run)."""
import os
import re


def check_file(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    md022 = md026 = md032 = 0
    in_code_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Toggle code block state on fence lines
        if re.match(r'^(```+|~~~+)\w*\s*$', stripped):
            in_code_block = not in_code_block
            continue

        # Skip checks inside code blocks
        if in_code_block:
            continue

        if re.match(r'^#{1,6}\s+\S', stripped):
            if i > 0 and lines[i -1].strip() != '' and lines[i -1].strip() != '---':
                before = lines[i -1].strip()
                if not re.match(r'^#{1,6}\s+\S', before) and not re.match(r'^[\s]*[-*+]\s', before):
                    md022 += 1
        if re.match(r'^(#{1,6}\s+)(.+?)([：:])\s*$', stripped):
            md026 += 1
        is_list = bool(re.match(r'^[\s]*[-*+]\s', stripped)) or bool(
            re.match(r'^[\s]*\d+[.)]\s', stripped))
        if is_list and i > 0 and lines[i -1].strip() != '':
            before = lines[i -1].strip()
            if not re.match(r'^#{1,6}\s+\S', before) and before != '---' and '|' not in before:
                md032 += 1
    return md022, md026, md032


docs_dir = 'f:/Qoder/btc-collision-engine/docs'
results = []

for root, dirs, files in os.walk(docs_dir):
    dirs[:] = [d for d in dirs if d != 'archive']
    for f in sorted(files):
        if not f.endswith('.md'):
            continue
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, 'f:/Qoder/btc-collision-engine')
        md022, md026, md032 = check_file(fp)
        total = md022 + md026 + md032
        if total > 0:
            results.append((total, md022, md026, md032, rel))

results.sort(key=lambda x: -x[0])
print(f"{'文件':<55} {'MD022':>6} {'MD026':>6} {'MD032':>6} {'总计':>6}")
print('-' * 80)
t022 = t026 = t032 = 0
for total, md022, md026, md032, rel in results:
    print(f"{rel:<55} {md022:>6} {md026:>6} {md032:>6} {total:>6}")
    t022 += md022
    t026 += md026
    t032 += md032
print('-' * 80)
print(f"{'总计':<55} {t022:>6} {t026:>6} {t032:>6} {t022 +t026 +t032:>6}")
print(f"共 {len(results)} 个文件有问题")
