import os
import re


def remove_git_conflicts(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    patterns = [
        r"<<<<<<< Updated upstream\n.*?=======\n.*?>>>>>>> Stashed changes\n",
        r"<<<<<<< Updated upstream\n.*?=======\n.*?>>>>>>> Stashed changes",
    ]

    original_length = len(content)
    for pattern in patterns:
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    if len(content) != original_length:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"清理完成: {file_path}")
        return True
    return False


def main():
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    docs_dir = os.path.abspath(docs_dir)

    conflict_files = []
    for root, _dirs, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    if "<<<<<<<" in content or "=======" in content or ">>>>>>>" in content:  # noqa: E501
                        conflict_files.append(file_path)

    print(f"发现 {len(conflict_files)} 个包含冲突标记的文件:")
    for file in conflict_files:
        print(f"  - {file}")

    print("\n开始清理...")
    cleaned_count = 0
    for file_path in conflict_files:
        if remove_git_conflicts(file_path):
            cleaned_count += 1

    print(f"\n清理完成，共处理 {cleaned_count} 个文件")


if __name__ == "__main__":
    main()
