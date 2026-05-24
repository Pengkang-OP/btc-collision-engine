#!/usr/bin/env python
"""
批量更新工具文件使用共享UTF8模块

自动将所有工具文件中的重复UTF-8设置代码替换为共享模块调用
"""

import re
from pathlib import Path

TOOLS_TO_UPDATE = [
    "tools/add_table_of_contents.py",
    "tools/add_version_info.py",
    "tools/fix_heading_levels.py",
    "tools/fix_code_blocks.py",
]

# 匹配旧的UTF-8设置代码模式
OLD_PATTERN = r"""# 修复Windows控制台编码问题
if sys\.platform == 'win32':
    try:
        import ctypes
        ctypes\.windll\.kernel32\.SetConsoleOutputCP\(65001\)
        ctypes\.windll\.kernel32\.SetConsoleCP\(65001\)
    except.*?:
        pass

    sys\.stdout = io\.TextIOWrapper\(sys\.stdout\.buffer, encoding='utf-8', errors='replace'\)
    sys\.stderr = io\.TextIOWrapper\(sys\.stderr\.buffer, encoding='utf-8', errors='replace'\)"""

NEW_CODE = """# 修复Windows控制台编码问题 - 使用共享模块
from tools.utf8_helper import setup_windows_utf8
setup_windows_utf8()"""


def update_file(file_path: str) -> bool:
    """更新单个文件"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  文件不存在: {file_path}")
        return False

    content = path.read_text(encoding="utf-8")

    # 检查是否已经更新过
    if "from tools.utf8_helper import setup_windows_utf8" in content:
        print(f"✅ 已更新: {file_path}")
        return True

    # 查找并替换
    new_content = re.sub(OLD_PATTERN, NEW_CODE, content, flags=re.DOTALL)

    if new_content == content:
        print(f"⚠️  未找到匹配代码: {file_path}")
        return False

    # 保存更新
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ 已更新: {file_path}")
    return True


def main():
    """主函数"""
    print("🔧 开始批量更新工具文件...\n")

    success_count = 0
    for tool in TOOLS_TO_UPDATE:
        if update_file(tool):
            success_count += 1

    print(f"\n{'=' * 60}")
    print("📊 更新报告")
    print(f"{'=' * 60}")
    print(f"\n✅ 成功更新: {success_count}/{len(TOOLS_TO_UPDATE)}")

    return success_count == len(TOOLS_TO_UPDATE)


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
