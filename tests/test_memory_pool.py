# -*- coding: utf-8 -*-
"""内存池优化模块单元测试"""

import pytest
import threading
from src.core.memory_pool import (
    ObjectPool,
    ECPointPool,
    ByteArrayPool,
    pool_manager,
    get_pool_manager,
)


class TestObjectPool:
    """通用对象池测试类"""

    def test_initialization(self):
        """测试初始化"""
        pool = ObjectPool(lambda: object(), initial_size=10, max_size=100)
        assert pool._initial_size == 10
        assert pool._max_size == 100
        assert len(pool._pool) == 10

    def test_invalid_initial_size(self):
        """测试无效初始大小"""
        with pytest.raises(ValueError):
            ObjectPool(lambda: object(), initial_size=-1)

    def test_acquire_release(self):
        """测试获取和归还对象"""
        pool = ObjectPool(lambda: {"data": None}, initial_size=5, max_size=10)

        # 获取对象
        obj = pool.acquire()
        assert obj is not None
        assert "data" in obj

        # 修改对象
        obj["data"] = "test"

        # 归还对象
        pool.release(obj)

        # 统计信息
        stats = pool.get_stats()
        assert stats["acquire_count"] == 1
        assert stats["release_count"] == 1

    def test_pool_exhaustion(self):
        """测试池耗尽时自动创建"""
        pool = ObjectPool(lambda: [], initial_size=2, max_size=5)

        # 获取所有对象
        pool.acquire()
        pool.acquire()

        # 池耗尽,应该创建新对象
        pool.acquire()

        stats = pool.get_stats()
        assert stats["created_count"] == 3  # 2个预分配 + 1个新创建

    def test_pool_max_size(self):
        """测试池最大容量限制"""
        pool = ObjectPool(lambda: [], initial_size=2, max_size=3)

        # 获取并归还,超过max_size应该丢弃
        objs = [pool.acquire() for _ in range(5)]
        for obj in objs:
            pool.release(obj)

        stats = pool.get_stats()
        assert stats["current_size"] <= 3

    def test_thread_safety(self):
        """测试线程安全性"""
        pool = ObjectPool(lambda: [], initial_size=100, max_size=200)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    obj = pool.acquire()
                    obj.append(1)
                    pool.release(obj)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_clear(self):
        """测试清空池"""
        pool = ObjectPool(lambda: [], initial_size=10, max_size=20)
        pool.acquire()
        pool.clear()

        stats = pool.get_stats()
        assert stats["current_size"] == 0


class TestECPointPool:
    """ECPoint专用池测试类"""

    def test_initialization(self):
        """测试初始化"""
        pool = ECPointPool(initial_size=50, max_size=100)
        assert pool is not None

    def test_acquire_release(self):
        """测试获取和归还"""
        from src.core.secp256k1 import Secp256k1

        pool = ECPointPool(initial_size=10, max_size=50)

        # 获取点
        point = pool.acquire(x=Secp256k1.Gx, y=Secp256k1.Gy)
        assert point.x == Secp256k1.Gx
        assert point.y == Secp256k1.Gy
        assert not point.is_infinity

        # 归还点
        pool.release(point)

    def test_infinity_point(self):
        """测试无穷远点"""
        pool = ECPointPool(initial_size=10)

        point = pool.acquire()  # 默认x=None, y=None
        assert point.is_infinity


class TestByteArrayPool:
    """ByteArray专用池测试类"""

    def test_initialization(self):
        """测试初始化"""
        pool = ByteArrayPool(buffer_size=32, initial_size=50, max_size=100)
        assert pool is not None

    def test_acquire_release_zeroing(self):
        """测试获取和归还(清零)"""
        pool = ByteArrayPool(buffer_size=32, initial_size=10, max_size=20)

        # 获取buffer
        buf = pool.acquire()
        assert len(buf) == 32

        # 写入数据
        for i in range(32):
            buf[i] = i

        # 归还(应该清零)
        pool.release(buf)

        # 验证已清零
        assert all(b == 0 for b in buf)

    def test_different_sizes(self):
        """测试不同大小"""
        pool32 = ByteArrayPool(buffer_size=32, initial_size=10)
        pool64 = ByteArrayPool(buffer_size=64, initial_size=10)

        buf32 = pool32.acquire()
        buf64 = pool64.acquire()

        assert len(buf32) == 32
        assert len(buf64) == 64


class TestGlobalPoolManager:
    """全局池管理器测试类"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = get_pool_manager()
        manager2 = pool_manager
        assert manager1 is manager2

    def test_initialize(self):
        """测试初始化"""
        manager = get_pool_manager()
        manager.initialize()

        assert manager._initialized is True
        assert hasattr(manager, "ecpoint_pool")
        assert hasattr(manager, "bytearray_pool_32")

    def test_get_pools(self):
        """测试获取池"""
        manager = get_pool_manager()
        manager.initialize()

        ec_pool = manager.get_ecpoint_pool()
        assert ec_pool is not None

        byte_pool = manager.get_bytearray_pool(32)
        assert byte_pool is not None
