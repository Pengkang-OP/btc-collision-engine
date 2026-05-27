#!/usr/bin/env python3
"""加密后端安全检查测试."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.core.crypto_backend import (  # noqa: E402
    get_backend_security_info,
    is_secure_backend_available,
    verify_production_ready,
)


def test_backend_security():
    """测试后端安全检查功能."""
    print("=" * 70)
    print("加密后端安全检查测试")
    print("=" * 70)

    # 测试1: 获取后端安全信息
    print("\n[测试1] 获取后端安全信息:")
    print("-" * 70)
    info = get_backend_security_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    # 测试2: 检查是否有安全后端
    print("\n[测试2] 检查是否有安全后端:")
    print("-" * 70)
    is_secure = is_secure_backend_available()
    print(f"  有安全后端可用: {is_secure}")

    # 测试3: 生产环境准备检查
    print("\n[测试3] 生产环境准备检查:")
    print("-" * 70)
    is_ready, message = verify_production_ready()
    print(f"  状态: {'✅ 通过' if is_ready else '❌ 未通过'}")
    print(f"  消息:\n{message}")

    # 测试4: 输出摘要
    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"后端名称: {info.get('backend', 'N/A')}")
    print(f"安全级别: {info.get('security_level', 'N/A')}")
    print(f"恒定时间: {info.get('is_constant_time', 'N/A')}")
    print(f"生产就绪: {'✅ 是' if is_ready else '❌ 否'}")
    print("=" * 70)

    return is_ready


if __name__ == "__main__":
    try:
        success = test_backend_security()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
