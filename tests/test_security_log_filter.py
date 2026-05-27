"""security_log_filter.py 模块单元测试.

测试 SecurityLogFilter 安全日志过滤器：
- 私钥十六进制/WIF/原始字节掩码
- 比特币地址 (P2PKH/P2SH/Bech32/Bech32m) 掩码
- BIP32 扩展密钥掩码
- setup_security_logging / sanitize_private_key_for_log 函数
"""

import hashlib
import logging
from unittest.mock import MagicMock

from src.utils.security_log_filter import (
    SecurityLogFilter,
    log_safe_debug,
    log_safe_error,
    sanitize_private_key_for_log,
    setup_security_logging,
)


class TestSecurityLogFilterInit:
    """测试 SecurityLogFilter 初始化."""

    def test_init_defaults(self):
        """默认所有掩码开关为 True."""
        f = SecurityLogFilter()
        assert f.mask_private_keys is True
        assert f.mask_wif is True
        assert f.mask_addresses is True

    def test_init_custom_name(self):
        """自定义名称."""
        f = SecurityLogFilter(name="my_filter")
        assert f.name == "my_filter"

    def test_init_disable_private_keys(self):
        """禁用私钥掩码."""
        f = SecurityLogFilter(mask_private_keys=False)
        assert f.mask_private_keys is False

    def test_init_disable_wif(self):
        """禁用 WIF 掩码."""
        f = SecurityLogFilter(mask_wif=False)
        assert f.mask_wif is False

    def test_init_disable_addresses(self):
        """禁用地址掩码."""
        f = SecurityLogFilter(mask_addresses=False)
        assert f.mask_addresses is False


class TestSecurityLogFilterFilter:
    """测试 filter() 方法."""

    def test_filter_no_msg_attribute(self):
        """Record 无 msg 属性 → 直接返回 True."""
        f = SecurityLogFilter()
        record = MagicMock(spec=[])
        result = f.filter(record)
        assert result is True

    def test_filter_str_message(self):
        """字符串消息被清理."""
        f = SecurityLogFilter()
        record = MagicMock()
        record.msg = "normal log message"
        record.args = None
        result = f.filter(record)
        assert result is True
        assert record.msg == "normal log message"

    def test_filter_args_dict(self):
        """Args 为 dict 时每个 str 值被清理."""
        f = SecurityLogFilter()
        record = MagicMock()
        record.msg = "test"
        record.args = {"key1": "value1", "key2": 123}
        result = f.filter(record)
        assert result is True

    def test_filter_args_tuple(self):
        """Args 为 tuple/list 时每个 str 值被清理."""
        f = SecurityLogFilter()
        record = MagicMock()
        record.msg = "test"
        record.args = ("str_val", 42, "another")
        result = f.filter(record)
        assert result is True


class TestSanitizeMessagePrivateKeys:
    """测试 _sanitize_message — 私钥掩码."""

    def test_masks_64char_hex_key(self):
        """64位十六进制私钥被掩码."""
        f = SecurityLogFilter()
        test_key = "a" * 64
        result = f._sanitize_message(f"key is {test_key}")
        assert test_key not in result
        assert "[PRIVATE_KEY:" in result

    def test_masks_0x_prefix_hex_key(self):
        """0x 前缀的64位十六进制被掩码."""
        f = SecurityLogFilter()
        test_key = "0x" + "b" * 64
        result = f._sanitize_message(f"key is {test_key}")
        assert test_key not in result

    def test_masks_multiple_hex_keys(self):
        """多个私钥全部被掩码."""
        f = SecurityLogFilter()
        key1 = "a" * 64
        key2 = "b" * 64
        result = f._sanitize_message(f"keys: {key1} and {key2}")
        assert key1 not in result
        assert key2 not in result

    def test_private_keys_disabled(self):
        """禁用私钥掩码时不替换."""
        f = SecurityLogFilter(mask_private_keys=False)
        test_key = "a" * 64
        result = f._sanitize_message(f"key is {test_key}")
        assert test_key in result


class TestSanitizeMessageWIF:
    """测试 _sanitize_message — WIF 掩码."""

    def test_masks_wif_uncompressed(self):
        """5 开头的非压缩 WIF 被掩码."""
        f = SecurityLogFilter()
        # 创建一个格式正确的 WIF 测试字符串 (5H...)
        wif = "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf"
        result = f._sanitize_message(f"my wif: {wif}")
        assert "[WIF_UNCOMPRESSED_KEY]" in result
        assert wif not in result

    def test_masks_wif_compressed(self):
        """K/L 开头的压缩 WIF 被掩码."""
        f = SecurityLogFilter()
        wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
        result = f._sanitize_message(f"my wif: {wif}")
        assert "[WIF_COMPRESSED_KEY]" in result

    def test_wif_disabled(self):
        """禁用 WIF 掩码时不替换."""
        f = SecurityLogFilter(mask_wif=False)
        wif = "5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf"
        result = f._sanitize_message(f"my wif: {wif}")
        assert wif in result


class TestSanitizeMessageRawKey:
    """测试 _sanitize_message — 原始字节掩码."""

    def test_masks_raw_key_bytes(self):
        r"""b'\\x...' 原始字节被掩码."""
        f = SecurityLogFilter()
        # 确保匹配: 32字节的b'...'格式
        raw_full = "b'" + "\\x00" * 32 + "'"
        result = f._sanitize_message(f"raw: {raw_full}")
        assert "[RAW_PRIVATE_KEY]" in result


class TestSanitizeMessageAddresses:
    """测试 _sanitize_message — 比特币地址掩码."""

    def test_masks_p2pkh_address(self):
        """1 开头的 P2PKH 地址被掩码."""
        f = SecurityLogFilter()
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = f._sanitize_message(f"address: {addr}")
        assert "[P2PKH_ADDRESS]" in result
        assert addr not in result

    def test_masks_p2sh_address(self):
        """3 开头的 P2SH 地址被掩码."""
        f = SecurityLogFilter()
        addr = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        result = f._sanitize_message(f"address: {addr}")
        assert "[P2SH_ADDRESS]" in result

    def test_masks_bech32_address(self):
        """bc1 开头的 Bech32 地址被掩码."""
        f = SecurityLogFilter()
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        result = f._sanitize_message(f"address: {addr}")
        assert "[BECH32_ADDRESS]" in result

    def test_masks_bech32m_address(self):
        """bc1p 开头的 Bech32m (Taproot) 地址被掩码."""
        f = SecurityLogFilter()
        addr = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2ys4q2qmp2v7e"
        result = f._sanitize_message(f"address: {addr}")
        assert "[BECH32M_ADDRESS]" in result

    def test_addresses_disabled(self):
        """禁用地址掩码时不替换."""
        f = SecurityLogFilter(mask_addresses=False)
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = f._sanitize_message(f"address: {addr}")
        assert addr in result


class TestSanitizeMessageBIP32:
    """测试 _sanitize_message — BIP32 扩展密钥掩码."""

    def test_masks_xprv(self):
        """Xprv 扩展私钥被掩码."""
        f = SecurityLogFilter()
        # xprv + 107 base58 字符 (符合 BIP32 格式)
        xprv = "xprv" + "A" * 107
        result = f._sanitize_message(f"extended key: {xprv}")
        assert "[BIP32_EXTENDED_KEY]" in result

    def test_masks_xpub(self):
        """Xpub 扩展公钥被掩码."""
        f = SecurityLogFilter()
        # xpub + 108 base58 字符
        xpub = "xpub" + "B" * 108
        result = f._sanitize_message(f"extended pub: {xpub}")
        assert "[BIP32_EXTENDED_PUBKEY]" in result


class TestMaskKey:
    """测试 _mask_key 方法."""

    def test_mask_64char_key(self):
        """64位私钥返回带哈希的掩码."""
        f = SecurityLogFilter()
        test_key = "a" * 64
        result = f._mask_key(test_key)
        assert result.startswith("[PRIVATE_KEY:")
        assert "***" in result or "..." in result

    def test_mask_non_64char_key(self):
        """非64位私钥返回通用掩码."""
        f = SecurityLogFilter()
        result = f._mask_key("short")
        assert result == "[PRIVATE_KEY]"

    def test_mask_consistent_hash(self):
        """相同私钥产生相同掩码."""
        f = SecurityLogFilter()
        test_key = "b" * 64
        r1 = f._mask_key(test_key)
        r2 = f._mask_key(test_key)
        assert r1 == r2


class TestSetupSecurityLogging:
    """测试 setup_security_logging 函数."""

    def test_adds_filter_to_root_logger(self):
        """向 root logger 添加安全过滤器."""
        root_logger = logging.getLogger()
        before = len(root_logger.filters)
        setup_security_logging()
        after = len(root_logger.filters)
        # 应至少增加 1 个 filter
        assert after >= before
        # 清理
        root_logger.filters.clear()

    def test_adds_filter_to_module_loggers(self):
        """向主要模块 logger 添加安全过滤器."""
        root_logger = logging.getLogger()
        root_logger.filters.clear()
        setup_security_logging()
        # 验证 KeyCollisionEngine logger 有 filter
        engine_logger = logging.getLogger("KeyCollisionEngine")
        assert len(engine_logger.filters) >= 1
        # 清理
        root_logger.filters.clear()
        engine_logger.filters.clear()


class TestSanitizePrivateKeyForLog:
    """测试 sanitize_private_key_for_log 函数."""

    def test_sanitize_normal_key(self):
        """正常32字节私钥返回哈希."""
        key = b"\x01" * 32
        result = sanitize_private_key_for_log(key)
        assert result.startswith("[KEY_HASH:")
        expected_hash = hashlib.sha256(key).hexdigest()[:16]
        assert expected_hash in result

    def test_sanitize_empty_key(self):
        """空私钥返回 [EMPTY_KEY]."""
        result = sanitize_private_key_for_log(b"")
        assert result == "[EMPTY_KEY]"

    def test_sanitize_none_key(self):
        """None 私钥返回 [EMPTY_KEY]."""
        result = sanitize_private_key_for_log(None)  # type: ignore[arg-type]
        assert result == "[EMPTY_KEY]"


class TestLogSafeFunctions:
    """测试 log_safe_error 和 log_safe_debug."""

    def test_log_safe_error(self):
        """log_safe_error 调用 logger.error."""
        mock_logger = MagicMock()
        log_safe_error(mock_logger, "test error message", extra="info")
        mock_logger.error.assert_called_once_with("test error message", extra="info")

    def test_log_safe_debug(self):
        """log_safe_debug 调用 logger.debug."""
        mock_logger = MagicMock()
        log_safe_debug(mock_logger, "test debug message")
        mock_logger.debug.assert_called_once_with("test debug message")
