# -*- coding: utf-8 -*-
"""Bech32/P2SH地址转换性能基准测试

测试目标:
- 验证LRU缓存效果
- 测量地址转换性能
- 对比缓存命中vs未命中的性能差异
"""

import pytest
from src.collision.targets.resolver import TargetResolver


class TestBech32P2SHPerformance:
    """Bech32/P2SH地址转换性能测试"""

    def test_bech32_cache_performance(self, benchmark):
        """测试Bech32地址缓存性能"""
        resolver = TargetResolver(enable_cache=True)
        bech32_addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

        # 预热缓存
        resolver.resolve(bech32_addr)

        # 基准测试（缓存命中）
        result = benchmark(resolver.resolve, bech32_addr)

        assert result is not None, "缓存命中应该返回结果"
        # 缓存命中应该在微秒级别

    def test_p2sh_cache_performance(self, benchmark):
        """测试P2SH地址缓存性能"""
        resolver = TargetResolver(enable_cache=True)
        p2sh_addr = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

        # 预热缓存
        resolver.resolve(p2sh_addr)

        # 基准测试（缓存命中）
        result = benchmark(resolver.resolve, p2sh_addr)

        assert result is not None, "缓存命中应该返回结果"

    def test_bech32_first_resolve_performance(self, benchmark):
        """测试Bech32首次解析性能（缓存未命中）"""
        resolver = TargetResolver(enable_cache=True)
        # 使用不同的地址避免缓存
        bech32_addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

        # 确保缓存为空
        if resolver.cache:
            resolver.cache.clear()

        # 基准测试（缓存未命中）
        result = benchmark(resolver.resolve, bech32_addr)

        assert result is not None, "首次解析应该成功"

    def test_batch_resolve_performance(self, benchmark):
        """测试批量解析性能"""
        resolver = TargetResolver(enable_cache=True)

        # 准备混合地址列表（使用真实有效的地址）
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
        ] * 10  # 重复10次

        # 基准测试
        results = benchmark(resolver.resolve_batch, addresses)

        # 验证返回的是字典
        assert isinstance(results, dict), "批量解析应该返回字典"
        # 验证缓存效果
        if resolver.cache:
            stats = resolver.cache.get_stats()
            assert stats["hits"] > 0, "批量解析应该有缓存命中"

    def test_cache_hit_rate_improvement(self):
        """测试缓存命中率提升"""
        resolver = TargetResolver(enable_cache=True)

        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        ]

        # 第一次解析（全部缓存未命中）
        for addr in addresses:
            resolver.resolve(addr)

        stats1 = resolver.cache.get_stats()
        assert stats1["hits"] == 0, "第一次解析应该没有缓存命中"
        assert stats1["misses"] == 3, "第一次解析应该有3次缓存未命中"

        # 第二次解析（全部缓存命中）
        for addr in addresses:
            resolver.resolve(addr)

        stats2 = resolver.cache.get_stats()
        assert stats2["hits"] == 3, "第二次解析应该有3次缓存命中"

        # 计算命中率
        hit_rate = stats2["hits"] / (stats2["hits"] + stats2["misses"]) * 100
        assert hit_rate == 50.0, "命中率应该是50%（3次命中，3次未命中）"

    def test_resolve_without_cache_performance(self, benchmark):
        """测试禁用缓存的性能"""
        resolver = TargetResolver(enable_cache=False)
        bech32_addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

        # 基准测试（无缓存）
        result = benchmark(resolver.resolve, bech32_addr)

        assert result is not None, "无缓存也应该能解析"

    @pytest.mark.benchmark(group="address_types")
    def test_p2pkh_resolve_performance(self, benchmark):
        """测试P2PKH地址解析性能"""
        resolver = TargetResolver(enable_cache=True)
        p2pkh_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        # 预热
        resolver.resolve(p2pkh_addr)

        # 基准测试
        result = benchmark(resolver.resolve, p2pkh_addr)
        assert result is not None

    @pytest.mark.benchmark(group="address_types")
    def test_p2sh_resolve_performance(self, benchmark):
        """测试P2SH地址解析性能"""
        resolver = TargetResolver(enable_cache=True)
        p2sh_addr = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

        # 预热
        resolver.resolve(p2sh_addr)

        # 基准测试
        result = benchmark(resolver.resolve, p2sh_addr)
        assert result is not None

    @pytest.mark.benchmark(group="address_types")
    def test_bech32_resolve_performance(self, benchmark):
        """测试Bech32地址解析性能"""
        resolver = TargetResolver(enable_cache=True)
        bech32_addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"

        # 预热
        resolver.resolve(bech32_addr)

        # 基准测试
        result = benchmark(resolver.resolve, bech32_addr)
        assert result is not None


class TestMemoryUsage:
    """内存使用测试"""

    def test_cache_memory_limit(self):
        """测试缓存内存限制"""
        # 创建小容量缓存
        resolver = TargetResolver(enable_cache=True, cache_max_size=10)

        # 使用真实地址重复解析（会触发缓存）
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        ] * 10  # 30次解析，但只有3个唯一地址

        for addr in addresses:
            resolver.resolve(addr)

        # 缓存大小不应超过限制，且应该只有3个唯一地址
        if resolver.cache:
            stats = resolver.cache.get_stats()
            # LRU缓存会自动淘汰旧数据，但这里只有3个唯一地址
            assert stats["lru_size"] <= 10, f"缓存大小不应超过10，实际为{stats['lru_size']}"
            assert stats["lru_size"] == 3, f"应该只有3个唯一地址，实际为{stats['lru_size']}"

    def test_large_batch_memory_stability(self):
        """测试大批量解析的内存稳定性"""
        resolver = TargetResolver(enable_cache=True, cache_max_size=1000)

        # 生成大量地址（重复使用相同的3个地址）
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        ] * 100

        # 批量解析
        results = resolver.resolve_batch(addresses)

        # resolve_batch返回字典，只包含唯一的地址
        assert isinstance(results, dict), "应该返回字典"
        assert len(results) == 3, "应该只有3个唯一的地址"

        # 缓存大小应该在合理范围内
        if resolver.cache:
            stats = resolver.cache.get_stats()
            assert stats["lru_size"] <= 1000, "缓存大小不应超过限制"


if __name__ == "__main__":
    # 运行性能测试（需要pytest-benchmark）
    pytest.main([__file__, "-v", "--benchmark-only", "--benchmark-sort=mean"])
