# -*- coding: utf-8 -*-
"""
P0-1: 日志安全过滤器测试

验证 SecurityLogFilter 的正确性：
- 私钥十六进制屏蔽
- WIF 格式私钥屏蔽
- BTC 地址屏蔽 (P2PKH/P2SH/Bech32/Bech32m)
- 普通日志消息不应被修改
- 过滤器集成到 logging 系统
"""
import logging
import unittest

from src.utils.security_log_filter import SecurityLogFilter


class TestSecurityLogFilterPatterns(unittest.TestCase):
    """验证各类敏感模式的正则匹配"""

    @classmethod
    def setUpClass(cls):
        cls.filter = SecurityLogFilter(
            name='test_filter',
            mask_private_keys=True,
            mask_wif=True,
            mask_addresses=True,
        )

    def _sanitize(self, msg: str) -> str:
        return self.filter._sanitize_message(msg)

    # ── 私钥屏蔽 ──────────────────────────────

    def test_masks_64_hex_private_key(self):
        """64位十六进制私钥应被屏蔽"""
        key = 'a' * 64
        result = self._sanitize(f"私钥: {key}")
        self.assertIn('[PRIVATE_KEY:', result)
        self.assertNotIn(key, result)

    def test_masks_0x_prefixed_private_key(self):
        """0x前缀的64位十六进制应被屏蔽"""
        key = '0x' + 'b' * 64
        result = self._sanitize(f"key={key}")
        # 0x前缀导致长度为66，_mask_key 返回 '[PRIVATE_KEY]'
        self.assertIn('[PRIVATE_KEY]', result)
        self.assertNotIn('0x' + 'b' * 64, result)

    def test_does_not_mask_short_hex(self):
        """短于64位的十六进制不应被屏蔽"""
        short_hex = 'abcd' * 8  # 32 characters
        result = self._sanitize(f"hash: {short_hex}")
        self.assertIn(short_hex, result)

    # ── WIF 屏蔽 ──────────────────────────────

    def test_masks_wif_private_key_5(self):
        """以 5 开头的 WIF 私钥应被屏蔽"""
        wif = '5KWDpqqbKJ6wDPobVmvQNkHFZHxQGBsHZ2qJLmcWmbFwD8GkVnM'
        result = self._sanitize(f"导入: {wif}")
        self.assertIn('[WIF_PRIVATE_KEY]', result)
        self.assertNotIn(wif, result)

    def test_masks_wif_private_key_K(self):
        """以 K 开头的 WIF 私钥应被屏蔽"""
        wif = 'KxFC1jmwwCoACiCAWZDgQLKxwFgJj7BjJwxqM5hDZJqGKV7LjJRR'
        result = self._sanitize(f"key={wif}")
        self.assertIn('[WIF_PRIVATE_KEY]', result)

    def test_masks_wif_private_key_L(self):
        """以 L 开头的 WIF 私钥应被屏蔽"""
        wif = 'L5AQtVQHsJhCJfYfGzGJXfQvKXHwDvRqJzGx7Y6Yq8zK3wN4pQrS'
        result = self._sanitize(f"wif={wif}")
        self.assertIn('[WIF_PRIVATE_KEY]', result)

    # ── 地址屏蔽 ──────────────────────────────

    def test_masks_p2pkh_address(self):
        """P2PKH 地址 (1...) 应被屏蔽"""
        addr = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        result = self._sanitize(f"匹配地址: {addr}")
        self.assertIn('[P2PKH_ADDRESS]', result)
        self.assertNotIn(addr, result)

    def test_masks_p2sh_address(self):
        """P2SH 地址 (3...) 应被屏蔽"""
        addr = '3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy'
        result = self._sanitize(f"target={addr}")
        self.assertIn('[P2SH_ADDRESS]', result)
        self.assertNotIn(addr, result)

    def test_masks_bech32_address(self):
        """Bech32 地址 (bc1...) 应被屏蔽"""
        addr = 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4'
        result = self._sanitize(f"found: {addr}")
        self.assertIn('[BECH32_ADDRESS]', result)
        self.assertNotIn(addr, result)

    def test_masks_bech32m_address(self):
        """Bech32m/Taproot 地址 (bc1p...) 应被屏蔽"""
        addr = 'bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acjw8c3p6vs7q8fhp'
        result = self._sanitize(f"taproot={addr}")
        self.assertIn('[BECH32M_ADDRESS]', result)
        self.assertNotIn(addr, result)

    # ── 正常消息不受影响 ──────────────────────

    def test_preserves_normal_message(self):
        """普通日志消息不应被修改"""
        msg = "引擎启动完成，已处理 10000 个密钥"
        result = self._sanitize(msg)
        self.assertEqual(msg, result)

    def test_preserves_partial_hex(self):
        """部分十六进制值不受影响"""
        msg = "batch_id=42, count=1000"
        result = self._sanitize(msg)
        self.assertEqual(msg, result)

    # ── 过滤器可禁用 ──────────────────────────

    def test_disabled_filter_passes_through(self):
        """禁用地址过滤后地址不被修改"""
        disabled = SecurityLogFilter(
            mask_private_keys=True,
            mask_wif=True,
            mask_addresses=False,
        )
        addr = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        result = disabled._sanitize_message(f"addr: {addr}")
        self.assertIn(addr, result)


class TestSecurityLogFilterIntegration(unittest.TestCase):
    """验证 SecurityLogFilter 集成到 Python logging 系统"""

    def test_filter_added_to_logger(self):
        """过滤器可添加到 logger 并生效"""
        logger = logging.getLogger('test_security_filter')
        sf = SecurityLogFilter(mask_private_keys=True, mask_wif=True, mask_addresses=True)
        logger.addFilter(sf)

        key = 'c' * 64
        with self.assertLogs(logger, level='INFO') as cm:
            logger.info("碰撞匹配！私钥: %s, 地址: %s",
                        key, '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        output = cm.output[0]
        self.assertNotIn(key, output)
        self.assertNotIn('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', output)
        self.assertIn('[PRIVATE_KEY:', output)
        self.assertIn('[P2PKH_ADDRESS]', output)


if __name__ == '__main__':
    unittest.main()
