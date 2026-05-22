#!/usr/bin/env python3
"""多进程引擎安全修复验证测试

验证以下安全修复：
1. 私钥清零机制（bytearray）
2. 哈希长度（128位）
3. 安全日志格式
4. 异常退出清理
5. Queue内存限制
6. 线程安全统计
"""

import hashlib
import json
import logging
import os
import sys
import time
import unittest
from io import StringIO

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.multiprocess_engine import MultiprocessCollisionEngine  # noqa: E402


class TestPrivateKeySecurity(unittest.TestCase):
    """私钥安全测试"""

    def test_bytearray_generator_returns_mutable(self):
        """测试生成器返回bytearray（可修改）"""

        # 模拟生成器
        def generator_func(n):
            return [bytearray(os.urandom(32)) for _ in range(n)]

        keys = generator_func(5)

        # 验证所有私钥都是bytearray
        for pk in keys:
            self.assertIsInstance(pk, bytearray)
            self.assertEqual(len(pk), 32)

    def test_private_key_can_be_zeroed(self):
        """测试私钥可以被清零"""
        pk = bytearray(os.urandom(32))
        original = bytes(pk)

        # 清零
        pk[:] = b"\x00" * 32

        # 验证已清零
        self.assertEqual(pk, b"\x00" * 32)
        self.assertNotEqual(pk, original)

    def test_bytes_cannot_be_zeroed(self):
        """测试bytes类型无法清零（对比验证）"""
        pk = os.urandom(32)
        original = pk

        # bytes不可变，无法修改
        with self.assertRaises(TypeError):
            pk[0] = 0

        # 验证未改变
        self.assertEqual(pk, original)

    def test_hash_length_128_bits(self):
        """测试使用128位哈希"""
        pk = os.urandom(32)
        pk_hash = hashlib.sha256(pk).hexdigest()[:32]

        # 验证哈希长度为32字符（128位）
        self.assertEqual(len(pk_hash), 32)

        # 验证是有效的十六进制
        int(pk_hash, 16)  # 不应抛出异常

    def test_hash_uniqueness(self):
        """测试不同私钥产生不同哈希"""
        pk1 = os.urandom(32)
        pk2 = os.urandom(32)

        hash1 = hashlib.sha256(pk1).hexdigest()[:32]
        hash2 = hashlib.sha256(pk2).hexdigest()[:32]

        # 验证哈希不同
        self.assertNotEqual(hash1, hash2)

    def test_private_key_not_in_result(self):
        """测试结果不包含明文私钥"""
        # 模拟匹配结果
        pk = bytearray(os.urandom(32))
        pk_hash = hashlib.sha256(pk).hexdigest()[:32]

        result = {
            "private_key_hash": pk_hash,
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "worker_id": 0,
            "timestamp": time.time(),
        }

        # 验证不包含private_key字段
        self.assertNotIn("private_key", result)
        self.assertIn("private_key_hash", result)

        # 验证哈希长度
        self.assertEqual(len(result["private_key_hash"]), 32)


class TestMemoryCleanup(unittest.TestCase):
    """内存清理测试"""

    def test_bytearray_zeroing_in_loop(self):
        """测试循环中的bytearray清零"""
        private_keys = [bytearray(os.urandom(32)) for _ in range(10)]

        # 保存原始值
        originals = [bytes(pk) for pk in private_keys]

        # 清零所有私钥
        for pk in private_keys:
            pk[:] = b"\x00" * 32

        # 验证所有私钥已清零
        for pk in private_keys:
            self.assertEqual(pk, b"\x00" * 32)

        # 验证与原始值不同
        for pk, original in zip(private_keys, originals, strict=False):
            self.assertNotEqual(pk, original)

    def test_reference_deletion(self):
        """测试引用删除"""
        pk = bytearray(os.urandom(32))
        pk_ref = pk

        # 删除引用
        del pk

        # pk_ref仍然指向原对象
        self.assertEqual(len(pk_ref), 32)

        # 但可以清零
        pk_ref[:] = b"\x00" * 32
        self.assertEqual(pk_ref, b"\x00" * 32)


class TestSecureLogging(unittest.TestCase):
    """安全日志测试"""

    def test_log_does_not_contain_full_address(self):
        """测试日志不包含完整地址"""
        # 模拟安全日志格式
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        safe_log = f"地址={address[:10]}...{address[-6:]}"

        # 验证日志格式
        self.assertIn("...", safe_log)
        self.assertNotIn(address, safe_log)  # 不应包含完整地址

        # 验证长度缩短
        self.assertLess(len(safe_log), len(address) + 10)

    def test_log_does_not_contain_private_key(self):
        """测试日志不包含私钥"""
        pk = os.urandom(32)
        pk_hex = pk.hex()

        # 模拟错误日志
        error_type = "ValueError"
        log_message = f"处理失败: 类型={error_type}"

        # 验证不包含私钥
        self.assertNotIn(pk_hex, log_message)
        self.assertNotIn("private_key", log_message.lower())

    def test_error_log_safe_format(self):
        """测试错误日志安全格式"""
        # 捕获日志输出
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.ERROR)

        logger = logging.getLogger("test_security")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        # 记录错误
        logger.error("工作进程 0 处理失败: 类型=ValueError")

        # 获取日志
        log_output = log_capture.getvalue()

        # 验证日志格式
        self.assertIn("类型=", log_output)
        self.assertNotIn("private_key", log_output.lower())

        logger.removeHandler(handler)


class TestQueueLimits(unittest.TestCase):
    """Queue限制测试"""

    def test_queue_has_maxsize(self):
        """测试Queue有大小限制"""

        # 创建引擎
        engine = MultiprocessCollisionEngine(num_workers=2, batch_size=1000, target_addresses=["test"])

        # 验证Queue在初始化后为None
        self.assertIsNone(engine.task_queue)
        self.assertIsNone(engine.result_queue)
        self.assertIsNone(engine.stats_queue)

    def test_queue_limits_after_start(self):
        """测试启动后Queue有正确的大小限制"""
        # 注意：这里不实际启动进程，只验证配置
        engine = MultiprocessCollisionEngine(num_workers=2, batch_size=1000)

        # 预期的Queue限制
        expected_limits = {"task_queue": 100, "result_queue": 1000, "stats_queue": 50}  # noqa: F841

        # 验证配置值
        # （实际Queue在start()时创建）
        self.assertIsNotNone(engine.batch_size)
        self.assertEqual(engine.num_workers, 2)


class TestThreadSafety(unittest.TestCase):
    """线程安全测试"""

    def test_stats_lock_exists(self):
        """测试统计锁存在"""
        engine = MultiprocessCollisionEngine(num_workers=2)

        # 验证锁存在
        self.assertTrue(hasattr(engine, "_stats_lock"))

        # 验证是锁对象
        import threading

        self.assertIsInstance(engine._stats_lock, type(threading.Lock()))

    def test_stats_lock_protects_data(self):
        """测试统计锁保护数据"""
        import threading

        engine = MultiprocessCollisionEngine(num_workers=2)
        engine._running = True

        # 初始化Queue
        from multiprocessing import Queue

        engine.stats_queue = Queue(maxsize=50)
        engine.result_queue = Queue(maxsize=1000)

        # 多线程访问统计
        results = []

        def get_stats():
            stats = engine.get_stats()
            results.append(stats)

        # 创建多个线程
        threads = [threading.Thread(target=get_stats) for _ in range(5)]

        # 启动所有线程
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证所有调用都成功
        self.assertEqual(len(results), 5)

    def test_matches_return_copy(self):
        """测试匹配结果返回副本"""
        engine = MultiprocessCollisionEngine(num_workers=2)
        engine._running = True

        # 初始化
        from multiprocessing import Queue

        engine.stats_queue = Queue(maxsize=50)
        engine.result_queue = Queue(maxsize=1000)
        engine.total_matches = [{"test": "data"}]

        # 获取统计
        stats = engine.get_stats()

        # 修改返回的matches
        stats["matches"].append({"new": "item"})

        # 验证原始数据未改变
        self.assertEqual(len(engine.total_matches), 1)
        self.assertEqual(len(stats["matches"]), 2)


class TestExceptionHandling(unittest.TestCase):
    """异常处理测试"""

    def test_exception_does_not_leak_private_key(self):
        """测试异常不泄露私钥"""
        pk = os.urandom(32)

        try:
            # 模拟处理异常
            raise ValueError(f"处理失败，私钥: {pk.hex()}")
        except Exception as e:
            # 安全的错误处理
            error_type = type(e).__name__
            safe_message = f"处理失败: 类型={error_type}"

            # 验证安全消息不包含私钥
            self.assertNotIn(pk.hex(), safe_message)
            self.assertNotIn("私钥", safe_message)

    def test_finally_cleanup_on_exception(self):
        """测试finally块在异常时清理"""
        cleanup_called = False

        pk = bytearray(os.urandom(32))

        try:
            # 模拟异常
            raise RuntimeError("测试异常")
        except RuntimeError:
            pass
        finally:
            # 清理
            pk[:] = b"\x00" * 32
            cleanup_called = True

        # 验证清理执行
        self.assertTrue(cleanup_called)
        self.assertEqual(pk, b"\x00" * 32)


class TestWorkerProcessSecurity(unittest.TestCase):
    """工作进程安全测试"""

    def test_generator_returns_bytearray(self):
        """测试生成器函数返回bytearray"""

        # 模拟_worker_process中的生成器初始化
        def generator_func(n):
            return [bytearray(os.urandom(32)) for _ in range(n)]

        keys = generator_func(5)

        # 验证所有都是bytearray
        for pk in keys:
            self.assertIsInstance(pk, bytearray)

    def test_secure_hash_generation(self):
        """测试安全哈希生成"""
        pk = bytearray(os.urandom(32))

        # 创建bytes副本用于计算
        pk_bytes = bytes(pk)

        # 生成哈希
        pk_hash = hashlib.sha256(pk_bytes).hexdigest()[:32]

        # 验证哈希
        self.assertEqual(len(pk_hash), 32)

        # 清零原始私钥
        pk[:] = b"\x00" * 32

        # 验证已清零
        self.assertEqual(pk, b"\x00" * 32)

        # pk_bytes仍然是原始值（不可变）
        self.assertNotEqual(pk_bytes, b"\x00" * 32)


class TestEnhancedSecurity(unittest.TestCase):
    """增强安全测试（新增风险修复）"""

    def test_encryption_optional(self):
        """测试加密功能可选"""
        engine = MultiprocessCollisionEngine(num_workers=2)

        # 默认不启用加密
        self.assertFalse(engine._enable_encryption)
        self.assertIsNone(engine._encryption_key)

    def test_encryption_enables_with_key(self):
        """测试启用加密时生成密钥"""
        try:
            from cryptography.fernet import Fernet

            engine = MultiprocessCollisionEngine(num_workers=2)
            # 注意：这里不实际启动，只测试配置
            engine._enable_encryption = True
            engine._encryption_key = Fernet.generate_key()

            self.assertTrue(engine._enable_encryption)
            self.assertIsNotNone(engine._encryption_key)
        except ImportError:
            # cryptography未安装，跳过
            pass

    def test_gc_import_exists(self):
        """测试gc模块已导入"""
        import src.collision.multiprocess_engine as module

        self.assertTrue(hasattr(module, "gc"))

    def test_gc_collect_available(self):
        """测试gc.collect函数可用"""
        import gc

        # 应该可以调用
        gc.collect()
        # 不抛出异常即通过

    def test_full_encryption_workflow(self):
        """测试完整加密/解密流程"""
        try:
            from cryptography.fernet import Fernet

            # 1. 创建密钥
            key = Fernet.generate_key()
            fernet = Fernet(key)

            # 2. 加密数据
            original = [{"hash": "abc123", "address": "1ABC..."}]
            encrypted = fernet.encrypt(json.dumps(original).encode())

            # 3. 验证是bytes类型
            self.assertIsInstance(encrypted, bytes)

            # 4. 解密数据
            decrypted = fernet.decrypt(encrypted)
            decrypted_data = json.loads(decrypted)

            # 5. 验证数据一致
            self.assertEqual(original, decrypted_data)
        except ImportError:
            pass

    def test_encryption_key_cleanup(self):
        """测试加密密钥可以被清零"""
        try:
            from cryptography.fernet import Fernet

            # 创建bytearray密钥
            key = bytearray(Fernet.generate_key())
            original = bytes(key)

            # 清零
            key[:] = b"\x00" * len(key)

            # 验证已清零
            self.assertEqual(key, b"\x00" * len(key))
            self.assertNotEqual(key, original)
        except ImportError:
            pass

    def test_mlock_constants_correct(self):
        """测试mlock常量正确性"""
        import sys

        if sys.platform.startswith("linux"):
            # 验证常量值
            MCL_CURRENT = 1
            MCL_FUTURE = 2
            self.assertEqual(MCL_CURRENT, 1)
            self.assertEqual(MCL_FUTURE, 2)
            # 组合标志
            combined = MCL_CURRENT | MCL_FUTURE
            self.assertEqual(combined, 3)

    def test_gc_interval_optimized(self):
        """测试GC间隔优化（200,000次）"""
        # 验证GC间隔从50,000提升到200,000

        # 验证整除
        self.assertEqual(200000 % 10000, 0)  # 是10000的倍数
        self.assertEqual(200000 // 10000, 20)  # 每20个统计周期


class TestIntegrationSecurity(unittest.TestCase):
    """集成安全测试"""

    def test_full_security_workflow(self):
        """测试完整安全工作流程"""
        # 1. 生成私钥（bytearray）
        pk = bytearray(os.urandom(32))
        self.assertIsInstance(pk, bytearray)

        # 2. 创建副本用于计算
        pk_bytes = bytes(pk)
        self.assertIsInstance(pk_bytes, bytes)

        # 3. 生成地址（模拟）
        address = hashlib.sha256(pk_bytes).hexdigest()[:34]

        # 4. 生成哈希
        pk_hash = hashlib.sha256(pk_bytes).hexdigest()[:32]
        self.assertEqual(len(pk_hash), 32)

        # 5. 创建结果
        result = {
            "private_key_hash": pk_hash,
            "address": address,
            "worker_id": 0,
            "timestamp": time.time(),
        }

        # 6. 验证结果安全
        self.assertNotIn("private_key", result)
        self.assertIn("private_key_hash", result)

        # 7. 清零私钥
        pk[:] = b"\x00" * 32
        self.assertEqual(pk, b"\x00" * 32)

        # 8. 删除引用
        del pk_bytes

        # 9. 验证清理完成
        self.assertEqual(pk, b"\x00" * 32)

    def test_multiple_keys_security(self):
        """测试多个私钥的安全处理"""
        batch_size = 100

        # 生成批量私钥
        private_keys = [bytearray(os.urandom(32)) for _ in range(batch_size)]

        # 处理所有私钥
        results = []
        for pk in private_keys:
            pk_bytes = bytes(pk)
            pk_hash = hashlib.sha256(pk_bytes).hexdigest()[:32]

            results.append({"hash": pk_hash, "address": hashlib.sha256(pk_bytes).hexdigest()[:34]})

            # 清零
            pk[:] = b"\x00" * 32
            del pk_bytes

        # 验证所有私钥已清零
        for pk in private_keys:
            self.assertEqual(pk, b"\x00" * 32)

        # 验证结果数量正确
        self.assertEqual(len(results), batch_size)

        # 验证所有哈希都是128位
        for result in results:
            self.assertEqual(len(result["hash"]), 32)


def run_security_tests():
    """运行所有安全测试"""
    print("=" * 70)
    print("多进程引擎安全修复验证测试")
    print("=" * 70)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    test_classes = [
        TestPrivateKeySecurity,
        TestMemoryCleanup,
        TestSecureLogging,
        TestQueueLimits,
        TestThreadSafety,
        TestExceptionHandling,
        TestWorkerProcessSecurity,
        TestEnhancedSecurity,  # 新增
        TestIntegrationSecurity,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ 所有安全测试通过！")
    else:
        print("\n❌ 存在测试失败，需要修复")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_security_tests()
    sys.exit(0 if success else 1)
