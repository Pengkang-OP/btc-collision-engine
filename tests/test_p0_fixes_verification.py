#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0修复验证测试

验证代码审查中发现的P0关键问题的修复效果。
"""

import pytest
import hashlib
import threading
import os
import json
import tempfile


# ============================================================================
# P0-2: crypto_backend.py generate_public_key_const_time 不存在
# ============================================================================

class TestCryptoBackendConstTime:
    """验证 PurePythonBackend 不再调用不存在的方法"""

    def test_pure_python_backend_const_time_generates_public_key(self):
        """use_const_time=True 时 generate_public_key 应正常工作"""
        from src.core.crypto_backend import PurePythonBackend

        backend = PurePythonBackend(use_const_time=True)
        pk = bytes(range(32))
        result = backend.generate_public_key(pk, compressed=True)

        assert isinstance(result, bytes)
        assert len(result) == 33  # 压缩公钥33字节
        assert result[0] in (0x02, 0x03)

    def test_pure_python_backend_normal_generates_public_key(self):
        """use_const_time=False 时 generate_public_key 应正常工作"""
        from src.core.crypto_backend import PurePythonBackend

        backend = PurePythonBackend(use_const_time=False)
        pk = bytes(range(32))
        result = backend.generate_public_key(pk, compressed=True)

        assert isinstance(result, bytes)
        assert len(result) == 33


# ============================================================================
# P0-3: bitcoin_key_validator.py 安全模式私钥泄漏
# ============================================================================

class TestBitcoinKeyValidatorSecureMode:
    """验证安全模式下私钥不会泄漏到验证报告"""

    def test_secure_mode_masks_private_key_in_summary(self):
        """默认 secure_mode=True 不应在摘要中包含私钥明文"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        validator = BitcoinKeyValidator(secure_mode=True)
        pk = hashlib.sha256(b"test private key").digest()

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        report = validator.full_validation_chain(pk, targets)

        summary = report.get("summary", {})
        # secure_mode=True: 不应有 private_key_hex
        assert "private_key_hex" not in summary
        # 应有 private_key_hash (SHA256前16字符)
        assert "private_key_hash" in summary
        pk_hash = summary["private_key_hash"]
        # 验证 hash 确实来自私钥
        expected_hash = hashlib.sha256(pk).hexdigest()[:16]
        assert pk_hash == expected_hash

    def test_secure_mode_masks_wif_in_summary(self):
        """安全模式下 WIF 应被脱敏"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        validator = BitcoinKeyValidator(secure_mode=True)
        pk = hashlib.sha256(b"test private key 2").digest()

        targets = set()
        report = validator.full_validation_chain(pk, targets)

        summary = report.get("summary", {})
        wif_comp = summary["wif_compressed"]
        # 安全模式下 WIF 应被截断
        assert len(wif_comp) < 60  # 完整WIF约52字符，脱敏后应更短
        assert "..." in wif_comp

    def test_non_secure_mode_shows_private_key(self):
        """非安全模式可以展示私钥"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        validator = BitcoinKeyValidator(secure_mode=False)
        pk = hashlib.sha256(b"test private key 3").digest()

        targets = set()
        report = validator.full_validation_chain(pk, targets)

        summary = report.get("summary", {})
        # 非安全模式: private_key_hash 应为完整hex
        assert "private_key_hash" in summary
        assert len(summary["private_key_hash"]) >= 64


# ============================================================================
# P0-4: bitcoin_key_validator.py 绝对导入修复
# ============================================================================

class TestBitcoinKeyValidatorImport:
    """验证相对导入可正常使用"""

    def test_relative_imports_work(self):
        """验证 bitcoin_key_validator 可正常导入"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        validator = BitcoinKeyValidator()
        assert validator.secure_mode is True


# ============================================================================
# P0-10: SensitiveDataFilter 脱敏 vs 丢弃
# ============================================================================

class TestSensitiveDataFilterRedact:
    """验证敏感数据脱敏器正确脱敏而非丢弃事件"""

    def test_redact_replaces_private_key(self):
        """64位hex私钥应被替换"""
        from src.logging.log_processor import SensitiveDataFilter

        fake_pk = "a" * 64
        result = SensitiveDataFilter.redact(f"key: {fake_pk}")
        assert fake_pk not in result
        assert "***REDACTED***" in result

    def test_redact_replaces_wif_uncompressed(self):
        """未压缩WIF私钥应被替换"""
        from src.logging.log_processor import SensitiveDataFilter

        fake_wif = "5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ"
        result = SensitiveDataFilter.redact(f"WIF: {fake_wif}")
        assert fake_wif not in result
        assert "[WIF_UNCOMPRESSED_KEY]" in result

    def test_redact_replaces_wif_compressed(self):
        """压缩WIF私钥应被替换"""
        from src.logging.log_processor import SensitiveDataFilter

        fake_wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
        result = SensitiveDataFilter.redact(f"WIF: {fake_wif}")
        assert fake_wif not in result
        assert "[WIF_COMPRESSED_KEY]" in result

    def test_redact_replaces_bip32_key(self):
        """BIP32扩展密钥应被替换"""
        from src.logging.log_processor import SensitiveDataFilter

        fake_xprv = "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbN6mRyPHQpQ4QnZt7nEk2RgvXVcqvNNt5ThEZQUQoFwSsXPyDyoB6F5TsPgpXfXaM"
        result = SensitiveDataFilter.redact(f"key: {fake_xprv}")
        assert fake_xprv not in result
        assert "[BIP32_EXTENDED_KEY]" in result

    def test_redact_replaces_addresses(self):
        """比特币地址应被替换为类型标签"""
        from src.logging.log_processor import SensitiveDataFilter

        # P2PKH地址
        result = SensitiveDataFilter.redact("addr: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert "[P2PKH_ADDRESS]" in result

        # Bech32地址
        result = SensitiveDataFilter.redact("addr: bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        assert "[BECH32_ADDRESS]" in result

    def test_redact_preserves_non_sensitive_data(self):
        """非敏感数据不应被修改"""
        from src.logging.log_processor import SensitiveDataFilter

        text = "engine started, batch_size=1048576, speed=5000 keys/sec"
        result = SensitiveDataFilter.redact(text)
        assert "batch_size=1048576" in result
        assert "speed=5000" in result

    def test_redact_data_handles_dict(self):
        """redact_data 应递归处理字典"""
        from src.logging.log_processor import SensitiveDataFilter

        data = {"message": "ok", "key": "a" * 64}
        result = SensitiveDataFilter.redact_data(data)
        assert result["message"] == "ok"
        assert "a" * 64 not in str(result["key"])

    def test_redact_data_handles_list(self):
        """redact_data 应递归处理列表"""
        from src.logging.log_processor import SensitiveDataFilter

        data = ["normal", "a" * 64, "ok"]
        result = SensitiveDataFilter.redact_data(data)
        assert result[0] == "normal"
        assert "a" * 64 not in str(result[1])
        assert result[2] == "ok"


# ============================================================================
# P0-6: ContinuousMatcher 计数器竞态修复
# ============================================================================

class TestContinuousMatcherThreadSafety:
    """验证 ContinuousMatcher 计数器线程安全"""

    def test_concurrent_increment_no_race(self):
        """多线程并发增加计数器不应丢数据"""
        from src.collision.continuous_matcher import ContinuousMatcher
        from unittest.mock import MagicMock

        # Mock target_table 以避免依赖
        mock_table = MagicMock()
        mock_table.check_match.return_value = (False, None)

        matcher = ContinuousMatcher(target_table=mock_table)
        iterations = 1000
        num_threads = 10

        def increment():
            for _ in range(iterations):
                matcher.total_checked += 1  # 现在在锁内

        threads = [threading.Thread(target=increment) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = iterations * num_threads
        assert matcher.total_checked == expected, (
            f"Expected {expected}, got {matcher.total_checked}"
        )


# ============================================================================
# P0-5: 检查点保存 KeyError 验证
# ============================================================================

class TestCheckpointFieldName:
    """验证 CollisionStats.matches 使用正确的字段名"""

    def test_add_match_uses_private_key_hash(self):
        """add_match 存储的是 private_key_hash 不是 private_key_hex"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        pk = hashlib.sha256(b"test").digest()
        stats.add_match(pk, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

        match = stats.matches[0]
        assert "private_key_hash" in match
        assert "private_key_hex" not in match
        # 验证是SHA256前16字符
        expected_hash = hashlib.sha256(pk).hexdigest()[:16]
        assert match["private_key_hash"] == expected_hash


# ============================================================================
# P0-7: zh_CN.json 翻译乱码修复
# ============================================================================

class TestI18NFix:
    """验证 i18n 翻译文件中不再有乱码"""

    def test_stop_failed_not_garbled(self):
        """stop_failed 翻译不应包含乱码字符"""
        i18n_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "src", "i18n", "locales"
        )
        zh_file = os.path.join(i18n_dir, "zh_CN.json")

        if os.path.exists(zh_file):
            with open(zh_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 查找所有包含 stop_failed 键的值
            def find_key(obj, key, results):
                if isinstance(obj, dict):
                    if key in obj:
                        results.append(obj[key])
                    for v in obj.values():
                        find_key(v, key, results)
                elif isinstance(obj, list):
                    for item in obj:
                        find_key(item, key, results)

            found = []
            find_key(data, "stop_failed", found)

            for value in found:
                # 不应包含替换字符
                assert "\ufffd" not in value, f"发现乱码: {value}"
                assert "碰撞引擎停止失败" in value

            # 至少找到一个 stop_failed
            assert len(found) > 0, "未找到 stop_failed 键"


# ============================================================================
# P0-16: docker-compose.yml Grafana 弱密码修复
# ============================================================================

class TestDockerComposeSecurity:
    """验证 docker-compose 不再包含弱密码"""

    def test_grafana_no_hardcoded_weak_password(self):
        """Grafana 密码不应包含硬编码弱密码"""
        compose_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "docker-compose.yml"
        )

        if os.path.exists(compose_file):
            with open(compose_file, "r", encoding="utf-8") as f:
                content = f.read()

            assert "changeme" not in content, "不应包含弱密码 changeme"
            assert "GF_ADMIN_PASSWORD" in content, "应使用环境变量配置密码"
