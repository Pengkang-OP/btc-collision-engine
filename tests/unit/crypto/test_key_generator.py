"""SecureKeyGenerator 全面单元测试 - 覆盖构造/生成/验证/统计/熵池路径"""

import unittest
from unittest.mock import patch

import pytest

from src.core.key_generator import SecureKeyGenerator
from src.core.secp256k1 import Secp256k1


class TestSecureKeyGeneratorInit:
    """测试构造函数与配置路径"""

    def test_init_default_config(self):
        """P0-1: 默认配置 - 无参数构造"""
        gen = SecureKeyGenerator()
        assert gen.batch_size == 1000
        assert gen.rate_limit == 0
        assert gen.key_format == "both"
        assert gen.entropy_check_enabled
        assert gen.min_entropy_bits == 1000
        assert gen._total_generated == 0
        assert gen.key_manager is not None

    def test_init_with_none_config(self):
        """P0-2: config=None 使用默认值"""
        gen = SecureKeyGenerator(config=None)
        assert gen.batch_size == 1000
        assert gen.rate_limit == 0

    def test_init_custom_config(self):
        """P0-3: 自定义 batch_size/rate_limit/key_format"""
        gen = SecureKeyGenerator(
            config={
                "batch_size": 500,
                "rate_limit": 100,
                "key_format": "compressed",
            },
        )
        assert gen.batch_size == 500
        assert gen.rate_limit == 100
        assert gen.key_format == "compressed"

    def test_init_entropy_config_enabled(self):
        """P0-4: 自定义熵池配置"""
        gen = SecureKeyGenerator(
            config={
                "entropy_check_enabled": True,
                "min_entropy_bits": 2000,
            },
        )
        assert gen.entropy_check_enabled
        assert gen.min_entropy_bits == 2000

    def test_init_entropy_config_disabled(self):
        """P0-5: 禁用熵池检查"""
        gen = SecureKeyGenerator(
            config={
                "entropy_check_enabled": False,
            },
        )
        assert not gen.entropy_check_enabled

    def test_init_stats_initialized(self):
        """P0-6: stats 字典初始化"""
        gen = SecureKeyGenerator()
        assert "low_entropy_count" in gen.stats
        assert "entropy_checks" in gen.stats
        assert "warnings_issued" in gen.stats
        assert gen.stats["low_entropy_count"] == 0


class TestGenerateBatch:
    """测试批量私钥生成"""

    def setup_method(self, method):
        self.gen = SecureKeyGenerator(config={"batch_size": 100})

    def test_generate_batch_valid_keys(self):
        """P0-7: 正常批量生成 - 返回有效 secp256k1 私钥"""
        keys = self.gen.generate_batch(3)
        assert len(keys) == 3
        for key in keys:
            # generate_batch() 返回 bytearray 以支持安全清零，bytes 和 bytearray 均可
            assert isinstance(key, (bytes, bytearray))
            assert len(key) == 32
            key_int = int.from_bytes(key, "big")
            assert key_int >= 1
            assert key_int < Secp256k1.N

    def test_generate_batch_single_key(self):
        """P0-8: 批量生成 1 个密钥"""
        keys = self.gen.generate_batch(1)
        assert len(keys) == 1
        assert len(keys[0]) == 32

    def test_generate_batch_zero_count(self):
        """P0-9: count=0 抛出 ValueError"""
        with pytest.raises(ValueError) as ctx:
            self.gen.generate_batch(0)
        assert "greater than 0" in str(ctx.value)

    def test_generate_batch_negative_count(self):
        """P0-10: count<0 抛出 ValueError"""
        with pytest.raises(ValueError):
            self.gen.generate_batch(-5)

    def test_generate_batch_updates_statistics(self):
        """P0-11: 批量生成后更新 total_generated"""
        before = self.gen._total_generated
        self.gen.generate_batch(5)
        assert self.gen._total_generated == before + 5

        self.gen.generate_batch(3)
        assert self.gen._total_generated == before + 8

    def test_generate_batch_all_keys_invalid_raises(self):
        """P1-1: 所有密钥无效时抛出 RuntimeError"""
        with patch.object(self.gen, "_is_valid_private_key", return_value=False):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                with pytest.raises(RuntimeError) as ctx:
                    self.gen.generate_batch(5)
                assert "Cannot generate any valid private keys" in str(ctx.value)

    def test_generate_batch_with_rate_limit(self):
        """P1-2: 速率限制生效 - 10 keys at 100/s 至少耗时约 0.1s"""
        import time

        gen = SecureKeyGenerator(config={"rate_limit": 100, "batch_size": 10})
        start = time.perf_counter()
        keys = gen.generate_batch(10)
        elapsed = time.perf_counter() - start
        # 10 keys at 100/s = minimum 0.1s; allow small epsilon for timer precision
        assert elapsed >= 0.05, f"速率限制未生效, 耗时仅 {elapsed:.4f}s"
        assert len(keys) == 10
        for key in keys:
            assert len(key) == 32

    def test_generate_batch_exception_handling(self):
        """P1-3: 单次生成异常时 continue 继续"""
        call_count = [0]

        def mock_token_bytes(n):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("模拟CSPRNG故障")
            return b"\x01" * 32

        with patch("secrets.token_bytes", side_effect=mock_token_bytes):
            # key \x01*32 = int(1) which is valid
            keys = self.gen.generate_batch(3)
            # One failed, two succeeded, or all three with one retry
            assert len(keys) > 0


class TestGenerateSingle:
    """测试单个私钥生成"""

    def setup_method(self, method):
        self.gen = SecureKeyGenerator()

    def test_generate_single_valid(self):
        """P0-12: 生成单个有效私钥"""
        key = self.gen.generate_single()
        assert isinstance(key, bytes)
        assert len(key) == 32
        key_int = int.from_bytes(key, "big")
        assert key_int >= 1
        assert key_int < Secp256k1.N

    def test_generate_single_updates_total(self):
        """P0-13: generate_single 更新 total_generated"""
        before = self.gen._total_generated
        self.gen.generate_single()
        assert self.gen._total_generated == before + 1

    def test_generate_single_max_attempts_exceeded(self):
        """P1-4: 100次尝试失败后抛出 RuntimeError"""
        with patch.object(self.gen, "_is_valid_private_key", return_value=False):
            with patch("secrets.token_bytes", return_value=b"\x00" * 32):
                with pytest.raises(RuntimeError) as ctx:
                    self.gen.generate_single()
                assert "exceeded max attempts" in str(ctx.value)

    def test_generate_single_second_attempt_succeeds(self):
        """P1-5: 第一次无效、第二次有效"""
        call_count = [0]

        def mock_is_valid(key):
            call_count[0] += 1
            return call_count[0] > 1  # Only valid on 2nd attempt

        with patch.object(self.gen, "_is_valid_private_key", side_effect=mock_is_valid):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                key = self.gen.generate_single()
                assert isinstance(key, bytes)
                assert len(key) == 32


class TestIsValidPrivateKey:
    """测试私钥验证"""

    def setup_method(self, method):
        self.gen = SecureKeyGenerator()

    def test_valid_key_passes(self):
        """P0-14: 有效私钥 (1)"""
        key = (1).to_bytes(32, "big")
        assert self.gen._is_valid_private_key(key)

    def test_valid_key_large(self):
        """P0-15: 有效私钥 (接近 N-1)"""
        key = (Secp256k1.N - 1).to_bytes(32, "big")
        assert self.gen._is_valid_private_key(key)

    def test_zero_key_rejected(self):
        """P0-16: 零密钥被拒绝"""
        key = (0).to_bytes(32, "big")
        assert not self.gen._is_valid_private_key(key)

    def test_key_equal_to_n_rejected(self):
        """P0-17: key == N 被拒绝"""
        key = Secp256k1.N.to_bytes(32, "big")
        assert not self.gen._is_valid_private_key(key)

    def test_key_above_n_rejected(self):
        """P0-18: key > N 被拒绝"""
        key = (Secp256k1.N + 1).to_bytes(32, "big")
        assert not self.gen._is_valid_private_key(key)

    def test_wrong_length_too_short(self):
        """P0-19: 密钥长度 < 32 被拒绝"""
        for length in [0, 1, 16, 31]:
            key = b"\x01" * length
            assert not self.gen._is_valid_private_key(key), f"Length {length} should be rejected"

    def test_wrong_length_too_long(self):
        """P0-20: 密钥长度 > 32 被拒绝"""
        for length in [33, 48, 64]:
            key = b"\x01" * length
            assert not self.gen._is_valid_private_key(key), f"Length {length} should be rejected"


class TestStatistics:
    """测试统计信息"""

    def setup_method(self, method):
        self.gen = SecureKeyGenerator()

    def test_get_statistics_initial(self):
        """P0-21: 初始统计信息"""
        stats = self.gen.get_statistics()
        assert stats["total_generated"] == 0
        assert "elapsed_seconds" in stats
        assert "generation_rate" in stats
        assert stats["batch_size"] == 1000
        assert stats["rate_limit"] == 0
        assert stats["key_format"] == "both"
        assert "entropy_check_enabled" in stats
        assert "min_entropy_bits" in stats
        assert "low_entropy_warnings" in stats
        assert "entropy_checks" in stats

    def test_get_statistics_after_generation(self):
        """P0-22: 生成密钥后的统计信息"""
        self.gen.generate_batch(5)
        stats = self.gen.get_statistics()
        assert stats["total_generated"] == 5
        assert stats["generation_rate"] >= 0

    def test_reset_statistics(self):
        """P0-23: 重置统计信息"""
        self.gen.generate_batch(10)
        assert self.gen._total_generated == 10
        self.gen.reset_statistics()
        assert self.gen._total_generated == 0
        stats = self.gen.get_statistics()
        assert stats["total_generated"] == 0

    def test_reset_statistics_then_regenerate(self):
        """P0-24: 重置后重新生成"""
        self.gen.generate_batch(10)
        self.gen.reset_statistics()
        self.gen.generate_batch(3)
        stats = self.gen.get_statistics()
        assert stats["total_generated"] == 3


class TestEntropyCheck:
    """测试熵池检查补充路径"""

    def setup_method(self, method):
        self.gen = SecureKeyGenerator(config={"entropy_check_enabled": True})

    def test_entropy_check_disabled_skips(self):
        """P1-6: entropy_check_enabled=False 直接返回 True"""
        self.gen.entropy_check_enabled = False
        # Even on Linux, should skip
        with patch("pathlib.Path.exists", return_value=True):
            result = self.gen._check_entropy_health()
            assert result

    def test_entropy_windows_no_file(self):
        """P2-1: Windows/macOS 无熵池文件 - 假设健康"""
        with patch("pathlib.Path.exists", return_value=False):
            result = self.gen._check_entropy_health()
            assert result
            # Should set entropy_checks to avoid repeat messages
            assert self.gen.stats["entropy_checks"] == 1

    def test_entropy_windows_first_check_logs_platform(self):
        """P2-2: 非 Linux 系统首次检查记录平台信息"""
        with patch("pathlib.Path.exists", return_value=False):
            with patch("platform.system", return_value="Windows"):
                result = self.gen._check_entropy_health()
                assert result
                assert self.gen.stats["entropy_checks"] == 1

    def test_entropy_check_exception_handling(self):
        """P2-3: 熵池检查异常时假设健康"""
        with patch("pathlib.Path.exists", side_effect=OSError("模拟系统错误")):
            result = self.gen._check_entropy_health()
            assert result


if __name__ == "__main__":
    unittest.main(verbosity=2)
