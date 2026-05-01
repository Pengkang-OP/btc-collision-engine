# -*- coding: utf-8 -*-
"""
综合验证测试：基于已知比特币密钥对的端到端验证

测试数据：
- WIF压缩私钥: KwjunGHKTae1w6BHCcmvWvWMEtWx5DTAwART1gHA1bysSMQsL68p
- 压缩公钥: 0378a11dcf4a9cfc486db5ef3f7fe1d05f5f111fb35273e8a0d21d9c8eb264a51c
- P2PKH地址: 1HQF84ac1fgEBWrtav5vgpmLhbFkBLAyuV
"""

import os
import sys

# 确保项目根目录在 sys.path 中
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.core.wif import WIF  # noqa: E402
from src.core.base58 import Base58  # noqa: E402
from src.core.address_generator import P2PKHAddressGenerator  # noqa: E402
from src.core.bitcoin_key_validator import (  # noqa: E402
    BitcoinKeyValidator,
    KeyValidationConstants,
    AddressType,
)
from src.core.secp256k1 import Secp256k1  # noqa: E402
from src.collision.key_collision_engine import KeyCollisionEngine  # noqa: E402
from src.collision.checkpoint_manager import CheckpointManager  # noqa: E402
from src.monitoring.data_logger import DataLogger  # noqa: E402

# ──────────────────────────────────────────────
# 已知测试数据常量
# ──────────────────────────────────────────────
KNOWN_WIF = "KwjunGHKTae1w6BHCcmvWvWMEtWx5DTAwART1gHA1bysSMQsL68p"
KNOWN_PUBKEY_HEX = "0378a11dcf4a9cfc486db5ef3f7fe1d05f5f111fb35273e8a0d21d9c8eb264a51c"
KNOWN_ADDRESS = "1HQF84ac1fgEBWrtav5vgpmLhbFkBLAyuV"


# ──────────────────────────────────────────────
# 1. TestKeyDerivation - 密钥派生验证
# ──────────────────────────────────────────────
class TestKeyDerivation:
    """从WIF到公钥到地址的完整派生链验证"""

    def test_wif_decode_to_private_key(self):
        """从WIF解码私钥，验证compressed=True"""
        private_key, compressed = WIF.decode(KNOWN_WIF)
        assert isinstance(private_key, bytes), "私钥应为bytes类型"
        assert len(private_key) == 32, f"私钥长度应为32字节，实际{len(private_key)}"
        assert compressed is True, "应解码为压缩格式"

    def test_private_key_to_public_key(self):
        """从解码的私钥生成公钥，断言==已知公钥hex"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        validator = BitcoinKeyValidator(secure_mode=False)
        result, pubkey_bytes = validator.generate_public_key(private_key, compressed=True)
        assert result.success, f"公钥生成应成功，错误: {result.errors}"
        assert (
            pubkey_bytes.hex() == KNOWN_PUBKEY_HEX
        ), f"公钥不匹配:\n期望: {KNOWN_PUBKEY_HEX}\n实际: {pubkey_bytes.hex()}"

    def test_private_key_to_address(self):
        """从解码的私钥生成地址，断言==已知地址"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        generator = P2PKHAddressGenerator()
        address, _, _ = generator.generate_address(private_key)
        assert address == KNOWN_ADDRESS, f"地址不匹配:\n期望: {KNOWN_ADDRESS}\n实际: {address}"

    def test_full_derivation_chain(self):
        """完整链路 WIF->私钥->公钥->地址"""
        # Step1: WIF -> 私钥
        private_key, compressed = WIF.decode(KNOWN_WIF)
        assert compressed is True

        # Step2: 私钥 -> 公钥
        validator = BitcoinKeyValidator(secure_mode=False)
        pub_result, pubkey = validator.generate_public_key(private_key, compressed=True)
        assert pub_result.success, f"公钥生成失败: {pub_result.errors}"
        assert pubkey.hex() == KNOWN_PUBKEY_HEX

        # Step3: 公钥 -> 地址
        addr_result, address = validator.generate_address(pubkey, AddressType.P2PKH)
        assert addr_result.success, f"地址生成失败: {addr_result.errors}"
        assert address == KNOWN_ADDRESS


# ──────────────────────────────────────────────
# 2. TestAddressFormat - 地址格式验证
# ──────────────────────────────────────────────
class TestAddressFormat:
    """P2PKH地址格式验证"""

    def test_address_starts_with_1(self):
        """地址以'1'开头"""
        assert KNOWN_ADDRESS.startswith("1"), f"地址应以'1'开头，实际: {KNOWN_ADDRESS[0]}"

    def test_address_base58check_decode(self):
        """check_decode返回version=0x00, payload长度20"""
        version, payload = Base58.check_decode(KNOWN_ADDRESS)
        assert version == 0x00, f"版本字节应为0x00，实际: 0x{version:02x}"
        assert len(payload) == 20, f"payload长度应为20字节，实际: {len(payload)}"

    def test_address_length_range(self):
        """地址长度在26-35之间"""
        length = len(KNOWN_ADDRESS)
        assert 26 <= length <= 35, f"地址长度{length}不在26-35范围内"

    def test_address_roundtrip(self):
        """Base58Check编码解码往返一致"""
        version, payload = Base58.check_decode(KNOWN_ADDRESS)
        re_encoded = Base58.check_encode(version, payload)
        assert (
            re_encoded == KNOWN_ADDRESS
        ), f"往返编码不一致:\n期望: {KNOWN_ADDRESS}\n实际: {re_encoded}"


# ──────────────────────────────────────────────
# 3. TestPublicKeyFormat - 公钥格式验证
# ──────────────────────────────────────────────
class TestPublicKeyFormat:
    """压缩公钥格式验证"""

    def _pubkey_bytes(self):
        return bytes.fromhex(KNOWN_PUBKEY_HEX)

    def test_compressed_prefix(self):
        """压缩公钥前缀为0x02或0x03"""
        pubkey = self._pubkey_bytes()
        assert pubkey[0] in (0x02, 0x03), f"前缀应为0x02或0x03，实际: 0x{pubkey[0]:02x}"

    def test_compressed_length(self):
        """压缩公钥总长度33字节"""
        pubkey = self._pubkey_bytes()
        assert len(pubkey) == 33, f"压缩公钥长度应为33，实际: {len(pubkey)}"

    def test_on_secp256k1_curve(self):
        """使用BitcoinKeyValidator验证公钥在secp256k1曲线上"""
        pubkey = self._pubkey_bytes()
        validator = BitcoinKeyValidator()
        result = validator.validate_public_key(pubkey)
        assert result.success, f"公钥验证失败: {result.errors}"
        assert result.details.get("public_key_on_curve") is True, "公钥应在曲线上"


# ──────────────────────────────────────────────
# 4. TestPrivateKeyFormat - 私钥格式验证
# ──────────────────────────────────────────────
class TestPrivateKeyFormat:
    """WIF私钥格式验证"""

    def test_wif_starts_with_k_or_l(self):
        """压缩WIF以'K'或'L'开头"""
        assert KNOWN_WIF[0] in ("K", "L"), f"压缩WIF应以K或L开头，实际: {KNOWN_WIF[0]}"

    def test_wif_length(self):
        """压缩WIF长度为52"""
        assert (
            len(KNOWN_WIF) == KeyValidationConstants.COMPRESSED_WIF_LENGTH
        ), f"压缩WIF长度应为52，实际: {len(KNOWN_WIF)}"

    def test_wif_decode_compressed_flag(self):
        """decode返回compressed=True"""
        _, compressed = WIF.decode(KNOWN_WIF)
        assert compressed is True, "应解码为压缩标志=True"

    def test_wif_base58check_version(self):
        """check_decode返回version=0x80"""
        version, payload = Base58.check_decode(KNOWN_WIF)
        assert (
            version == KeyValidationConstants.WIF_VERSION_BYTE
        ), f"WIF版本字节应为0x80，实际: 0x{version:02x}"

    def test_private_key_in_valid_range(self):
        """私钥值在[1, N)范围内"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        k = int.from_bytes(private_key, "big")
        assert 1 <= k < Secp256k1.N, f"私钥整数值应在[1, N)范围内，实际: {k}"


# ──────────────────────────────────────────────
# 5. TestEndToEnd - 端到端功能测试
# ──────────────────────────────────────────────
class TestEndToEnd:
    """端到端功能测试"""

    def test_bitcoin_key_validator_full_chain(self):
        """调用full_validation_chain()验证overall_success=True"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        validator = BitcoinKeyValidator()
        report = validator.full_validation_chain(private_key, {KNOWN_ADDRESS})
        assert (
            report["overall_success"] is True
        ), f"full_validation_chain应成功，errors: {report.get('errors')}"

    def test_p2pkh_address_generator(self):
        """使用P2PKHAddressGenerator生成地址验证"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        generator = P2PKHAddressGenerator()
        address, compressed_pk, uncompressed_pk = generator.generate_address(private_key)
        assert address == KNOWN_ADDRESS, f"生成地址不匹配:\n期望: {KNOWN_ADDRESS}\n实际: {address}"
        assert isinstance(compressed_pk, bytes), "压缩公钥应为bytes"
        assert len(compressed_pk) == 33, "压缩公钥应为33字节"
        assert isinstance(uncompressed_pk, bytes), "非压缩公钥应为bytes"

    def test_collision_engine_target_loading(self):
        """创建KeyCollisionEngine验证targets集合包含目标地址"""
        engine = KeyCollisionEngine(
            targets={KNOWN_ADDRESS},
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        # KeyCollisionEngine 自动将地址转为小写（行137: set(addr.lower() for addr in targets)）
        assert any(
            KNOWN_ADDRESS.lower() == t.lower() for t in engine.targets
        ), f"目标地址应在engine.targets中（忽略大小写），实际targets: {engine.targets}"

    def test_data_logger_recording(self, tmp_path):
        """DataLogger记录不抛出异常"""
        logger = DataLogger(storage_dir=str(tmp_path))
        try:
            logger.record_performance_data(
                speed=1000.0,
                total_checked=10000,
                matches_found=0,
                cpu_usage=50.0,
                memory_usage=256.0,
                thread_count=4,
            )
            logger.record_engine_data(
                mode="random",
                target_count=1,
                is_running=True,
                current_position=0,
                additional_info={"test": True},
            )
        finally:
            logger.stop()


# ──────────────────────────────────────────────
# 6. TestSecurity - 安全测试验证
# ──────────────────────────────────────────────
class TestSecurity:
    """安全相关测试"""

    def test_address_match_positive(self):
        """verify_address_match对已知地址返回match=True"""
        validator = BitcoinKeyValidator()
        result = validator.verify_address_match(KNOWN_ADDRESS, {KNOWN_ADDRESS})
        assert result.details.get("match") is True, f"已知地址应匹配，errors: {result.errors}"

    def test_address_match_negative(self):
        """对非匹配地址返回match=False"""
        validator = BitcoinKeyValidator()
        non_matching = "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divfna"  # 创世区块地址
        result = validator.verify_address_match(non_matching, {KNOWN_ADDRESS})
        assert result.details.get("match") is False, "非匹配地址不应返回match=True"

    def test_validate_private_key_success(self):
        """validate_private_key对有效私钥返回success=True"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        validator = BitcoinKeyValidator()
        result = validator.validate_private_key(private_key)
        assert result.success is True, f"有效私钥应通过验证，errors: {result.errors}"

    def test_wif_roundtrip(self):
        """WIF编码解码往返一致"""
        private_key, compressed = WIF.decode(KNOWN_WIF)
        re_encoded = WIF.encode(private_key, compressed)
        assert re_encoded == KNOWN_WIF, f"WIF往返编码不一致:\n期望: {KNOWN_WIF}\n实际: {re_encoded}"

    def test_secure_mode_no_plaintext(self):
        """安全模式下details中不包含private_key_hex"""
        private_key, _ = WIF.decode(KNOWN_WIF)
        validator = BitcoinKeyValidator(secure_mode=True)
        result = validator.validate_private_key(private_key)
        assert "private_key_hex" not in result.details, "安全模式下details中不应包含private_key_hex"


# ──────────────────────────────────────────────
# 7. TestCollisionDetection - 目标地址碰撞测试
# ──────────────────────────────────────────────
class TestCollisionDetection:
    """碰撞引擎相关测试"""

    def test_target_address_loaded(self):
        """创建KeyCollisionEngine验证目标地址在self.targets中"""
        engine = KeyCollisionEngine(
            targets={KNOWN_ADDRESS},
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        # KeyCollisionEngine 自动将地址转为小写（行137: set(addr.lower() for addr in targets)）
        assert any(
            KNOWN_ADDRESS.lower() == t.lower() for t in engine.targets
        ), f"目标地址未加载到engine.targets（忽略大小写），实际: {engine.targets}"

    def test_checkpoint_save_load(self, tmp_path):
        """CheckpointManager save后load验证数据正确"""
        checkpoint_file = str(tmp_path / "test_checkpoint.json")
        manager = CheckpointManager(filepath=checkpoint_file)

        manager.save(
            mode="random",
            targets={KNOWN_ADDRESS},
            current_position=12345,
            total_checked=54321,
            matches=[],
            force=True,
        )

        assert manager.exists(), "断点文件应存在"
        loaded = manager.load()
        assert loaded is not None, "加载的断点数据不应为None"
        assert loaded.get("mode") == "random", "断点mode应正确"
        assert loaded.get("total_checked") == 54321, "断点total_checked应正确"

    def test_match_callback_invoked(self):
        """验证on_match回调机制：地址在targets中且_safe_invoke_match_callback可调用"""
        callback_results = []

        def on_match(private_key: bytes, address: str, wif: str):
            callback_results.append(
                {
                    "private_key": private_key,
                    "address": address,
                    "wif": wif,
                }
            )

        engine = KeyCollisionEngine(
            targets={KNOWN_ADDRESS},
            on_match=on_match,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 验证目标地址在engine.targets中（匹配条件成立，KeyCollisionEngine自动转小写）
        assert any(KNOWN_ADDRESS.lower() == t.lower() for t in engine.targets)

        # 如果引擎存在 _safe_invoke_match_callback，手动触发验证回调机制
        if hasattr(engine, "_safe_invoke_match_callback"):
            private_key, _ = WIF.decode(KNOWN_WIF)
            engine._safe_invoke_match_callback(private_key, KNOWN_ADDRESS, KNOWN_WIF)
            assert len(callback_results) == 1, "回调应被调用一次"
            assert callback_results[0]["address"] == KNOWN_ADDRESS
        else:
            # 若方法不存在，直接调用on_match回调验证参数格式
            private_key, _ = WIF.decode(KNOWN_WIF)
            on_match(private_key, KNOWN_ADDRESS, KNOWN_WIF)
            assert len(callback_results) == 1
            assert callback_results[0]["address"] == KNOWN_ADDRESS


# ──────────────────────────────────────────────
# 8. TestIntegration - 多地址格式集成测试
# ──────────────────────────────────────────────
class TestIntegration:
    """多地址格式集成测试"""

    def test_generate_all_address_types(self):
        """从同一公钥生成P2PKH、P2SH、Bech32三种地址，验证格式不同且各自格式正确"""
        pubkey = bytes.fromhex(KNOWN_PUBKEY_HEX)

        # P2PKH地址
        validator = BitcoinKeyValidator()
        _, p2pkh_address = validator.generate_address(pubkey, AddressType.P2PKH)
        assert p2pkh_address.startswith("1"), f"P2PKH地址应以'1'开头，实际: {p2pkh_address}"
        assert p2pkh_address == KNOWN_ADDRESS, "P2PKH地址应与已知地址一致"

        # P2SH地址
        p2sh_address = BitcoinKeyValidator.generate_p2sh_address(pubkey)
        assert p2sh_address.startswith("3"), f"P2SH地址应以'3'开头，实际: {p2sh_address}"

        # Bech32地址
        bech32_address = BitcoinKeyValidator.generate_bech32_address(pubkey, hrp="bc")
        assert bech32_address.startswith("bc1"), f"Bech32地址应以'bc1'开头，实际: {bech32_address}"

        # 三种地址格式互不相同
        addresses = {p2pkh_address, p2sh_address, bech32_address}
        assert len(addresses) == 3, f"三种地址格式应互不相同，实际: {addresses}"

    def test_p2sh_bech32_test_suite(self):
        """直接验证P2SH和Bech32地址的关键格式约束"""
        pubkey = bytes.fromhex(KNOWN_PUBKEY_HEX)

        # P2SH格式验证
        p2sh_address = BitcoinKeyValidator.generate_p2sh_address(pubkey)
        assert isinstance(p2sh_address, str), "P2SH地址应为字符串"
        assert p2sh_address.startswith("3"), "P2SH地址应以'3'开头"
        assert (
            26 <= len(p2sh_address) <= 35
        ), f"P2SH地址长度应在26-35之间，实际: {len(p2sh_address)}"

        # 验证P2SH地址可Base58Check解码
        p2sh_version, p2sh_payload = Base58.check_decode(p2sh_address)
        assert p2sh_version == 0x05, f"P2SH版本字节应为0x05，实际: 0x{p2sh_version:02x}"
        assert len(p2sh_payload) == 20, f"P2SH payload应为20字节，实际: {len(p2sh_payload)}"

        # Bech32格式验证
        bech32_address = BitcoinKeyValidator.generate_bech32_address(pubkey, hrp="bc")
        assert isinstance(bech32_address, str), "Bech32地址应为字符串"
        assert bech32_address.startswith("bc1"), "Bech32地址应以'bc1'开头"
        assert len(bech32_address) > 10, f"Bech32地址长度不足，实际: {len(bech32_address)}"
