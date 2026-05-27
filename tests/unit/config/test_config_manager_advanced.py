"""配置管理器高级功能测试 — 覆盖 _validate_manual 等方法."""

import json
import os
import pathlib
import tempfile
import unittest

from src.config.config_manager import ConfigManager


class TestConfigManagerAdvanced:
    """ConfigManager 高级功能测试 — _validate_manual 验证逻辑."""

    def setup_method(self, method):
        self.cm = ConfigManager()

    def test_strip_comments_removes_comment_keys(self):
        config = {
            "_comment": "这是一个注释",
            "collision": {"_comment_section": "section comment", "max_workers": 8},
            "logging": {"level": "DEBUG", "_comment_log": "log comment"},
        }
        stripped = ConfigManager._strip_comments(config)
        assert "_comment" not in stripped
        assert "collision" in stripped
        assert "_comment_section" not in stripped["collision"]
        assert stripped["collision"]["max_workers"] == 8
        assert "_comment_log" not in stripped["logging"]
        assert stripped["logging"]["level"] == "DEBUG"

    def test_strip_comments_non_dict(self):
        result = ConfigManager._strip_comments(42)
        assert result == 42
        result = ConfigManager._strip_comments("hello")
        assert result == "hello"

    def test_is_strict_bool_true_false(self):
        assert ConfigManager._is_strict_bool(True)
        assert ConfigManager._is_strict_bool(False)

    def test_is_strict_bool_int_rejected(self):
        assert not ConfigManager._is_strict_bool(1)
        assert not ConfigManager._is_strict_bool(0)

    def test_is_strict_bool_none_rejected(self):
        assert not ConfigManager._is_strict_bool(None)

    def test_is_strict_bool_string_rejected(self):
        assert not ConfigManager._is_strict_bool("true")

    def test_validate_empty_config(self):
        errors = self.cm._validate_manual({})
        assert errors == {}

    def test_validate_collision_max_workers_positive(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 4}})
        assert "collision.max_workers" not in errors

    def test_validate_collision_max_workers_zero(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 0}})
        assert "collision.max_workers" in errors

    def test_validate_collision_max_workers_negative(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": -1}})
        assert "collision.max_workers" in errors

    def test_validate_collision_max_workers_over_limit(self):
        errors = self.cm._validate_manual({"collision": {"max_workers": 9999}})
        assert "collision.max_workers" in errors

    def test_validate_collision_progress_interval_valid(self):
        errors = self.cm._validate_manual({"collision": {"progress_interval": 100}})
        assert "collision.progress_interval" not in errors

    def test_validate_collision_progress_interval_negative(self):
        errors = self.cm._validate_manual({"collision": {"progress_interval": -1}})
        assert "collision.progress_interval" in errors

    def test_validate_collision_checkpoint_interval_valid(self):
        errors = self.cm._validate_manual({"collision": {"checkpoint_interval": 30}})
        assert "collision.checkpoint_interval" not in errors

    def test_validate_collision_dedup_max_size_invalid(self):
        errors = self.cm._validate_manual({"collision": {"dedup_max_size": 0}})
        assert "collision.dedup_max_size" in errors

    def test_validate_logging_level_valid(self):
        errors = self.cm._validate_manual({"logging": {"level": "DEBUG"}})
        assert "logging.level" not in errors

    def test_validate_logging_level_invalid(self):
        errors = self.cm._validate_manual({"logging": {"level": "VERBOSE"}})
        assert "logging.level" in errors

    def test_validate_logging_format_valid(self):
        errors = self.cm._validate_manual({"logging": {"format": "%(message)s"}})
        assert "logging.format" not in errors

    def test_validate_logging_format_invalid(self):
        errors = self.cm._validate_manual({"logging": {"format": 123}})
        assert "logging.format" in errors

    def test_validate_logging_file_valid(self):
        errors = self.cm._validate_manual({"logging": {"file": "app.log"}})
        assert "logging.file" not in errors

    def test_validate_logging_file_invalid(self):
        errors = self.cm._validate_manual({"logging": {"file": 456}})
        assert "logging.file" in errors

    def test_validate_logging_max_bytes_valid(self):
        errors = self.cm._validate_manual({"logging": {"max_bytes": 1048576}})
        assert "logging.max_bytes" not in errors

    def test_validate_logging_max_bytes_invalid(self):
        errors = self.cm._validate_manual({"logging": {"max_bytes": -1}})
        assert "logging.max_bytes" in errors

    def test_validate_logging_backup_count_valid(self):
        errors = self.cm._validate_manual({"logging": {"backup_count": 5}})
        assert "logging.backup_count" not in errors

    def test_validate_logging_backup_count_negative(self):
        errors = self.cm._validate_manual({"logging": {"backup_count": -1}})
        assert "logging.backup_count" in errors

    def test_validate_logging_enable_console_bool(self):
        errors = self.cm._validate_manual({"logging": {"enable_console": True}})
        assert "logging.enable_console" not in errors

    def test_validate_logging_enable_console_int(self):
        errors = self.cm._validate_manual({"logging": {"enable_console": 1}})
        assert "logging.enable_console" in errors

    def test_validate_logging_enable_file_bool(self):
        errors = self.cm._validate_manual({"logging": {"enable_file": False}})
        assert "logging.enable_file" not in errors

    def test_validate_logging_enable_file_int(self):
        errors = self.cm._validate_manual({"logging": {"enable_file": 0}})
        assert "logging.enable_file" in errors

    def test_validate_logging_rotation_type_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "size"}})
        assert "logging.rotation_type" not in errors

    def test_validate_logging_rotation_type_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "daily"}})
        assert "logging.rotation_type" in errors

    def test_validate_logging_rotation_when_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_when": "midnight"}})
        assert "logging.rotation_when" not in errors

    def test_validate_logging_rotation_when_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_when": 12345}})
        assert "logging.rotation_when" in errors

    def test_validate_logging_rotation_interval_valid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_interval": 1}})
        assert "logging.rotation_interval" not in errors

    def test_validate_logging_rotation_interval_invalid(self):
        errors = self.cm._validate_manual({"logging": {"rotation_interval": 0}})
        assert "logging.rotation_interval" in errors

    def test_validate_logging_compress_backups_bool(self):
        errors = self.cm._validate_manual({"logging": {"compress_backups": True}})
        assert "logging.compress_backups" not in errors

    def test_validate_logging_compress_backups_int(self):
        errors = self.cm._validate_manual({"logging": {"compress_backups": 1}})
        assert "logging.compress_backups" in errors

    def test_validate_gpu_batch_size_valid(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 65536}})
        assert "gpu.batch_size" not in errors

    def test_validate_gpu_batch_size_invalid(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 0}})
        assert "gpu.batch_size" in errors

    def test_validate_gpu_batch_size_over_limit(self):
        errors = self.cm._validate_manual({"gpu": {"batch_size": 99999999}})
        assert "gpu.batch_size" in errors

    def test_validate_gpu_device_index_valid(self):
        errors = self.cm._validate_manual({"gpu": {"device_index": 0}})
        assert "gpu.device_index" not in errors

    def test_validate_gpu_device_index_invalid(self):
        errors = self.cm._validate_manual({"gpu": {"device_index": "zero"}})
        assert "gpu.device_index" in errors

    def test_validate_gpu_memory_ratio_valid(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 0.5}})
        assert "gpu.memory_usage_ratio" not in errors

    def test_validate_gpu_memory_ratio_zero(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 0}})
        assert "gpu.memory_usage_ratio" in errors

    def test_validate_gpu_memory_ratio_negative(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": -0.5}})
        assert "gpu.memory_usage_ratio" in errors

    def test_validate_gpu_memory_ratio_over_one(self):
        errors = self.cm._validate_manual({"gpu": {"memory_usage_ratio": 1.5}})
        assert "gpu.memory_usage_ratio" in errors

    def test_validate_gpu_use_gpu_bool(self):
        errors = self.cm._validate_manual({"gpu": {"use_gpu": True}})
        assert "gpu.use_gpu" not in errors

    def test_validate_gpu_use_gpu_int(self):
        errors = self.cm._validate_manual({"gpu": {"use_gpu": 1}})
        assert "gpu.use_gpu" in errors

    def test_validate_gpu_auto_detect_bool(self):
        errors = self.cm._validate_manual({"gpu": {"auto_detect": False}})
        assert "gpu.auto_detect" not in errors

    def test_validate_gpu_auto_detect_int(self):
        errors = self.cm._validate_manual({"gpu": {"auto_detect": 0}})
        assert "gpu.auto_detect" in errors

    def test_validate_gpu_vendor_opts_bool(self):
        errors = self.cm._validate_manual({"gpu": {"enable_vendor_optimizations": True}})
        assert "gpu.enable_vendor_optimizations" not in errors

    def test_validate_perf_enabled_bool(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"enabled": True}})
        assert "performance_monitoring.enabled" not in errors

    def test_validate_perf_enabled_int(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"enabled": 1}})
        assert "performance_monitoring.enabled" in errors

    def test_validate_perf_track_slow_bool(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"track_slow_operations": False}})
        assert "performance_monitoring.track_slow_operations" not in errors

    def test_validate_perf_threshold_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"slow_threshold_ms": 500}})
        assert "performance_monitoring.slow_threshold_ms" not in errors

    def test_validate_perf_threshold_negative(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"slow_threshold_ms": -1}})
        assert "performance_monitoring.slow_threshold_ms" in errors

    def test_validate_perf_max_records_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"max_records": 1000}})
        assert "performance_monitoring.max_records" not in errors

    def test_validate_perf_max_records_invalid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"max_records": 0}})
        assert "performance_monitoring.max_records" in errors

    def test_validate_perf_log_level_valid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"log_level": "WARNING"}})
        assert "performance_monitoring.log_level" not in errors

    def test_validate_perf_log_level_invalid(self):
        errors = self.cm._validate_manual({"performance_monitoring": {"log_level": "FATAL"}})
        assert "performance_monitoring.log_level" in errors

    def test_validate_crypto_backend_valid(self):
        errors = self.cm._validate_manual({"crypto": {"backend": "coincurve"}})
        assert "crypto.backend" not in errors

    def test_validate_crypto_backend_invalid(self):
        errors = self.cm._validate_manual({"crypto": {"backend": "bitcoinj"}})
        assert "crypto.backend" in errors

    def test_validate_crypto_constant_time_bool(self):
        errors = self.cm._validate_manual({"crypto": {"constant_time": True}})
        assert "crypto.constant_time" not in errors

    def test_validate_crypto_constant_time_int(self):
        errors = self.cm._validate_manual({"crypto": {"constant_time": 0}})
        assert "crypto.constant_time" in errors

    def test_validate_crypto_verify_checksums_bool(self):
        errors = self.cm._validate_manual({"crypto": {"verify_checksums": False}})
        assert "crypto.verify_checksums" not in errors

    def test_validate_crypto_verify_checksums_int(self):
        errors = self.cm._validate_manual({"crypto": {"verify_checksums": 1}})
        assert "crypto.verify_checksums" in errors

    def test_validate_crypto_strict_wif_bool(self):
        errors = self.cm._validate_manual({"crypto": {"strict_wif_validation": False}})
        assert "crypto.strict_wif_validation" not in errors

    def test_validate_crypto_strict_wif_int(self):
        errors = self.cm._validate_manual({"crypto": {"strict_wif_validation": 1}})
        assert "crypto.strict_wif_validation" in errors

    def test_validate_size_rotation_needs_max_bytes(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "size"}})
        assert "logging.max_bytes" in errors

    def test_validate_time_rotation_needs_rotation_when(self):
        errors = self.cm._validate_manual({"logging": {"rotation_type": "time"}})
        assert "logging.rotation_when" in errors


class TestConfigManagerLifecycle:
    """ConfigManager 生命周期测试."""

    def setup_method(self, method):
        self.cm = ConfigManager()

    def test_init_no_file_uses_defaults(self):
        cm = ConfigManager()
        assert cm.config_file is None
        assert cm.get("collision.progress_interval") == 1000

    def test_init_with_file_that_doesnt_exist(self):
        cm = ConfigManager(config_file="/nonexistent/config.json")
        assert cm.get("collision.progress_interval") == 1000

    def test_load_config_no_file(self):
        cm = ConfigManager()
        result = cm.load_config()
        assert not result

    def test_save_config_no_file(self):
        cm = ConfigManager()
        result = cm.save_config()
        assert not result

    def test_on_config_changed(self):
        called = []

        def callback():
            called.append(1)

        self.cm.on_config_changed(callback)
        self.cm._notify_change_callbacks()
        assert len(called) == 1

    def test_on_config_changed_multiple(self):
        results = []

        def cb1():
            results.append(1)

        def cb2():
            results.append(2)

        self.cm.on_config_changed(cb1)
        self.cm.on_config_changed(cb2)
        self.cm._notify_change_callbacks()
        assert results == [1, 2]

    def test_on_config_changed_exception_doesnt_block(self):
        results = []

        def bad_cb():
            raise RuntimeError("test error")

        def good_cb():
            results.append(1)

        self.cm.on_config_changed(bad_cb)
        self.cm.on_config_changed(good_cb)
        self.cm._notify_change_callbacks()
        assert results == [1]

    def test_reload_config_no_file(self):
        cm = ConfigManager()
        result = cm.reload_config()
        assert not result

    def test_start_watching_no_file(self):
        cm = ConfigManager()
        result = cm.start_watching()
        assert not result

    def test_stop_watching_no_watcher(self):
        cm = ConfigManager()
        cm.stop_watching()

    def test_get_nonexistent_key(self):
        result = self.cm.get("nonexistent.key")
        assert result is None

    def test_get_with_default(self):
        result = self.cm.get("nonexistent.key", "default_value")
        assert result == "default_value"

    def test_get_partial_path(self):
        result = self.cm.get("collision.nonexistent", 42)
        assert result == 42

    def test_set_and_get(self):
        self.cm.set("collision.max_workers", 16)
        assert self.cm.get("collision.max_workers") == 16

    def test_set_nested_key(self):
        self.cm.set("custom.section.key", "value")
        assert self.cm.get("custom.section.key") == "value"

    def test_validate_with_schema_valid(self):
        config = {"collision": {"max_workers": 8}}
        errors = self.cm.validate(config)
        assert errors == {}

    def test_validate_with_schema_invalid_type(self):
        config = {"collision": {"max_workers": "not_a_number"}}
        errors = self.cm.validate(config)
        assert len(errors) > 0

    def test_validate_no_config_uses_current(self):
        errors = self.cm.validate()
        assert errors == {}


class TestConfigManagerWithTempFile:
    """ConfigManager 文件操作测试."""

    def setup_method(self, method):
        self.tmpdir = tempfile.mkdtemp()
        self.tmpfile = os.path.join(self.tmpdir, "test_config.json")

    def teardown_method(self, method):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_roundtrip(self):
        with pathlib.Path(self.tmpfile).open("w") as f:
            json.dump({"collision": {"max_workers": 32}}, f)

        cm = ConfigManager(config_file=self.tmpfile)
        cm.load_config()
        assert cm.get("collision.max_workers") == 32

    def test_save_config_to_file(self):
        cm = ConfigManager(config_file=self.tmpfile)
        cm.set("collision.max_workers", 64)
        result = cm.save_config()
        assert result

        cm2 = ConfigManager(config_file=self.tmpfile)
        cm2.load_config()
        assert cm2.get("collision.max_workers") == 64

    def test_load_config_with_comments(self):
        config_with_comments = {
            "_comment": "top level comment",
            "collision": {"_comment_section": "section", "max_workers": 16},
        }
        with pathlib.Path(self.tmpfile).open("w") as f:
            json.dump(config_with_comments, f)

        cm = ConfigManager(config_file=self.tmpfile)
        result = cm.load_config()
        assert result
        assert cm.get("collision.max_workers") == 16

    def test_reload_config_file(self):
        with pathlib.Path(self.tmpfile).open("w") as f:
            json.dump({"collision": {"max_workers": 8}}, f)

        cm = ConfigManager(config_file=self.tmpfile)
        cm.load_config()
        assert cm.get("collision.max_workers") == 8

        with pathlib.Path(self.tmpfile).open("w") as f:
            json.dump({"collision": {"max_workers": 16}}, f)

        result = cm.reload_config()
        assert result
        assert cm.get("collision.max_workers") == 16


if __name__ == "__main__":
    unittest.main(verbosity=2)
