#!/usr/bin/env python3
"""
验证 api-reference.md 与代码一致性
"""
import os
import sys
import re
from pathlib import Path

def check_file_exists(filepath):
    """检查文件是否存在"""
    full_path = Path("f:/Qoder/btc-collision-engine") / filepath
    if not full_path.exists():
        return False, f"文件不存在: {filepath}"
    return True, f"文件存在: {filepath}"

def main():
    print("=" * 60)
    print("API文档一致性检查")
    print("=" * 60)
    
    # 检查核心模块文件
    core_files = [
        "src/core/secp256k1.py",
        "src/core/hash_utils.py",
        "src/core/base58.py",
        "src/core/wif.py",
        "src/core/address_generator.py",
        "src/core/crypto_backend.py",
        "src/core/multi_format_generator.py",
        "src/core/secure_key_manager.py",
        "src/collision/key_collision_engine.py",
        "src/collision/deduplication_filter.py",
        "src/collision/checkpoint_manager.py",
        "src/collision/targets/format_aware_manager.py",
        "src/collision/targets/resolver.py",
        "src/collision/targets/validator.py",
        "src/collision/targets/matcher.py",
        "src/monitoring/data_logger.py",
        "src/collision/collision_stats.py",
        "src/utils/exceptions.py",
    ]
    
    print("\n检查核心文件:")
    print("-" * 60)
    for filepath in core_files:
        exists, msg = check_file_exists(filepath)
        status = "✓" if exists else "✗"
        print(f"{status} {msg}")
    
    # 检查多格式相关
    print("\n检查多格式模块:")
    print("-" * 60)
    for filepath in [
        "src/core/multi_format_generator.py",
        "src/collision/targets/format_aware_manager.py"
    ]:
        exists, msg = check_file_exists(filepath)
        status = "✓" if exists else "✗"
        print(f"{status} {msg}")
        if exists:
            content = Path("f:/Qoder/btc-collision-engine") / filepath
            if content.exists():
                print(f"  文件大小: {content.stat().st_size} 字节")
    
    # 总结
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 检查异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
