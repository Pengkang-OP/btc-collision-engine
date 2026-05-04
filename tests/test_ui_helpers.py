"""ui_helpers 单元测试

覆盖 src/utils/ui_helpers.py 全部 11 个纯函数：
格式函数、速度/时间函数、验证与显示函数。
"""

import unittest

from src.utils.ui_helpers import (
    format_bytes,
    format_elapsed_time,
    format_eta,
    format_mode_name,
    format_number_with_commas,
    format_speed,
    format_timestamp,
    sanitize_display_text,
    truncate_address,
    validate_address_format,
    validate_hex_string,
)


class TestFormatFunctions(unittest.TestCase):
    """格式函数测试。"""

    # ── format_timestamp ──────────────────────────────────────

    def test_format_timestamp_valid(self):
        """有效 ISO 时间戳格式化。"""
        result = format_timestamp("2025-06-15T14:30:00")
        self.assertEqual(result, "06-15 14:30")

    def test_format_timestamp_custom_fmt(self):
        """自定义格式字符串。"""
        result = format_timestamp("2025-06-15T14:30:00", "%Y/%m/%d")
        self.assertEqual(result, "2025/06/15")

    def test_format_timestamp_empty(self):
        """空字符串返回 None。"""
        self.assertIsNone(format_timestamp(""))

    def test_format_timestamp_invalid(self):
        """无效时间戳返回 None。"""
        self.assertIsNone(format_timestamp("not-a-date"))

    # ── format_mode_name ──────────────────────────────────────

    def test_format_mode_name_known(self):
        """已知模式返回中文名。"""
        self.assertEqual(format_mode_name("random"), "随机")
        self.assertEqual(format_mode_name("range"), "范围")
        self.assertEqual(format_mode_name("brute_force"), "穷举")
        self.assertEqual(format_mode_name("gpu"), "GPU")

    def test_format_mode_name_unknown(self):
        """未知模式返回原值。"""
        self.assertEqual(format_mode_name("quantum"), "quantum")

    # ── format_number_with_commas ─────────────────────────────

    def test_format_number_int(self):
        """整数千位分隔。"""
        self.assertEqual(format_number_with_commas(1000000), "1,000,000")

    def test_format_number_float(self):
        """浮点数千位分隔。"""
        self.assertEqual(format_number_with_commas(1234567.89), "1,234,567.89")


class TestSpeedTimeFunctions(unittest.TestCase):
    """速度与时间格式化测试。"""

    # ── format_speed ──────────────────────────────────────────

    def test_format_speed_negative(self):
        """负数返回 0/s。"""
        self.assertEqual(format_speed(-1), "0/s")

    def test_format_speed_zero(self):
        """零值显示。"""
        self.assertEqual(format_speed(0), "0/s")

    def test_format_speed_below_1k(self):
        """< 1000 显示原始值。"""
        self.assertEqual(format_speed(500), "500/s")

    def test_format_speed_k(self):
        """1000-1M 显示 K/s。"""
        self.assertEqual(format_speed(50000), "50.00K/s")

    def test_format_speed_m(self):
        """1M-1B 显示 M/s。"""
        self.assertEqual(format_speed(5000000), "5.00M/s")

    def test_format_speed_b(self):
        """≥ 1B 显示 B/s。"""
        self.assertEqual(format_speed(2000000000), "2.00B/s")

    def test_format_speed_nan(self):
        """NaN 返回 0/s。"""
        self.assertEqual(format_speed(float('nan')), "0/s")

    def test_format_speed_inf(self):
        """±inf 返回 0/s。"""
        self.assertEqual(format_speed(float('inf')), "0/s")
        self.assertEqual(format_speed(-float('inf')), "0/s")

    # ── format_elapsed_time ───────────────────────────────────

    def test_format_elapsed_negative(self):
        """负数返回 00:00:00。"""
        self.assertEqual(format_elapsed_time(-10), "00:00:00")

    def test_format_elapsed_zero(self):
        """零秒。"""
        self.assertEqual(format_elapsed_time(0), "00:00:00")

    def test_format_elapsed_seconds_only(self):
        """纯秒数。"""
        self.assertEqual(format_elapsed_time(45), "00:00:45")

    def test_format_elapsed_minutes(self):
        """分钟+秒。"""
        self.assertEqual(format_elapsed_time(125), "00:02:05")

    def test_format_elapsed_hours(self):
        """小时+分钟+秒。"""
        self.assertEqual(format_elapsed_time(3661), "01:01:01")

    # ── format_eta ────────────────────────────────────────────

    def test_format_eta_negative(self):
        """负数返回 '-'。"""
        self.assertEqual(format_eta(-1), "-")

    def test_format_eta_seconds(self):
        """< 60s 显示秒。"""
        self.assertEqual(format_eta(30), "30s")

    def test_format_eta_minutes(self):
        """60-3600s 显示分钟。"""
        self.assertEqual(format_eta(1800), "30.0m")

    def test_format_eta_hours(self):
        """3600-86400s 显示小时。"""
        self.assertEqual(format_eta(7200), "2.0h")

    def test_format_eta_days(self):
        """≥ 86400s 显示天。"""
        self.assertEqual(format_eta(172800), "2.0d")

    def test_format_eta_inf(self):
        """inf 返回 '-'。"""
        self.assertEqual(format_eta(float('inf')), "-")


class TestValidationDisplayFunctions(unittest.TestCase):
    """验证与显示函数测试。"""

    # ── truncate_address ──────────────────────────────────────

    def test_truncate_short_address(self):
        """短于 max_length 不截断。"""
        self.assertEqual(truncate_address("1Short", 10), "1Short")

    def test_truncate_long_address(self):
        """长于 max_length 截断加 ...。"""
        result = truncate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 10)
        self.assertEqual(result, "1A1zP1eP5Q...")

    def test_truncate_invalid_max_length(self):
        """max_length ≤ 0 返回 '...'。"""
        self.assertEqual(truncate_address("1A1zP1", 0), "...")
        self.assertEqual(truncate_address("1A1zP1", -5), "...")

    # ── validate_address_format ───────────────────────────────

    def test_validate_p2pkh(self):
        """P2PKH 地址 (1 开头)。"""
        self.assertTrue(validate_address_format(
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

    def test_validate_p2sh(self):
        """P2SH 地址 (3 开头)。"""
        self.assertTrue(validate_address_format(
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"))

    def test_validate_bech32(self):
        """Bech32 地址 (bc1 开头)。"""
        self.assertTrue(validate_address_format(
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"))

    def test_validate_wif(self):
        """WIF 私钥格式 (5 开头, 51 字符)。"""
        # 合成符合格式的有效 WIF（非真实密钥）
        self.assertTrue(validate_address_format(
            "5" + "A" * 50))

    def test_validate_compressed_pubkey(self):
        """压缩公钥 (02/03 开头, 66 字符 hex)。"""
        self.assertTrue(validate_address_format(
            "02" + "a" * 64))

    def test_validate_uncompressed_pubkey(self):
        """非压缩公钥 (04 开头, 130 字符 hex)。"""
        self.assertTrue(validate_address_format(
            "04" + "a" * 128))

    def test_validate_address_empty(self):
        """空字符串返回 False。"""
        self.assertFalse(validate_address_format(""))

    def test_validate_address_whitespace_only(self):
        """纯空白返回 False。"""
        self.assertFalse(validate_address_format("   "))

    def test_validate_address_invalid(self):
        """无效格式返回 False。"""
        self.assertFalse(validate_address_format("not-an-address"))

    # ── validate_hex_string ───────────────────────────────────

    def test_validate_hex_valid(self):
        """有效 hex 字符串。"""
        self.assertTrue(validate_hex_string("abcdef"))

    def test_validate_hex_with_prefix(self):
        """带 0x 前缀。"""
        self.assertTrue(validate_hex_string("0xabcdef"))

    def test_validate_hex_empty(self):
        """空字符串。"""
        self.assertFalse(validate_hex_string(""))

    def test_validate_hex_non_string(self):
        """非字符串输入。"""
        self.assertFalse(validate_hex_string(123))

    def test_validate_hex_invalid(self):
        """无效 hex 字符。"""
        self.assertFalse(validate_hex_string("xyz"))

    def test_validate_hex_disallow_prefix(self):
        """不允许 0x 前缀时，非 hex 字符才返回 False。"""
        self.assertFalse(validate_hex_string("0xggg", allow_prefix=False))

    def test_validate_hex_only_prefix(self):
        """仅 0x 前缀无实际 hex 内容返回 False。"""
        self.assertFalse(validate_hex_string("0x"))

    # ── format_bytes ──────────────────────────────────────────

    def test_format_bytes_b(self):
        """< 1024 显示 B。"""
        self.assertEqual(format_bytes(512), "512 B")

    def test_format_bytes_kb(self):
        """KB 范围。"""
        self.assertEqual(format_bytes(2048), "2.00 KB")

    def test_format_bytes_mb(self):
        """MB 范围。"""
        self.assertEqual(format_bytes(5 * 1024**2), "5.00 MB")

    def test_format_bytes_gb(self):
        """GB 范围。"""
        self.assertEqual(format_bytes(3 * 1024**3), "3.00 GB")

    def test_format_bytes_tb(self):
        """TB 范围。"""
        self.assertEqual(format_bytes(2 * 1024**4), "2.00 TB")

    # ── sanitize_display_text ─────────────────────────────────

    def test_sanitize_empty(self):
        """空字符串。"""
        self.assertEqual(sanitize_display_text(""), "")

    def test_sanitize_control_chars(self):
        """移除控制字符（\x00-\x08, \x0b, \x0c, \x0e-\x1f, \x7f）。"""
        self.assertEqual(sanitize_display_text("\x00hello\x7f"), "hello")

    def test_sanitize_whitespace_trim(self):
        """首尾空格被移除。"""
        self.assertEqual(sanitize_display_text("  hello  "), "hello")

    def test_sanitize_preserves_newline_tab(self):
        """保留换行和制表符。"""
        result = sanitize_display_text("a\nb\tc")
        self.assertIn("\n", result)
        self.assertIn("\t", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
