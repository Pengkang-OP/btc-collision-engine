#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 secp256k1.py 和 logger.py 的修复

测试内容:
1. secp256k1.py 的弃用警告和文档
2. logger.py 的异步日志功能
3. SampledLogger 计数器溢出保护
4. ThreadSafeLogger 弃用警告
"""

import sys
import os
import warnings
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.secp256k1 import Secp256k1, ECPoint, EllipticCurve
from src.utils.logger import (
    ThreadSafeLogger,
    SampledLogger,
    AsyncLogger,
    AsyncFileHandler,
    setup_logger,
)


def test_secp256k1_deprecation_warning():
    """测试 secp256k1 的弃用警告"""
    print("\n" + "=" * 60)
    print("测试 1: secp256k1.py 弃用警告")
    print("=" * 60)

    ec = EllipticCurve()
    G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    # 捕获弃用警告
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # 调用旧版标量乘法（应触发警告）
        result = ec.scalar_multiply(2, G)

        # 检查警告
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "不是恒定时间实现" in str(w[0].message)
        assert "crypto_backend.py" in str(w[0].message)

        print("✅ 旧版 scalar_multiply() 正确触发弃用警告")
        print(f"   警告内容: {w[0].message}")

    # 测试新版恒定时间实现（不应触发警告）
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        result = ec.scalar_multiply_const_time(2, G)

        # 过滤掉可能的其他警告
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0

        print("✅ 新版 scalar_multiply_const_time() 无弃用警告")

    # 验证计算结果正确
    expected_x = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    assert result.x == expected_x, f"X坐标不匹配: {result.x:#x} != {expected_x:#x}"
    print(f"✅ 计算结果正确: 2G 的 X 坐标 = {result.x:#x}")

    print("\n✅ 测试 1 通过\n")


def test_threadsafe_logger_deprecation():
    """测试 ThreadSafeLogger 的弃用警告"""
    print("\n" + "=" * 60)
    print("测试 2: ThreadSafeLogger 弃用警告")
    print("=" * 60)

    logger = setup_logger("test_threadsafe", level="WARNING")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # 创建 ThreadSafeLogger（应触发警告）
        ts_logger = ThreadSafeLogger(logger)

        # 检查警告
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "双重锁" in str(w[0].message)

        print("✅ ThreadSafeLogger 正确触发弃用警告")
        print(f"   警告内容: {w[0].message}")

    print("\n✅ 测试 2 通过\n")


def test_sampled_logger_counter_overflow():
    """测试 SampledLogger 计数器溢出保护"""
    print("\n" + "=" * 60)
    print("测试 3: SampledLogger 计数器溢出保护")
    print("=" * 60)

    logger = setup_logger("test_sampled", level="DEBUG")
    sampled = SampledLogger(logger, sample_rate=100)

    # 模拟计数器接近上限
    sampled._counter = SampledLogger._COUNTER_MAX - 50

    # 记录日志触发溢出
    for i in range(100):
        sampled.debug(f"Test message {i}")

    # 验证计数器已重置
    assert sampled._counter < 100, f"计数器未重置: {sampled._counter}"

    print(f"✅ 计数器溢出保护正常，当前计数: {sampled._counter}")
    print(f"   上限: {SampledLogger._COUNTER_MAX}")

    print("\n✅ 测试 3 通过\n")


def test_async_logger():
    """测试异步日志功能"""
    print("\n" + "=" * 60)
    print("测试 4: 异步日志功能")
    print("=" * 60)

    import tempfile

    # 创建临时日志文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_file = f.name

    try:
        # 创建异步处理器
        async_handler = AsyncFileHandler(log_file, max_bytes=1024 * 1024, backup_count=2)
        async_handler.setLevel("DEBUG")

        # 创建日志器
        logger = setup_logger("test_async", level="DEBUG")
        logger.addHandler(async_handler)

        # 记录大量日志（测试非阻塞）
        start_time = time.time()
        for i in range(1000):
            logger.debug(f"Async log message {i}")
        elapsed = time.time() - start_time

        print(f"✅ 异步记录 1000 条日志耗时: {elapsed*1000:.2f}ms")
        print(f"   平均每条: {elapsed*1000/1000:.2f}ms")

        # 检查统计信息
        stats = async_handler.get_stats()
        print(f"✅ 异步日志统计: {stats}")

        # 等待队列清空
        async_handler.close()

        # 验证日志文件存在
        assert os.path.exists(log_file), "日志文件未创建"
        file_size = os.path.getsize(log_file)
        print(f"✅ 日志文件大小: {file_size} bytes")

        print("\n✅ 测试 4 通过\n")

    finally:
        # 清理临时文件
        if os.path.exists(log_file):
            os.remove(log_file)


def test_secp256k1_documentation():
    """测试 secp256k1 的文档字符串"""
    print("\n" + "=" * 60)
    print("测试 5: secp256k1.py 文档完善")
    print("=" * 60)

    # 检查模块级文档
    from src.core import secp256k1

    doc = secp256k1.__doc__

    assert "教学参考实现" in doc, "缺少教学参考实现说明"
    assert "生产环境" in doc, "缺少生产环境警告"
    assert "crypto_backend" in doc, "缺少crypto_backend引用"

    print("✅ 模块级文档包含生产环境警告")

    # 检查 mod_inverse 文档
    ec = EllipticCurve()
    mod_inverse_doc = ec.mod_inverse.__doc__
    assert "性能警告" in mod_inverse_doc, "缺少性能警告"

    print("✅ mod_inverse() 包含性能警告")

    # 检查 _const_time_select 文档
    const_time_doc = ec._const_time_select.__doc__
    assert "Python限制" in const_time_doc, "缺少Python限制说明"

    print("✅ _const_time_select() 包含Python限制说明")

    print("\n✅ 测试 5 通过\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("BTC碰撞引擎核心模块修复验证")
    print("=" * 60)

    tests = [
        test_secp256k1_deprecation_warning,
        test_threadsafe_logger_deprecation,
        test_sampled_logger_counter_overflow,
        test_async_logger,
        test_secp256k1_documentation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ 测试失败: {test.__name__}")
            print(f"   错误: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"✅ 通过: {passed}/{len(tests)}")
    print(f"❌ 失败: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 所有测试通过！修复验证成功！")
        return 0
    else:
        print(f"\n⚠️ {failed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
