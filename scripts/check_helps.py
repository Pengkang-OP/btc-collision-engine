import re

with open("src/cli/arg_parser.py", encoding="utf-8") as f:
    content = f.read()

# 查找所有help参数
helps = re.findall(r'help="([^"]+)"', content)
print(f"Found {len(helps)} help strings")

for i, h in enumerate(helps[:20]):
    # 检查是否有格式化问题
    if "%(" in h or "{" in h:
        print(f"{i + 1}: {repr(h[:80])}")
