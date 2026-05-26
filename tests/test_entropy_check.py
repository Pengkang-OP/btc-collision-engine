"""密钥生成器熵池检查测试

验证P1-3修复：熵池健康检查完整实现
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

from src.core.key_generator import SecureKeyGenerator


class TestEntropyHealthCheck:
    """熵池健康检查测试"""

    def test_entropy_check_enabled_by_default(self):
        """测试熵池检查默认启用"""
        generator = SecureKeyGenerator()
        assert generator.entropy_check_enabled
        assert generator.min_entropy_bits == 1000

    def test_entropy_check_can_be_disabled(self):
        """测试熵池检查可以禁用"""
        config = {"entropy_check_enabled": False}
        generator = SecureKeyGenerator(config)
        assert not generator.entropy_check_enabled

    def test_custom_min_entropy_bits(self):
        """测试自定义最小熵值阈值"""
        config = {"min_entropy_bits": 2000}
        generator = SecureKeyGenerator(config)
        assert generator.min_entropy_bits == 2000

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_low_entropy_detected(self, mock_open, mock_exists):
        """测试低熵检测"""
        # Mock Linux熵池文件
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read.return_value = "500"  # 低熵值
        mock_open.return_value = mock_file

        generator = SecureKeyGenerator()
        result = generator._check_entropy_health()

        # 应该返回False（熵池不健康）
        assert not result
        # 应该记录低熵次数
        assert generator.stats["low_entropy_count"] > 0

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_adequate_entropy(self, mock_open, mock_exists):
        """测试熵池充足"""
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read.return_value = "3000"  # 充足熵值
        mock_open.return_value = mock_file

        generator = SecureKeyGenerator()
        result = generator._check_entropy_health()

        # 应该返回True（熵池健康）
        assert result
        assert generator.stats["low_entropy_count"] == 0

    @patch("pathlib.Path.exists")
    def test_windows_no_entropy_check(self, mock_exists):
        """测试Windows系统不检查熵池"""
        # Mock文件不存在（Windows）
        mock_exists.return_value = False

        generator = SecureKeyGenerator()
        result = generator._check_entropy_health()

        # 应该返回True（假设健康）
        assert result

    def test_entropy_check_disabled_skips_check(self):
        """测试禁用熵池检查时跳过检查"""
        config = {"entropy_check_enabled": False}
        generator = SecureKeyGenerator(config)

        # 即使熵池低，也应该返回True
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.open") as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.read.return_value = "100"  # 非常低的熵
            mock_open.return_value = mock_file

            result = generator._check_entropy_health()
            assert result


class TestKeyGenerationWithEntropyCheck:
    """密钥生成与熵池检查集成测试"""

    @patch.object(SecureKeyGenerator, "_check_entropy_health")
    def test_generate_batch_with_healthy_entropy(self, mock_check):
        """测试熵池健康时生成密钥"""
        mock_check.return_value = True

        generator = SecureKeyGenerator()
        keys = generator.generate_batch(10)

        # 应该成功生成10个密钥
        assert len(keys) == 10
        for key in keys:
            assert len(key) == 32

    @patch.object(SecureKeyGenerator, "_check_entropy_health")
    def test_generate_batch_with_low_entropy(self, mock_check):
        """测试熵池低时仍然生成密钥（带警告）"""
        mock_check.return_value = False

        generator = SecureKeyGenerator()
        keys = generator.generate_batch(10)

        # 仍然应该生成密钥（不阻塞）
        assert len(keys) == 10

    def test_generate_batch_validates_keys(self):
        """测试生成的密钥有效性"""
        generator = SecureKeyGenerator()
        keys = generator.generate_batch(100)

        # 所有密钥都应该有效
        for key in keys:
            assert len(key) == 32
            key_int = int.from_bytes(key, "big")
            # 验证范围: 1 <= k < n
            assert key_int >= 1
            assert key_int < 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


class TestEntropyStatistics:
    """熵池统计测试"""

    def test_statistics_include_entropy_info(self):
        """测试统计信息包含熵池数据"""
        generator = SecureKeyGenerator()
        generator.generate_batch(10)

        stats = generator.get_statistics()

        # 应该包含熵池统计
        assert "entropy_check_enabled" in stats
        assert "min_entropy_bits" in stats
        assert "low_entropy_warnings" in stats
        assert "entropy_checks" in stats

    def test_statistics_track_low_entropy_warnings(self):
        """测试统计信息跟踪低熵警告"""
        generator = SecureKeyGenerator()

        # 模拟多次低熵检查
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.open") as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.read.return_value = "500"
            mock_open.return_value = mock_file

            # 多次检查
            for _ in range(3):
                generator._check_entropy_health()

        stats = generator.get_statistics()

        # 应该记录3次低熵
        assert stats["low_entropy_warnings"] == 3
        assert stats["entropy_checks"] == 3

    def test_reset_statistics(self):
        """测试重置统计信息"""
        generator = SecureKeyGenerator()
        generator.generate_batch(100)

        # 重置前
        stats_before = generator.get_statistics()
        assert stats_before["total_generated"] > 0

        # 重置
        generator.reset_statistics()

        # 重置后
        stats_after = generator.get_statistics()
        assert stats_after["total_generated"] == 0


class TestEntropyCheckEdgeCases:
    """熵池检查边界情况测试"""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_entropy_file_read_error(self, mock_open, mock_exists):
        """测试熵池文件读取错误"""
        mock_exists.return_value = True
        mock_open.side_effect = OSError("Cannot read file")

        generator = SecureKeyGenerator()
        result = generator._check_entropy_health()

        # 应该返回True（假设健康）
        assert result

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_entropy_invalid_value(self, mock_open, mock_exists):
        """测试熵池无效值"""
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read.return_value = "invalid"  # 无效值
        mock_open.return_value = mock_file

        generator = SecureKeyGenerator()
        result = generator._check_entropy_health()

        # 应该返回True（异常处理）
        assert result

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_entropy_boundary_values(self, mock_open, mock_exists):
        """测试熵池边界值"""
        mock_exists.return_value = True

        test_cases = [
            ("0", False),  # 零熵
            ("999", False),  # 低于阈值
            ("1000", True),  # 等于阈值
            ("1001", True),  # 略高于阈值
            ("1999", True),  # 接近2倍阈值
            ("2000", True),  # 2倍阈值
            ("10000", True),  # 高熵
        ]

        for entropy_str, expected in test_cases:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.read.return_value = entropy_str
            mock_open.return_value = mock_file

            generator = SecureKeyGenerator()
            result = generator._check_entropy_health()

            assert result == expected, f"熵值 {entropy_str} 应该返回 {expected}"


class TestEntropyCheckConfiguration:
    """熵池检查配置测试"""

    def test_default_configuration(self):
        """测试默认配置"""
        generator = SecureKeyGenerator()

        assert generator.entropy_check_enabled
        assert generator.min_entropy_bits == 1000

    def test_custom_configuration(self):
        """测试自定义配置"""
        config = {"entropy_check_enabled": True, "min_entropy_bits": 2000, "batch_size": 500}
        generator = SecureKeyGenerator(config)

        assert generator.entropy_check_enabled
        assert generator.min_entropy_bits == 2000
        assert generator.batch_size == 500

    def test_disable_entropy_check(self):
        """测试禁用熵池检查"""
        config = {"entropy_check_enabled": False}
        generator = SecureKeyGenerator(config)

        assert not generator.entropy_check_enabled
        # 即使熵池低也应该返回True
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.open") as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.read.return_value = "100"
            mock_open.return_value = mock_file

            result = generator._check_entropy_health()
            assert result

