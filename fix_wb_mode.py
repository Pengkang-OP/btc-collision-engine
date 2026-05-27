#!/usr/bin/env python3
"""批量修复 src 中的 "wb" 模式为文本模式（json.dump 需要文本模式）"""

import os

BASE = r"f:\Qoder\btc-collision-engine"

files = {
    "src/monitoring/monitoring_system.py": [
        ('open("wb")', 'open("w", encoding="utf-8")'),
    ],
    "src/monitoring/data_logger.py": [
        ('open("wb")', 'open("w", encoding="utf-8")'),
    ],
}

for relpath, replacements in files.items():
    full = os.path.join(BASE, relpath)
    with open(full, "r", encoding="utf-8") as f:
        content = f.read()
    orig = content
    for old, new in replacements:
        content = content.replace(old, new)
    if content != orig:
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  FIXED: {relpath} ({content.count(new)} replacements)")
    else:
        print(f"  OK: {relpath} (no changes)")

print("\nDone!")
