#!/usr/bin/env python3
"""密钥审计功能测试"""

import os
import sys

from src.utils.key_audit import (  # 需 sys.path 前置
    KeyAuditLevel,
    KeyAuditLogger,
    KeyOperationType,
    get_audit_logger,
    log_key_display,
)


def test_key_audit_logger():
    """测试密钥审计日志器"""
    print("=" * 70)
    print("密钥审计功能测试")
    print("=" * 70)

    # 测试1: 直接使用审计日志器
    print("\n[测试1] 直接使用审计日志器:")
    print("-" * 70)
    audit_logger = KeyAuditLogger(log_file="data_logs/test_key_audit.log")

    # 记录各种操作
    audit_logger.log_operation(
        operation=KeyOperationType.DISPLAY,
        level=KeyAuditLevel.INFO,
        address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        key_hash="abcdef1234567890" * 4,
        display_mode="masked",
        details="测试掩码显示",
    )

    audit_logger.log_operation(
        operation=KeyOperationType.DISPLAY,
        level=KeyAuditLevel.CRITICAL,
        address="1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        key_hash="1234567890abcdef" * 4,
        display_mode="full",
        details="危险！完整密钥已显示",
    )

    # 获取统计
    stats = audit_logger.get_statistics()
    print(f"  审计统计: {stats}")

    # 测试2: 使用便捷函数
    print("\n[测试2] 使用便捷函数:")
    print("-" * 70)

    # 模拟密钥
    test_private_key = b"test_private_key_32_bytes_here!"

    log_key_display(
        address="1CounterpartyXXXXXXXXXXXXXXXUWLpVr",
        private_key=test_private_key,
        display_mode="masked",
    )

    log_key_display(
        address="1Bitcoin1111111111111111111114sWeT",
        private_key=test_private_key,
        display_mode="hash_only",
    )

    # 测试3: 获取全局审计日志器
    print("\n[测试3] 获取全局审计日志器:")
    print("-" * 70)
    global_logger = get_audit_logger()
    print(f"  全局日志器已获取: {global_logger is not None}")
    print(f"  全局日志器类型: {type(global_logger).__name__}")

    # 测试4: 验证日志文件
    print("\n[测试4] 验证审计日志文件:")
    print("-" * 70)
    log_files = [
        "data_logs/test_key_audit.log",
        "data_logs/key_audit.log",
    ]

    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            print(f"  ✅ {log_file}: {size} 字节")
        else:
            print(f"  ⚠️  {log_file}: 不存在")

    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        success = test_key_audit_logger()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
