"""分析并修复文档标题层级跳跃"""
import re
from pathlib import Path

POOR_DOCS = [
    "USER_GUIDE.md", "DOCKER_DEPLOYMENT.md", "PROJECT_COMPREHENSIVE_ANALYSIS_V3.md",
    "SYSTEMD_DEPLOYMENT.md", "api-reference.md", "CRYPTO_BACKEND_MIGRATION_REPORT.md",
    "architecture.md", "GPU_ASYNC_LOGGING_USAGE_EXAMPLES.md",
]

def analyze_jumps(doc_name):
    path = Path("docs", doc_name)
    if not path.exists():
        return [], []
    lines = path.read_text(encoding="utf-8").split("\n")
    headings = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.+)$", line)
        if m:
            headings.append((len(m.group(1)), m.group(2), i))

    jumps = []
    for i in range(1, len(headings)):
        prev_lvl, prev_title, _ = headings[i-1]
        curr_lvl, curr_title, _ = headings[i]
        if curr_lvl > prev_lvl + 1:
            jumps.append((prev_lvl, prev_title, curr_lvl, curr_title, headings[i][2]))
    return headings, jumps

def fix_doc_heading_jumps(content):
    """提升子标题一级以消除跳跃"""
    lines = content.split("\n")
    result = []
    prev_level = 0

    for line in lines:
        m = re.match(r"^(#+)\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()

            if prev_level > 0 and level > prev_level + 1:
                # 有跳跃：将当前标题提升为 prev_level + 1
                level = prev_level + 1

            prev_level = level
            result.append("#" * level + " " + title)
        else:
            result.append(line)

    return "\n".join(result)

print("=" * 60)
print("标题层级跳跃分析")
print("=" * 60)

total_fixed = 0
for doc in POOR_DOCS:
    path = Path("docs", doc)
    if not path.exists():
        print(f"\n⚠️ {doc}: 不存在"); continue

    headings, jumps = analyze_jumps(doc)
    if not jumps:
        print(f"\n✅ {doc}: 无标题跳跃 (共 {len(headings)} 个标题)")
        continue

    print(f"\n⚠️ {doc}: {len(jumps)} 处跳跃 (共 {len(headings)} 个标题)")
    for prev_lvl, prev_title, curr_lvl, curr_title, line_no in jumps:
        print(f"  L{line_no}: {'#'*prev_lvl} {prev_title[:40]}")
        print(f"          → {'#'*curr_lvl} {curr_title[:40]} (应降为 {'#'*(prev_lvl+1)})")

    # 修复
    content = path.read_text(encoding="utf-8")
    fixed = fix_doc_heading_jumps(content)
    if fixed != content:
        path.write_text(fixed, encoding="utf-8")
        total_fixed += 1
        print("  ✅ 已修复")

print(f"\n{'='*60}")
print(f"修复完成: {total_fixed}/{sum(1 for d in POOR_DOCS if Path('docs',d).exists())}")
