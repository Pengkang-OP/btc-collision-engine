#!/usr/bin/env python3
"""Show detailed MD022 remaining issues in specific files."""
import re

files = [
    'f:/Qoder/btc-collision-engine/docs/audit-reports/fixes_report_20260519.md',
    'f:/Qoder/btc-collision-engine/docs/CLI_QUICK_REFERENCE.md',
]

for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        ln = i + 1
        if re.match(r'^#{1,6}\s+\S', stripped):
            if i > 0 and lines[i -1].strip() != '' and lines[i -1].strip() != '---':
                before = lines[i -1].strip()
                before_is_heading = bool(re.match(r'^#{1,6}\s+\S', before))
                before_is_list = bool(re.match(r'^[\s]*[-*+]\s', before))
                if not before_is_heading and not before_is_list:
                    prev_snippet = lines[i -1].strip()[:60]
                    print(f"{fp}\n  Ln{ln}: MD022 - heading \"{stripped[:60]}\"")
                    print(f"        prev line (Ln{i}): \"{prev_snippet}\"")
                    print()
