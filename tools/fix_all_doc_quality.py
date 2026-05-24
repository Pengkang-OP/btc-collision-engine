"""批量修复所有文档的代码块语言缺失问题"""

import re
from pathlib import Path

DOCS_DIR = Path("docs")


def fix_code_blocks(content: str, fname: str) -> str:
    lines = content.split("\n")
    result = []
    in_code = False
    lang = "text"

    for line in lines:
        s = line.strip()
        if s.startswith("```") and not in_code:
            fence_content = s[3:].strip()
            if not fence_content:
                # 根据内容推断语言
                result.append(f"```{lang}")
            else:
                result.append(line)
            in_code = True
            lang = "text"  # reset
        elif s == "```" and in_code:
            result.append(line)
            in_code = False
        elif in_code and not any(l.strip().startswith("```") for l in [line]):
            # 根据代码内容更新语言推断
            if lang == "text":
                stripped = line.strip()
                if (
                    stripped.startswith("$ ")
                    or stripped.startswith("# ")
                    or "apt-get" in stripped
                    or "pip install" in stripped
                    or "git " in stripped
                    or "docker " in stripped
                ):
                    lang = "bash"
                elif any(
                    stripped.startswith(x) for x in ["import ", "from ", "def ", "class ", "print("]
                ):
                    lang = "python"
                elif stripped.startswith("{") and '"' in stripped:
                    lang = "json"
            result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def fix_version_header(content: str) -> str:
    if "版本" in content[:500] or "Version" in content[:500]:
        return content
    m = re.search(r"^(# .+)$", content, re.MULTILINE)
    if m:
        pos = m.end()
        return content[:pos] + "\n\n**版本**: v4.5.1\n" + content[pos:]
    return content


def main():
    fixed_lang = 0
    fixed_ver = 0
    total_docs = 0

    for fpath in sorted(DOCS_DIR.glob("*.md")):
        total_docs += 1
        content = fpath.read_text(encoding="utf-8")
        original = content

        content = fix_version_header(content)
        content = fix_code_blocks(content, fpath.name)

        if content != original:
            fpath.write_text(content, encoding="utf-8")
            printed = False
            # Check what changed
            if fix_version_header(original) != fix_version_header(content):
                fixed_ver += 1
                if not printed:
                    print(f"  ✅ {fpath.name}")
                    printed = True
            else:
                fixed_lang += 1
                if not printed:
                    print(f"  ✅ {fpath.name}")
                    printed = True

    print(f"\n总计: {total_docs} 个文档")
    print(f"版本信息添加: {fixed_ver}")
    print(f"代码块语言修复: {fixed_lang}")


if __name__ == "__main__":
    main()
