"""配置管理器高级功能测试 — 覆盖 _validate_manual 等方法"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.config_manager import ConfigManager  # noqa: E402


class TestConfigManagerAdvanced(unittest.TestCase):
    """ConfigManager 高级功能测试 — _validate_manual 验证逻辑"""

    def setUp(self):
        self.cm = ConfigManager()

    def test_strip_comments_removes_comment_keys(self):
        config = {
            "_comment": "这是一个注释",
            "collision": {"_comment_section": "section comment", "max_workers": 8},
            "logging": {"level": "DEBUG", "_comment_log": "log comment"},
        }
        stripped = ConfigManager._strip_comments(config)
        self.assertNotIn("_comment", stripped)
        self.assertIn("collision", stripped)
        self.assertNotIn("_comment_section", stripped["collision"])
        self.assertEqual(stripped["collision"]["max_workers"], 8)
        self.assertNotIn("_comment_log", stripped["logging"])
        self.assertEqual(stripped["logging"]["level"], "DEBUG")

    def test_strip_comments_non_dict(self):
        result = ConfigManager._strip_comments(42)
        self.assertEqual(result, 42)
        result = ConfigManager._strip_comments("hello")
        self.assertEqual(result, "hello")

    def test_is_strict_bool_true_false(self):
        self.assertTrue(ConfigManager._is_strict_bool(True))
        self.assertTrue(ConfigManager._is_strict_bool(False))

    def test_is_strict_bool_int_rejected(self):
        self.assertFalse(ConfigManager._is_strict_bool(1))
        self.assertFalse(ConfigManager._is_strict_bool(0))

    def test_is_strict_bool_none_rejected(self):
        self.assertFalse(ConfigManager._is_strict_bool(None))

    def test_is_strict_bool_string_rejected(self):
        self.assertFalse(ConfigManager._is_strict_bool("true"))

    def test_validate_empty_config(self):
        errors = self.cm._validate_manual({})
        self.assertEqual(errors, {})

    def test_validate_collision_max_workers_positive(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 4}})
        self.assertNotIn("collision.max_workers", errors)

    def test_validate_collision_max_workers_zero(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 0}})
        self.assertIn("collision.max_workers", errors)

    def test_validate_collision_max_workers_negative(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": -1}})
        self.assertIn("collision.max_workers", errors)

    def test_validate_collision_max_workers_over_limit(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 9999}})
        self.assertIn("collision.max_workers", errors)

    def test_validate_collision_progress_interval_valid(self):
        errors = self.cm._validate_manual({"collision": {"progress_interval": 100}})
        self.assertNotIn("collision.progress_interval", errors)

    def test_validate_collision_progress_interval_negative(self):
        errors = self.cm._validate_manual({"collision": {"progress_interval": -1}})
        self.assertIn("collision.progress_interval", errors)

    def test_validate_collision_checkpoint_interval_valid(self):
        errors = self.cm._validate_manual({"collision": {"checkpoint_interval": 30}})
        self.assertNotIn("collision.checkpoint_interval", errors)

    def test_validate_collision_dedup_max_size_invalid(self):
        errors = self.cm._validate_manual({"collision": {"dedup_max_size": 0}})
        self.assertIn("collision.dedup_max_size", errors)

    def test_validate_logging_level_valid(self):
        errors = self.cm._validate_manual({"logging": {"level": "DEBUG"}})
        self.assertNotIn("logging.level", errors)

    def test_validate_logging_level_invalid(self):
        errors = self.cm._validate_manual({"logging": {"level": "VERBOSE"}})
        self.assertIn("logging.level", errors)

    def test_validate_logging_format_valid(self):
        errors = self.cm._validate_manual({"logging": {"format": "%(message)s"}})
        self.assertNotIn("logging.format", errors)

    def test_validate_logging_format_invalid(self):
        errors = self.cm._validate_manual({"logging": {"format": 123}})
        self.assertIn("logging.format", errors)

    def test_validate_logging_file_valid(self):
        errors = self.cm._validate_manual({"logging": {"file": "app.log"}})
        self.assertNotIn("logging.file", errors)

    def test_validate_logging_file_invalid(self):
        errors = self.cm._validate_manual({"logging": {"file": 456}})
        self.assertIn("logging.file", errors)

    def test_validate_logging_max_bytes_valid(self):
        errors = self.cm._validate_manual({"logging": {"max_bytes": 1048576}})
        self.assertNotIn("logging.max_bytes", errors)

    def test_validate_logging_max_bytes_invalid(self):
        errors = self.cm._validate_manual({"logging": {"max_bytes": -1}})
        self.assertIn("logging.max_bytes", errors)

    def test_validate_logging_backup_count_valid(self):
        errors = self.cm._validate_manual({"logging": {"backup_count": 5}})
        self.assertNotIn("logging.backup_count", errors)

    def test_validate_logging_backup_count_negative(self):
        errors = self.cm._validate_manual({"logging": {"backup_count": -1}})
        self.assertIn("logging.backup_count", errors)

    def test_validate_logging_enable_console_bool(self):
        errors = self.cm._validate_manual({"logging": {"enable_console": True}})
        self.assertNotIn("logging.enable_console", errors)

    def test_validate_logging_enable_console_int(self):
        errors = self.cm._validate_manual({"logging": {"enable_console": 1}})
        self.assertIn("logging.enable_console", errors)

    def test_validate_logging_enable_file_bool(self):
        errors = self.cm._validate_manual({"logging": {"enable_file": False}})
        self.assertNotIn("logging.enable_file", errors)

    def test_validate_logging_enable_file_int(self):
        errors = self.cm._validate_manual({"logging": {"enable_file": 0}})
        self.assertIn("logging.enable_file", errors)

    def test_validate_logging_rotation_type_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "size"}})
        self.assertNotIn("logging.rotation_type", errors)

    def test_validate_logging_rotation_type_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "daily"}})
        self.assertIn("logging.rotation_type", errors)

    def test_validate_logging_rotation_when_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_when": "midnight"}})
        self.assertNotIn("logging.rotation_when", errors)

    def test_validate_logging_rotation_when_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_when": 12345}})
        self.assertIn("logging.rotation_when", errors)

    def test_validate_logging_rotation_interval_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_interval": 1}})
        self.assertNotIn("logging.rotation_interval", errors)

    def test_validate_logging_rotation_interval_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_interval": 0}})
        self.assertIn("logging.rotation_interval", errors)

    def test_validate_logging_compress_backups_bool(self):
        errors = self.cm._validate_manual({"logging": {"compress_backups": True}})
        self.assertNotIn("logging.compress_backups", errors)

    def test_validate_logging_compress_backups_int(self):
        errors = self.cm._validate_manual({"logging": {"compress_backups": 1}})
        self.assertIn("logging.compress_backups", errors)

    def test_validate_gpu_batch_size_valid(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 65536}})
        self.assertNotIn("gpu.batch_size", errors)

    def test_validate_gpu_batch_size_invalid(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 0}})
        self.assertIn("gpu.batch_size", errors)

    def test_validate_gpu_batch_size_over_limit(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 99999999}})
        self.assertIn("gpu.batch_size", errors)

    def test_validate_gpu_device_index_valid(self):
        errors = self.cm._validate_manual({"gpu": {"device_index": 0}})
        self.assertNotIn("gpu.device_index", errors)

    def test_validate_gpu_device_index_invalid(self):
        errors = self.cm._validate_manual({"gpu": {"device_index": "zero"}})
        self.assertIn("gpu.device_index", errors)

    def test_validate_gpu_memory_ratio_valid(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 0.5}})
        self.assertNotIn("gpu.memory_usage_ratio", errors)

    def test_validate_gpu_memory_ratio_zero(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 0}})
        self.assertIn("gpu.memory_usage_ratio", errors)

    def test_validate_gpu_memory_ratio_negative(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": -0.5}})
        self.assertIn("gpu.memory_usage_ratio", errors)

    def test_validate_gpu_memory_ratio_over_one(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 1.5}})
        self.assertIn("gpu.memory_usage_ratio", errors)

    def test_validate_gpu_use_gpu_bool(self):
        errors = self.cm._validate_manual({"gpu": {"use_gpu": True}})
        self.assertNotIn("gpu.use_gpu", errors)

    def test_validate_gpu_use_gpu_int(self):
        errors = self.cm._validate_manual({"gpu": {"use_gpu": 1}})
        self.assertIn("gpu.use_gpu", errors)

    def test_validate_gpu_auto_detect_bool(self):
        errors = self.cm._validate_manual({"gpu": {"auto_detect": False}})
        self.assertNotIn("gpu.auto_detect", errors)

    def test_validate_gpu_auto_detect_int(self):
        errors = self.cm._validate_manual({"gpu": {"auto_detect": 0}})
        self.assertIn("gpu.auto_detect", errors)

    def test_validate_gpu_vendor_opts_bool(self):
        errors = self.cm._validate_manual({"gpu": {"enable_vendor_optimizations": True}})
        self.assertNotIn("gpu.enable_vendor_optimizations", errors)

    def test_validate_perf_enabled_bool(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"enabled": True}})
        self.assertNotIn("performance_monitoring.enabled", errors)

    def test_validate_perf_enabled_int(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"enabled": 1}})
        self.assertIn("performance_monitoring.enabled", errors)

    def test_validate_perf_track_slow_bool(self):
        errors = self.cm._validate_manual(
            {"performance_monitoring": {"track_slow_operations": False}}
        )
        self.assertNotIn("performance_monitoring.track_slow_operations", errors)

    def test_validate_perf_threshold_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"slow_threshold_ms": 500}})
        self.assertNotIn("performance_monitoring.slow_threshold_ms", errors)

    def test_validate_perf_threshold_negative(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"slow_threshold_ms": -1}})
        self.assertIn("performance_monitoring.slow_threshold_ms", errors)

    def test_validate_perf_max_records_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"max_records": 1000}})
        self.assertNotIn("performance_monitoring.max_records", errors)

    def test_validate_perf_max_records_invalid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"max_records": 0}})
        self.assertIn("performance_monitoring.max_records", errors)

    def test_validate_perf_log_level_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"log_level": "WARNING"}})
        self.assertNotIn("performance_monitoring.log_level", errors)

    def test_validate_perf_log_level_invalid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"log_level": "FATAL"}})
        self.assertIn("performance_monitoring.log_level", errors)

    def test_validate_crypto_backend_valid(self):
        errors = self.cm._validate_manual({"crypto": {"backend": "coincurve"}})
        self.assertNotIn("crypto.backend", errors)

    def test_validate_crypto_backend_invalid(self):
        errors = self.cm._validate_manual({"crypto": {"backend": "bitcoinj"}})
        self.assertIn("crypto.backend", errors)

    def test_validate_crypto_constant_time_bool(self):
        errors = self.cm._validate_manual({"crypto": {"constant_time": True}})
        self.assertNotIn("crypto.constant_time", errors)

    def test_validate_crypto_constant_time_int(self):
        errors = self.cm._validate_manual({"crypto": {"constant_time": 0}})
        self.assertIn("crypto.constant_time", errors)

    def test_validate_crypto_verify_checksums_bool(self):
        errors = self.cm._validate_manual({"crypto": {"verify_checksums": False}})
        self.assertNotIn("crypto.verify_checksums", errors)

    def test_validate_crypto_verify_checksums_int(self):
        errors = self.cm._validate_manual({"crypto": {"verify_checksums": 1}})
        self.assertIn("crypto.verify_checksums", errors)

    def test_validate_crypto_strict_wif_bool(self):
        errors = self.cm._validate_manual({"crypto": {"strict_wif_validation": False}})
        self.assertNotIn("crypto.strict_wif_validation", errors)

    def test_validate_crypto_strict_wif_int(self):
        errors = self.cm._validate_manual({"crypto": {"strict_wif_validation": 1}})
        self.assertIn("crypto.strict_wif_validation", errors)

    def test_validate_size_rotation_needs_max_bytes(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "size"}})
        self.assertIn("logging.max_bytes", errors)

    def test_validate_time_rotation_needs_rotation_when(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "time"}})
        self.assertIn("logging.rotation_when", errors)


class TestConfigManagerLifecycle(unittest.TestCase):
    """ConfigManager 生命周期测试"""

    def setUp(self):
        self.cm = ConfigManager()

    def test_init_no_file_uses_defaults(self):
        cm = ConfigManager()
        self.assertIsNone(cm.config_file)
        self.assertEqual(cm.get("collision.progress_interval"), 1000)

    def test_init_with_file_that_doesnt_exist(self):
        cm = ConfigManager(config_file="/nonexistent/config.json")
        self.assertEqual(cm.get("collision.progress_interval"), 1000)

    def test_load_config_no_file(self):
        cm = ConfigManager()
        result = cm.load_config()
        self.assertFalse(result)

    def test_save_config_no_file(self):
        cm = ConfigManager()
        result = cm.save_config()
        self.assertFalse(result)

    def test_on_config_changed(self):
        called = []

        def callback():
            called.append(1)

        self.cm.on_config_changed(callback)
        self.cm._notify_change_callbacks()
        self.assertEqual(len(called), 1)

    def test_on_config_changed_multiple(self):
        results = []

        def cb1():
            results.append(1)

        def cb2():
            results.append(2)

        self.cm.on_config_changed(cb1)
        self.cm.on_config_changed(cb2)
        self.cm._notify_change_callbacks()
        self.assertEqual(results, [1, 2])

    def test_on_config_changed_exception_doesnt_block(self):
        results = []

        def bad_cb():
            raise RuntimeError("test error")

        def good_cb():
            results.append(1)

        self.cm.on_config_changed(bad_cb)
        self.cm.on_config_changed(good_cb)
        self.cm._notify_change_callbacks()
        self.assertEqual(results, [1])

    def test_reload_config_no_file(self):
        cm = ConfigManager()
        result = cm.reload_config()
        self.assertFalse(result)

    def test_start_watching_no_file(self):
        cm = ConfigManager()
        result = cm.start_watching()
        self.assertFalse(result)

    def test_stop_watching_no_watcher(self):
        cm = ConfigManager()
        cm.stop_watching()

    def test_get_nonexistent_key(self):
        result = self.cm.get("nonexistent.key")
        self.assertIsNone(result)

    def test_get_with_default(self):
        result = self.cm.get("nonexistent.key", "default_value")
        self.assertEqual(result, "default_value")

    def test_get_partial_path(self):
        result = self.cm.get("collision.nonexistent", 42)
        self.assertEqual(result, 42)

    def test_set_and_get(self):
        self.cm.set("collision.max_workers", 16)
        self.assertEqual(self.cm.get("collision.max_workers"), 16)

    def test_set_nested_key(self):
        self.cm.set("custom.section.key", "value")
        self.assertEqual(self.cm.get("custom.section.key"), "value")

    def test_validate_with_schema_valid(self):
        config = {"collision": {"max_workers": 8}}
        errors = self.cm.validate(config)
        self.assertEqual(errors, {})

    def test_validate_with_schema_invalid_type(self):
        config = {"collision": {"max_workers": "not_a_number"}}
        errors = self.cm.validate(config)
        self.assertTrue(len(errors) > 0)

    def test_validate_no_config_uses_current(self):
        errors = self.cm.validate()
        self.assertEqual(errors, {})


class TestConfigManagerWithTempFile(unittest.TestCase):
    """ConfigManager 文件操作测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmpfile = os.path.join(self.tmpdir, "test_config.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_roundtrip(self):
        with open(self.tmpfile, "w") as f:
            json.dump({"collision": {"max_workers": 32}}, f)

        cm = ConfigManager(config_file=self.tmpfile)
        cm.load_config()
        self.assertEqual(cm.get("collision.max_workers"), 32)

    def test_save_config_to_file(self):
        cm = ConfigManager(config_file=self.tmpfile)
        cm.set("collision.max_workers", 64)
        result = cm.save_config()
        self.assertTrue(result)

        cm2 = ConfigManager(config_file=self.tmpfile)
        cm2.load_config()
        self.assertEqual(cm2.get("collision.max_workers"), 64)

    def test_load_config_with_comments(self):
        config_with_comments = {
            "_comment": "top level comment",
            "collision": {"_comment_section": "section", "max_workers": 16},
        }
        with open(self.tmpfile, "w") as f:
            json.dump(config_with_comments, f)

        cm = ConfigManager(config_file=self.tmpfile)
        result = cm.load_config()
        self.assertTrue(result)
        self.assertEqual(cm.get("collision.max_workers"), 16)

    def test_reload_config_file(self):
        with open(self.tmpfile, "w") as f:
            json.dump({"collision": {"max_workers": 8}}, f)

        cm = ConfigManager(config_file=self.tmpfile)
        cm.load_config()
        self.assertEqual(cm.get("collision.max_workers"), 8)

        with open(self.tmpfile, "w") as f:
            json.dump({"collision": {"max_workers": 16}}, f)

        result = cm.reload_config()
        self.assertTrue(result)
        self.assertEqual(cm.get("collision.max_workers"), 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
