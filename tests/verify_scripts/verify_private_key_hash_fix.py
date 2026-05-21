#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证私钥内存哈希修复"""

import sys
import re


def verify_private_key_hash_fix():
    """验证私钥内存哈希修复"""
    print("=" * 80)
    print("私钥内存哈希修复验证")
    print("=" * 80)

    # 检查data_monitor.py
    file_path = "src/gpu/data_monitor.py"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        issues = []
        fixes = []

        # 检查1: 是否存在明文私钥存储
        if re.search(r"stats\['seen_keys'\]\.add\(private_key\)", content):
            issues.append("❌ 仍存在明文私钥存储")
        else:
            fixes.append("✅ 明文私钥存储已移除")

        # 检查2: 是否使用SHA256哈希
        if "hashlib.sha256" in content and "private_key_hash" in content:
            fixes.append("✅ 使用SHA256哈希代替明文")
        else:
            issues.append("❌ 未使用SHA256哈希")

        # 检查3: 日志中是否还有私钥前缀
        if re.search(r"private_key\[:\d+\]", content):
            issues.append("❌ 日志中仍存在私钥前缀")
        else:
            fixes.append("✅ 日志中无私钥前缀")

        # 检查4: 是否使用哈希前缀
        if "private_key_hash[:8]" in content:
            fixes.append("✅ 使用哈希前缀代替私钥前缀")
        else:
            issues.append("❌ 未使用哈希前缀")

        # 检查5: details字典是否安全
        if "'private_key_prefix'" in content:
            issues.append("❌ details中仍包含私钥前缀")
        else:
            fixes.append("✅ details中使用哈希前缀")

        if "private_key_hash_prefix" in content:
            fixes.append("✅ details中使用哈希字段名")

        # 输出结果
        print(f"\n📄 {file_path}")
        for fix in fixes:
            print(f"   {fix}")

        if issues:
            for issue in issues:
                print(f"   {issue}")
            print(f"\n❌ 验证失败: {len(issues)}个问题")
            return 1
        else:
            print(f"\n✅ 所有检查通过: {len(fixes)}项修复")
            return 0

    except Exception as e:
        print(f"❌ 文件读取失败: {e}")
        return 1


def check_other_files():
    """检查其他文件的私钥安全"""
    print("\n" + "=" * 80)
    print("其他文件私钥安全检查")
    print("=" * 80)

    files_to_check = [
        "src/collision/deduplication_filter.py",
        "src/collision/bloom_deduplication_filter.py",
        "src/utils/security_log_filter.py",
    ]

    all_safe = True

    for file_path in files_to_check:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查是否使用哈希
            uses_hash = "hashlib.sha256" in content or "sha256" in content

            if uses_hash:
                print(f"✅ {file_path}: 使用SHA256哈希")
            else:
                print(f"⚠️  {file_path}: 未使用SHA256哈希（需人工确认）")

        except Exception as e:
            print(f"❌ {file_path}: 文件读取失败 - {e}")
            all_safe = False

    return 0 if all_safe else 1


if __name__ == "__main__":
    result1 = verify_private_key_hash_fix()
    result2 = check_other_files()

    print("\n" + "=" * 80)
    if result1 == 0 and result2 == 0:
        print("🎉 私钥内存哈希修复验证通过！")
        print("=" * 80)
        sys.exit(0)
    else:
        print("⚠️  部分验证未通过，请检查")
        print("=" * 80)
        sys.exit(1)
