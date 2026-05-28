#!/usr/bin/env python3
"""端到端测试：从地址导入到碰撞检测."""

import json
import logging
import pathlib
import time

import pytest

from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.targets.storage import AddressStorage

# 禁用日志以避免文件锁定问题
logging.basicConfig(level=logging.CRITICAL)


@pytest.mark.integration
def test_end_to_end_address_import():
    """端到端测试：地址导入 + 碰撞检测."""
    print("=== 端到端测试：地址导入模式 ===")
    print()

    # 1. 测试地址导入
    print("1. 开始地址导入测试...")

    # 创建存储实例
    storage = AddressStorage()

    # 导入地址
    result = storage.import_addresses(
        source_path="test_addresses.txt",
        storage_dir="./test_targets",
        validate=True,
        storage_type="json",
    )

    print(f"   导入结果: {'成功' if result['success'] else '失败'}")
    print(f"   有效地址数: {result['imported_count']}")
    print(f"   无效地址数: {result['invalid_count']}")
    print(f"   总处理地址数: {result['total_count']}")
    print(f"   存储路径: {result['storage_path']}")

    if not result["success"]:
        print(f"   错误信息: {result['error']}")
        return False

    # 2. 验证导入的地址
    print("\n2. 验证导入的地址...")

    with pathlib.Path(result["storage_path"]).open(encoding="utf-8") as f:
        data = json.load(f)
        print(f"   存储文件版本: {data.get('version', 'unknown')}")
        print(f"   目标地址数: {len(data.get('targets', []))}")
        print(f"   元数据: {data.get('metadata', {})}")

    # 3. 测试碰撞检测引擎初始化
    print("\n3. 初始化碰撞检测引擎...")

    try:
        # 从文件加载目标地址
        targets = data.get("targets", [])

        if not targets:
            print("   错误: 没有加载到目标地址")
            return False

        # 直接创建 KeyCollisionEngine 实例
        engine = KeyCollisionEngine(targets=set(targets))

        print(f"   引擎类型: {type(engine).__name__}")
        print(f"   目标地址数: {len(targets)}")
        print("   引擎初始化: 成功")

    except Exception as e:
        print(f"   引擎初始化失败: {e!s}")
        return False

    # 4. 运行简短的碰撞检测测试
    print("\n4. 运行碰撞检测测试...")

    try:
        # 启动引擎运行（设置超时机制）
        import threading

        # 定义停止函数
        def stop_engine():
            time.sleep(2)  # 运行2秒后停止
            engine.stop()

        # 启动停止线程
        stop_thread = threading.Thread(target=stop_engine)
        stop_thread.daemon = True
        stop_thread.start()

        # 运行碰撞检测
        engine.start(mode="random")
        print("   碰撞检测测试: 成功")

        # 检查是否有碰撞
        stats = engine.get_stats()
        matches = getattr(stats, "matches", [])
        print(f"   检测到的碰撞数: {len(matches)}")

    except Exception as e:
        print(f"   碰撞检测测试失败: {e!s}")
        return False

    print("\n=== 端到端测试完成 ===")
    return True


if __name__ == "__main__":
    success = test_end_to_end_address_import()
    if success:
        print("\nOK 所有测试通过！")
    else:
        print("\nERR 测试失败！")
