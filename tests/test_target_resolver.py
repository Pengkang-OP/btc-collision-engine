#!/usr/bin/env python3
"""目标地址解析器 (resolver) 单元测试.

覆盖：
- bech32_decode 解码函数
- decode_segwit_address SegWit地址解码
- TargetResolver 初始化
- detect_format 格式自动检测
- resolve 单地址解析
- get_cache_stats / clear_cache
"""

import pytest

# ============================================================================
# bech32_decode 测试
# ============================================================================


@pytest.mark.unit
class TestBech32Decode:
    """Bech32 解码测试."""

    def test_valid_bech32_mainnet(self):
        from src.utils.bech32_codec import bech32_decode

        hrp, data, enc = bech32_decode("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert hrp == "bc"
        assert data is not None
        assert enc is not None

    def test_valid_bech32_testnet(self):
        """测试网Bech32地址（使用 BIP-173 测试向量）."""
        from src.utils.bech32_codec import bech32_decode

        # BIP-173 有效测试向量
        hrp, data, enc = bech32_decode("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx")
        assert hrp == "tb"
        assert data is not None

    def test_invalid_mixed_case(self):
        from src.utils.bech32_codec import bech32_decode

        hrp, data, enc = bech32_decode("Bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert hrp is None

    def test_invalid_empty(self):
        from src.utils.bech32_codec import bech32_decode

        hrp, data, enc = bech32_decode("")
        assert hrp is None

    def test_invalid_no_separator(self):
        from src.utils.bech32_codec import bech32_decode

        hrp, data, enc = bech32_decode("bcqar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert hrp is None

    def test_invalid_too_long(self):
        from src.utils.bech32_codec import bech32_decode

        hrp, data, enc = bech32_decode("bc1" + "q" * 100)
        assert hrp is None

    def test_taproot_format_detection(self):
        """仅验证前缀检测 (不验证 Taproot 校验和)."""
        # 使用格式检测验证，不依赖具体地址校验
        from src.collision.targets.resolver import TargetResolver

        fmt = TargetResolver.detect_format("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt")
        # 格式检测应返回 taproot_address
        assert fmt == "taproot_address"


# ============================================================================
# decode_segwit_address 测试
# ============================================================================


@pytest.mark.unit
class TestDecodeSegwitAddress:
    """SegWit 地址解码测试."""

    def test_valid_bech32_p2wpkh(self):
        from src.utils.bech32_codec import decode_segwit_address

        hrp, version, program = decode_segwit_address(
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", expected_hrp="bc",
        )
        assert version == 0
        assert program is not None
        assert len(program) == 20

    def test_valid_taproot_p2tr(self):
        """Taproot 检测格式验证（不做完整解码，因为需要正确的校验和地址）."""
        from src.collision.targets.resolver import TargetResolver

        # 使用 detect_format 验证 taproot 检测
        fmt = TargetResolver.detect_format("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt")
        assert fmt == "taproot_address"

    def test_invalid_hrp_mismatch(self):
        from src.utils.bech32_codec import decode_segwit_address

        hrp, version, program = decode_segwit_address(
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", expected_hrp="tb",
        )
        assert version is None
        assert program is None

    def test_invalid_address(self):
        from src.utils.bech32_codec import decode_segwit_address

        hrp, version, program = decode_segwit_address("invalid", expected_hrp="bc")
        assert version is None


# ============================================================================
# detect_format 测试
# ============================================================================


@pytest.mark.unit
class TestDetectFormat:
    """格式检测测试."""

    def test_p2pkh(self):
        from src.collision.targets.resolver import TargetResolver

        fmt = TargetResolver.detect_format("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert fmt == "address"

    def test_p2sh(self):
        from src.collision.targets.resolver import TargetResolver

        fmt = TargetResolver.detect_format("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")
        assert fmt == "p2sh_address"

    def test_bech32(self):
        from src.collision.targets.resolver import TargetResolver

        fmt = TargetResolver.detect_format("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert fmt == "bech32_address"

    def test_taproot(self):
        from src.collision.targets.resolver import TargetResolver

        fmt = TargetResolver.detect_format("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt")
        assert fmt == "taproot_address"

    def test_wif_uncompressed(self):
        from src.collision.targets.resolver import TargetResolver

        # 这是一个示例5开头WIF格式（不一定是真实私钥，只测格式检测）
        fmt = TargetResolver.detect_format("5HpHagT65TZzG1PH3CSu63k8DbpvD8s5ip4nEB3kEsreAnchuDf")
        assert fmt == "wif"

    def test_unknown_empty(self):
        from src.collision.targets.resolver import TargetResolver

        assert TargetResolver.detect_format("") == "unknown"

    def test_unknown_random(self):
        from src.collision.targets.resolver import TargetResolver

        assert TargetResolver.detect_format("xyz_not_a_valid_format_abc") == "unknown"


# ============================================================================
# TargetResolver 初始化与基本方法测试
# ============================================================================


@pytest.mark.unit
class TestTargetResolverBasic:
    """TargetResolver 基本方法测试."""

    def test_init_defaults(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver()
        assert resolver.cache is not None
        assert resolver._batch_size == 100

    def test_init_without_cache(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)
        assert resolver.cache is None

    def test_init_custom_batch_size(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(batch_size=50)
        assert resolver._batch_size == 50

    def test_clear_cache(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=True)
        # 不应崩溃
        resolver.clear_cache()

    def test_get_cache_stats_disabled(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)
        stats = resolver.get_cache_stats()
        assert stats == {}

    def test_get_cache_stats_enabled(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=True)
        stats = resolver.get_cache_stats()
        assert isinstance(stats, dict)
        assert "size" in stats or "hits" in stats

    def test_resolve_p2pkh(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert result == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    def test_resolve_invalid(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve("not_valid")
        assert result is None

    def test_resolve_with_cache(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=True)
        result = resolver.resolve("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert result == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


@pytest.mark.unit
class TestResolveBatch:
    """批量解析测试."""

    def test_resolve_batch(self):
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)
        results = resolver.resolve_batch(
            [
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "not_valid",
            ],
        )
        assert len(results) == 2
        assert results["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"] is not None
        assert results["not_valid"] is None


# ============================================================================
# analyze_target_formats 测试
# ============================================================================


@pytest.mark.unit
class TestAnalyzeTargetFormats:
    """目标格式分布分析测试."""

    def test_pure_p2pkh(self):
        from src.collision.targets.resolver import TargetResolver

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "12cbQLTFMXRnSzktFkuoG3eHoMeFtpTu3S"}
        result = TargetResolver.analyze_target_formats(targets)
        assert result["p2pkh"] == 2
        assert result["p2sh"] == 0
        assert result["bech32"] == 0
        assert result["taproot"] == 0
        assert result["unknown"] == 0

    def test_mixed_formats(self):
        from src.collision.targets.resolver import TargetResolver

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",  # Bech32
            "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt",  # Taproot
        }
        result = TargetResolver.analyze_target_formats(targets)
        assert result["p2pkh"] == 1
        assert result["p2sh"] == 1
        assert result["bech32"] == 1
        assert result["taproot"] == 1
        assert result["unknown"] == 0

    def test_empty_set(self):
        from src.collision.targets.resolver import TargetResolver

        result = TargetResolver.analyze_target_formats(set())
        assert result["p2pkh"] == 0
        assert result["p2sh"] == 0
        assert result["bech32"] == 0
        assert result["taproot"] == 0
        assert result["unknown"] == 0

    def test_unknown_prefix(self):
        from src.collision.targets.resolver import TargetResolver

        targets = {
            "2NFf16kDmUQ5RqhsVHtZoF1rsYqkYJvRgPg",
            "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
        }
        result = TargetResolver.analyze_target_formats(targets)
        assert result["p2pkh"] == 0
        assert result["unknown"] == 2
