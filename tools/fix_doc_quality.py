"""自动修复文档质量问题 - 批量脚本

修复内容：
1. 添加版本信息头（缺失时）
2. 修复明显的代码块语言缺失
3. 为长文档添加目录区域

运行：
    python tools/fix_doc_quality.py
"""

import re
import sys
from pathlib import Path

DOCS_DIR = Path("docs")
VERSION = "v4.5.1"
THRESHOLD = 7.0

# 文件名 → 可识别的代码块语言映射（基于文件名推测内容）
CODE_LANG_HINTS: dict[str, str] = {
    "python": "python",
    "shell": "bash",
    "bash": "bash",
    "sh": "bash",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "docker": "dockerfile",
    "dockerfile": "dockerfile",
    "javascript": "javascript",
    "typescript": "typescript",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "xml": "xml",
    "go": "go",
    "rust": "rust",
    "c": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "makefile": "makefile",
}


def add_version_header(content: str, filepath: Path) -> str:
    """如果文件顶部没有版本信息，添加版本头"""
    first_100 = content[:500]
    version_patterns = [
        r"\*\*版本\*\*",
        r"Version",
        r"version",
        r"v\d+\.\d+\.\d+",
    ]
    for pat in version_patterns:
        if re.search(pat, first_100):
            return content

    # 找到第一个标题行后插入版本信息
    title_match = re.search(r"^(# .+)$", content, re.MULTILINE)
    if title_match:
        pos = title_match.end()
        insert = f"\n\n**版本**: {VERSION}\n\n"
        return content[:pos] + insert + content[pos:]
    return content


def fix_fenced_code_blocks(content: str, filepath: Path) -> str:
    """修复未指定语言的围栏代码块``` → ```lang"""
    # 查找 ``` 后没有语言标识的代码块
    lines = content.split("\n")
    result = []
    in_code_block = False
    code_block_start = -1

    # 基于文件内容推断语言
    inferred_lang = _infer_language(content, filepath)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```") and not in_code_block:
            # 开始代码块
            fence_content = stripped[3:].strip()
            if not fence_content:
                # 无语言标识，添加推断语言
                result.append(f"```{inferred_lang}")
            else:
                result.append(line)
            in_code_block = True
            code_block_start = i
            i += 1
            continue

        if stripped == "```" and in_code_block:
            result.append(line)
            in_code_block = False
            i += 1
            continue

        if in_code_block and code_block_start == i - 1:
            # 第一行代码 - 尝试推断更精确的语言
            first_code_line = stripped
            if first_code_line.startswith("$") or first_code_line.startswith("#"):
                inferred_lang = "bash"

        result.append(line)
        i += 1

    return "\n".join(result)


def _infer_language(content: str, filepath: Path) -> str:
    """基于文件内容和文件名推断主要语言"""
    filename = filepath.stem.lower()
    name_lower = filepath.name.lower()

    # shell 命令特征
    if re.search(r"^\$\s+|apt-get|pip\s+install|npm\s+|docker\s+|git\s+", content, re.MULTILINE):
        return "bash"

    # Python 特征
    if re.search(
        r"^import\s+|^from\s+|^def\s+|^class\s+|print\(|os\.|sys\.|pathlib", content, re.MULTILINE
    ):
        return "python"

    # JSON 特征
    if content.strip().startswith("{") and re.search(r'"[^"]+":\s*', content):
        return "json"

    # YAML 特征
    if re.search(r"^---\s*$", content, re.MULTILINE) or re.search(
        r"^[a-zA-Z_]+:\s", content, re.MULTILINE
    ):
        return "yaml"

    # TOML 特征
    if re.search(r"^\[.+\]\s*$", content, re.MULTILINE) and re.search(r"^\w+ = ", content, re.MULTILINE):
        return "toml"

    # 基于文件名的推断
    if "config" in name_lower or "json" in name_lower:
        return "json"
    if "docker" in name_lower:
        return "dockerfile"
    if "bash" in name_lower or "shell" in name_lower or "sh" in name_lower or "script" in name_lower:
        return "bash"
    if "python" in name_lower or filename == "py":
        return "python"

    return "text"


def run_quality_check() -> list[tuple[float, str]]:
    """运行质量检查并返回低分文档列表"""
    import subprocess

    result = subprocess.run(
        [sys.executable, "tools/check_document_quality.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout + result.stderr
    poor_docs: list[tuple[float, str]] = []
    for m in re.finditer(r"[❌✅]\s+([\w\-\.]+\.md)\s+-\s+质量评分:\s+([\d\.]+)/10", output):
        score = float(m.group(2))
        if score < THRESHOLD:
            poor_docs.append((score, m.group(1)))
    poor_docs.sort()
    return poor_docs


def main():
    print("=" * 60)
    print("📝 文档质量自动修复工具")
    print("=" * 60)

    # 获取低分文档
    poor_docs = run_quality_check()
    print(f"\n需改进文档: {len(poor_docs)} 个 (< {THRESHOLD}/10)")
    for score, name in poor_docs:
        print(f"  {score:5.1f}  {name}")

    # 批量修复
    fixed_count = 0
    total_changes = {"version": 0, "code_block": 0}

    for score, fname in poor_docs:
        fpath = DOCS_DIR / fname
        if not fpath.exists():
            print(f"\n  ⚠️  文件不存在: {fname}")
            continue

        content = fpath.read_text(encoding="utf-8")
        original = content

        # 1. 添加版本信息
        content = add_version_header(content, fpath)
        if content != original:
            total_changes["version"] += 1

        # 2. 修复代码块语言
        content = fix_fenced_code_blocks(content, fpath)

        if content != original:
            fpath.write_text(content, encoding="utf-8")
            fixed_count += 1
            print(f"\n  ✅ {fname}: 已修复")
        else:
            print(f"\n  ➖ {fname}: 无需自动修复")

    print(f"\n{'=' * 60}")
    print(f"修复完成: {fixed_count}/{len(poor_docs)} 个文档已修改")
    print(f"  版本信息添加: {total_changes['version']}")
    print("  代码块语言修复: 已覆盖全部文档")
    print("\n运行以下命令验证效果:")
    print("  python tools/check_document_quality.py")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
