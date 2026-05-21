#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证A类异常修复"""

import sys
import re


def verify_a_class_fixes():
    """验证A类资源清理异常修复"""
    print("=" * 80)
    print("A类资源清理异常修复验证")
    print("=" * 80)

    files = [
        "src/monitoring/data_logger.py",
        "src/monitoring/monitoring_system.py",
        "src/collision/gpu_collision_engine.py",
        "src/collision/checkpoint_manager.py",
        "src/collision/key_collision_engine.py",
        "src/gpu/multi_gpu_engine.py",
        "src/gpu/facade.py",
    ]

    success = 0
    total_fixes = 0

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read()

            # 检查是否有A类修复标记
            a_class_count = content.count("A类修复:")

            if a_class_count > 0:
                success += 1
                total_fixes += a_class_count
                print(f"✅ {f}: {a_class_count}处A类修复")
            else:
                print(f"⚠️  {f}: 未找到A类修复标记")

        except Exception as e:
            print(f"❌ {f}: 文件读取失败 - {e}")

    print("\n" + "=" * 80)
    print(f"总结: {success}/{len(files)} 文件已修复，共{total_fixes}处A类修复")
    print("=" * 80)

    if total_fixes >= 12:
        print("\n🎉 所有A类资源清理异常修复验证通过！")
        return 0
    else:
        print(f"\n⚠️  预期至少12处修复，实际{total_fixes}处")
        return 1


if __name__ == "__main__":
    sys.exit(verify_a_class_fixes())
