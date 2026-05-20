"""CryptoConfig 单元测试

覆盖 src/config/crypto_config.py 中未直接测试的路径：
- save() 文件写入
- load() 异常处理
- get_backend_type() 无效回退
- reset_to_defaults() / to_dict()
"""

import json
import os
import tempfile
import unittest

from src.config.crypto_config import CryptoBackendType, CryptoConfig


class TestCryptoConfig(unittest.TestCase):
    """CryptoConfig 核心方法测试"""

    def setUp(self):
        self.cfg = CryptoConfig()

    # ── save() ─────────────────────────────────────────────────

    def test_save_success(self):
        """save() 将 config 写入 JSON 文件"""
        tmpdir = tempfile.mkdtemp()
        try:
            tmpfile = os.path.join(tmpdir, "crypto.json")
            cfg = CryptoConfig(config_file=tmpfile)
            cfg.set("backend", "coincurve")
            result = cfg.save()
            self.assertTrue(result)
            with open(tmpfile, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["backend"], "coincurve")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_no_config_file(self):
        """无 config_file 时 save() 返回 False"""
        result = self.cfg.save()
        self.assertFalse(result)

    # ── load() ─────────────────────────────────────────────────

    def test_load_exception(self):
        """load() 读取无效 JSON 时捕获异常返回 False"""
        tmpdir = tempfile.mkdtemp()
        try:
            tmpfile = os.path.join(tmpdir, "bad.json")
            with open(tmpfile, "w", encoding="utf-8") as f:
                f.write("{invalid json")
            cfg = CryptoConfig(config_file=tmpfile)
            result = cfg.load()
            self.assertFalse(result)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_no_config_file(self):
        """无 config_file 时 load() 返回 False"""
        result = self.cfg.load()
        self.assertFalse(result)

    # ── get_backend_type() ─────────────────────────────────────

    def test_get_backend_type_valid(self):
        """get_backend_type() 返回有效的后端类型"""
        self.cfg.set("backend", "coincurve")
        self.assertEqual(self.cfg.get_backend_type(), CryptoBackendType.COINCURVE)

    def test_get_backend_type_invalid_fallback(self):
        """get_backend_type() 无效值时回退到 AUTO"""
        self.cfg.set("backend", "invalid_backend")
        result = self.cfg.get_backend_type()
        self.assertEqual(result, CryptoBackendType.AUTO)

    # ── reset / to_dict ────────────────────────────────────────

    def test_reset_to_defaults(self):
        """reset_to_defaults() 恢复为 DEFAULT_CONFIG"""
        self.cfg.set("backend", "coincurve")
        self.cfg.set("constant_time", True)
        self.cfg.reset_to_defaults()
        self.assertEqual(self.cfg.config, CryptoConfig.DEFAULT_CONFIG)

    def test_to_dict(self):
        """to_dict() 返回 config 副本"""
        self.cfg.set("backend", "ecdsa")
        d = self.cfg.to_dict()
        self.assertEqual(d["backend"], "ecdsa")
        self.assertIsNot(d, self.cfg.config)  # 确保是副本

    # ── set / get ──────────────────────────────────────────────

    def test_set_and_get(self):
        """set()/get() 设置和获取配置值"""
        self.cfg.set("constant_time", True)
        self.assertEqual(self.cfg.get("constant_time"), True)
        self.assertEqual(self.cfg.get("nonexistent", 42), 42)

    def test_set_backend_type(self):
        """set_backend_type() 设置后端类型"""
        result = self.cfg.set_backend_type(CryptoBackendType.ECDSA)
        self.assertTrue(result)
        self.assertEqual(self.cfg.get("backend"), "ecdsa")

    # ── validate ──────────────────────────────────────────────

    def test_validate_valid_config(self):
        """validate() 有效配置返回空列表"""
        errors = self.cfg.validate()
        self.assertEqual(errors, [])

    def test_validate_invalid_backend(self):
        """validate() 检测无效后端类型"""
        self.cfg.set("backend", "bitcoinj")
        errors = self.cfg.validate()
        self.assertIn("无效的后端类型", errors[0])

    def test_validate_non_bool_fields(self):
        """validate() 检测非布尔字段"""
        self.cfg.set("constant_time", "yes")
        errors = self.cfg.validate()
        self.assertTrue(any("constant_time" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
