# -*- coding: utf-8 -*-
"""
优化模块集成测试
测试优化模块在实际碰撞引擎中的表现
"""

import pytest
import time
import secrets
import threading
from src.collision.key_collision_engine import KeyCollisionEngine
from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator
from src.core.address_generator import P2PKHAddressGenerator
from src.monitoring.optimization_monitor import OptimizationPerformanceMonitor


class TestOptimizedEngineIntegration:
    """优化引擎集成测试类"""

    def test_optimized_engine_initialization(self):
        """测试优化引擎初始化"""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

        engine = KeyCollisionEngine(
            targets=targets,
            use_performance_optimization=True,
            precomputed_window_size=8,
            use_simd_hash=True,
            use_memory_pool=True,
        )

        assert engine.generator is not None
        assert isinstance(engine.generator, OptimizedP2PKHAddressGenerator)
        assert len(engine.targets) == 1

    def test_standard_engine_initialization(self):
        """测试标准引擎初始化(兼容模式)"""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

        engine = KeyCollisionEngine(targets=targets, use_performance_optimization=False)

        assert engine.generator is not None
        assert isinstance(engine.generator, P2PKHAddressGenerator)

    def test_optimized_address_generation(self):
        """测试优化版地址生成"""
        engine = KeyCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}, use_performance_optimization=True
        )

        # 生成地址
        private_key = secrets.token_bytes(32)
        address = engine.generator.generate_from_private_key(private_key)

        # 验证地址格式
        assert isinstance(address, str)
        assert len(address) >= 26
        assert address.startswith("1")

    def test_batch_address_generation(self):
        """测试批量地址生成"""
        generator = OptimizedP2PKHAddressGenerator()

        # 生成10个私钥
        private_keys = [secrets.token_bytes(32) for _ in range(10)]

        # 批量生成
        addresses = generator.batch_generate(private_keys)

        assert len(addresses) == 10
        for addr in addresses:
            assert isinstance(addr, str)
            assert addr.startswith("1")

    def test_performance_with_monitoring(self):
        """测试带监控的性能"""
        monitor = OptimizationPerformanceMonitor()
        monitor.start()

        try:
            generator = OptimizedP2PKHAddressGenerator()

            num_keys = 50
            start = time.perf_counter()

            for _ in range(num_keys):
                pk = secrets.token_bytes(32)
                generator.generate_from_private_key(pk)

            elapsed = time.perf_counter() - start

            # 记录指标
            monitor.record_metrics(
                addresses_generated=num_keys,
                elapsed_time=elapsed,
                optimization_enabled=True,
                precomputed_table=True,
                simd_hash=True,
                memory_pool=True,
            )

            # 验证指标
            report = monitor.get_performance_report()
            assert report["summary"]["total_addresses"] == num_keys
            assert report["summary"]["avg_speed"] > 0

        finally:
            monitor.stop()

    def test_concurrent_address_generation(self):
        """测试并发地址生成"""
        generator = OptimizedP2PKHAddressGenerator()
        errors = []
        results = []
        lock = threading.Lock()

        def worker(num_keys):
            try:
                for _ in range(num_keys):
                    pk = secrets.token_bytes(32)
                    addr = generator.generate_from_private_key(pk)
                    with lock:
                        results.append(addr)
            except Exception as e:
                with lock:
                    errors.append(e)

        # 启动4个线程
        threads = [threading.Thread(target=worker, args=(25,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100  # 4*25


class TestPerformanceComparison:
    """性能对比测试类"""

    def test_optimized_vs_standard_single(self):
        """测试单地址生成性能对比"""
        num_keys = 50
        test_keys = [secrets.token_bytes(32) for _ in range(num_keys)]

        # 优化版
        generator_opt = OptimizedP2PKHAddressGenerator()
        start = time.perf_counter()
        for pk in test_keys:
            generator_opt.generate_from_private_key(pk)
        elapsed_opt = time.perf_counter() - start

        # 标准版
        generator_std = P2PKHAddressGenerator()
        start = time.perf_counter()
        for pk in test_keys:
            generator_std.generate_address(pk)
        elapsed_std = time.perf_counter() - start

        # 记录性能数据(不assert,因为取决于后端)
        print(f"\n  优化版: {elapsed_opt:.4f}s")
        print(f"  标准版: {elapsed_std:.4f}s")
        print(f"  比值: {elapsed_std/elapsed_opt:.2f}x")

    def test_optimized_vs_standard_batch(self):
        """测试批量生成性能对比"""
        num_keys = 100
        test_keys = [secrets.token_bytes(32) for _ in range(num_keys)]

        # 优化版批量
        generator_opt = OptimizedP2PKHAddressGenerator()
        start = time.perf_counter()
        generator_opt.batch_generate(test_keys)
        elapsed_opt = time.perf_counter() - start

        # 标准版逐个
        generator_std = P2PKHAddressGenerator()
        start = time.perf_counter()
        for pk in test_keys:
            generator_std.generate_address(pk)
        elapsed_std = time.perf_counter() - start

        print(f"\n  优化版(批量): {elapsed_opt:.4f}s")
        print(f"  标准版(逐个): {elapsed_std:.4f}s")
        print(f"  比值: {elapsed_std/elapsed_opt:.2f}x")


class TestOptimizationConfigs:
    """不同优化配置测试类"""

    def test_full_optimization(self):
        """测试全优化配置"""
        engine = KeyCollisionEngine(
            targets={"test"},
            use_performance_optimization=True,
            precomputed_window_size=8,
            use_simd_hash=True,
            use_memory_pool=True,
        )

        pk = secrets.token_bytes(32)
        address = engine.generator.generate_from_private_key(pk)
        assert address.startswith("1")

    def test_partial_optimization(self):
        """测试部分优化配置"""
        engine = KeyCollisionEngine(
            targets={"test"},
            use_performance_optimization=True,
            precomputed_window_size=6,
            use_simd_hash=False,
            use_memory_pool=False,
        )

        pk = secrets.token_bytes(32)
        address = engine.generator.generate_from_private_key(pk)
        assert address.startswith("1")

    def test_no_optimization(self):
        """测试无优化配置"""
        engine = KeyCollisionEngine(targets={"test"}, use_performance_optimization=False)

        pk = secrets.token_bytes(32)
        result = engine.generator.generate_address(pk)
        # generate_address可能返回元组(address, ...)或字符串
        address = result[0] if isinstance(result, tuple) else result
        assert str(address).startswith("1")

    def test_different_window_sizes(self):
        """测试不同窗口大小"""
        for window_size in [4, 6, 8]:
            engine = KeyCollisionEngine(
                targets={"test"},
                use_performance_optimization=True,
                precomputed_window_size=window_size,
                use_simd_hash=False,
                use_memory_pool=False,
            )

            pk = secrets.token_bytes(32)
            address = engine.generator.generate_from_private_key(pk)
            assert address.startswith("1")


class TestMemoryPoolIntegration:
    """内存池集成测试类"""

    def test_memory_pool_initialization(self):
        """测试内存池初始化"""
        from src.core.memory_pool import get_pool_manager

        manager = get_pool_manager()
        manager.initialize()

        ec_pool = manager.get_ecpoint_pool()
        assert ec_pool is not None

        stats = ec_pool.get_stats()
        assert "current_size" in stats
        assert "max_size" in stats

    def test_memory_pool_usage(self):
        """测试内存池使用"""
        from src.core.memory_pool import get_pool_manager
        from src.core.secp256k1 import Secp256k1

        manager = get_pool_manager()
        manager.initialize()

        ec_pool = manager.get_ecpoint_pool()

        # 使用内存池
        point = ec_pool.acquire(x=Secp256k1.Gx, y=Secp256k1.Gy)
        assert point.x == Secp256k1.Gx
        assert point.y == Secp256k1.Gy

        # 归还
        ec_pool.release(point)

        stats = ec_pool.get_stats()
        assert stats["acquire_count"] > 0
        assert stats["release_count"] > 0
