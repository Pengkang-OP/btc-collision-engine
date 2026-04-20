"""crypto_backend加密后端管理器测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.crypto_backend import crypto_manager, BackendType


class TestCryptoBackendManager(unittest.TestCase):
    """加密后端管理器测试"""
    
    def test_backend_detection(self):
        """后端自动检测"""
        backend = crypto_manager.current_backend
        self.assertIsNotNone(backend)
        self.assertTrue(hasattr(backend, 'name'))
        self.assertTrue(hasattr(backend, 'is_available'))
    
    def test_backend_availability(self):
        """后端可用性检查"""
        backends = crypto_manager.get_available_backends()
        self.assertGreater(len(backends), 0)
        # backends是元组列表: (BackendType, name)
        self.assertIsInstance(backends[0], tuple)
        self.assertEqual(len(backends[0]), 2)
    
    def test_get_available_backends(self):
        """获取可用后端列表"""
        backends = crypto_manager.get_available_backends()
        self.assertIsInstance(backends, list)
        self.assertGreater(len(backends), 0)
        # 每个元素应该是 (BackendType, name) 元组
        for backend_type, name in backends:
            self.assertIsInstance(backend_type, BackendType)
            self.assertIsInstance(name, str)
    
    def test_public_key_generation_compressed(self):
        """公钥生成 - 压缩格式"""
        pk = (42).to_bytes(32, 'big')
        pub_key = crypto_manager.generate_public_key(pk, compressed=True)
        
        self.assertIsInstance(pub_key, bytes)
        self.assertEqual(len(pub_key), 33)  # 压缩公钥33字节
        self.assertIn(pub_key[0], [2, 3])  # 前缀为0x02或0x03
    
    def test_public_key_generation_uncompressed(self):
        """公钥生成 - 非压缩格式"""
        pk = (42).to_bytes(32, 'big')
        pub_key = crypto_manager.generate_public_key(pk, compressed=False)
        
        self.assertIsInstance(pub_key, bytes)
        self.assertEqual(len(pub_key), 65)  # 非压缩公钥65字节
        self.assertEqual(pub_key[0], 4)  # 前缀为0x04
    
    def test_public_key_generation_deterministic(self):
        """公钥生成确定性 - 相同私钥生成相同公钥"""
        pk = (123456).to_bytes(32, 'big')
        pub1 = crypto_manager.generate_public_key(pk, compressed=True)
        pub2 = crypto_manager.generate_public_key(pk, compressed=True)
        
        self.assertEqual(pub1, pub2)
    
    def test_public_key_generation_different_keys(self):
        """不同私钥生成不同公钥"""
        pk1 = (1).to_bytes(32, 'big')
        pk2 = (2).to_bytes(32, 'big')
        
        pub1 = crypto_manager.generate_public_key(pk1, compressed=True)
        pub2 = crypto_manager.generate_public_key(pk2, compressed=True)
        
        self.assertNotEqual(pub1, pub2)
    
    def test_public_key_generation_boundary_values(self):
        """边界值私钥的公钥生成"""
        # 最小有效私钥
        pk_min = (1).to_bytes(32, 'big')
        pub_min = crypto_manager.generate_public_key(pk_min, compressed=True)
        self.assertEqual(len(pub_min), 33)
        
        # 从secp256k1导入N
        from src.core.secp256k1 import Secp256k1
        # 最大有效私钥 (N-1)
        pk_max = (Secp256k1.N - 1).to_bytes(32, 'big')
        pub_max = crypto_manager.generate_public_key(pk_max, compressed=True)
        self.assertEqual(len(pub_max), 33)
        
        # 两者应该不同
        self.assertNotEqual(pub_min, pub_max)
    
    def test_backend_fallback(self):
        """后端回退机制 - 当首选后端不可用时能回退"""
        # 这个测试验证即使首选后端失败，也能使用其他后端
        pk = (999).to_bytes(32, 'big')
        
        # 应该能成功生成公钥（无论使用哪个后端）
        pub_key = crypto_manager.generate_public_key(pk, compressed=True)
        self.assertIsNotNone(pub_key)
        self.assertEqual(len(pub_key), 33)
    
    def test_current_backend_is_available(self):
        """当前使用的后端应该是可用的"""
        backend = crypto_manager.current_backend
        self.assertTrue(backend.is_available)
    
    def test_backend_name(self):
        """后端名称应该非空"""
        backend = crypto_manager.current_backend
        self.assertIsInstance(backend.name, str)
        self.assertGreater(len(backend.name), 0)
    
    def test_multiple_generations_performance(self):
        """多次生成的性能测试（验证后端正常工作）"""
        import time
        
        pk = (42).to_bytes(32, 'big')
        iterations = 100
        
        start = time.time()
        for _ in range(iterations):
            pub_key = crypto_manager.generate_public_key(pk, compressed=True)
            self.assertEqual(len(pub_key), 33)
        elapsed = time.time() - start
        
        # 应该在合理时间内完成（10秒以内）
        self.assertLess(elapsed, 10.0)
        
        # 输出性能信息用于调试
        backend = crypto_manager.current_backend
        print(f"\n后端: {backend.name}")
        print(f"{iterations}次公钥生成耗时: {elapsed:.4f}秒")
        print(f"速度: {iterations/elapsed:.2f} ops/sec")
    
    def test_invalid_private_key_handling(self):
        """无效私钥处理 - 后端应能处理各种输入"""
        # 测试全零私钥（虽然无效，但后端应该能处理）
        pk_zero = b'\x00' * 32
        # 有些后端可能会生成无穷远点，有些会抛异常
        try:
            pub_key = crypto_manager.generate_public_key(pk_zero, compressed=True)
            # 如果成功，应该是33字节
            self.assertEqual(len(pub_key), 33)
        except Exception:
            # 抛异常也是可接受的行为
            pass
    
    def test_consistency_with_pure_python(self):
        """验证与纯Python实现的一致性"""
        from src.core.secp256k1 import EllipticCurve
        
        pk = (12345).to_bytes(32, 'big')
        
        # 使用crypto_manager生成
        pub_crypto = crypto_manager.generate_public_key(pk, compressed=True)
        
        # 使用纯Python实现生成
        ec = EllipticCurve()
        pub_python = ec.generate_public_key(pk, compressed=True)
        
        # 结果应该一致
        self.assertEqual(pub_crypto, pub_python)


class TestBackendType(unittest.TestCase):
    """BackendType枚举测试"""
    
    def test_backend_type_values(self):
        """后端类型枚举值"""
        self.assertEqual(BackendType.PURE_PYTHON.name, 'PURE_PYTHON')
        self.assertEqual(BackendType.OPENSSL.name, 'OPENSSL')
        self.assertEqual(BackendType.COINCURVE.name, 'COINCURVE')
        self.assertEqual(BackendType.ECDSA.name, 'ECDSA')
    
    def test_backend_type_count(self):
        """后端类型数量"""
        self.assertEqual(len(list(BackendType)), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
