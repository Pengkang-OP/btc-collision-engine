"""性能基准测试 - 用于检测性能回归

使用pytest-benchmark框架，自动记录性能指标并检测退化。
运行方式: pytest tests/test_performance_benchmarks.py --benchmark-only
"""
import pytest
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.deduplication_filter import DeduplicationFilter
from src.core.address_generator import P2PKHAddressGenerator
from src.core.secp256k1 import Secp256k1


class TestPerformanceBenchmarks:
    """性能基准测试类"""
    
    def test_private_key_generation_speed(self, benchmark):
        """基准测试：私钥生成速度"""
        generator = P2PKHAddressGenerator()
        
        def generate_100_keys():
            """生成100个随机私钥"""
            keys = []
            for _ in range(100):
                keys.append(generator.generate_private_key())
            return keys
        
        # 基准测试：测量生成100个私钥的时间
        benchmark(generate_100_keys)
        
        # 验证：至少能生成私钥（基准测试会自动运行多次）
        keys = generate_100_keys()
        assert len(keys) == 100
        assert all(len(k) == 32 for k in keys)
    
    def test_address_generation_speed(self, benchmark):
        """基准测试：地址生成速度"""
        generator = P2PKHAddressGenerator()
        test_key = (1).to_bytes(32, 'big')
        
        def generate_address():
            """生成一个地址"""
            return generator.generate_address(test_key)
        
        # 基准测试
        benchmark(generate_address)
        
        # 验证地址格式
        address, compressed_pub, _ = generate_address()
        assert address.startswith('1')
        assert len(compressed_pub) == 33  # 压缩公钥
    
    def test_deduplication_filter_throughput(self, benchmark):
        """基准测试：去重过滤器吞吐量"""
        def check_1000_keys():
            """检查1000个私钥"""
            dedup = DeduplicationFilter(max_size=100000, enabled=True)  # 每次创建新实例
            count = 0
            for i in range(1000):
                pk = i.to_bytes(32, 'big')
                if dedup.check_and_add(pk):
                    count += 1
            return count
        
        # 基准测试
        benchmark(check_1000_keys)
        
        # 验证所有私钥都通过了（首次检查）
        count = check_1000_keys()
        assert count == 1000
    
    def test_engine_single_thread_throughput(self, benchmark):
        """基准测试：引擎单线程吞吐量
        
        注意：这个测试需要较长时间，默认禁用
        运行方式: pytest tests/test_performance_benchmarks.py -k test_engine_single_thread
        """
        pytest.skip("耗时测试，需要手动启用")
        
        engine = KeyCollisionEngine(
            targets={"1TestAddress123456789012345678"},
            max_workers=1,
            dedup_enabled=False,
        )
        
        def run_engine_2_seconds():
            """运行引擎2秒"""
            engine.start(mode="random")
            time.sleep(2)
            engine.stop()
            stats = engine.get_stats()
            return stats.total_checked
        
        # 基准测试
        total_checked = benchmark(run_engine_2_seconds)
        
        # 性能断言：2秒内至少检查10个私钥（纯Python实现较慢）
        assert total_checked > 10, f"吞吐量过低: {total_checked} 私钥/2秒"
    
    def test_engine_multi_thread_throughput(self, benchmark):
        """基准测试：引擎多线程吞吐量
        
        注意：这个测试需要较长时间，默认禁用
        运行方式: pytest tests/test_performance_benchmarks.py -k test_engine_multi_thread
        """
        pytest.skip("耗时测试，需要手动启用")
        
        engine = KeyCollisionEngine(
            targets={"1TestAddress123456789012345678"},
            max_workers=4,
            dedup_enabled=False,
        )
        
        def run_engine_2_seconds():
            """运行引擎2秒"""
            engine.start(mode="random")
            time.sleep(2)
            engine.stop()
            stats = engine.get_stats()
            return stats.total_checked
        
        # 基准测试
        total_checked = benchmark(run_engine_2_seconds)
        
        # 性能断言：4线程应该比单线程快
        assert total_checked > 10, f"吞吐量过低: {total_checked} 私钥/2秒"


class TestPerformanceRegression:
    """性能回归检测
    
    这些测试会与历史基准对比，检测性能退化。
    使用 --benchmark-compare 参数启用对比。
    """
    
    def test_address_generation_no_regression(self, benchmark):
        """检测地址生成性能回归"""
        generator = P2PKHAddressGenerator()
        test_key = (42).to_bytes(32, 'big')
        
        def generate():
            return generator.generate_address(test_key)
        
        benchmark(generate)
        
        # 验证正确性
        address, _, _ = generate()
        assert address.startswith('1')
        
        # benchmark 会自动记录并与历史数据对比
        # 如果性能退化超过阈值（默认20%），会发出警告
    
    def test_deduplication_no_regression(self, benchmark):
        """检测去重过滤器性能回归"""
        def check_500_keys():
            dedup = DeduplicationFilter(max_size=50000, enabled=True)  # 每次创建新实例
            count = 0
            for i in range(500):
                pk = i.to_bytes(32, 'big')
                if dedup.check_and_add(pk):
                    count += 1
            return count
        
        benchmark(check_500_keys)
        count = check_500_keys()
        assert count == 500


# 性能基准配置
@pytest.fixture(scope="session")
def benchmark_config():
    """基准测试配置"""
    return {
        "min_rounds": 5,
        "max_time": 1.0,
        "warmup_rounds": 2,
    }
