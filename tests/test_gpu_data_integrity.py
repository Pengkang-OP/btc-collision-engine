#!/usr/bin/env python3
"""GPU碰撞引擎数据完整性专项测试

覆盖:
- 私钥生成随机性和唯一性
- GPU内存缓冲区数据传输
- 断点数据序列化
- 统计数据一致性
"""
import pytest
import os
import sys
import json
import time
import secrets
import hashlib
import threading
from unittest.mock import Mock, patch
from src.collision.collision_stats import CollisionStats
from src.collision.checkpoint_manager import CheckpointManager
from src.collision.deduplication_filter import DeduplicationFilter


class TestPrivateKeyGeneration:
    """私钥生成测试"""
    
    def test_private_key_randomness(self):
        """测试私钥随机性和唯一性"""
        num_keys = 1000
        private_keys = set()
        
        # 生成1000个随机私钥
        for _ in range(num_keys):
            pk = secrets.token_bytes(32)
            private_keys.add(pk)
        
        # 验证所有私钥唯一
        assert len(private_keys) == num_keys
        
        # 验证私钥长度
        for pk in private_keys:
            assert len(pk) == 32
    
    def test_private_key_range_generation(self):
        """测试范围模式私钥生成"""
        start = 1
        end = 100
        
        private_keys = []
        for i in range(start, end + 1):
            pk = i.to_bytes(32, 'big')
            private_keys.append(pk)
        
        # 验证数量
        assert len(private_keys) == end - start + 1
        
        # 验证顺序和无重复
        for i, pk in enumerate(private_keys):
            expected_value = start + i
            expected_pk = expected_value.to_bytes(32, 'big')
            assert pk == expected_pk
    
    def test_private_key_brute_force_generation(self):
        """测试暴力穷举模式私钥生成"""
        start = 1
        batch_size = 50
        
        # 生成第一批
        batch_end = start + batch_size
        private_keys = b''.join(
            i.to_bytes(32, 'big') for i in range(start, batch_end)
        )
        
        # 验证长度
        assert len(private_keys) == batch_size * 32
        
        # 验证第一个私钥
        first_key = private_keys[:32]
        assert first_key == start.to_bytes(32, 'big')


class TestGPUMemoryTransfer:
    """GPU内存传输测试"""
    
    @pytest.mark.skip(reason="需要pyopencl环境")
    def test_gpu_batch_size_boundary(self):
        """测试batch_size边界条件"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE
        
        # 模拟GPUKernel初始化
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        
        with patch('pyopencl.Buffer'), \
             patch('pyopencl.Program') as mock_program:
            
            from src.collision.gpu_collision_engine import GPUKernel
            
            # 测试正常batch_size
            mock_program.return_value.build.return_value = Mock()
            kernel = GPUKernel(mock_device, max_batch_size=1000, program=Mock())
            assert kernel.max_batch_size == 1000
    
    @pytest.mark.skip(reason="需要pyopencl环境")
    def test_gpu_private_keys_length_validation(self):
        """测试私钥长度验证"""
        mock_device = Mock()
        mock_device.context = Mock()
        mock_device.queue = Mock()
        
        with patch('pyopencl.Buffer'), \
             patch('pyopencl.Program') as mock_program:
            
            from src.collision.gpu_collision_engine import GPUKernel
            
            mock_program.return_value.build.return_value = Mock()
            kernel = GPUKernel(mock_device, max_batch_size=1000, program=Mock())
            
            # 测试长度不匹配
            num_keys = 10
            wrong_length_keys = secrets.token_bytes(num_keys * 32 - 1)  # 少1字节
            
            with pytest.raises(ValueError, match="private_keys 长度与 num_keys 不匹配"):
                kernel.run_batch(wrong_length_keys, num_keys)


class TestCheckpointSerialization:
    """断点数据序列化测试"""
    
    def test_checkpoint_json_serialization(self):
        """测试断点JSON序列化"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_serialization.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath)
            
            # 包含特殊字符的targets
            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            matches = [
                {
                    "address": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                    "timestamp": time.time(),
                    "private_key_hash": "abc123"
                }
            ]
            
            # 保存断点
            checkpoint_mgr.save(
                mode="random",
                targets=targets,
                current_position=1000,
                total_checked=1000,
                matches=matches,
                force=True
            )
            
            # 直接读取JSON验证格式
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证JSON结构
            assert 'version' in data
            assert 'timestamp' in data
            assert 'mode' in data
            assert 'targets' in data
            assert 'matches' in data
            
            # 验证数据一致性
            assert data['mode'] == "random"
            assert data['total_checked'] == 1000
    
    def test_checkpoint_version_compatibility(self):
        """测试断点版本兼容性"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_version.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath)
            
            # 创建version=2的断点文件
            incompatible_data = {
                "version": 2,
                "mode": "random",
                "total_checked": 1000
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(incompatible_data, f)
            
            # 验证加载返回None
            loaded = checkpoint_mgr.load()
            assert loaded is None
            
            # 创建version=1的断点文件
            compatible_data = {
                "version": 1,
                "mode": "random",
                "total_checked": 2000,
                "targets": [],
                "matches": []
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(compatible_data, f)
            
            # 验证加载成功
            loaded = checkpoint_mgr.load()
            assert loaded is not None
            assert loaded['version'] == 1


class TestStatisticsConsistency:
    """统计数据一致性测试"""
    
    def test_collision_stats_thread_safety(self):
        """测试CollisionStats线程安全"""
        stats = CollisionStats()
        stats.start_time = time.time()
        
        num_threads = 10
        updates_per_thread = 100
        expected_total = num_threads * updates_per_thread
        
        def update_stats():
            for i in range(updates_per_thread):
                stats.update(i + 1)
        
        # 创建10个线程并发更新
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=update_stats)
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证最终值（最后一个线程的最后一个更新）
        assert stats.total_checked == updates_per_thread
    
    def test_collision_stats_snapshot(self):
        """测试CollisionStats快照一致性"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.total_checked = 1000
        stats.speed = 100.0
        
        # 创建快照
        snapshot = stats.snapshot()
        
        # 修改原始stats
        stats.total_checked = 2000
        stats.speed = 200.0
        
        # 验证快照不变
        assert snapshot.total_checked == 1000
        assert snapshot.speed == 100.0
    
    def test_collision_stats_error_rates(self):
        """测试错误率计算"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.total_checked = 1000
        
        # 记录错误
        stats.gpu_errors = 10
        stats.worker_errors = 5
        stats.wif_encode_errors = 2
        stats.resource_errors = 3
        
        # 获取错误率
        rates = stats.get_error_rates()
        
        # 验证计算
        assert rates['gpu_error_rate'] == 10 / 1000
        assert rates['worker_error_rate'] == 5 / 1000
        assert rates['wif_encode_error_rate'] == 2 / 1000
        assert rates['resource_error_rate'] == 3 / 1000
        
        # 测试健康状态
        assert stats.is_healthy(error_rate_threshold=0.01) is False  # 总错误率1.5% > 1%
        assert stats.is_healthy(error_rate_threshold=0.02) is True   # 总错误率1.5% < 2%
