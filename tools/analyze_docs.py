"""分析文档质量修复进度"""

import re
from pathlib import Path

docs = list(Path("docs").glob("*.md"))
print(f"docs/ 目录: {len(docs)} 个 .md 文件\n")

for fname in sorted(d.name for d in docs):
    content = Path("docs", fname).read_text(encoding="utf-8")
    lines = content.splitlines()

    # 统计
    code_blocks = 0
    no_lang_blocks = 0
    in_code = False
    headings = []

    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            if in_code:
                code_blocks += 1
                in_code = False
            else:
                lang = s[3:].strip()
                if not lang:
                    no_lang_blocks += 1
                in_code = True
        if s.startswith("#") and not s.startswith("```"):
            match = re.match(r"^(#+)", s)
            if match:
                headings.append(len(match.group(1)))

    has_toc = "目录" in content[:1000] or "Table of Contents" in content[:1000]
    has_version = "版本" in content[:500] or "Version" in content[:500]
    heading_jumps = sum(1 for i in range(1, len(headings)) if headings[i] - headings[i - 1] > 1)

    print(f"{'✅' if no_lang_blocks == 0 else '⚠️'} {fname}")
    print(
        f"   代码块: {code_blocks} | 无语言: {no_lang_blocks} | "
        f"标题跳跃: {heading_jumps} | 目录: {'有' if has_toc else '无'} | "
        f"版本: {'有' if has_version else '无'}"
    )
