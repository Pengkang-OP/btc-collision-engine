#!/usr/bin/env python3
"""配置版本迁移 (config_migration) 单元测试

覆盖：
- detect_config_version 版本检测
- migrate_config 迁移逻辑
- backup_config 备份
- validate_migrated_config 验证
- MIGRATION_RULES 结构完整性
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_config_dir():
    """临时配置目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def v2_config():
    """v2.x 配置"""
    return {
        "crypto": {"backend": "gmpy2", "use_gpu": False},
        "collision": {"batch_size": 1000000},
        "logging": {"level": "INFO"},
    }


@pytest.fixture
def v30_config():
    """v4.2.1 配置"""
    return {
        "crypto": {"backend": "gmpy2", "use_gpu": True},
        "collision": {"batch_size": 2000000},
        "logging": {"level": "DEBUG"},
        "gpu": {"use_new_module": True},
        "monitoring": {"enabled": True},
    }


@pytest.fixture
def v31_config():
    """v4.2.1 配置"""
    return {
        "crypto": {"backend": "gmpy2", "use_gpu": True},
        "collision": {"batch_size": 2000000},
        "logging": {"level": "DEBUG"},
        "gpu": {"use_new_module": True},
        "monitoring": {"enabled": True},
        "performance_monitoring": {"enabled": False},
    }


# ============================================================================
# detect_config_version 测试
# ============================================================================


@pytest.mark.unit
class TestDetectConfigVersion:
    """版本检测测试"""

    def test_detect_v31(self, v31_config):
        from src.cli.config_migration import detect_config_version

        assert detect_config_version(v31_config) == "3.1.0"

    def test_detect_v30(self, v30_config):
        from src.cli.config_migration import detect_config_version

        assert detect_config_version(v30_config) == "3.0.0"

    def test_detect_v2x(self, v2_config):
        from src.cli.config_migration import detect_config_version

        assert detect_config_version(v2_config) == "2.x"

    def test_detect_v2x_with_extra_fields(self):
        """v2.x 可能有一些额外字段但不含 gpu+monitoring"""
        from src.cli.config_migration import detect_config_version

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gui": {},
            "engine": {},
        }
        assert detect_config_version(config) == "2.x"

    def test_unknown_empty(self):
        from src.cli.config_migration import detect_config_version

        assert detect_config_version({}) == "unknown"

    def test_unknown_non_dict(self):
        from src.cli.config_migration import detect_config_version

        assert detect_config_version("not a dict") == "unknown"
        assert detect_config_version(None) == "unknown"
        assert detect_config_version([]) == "unknown"

    def test_ignores_comment_keys(self):
        """_comment 开头的键应被忽略"""
        from src.cli.config_migration import detect_config_version

        config = {
            "_comment": "test",
            "crypto": {},
            "collision": {},
            "logging": {},
        }
        assert detect_config_version(config) == "2.x"


# ============================================================================
# migrate_config 测试
# ============================================================================


@pytest.mark.unit
class TestMigrateConfig:
    """配置迁移测试"""

    def test_migrate_v2_to_v31(self, v2_config):
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        result, changelog = migrate_config(v2_config, target_version=CONFIG_VERSION)
        assert isinstance(result, dict)
        assert isinstance(changelog, list)
        # 应包含新增的段
        assert "gpu" in result
        assert "monitoring" in result
        assert "performance_monitoring" in result
        # 保留原有字段
        assert result["crypto"]["backend"] == "gmpy2"
        # changelog 不应为空
        assert len(changelog) > 1

    def test_migrate_v30_to_v31(self, v30_config):
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        result, changelog = migrate_config(v30_config, target_version=CONFIG_VERSION)
        # 应新增 performance_monitoring
        assert "performance_monitoring" in result
        # gpu 段应有 per_device_config
        assert "per_device_config" in result["gpu"]
        # changelog 中有迁移路径信息
        assert any("3.0_to_3.1" in entry for entry in changelog)

    def test_migrate_already_v31(self, v31_config):
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        result, changelog = migrate_config(v31_config, target_version=CONFIG_VERSION)
        assert "配置已是最新版本" in changelog[-2] or any("无需迁移" in e for e in changelog)

    def test_migrate_preserves_user_values(self):
        """迁移不应覆盖用户自定义值"""
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        config = {
            "crypto": {"backend": "custom_backend", "use_gpu": False},
            "collision": {
                "batch_size": 500000,
                "use_performance_optimization": False,  # 用户已设置
            },
            "logging": {"level": "WARNING"},
        }
        result, _ = migrate_config(config, target_version=CONFIG_VERSION)
        # 用户值应保留
        assert result["collision"]["use_performance_optimization"] is False
        assert result["crypto"]["backend"] == "custom_backend"

    def test_migrate_unknown_version(self):
        """unknown 版本应尝试全部迁移规则"""
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        config = {"unknown_section": {}}
        result, changelog = migrate_config(config, target_version=CONFIG_VERSION)
        assert "无法识别版本" in str(changelog)
        # 应用了全部规则后应有新段
        assert "gpu" in result
        assert "performance_monitoring" in result

    def test_migrate_does_not_modify_original(self, v2_config):
        import copy

        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        original = copy.deepcopy(v2_config)
        result, _ = migrate_config(v2_config, target_version=CONFIG_VERSION)
        # 原始配置不应被修改
        assert v2_config == original
        # 结果应有新字段
        assert "gpu" in result

    def test_migrate_section_already_exists(self):
        """已有段不应被覆盖"""
        from src.cli.config_migration import CONFIG_VERSION, migrate_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"custom_field": "keep_me", "use_new_module": False},
        }
        result, changelog = migrate_config(config, target_version=CONFIG_VERSION)
        assert result["gpu"]["custom_field"] == "keep_me"
        assert result["gpu"]["use_new_module"] is False  # 用户值保留


# ============================================================================
# backup_config 测试
# ============================================================================


@pytest.mark.unit
class TestBackupConfig:
    """配置备份测试"""

    def test_backup_creates_file(self, temp_config_dir):
        from src.cli.config_migration import backup_config

        config_path = os.path.join(temp_config_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"test": True}, f)

        backup_path = backup_config(config_path)
        assert os.path.exists(backup_path)
        # 备份文件名应包含时间戳
        assert ".bak." in backup_path

    def test_backup_file_not_found(self):
        from src.cli.config_migration import backup_config

        with pytest.raises(FileNotFoundError):
            backup_config("nonexistent_config.json")

    def test_backup_preserves_content(self, temp_config_dir):
        from src.cli.config_migration import backup_config

        config_path = os.path.join(temp_config_dir, "config.json")
        original = {"crypto": {"key": "value"}, "logging": {"level": "DEBUG"}}
        with open(config_path, "w") as f:
            json.dump(original, f)

        backup_path = backup_config(config_path)
        with open(backup_path) as f:
            restored = json.load(f)
        assert restored == original


# ============================================================================
# validate_migrated_config 测试
# ============================================================================


@pytest.mark.unit
class TestValidateMigratedConfig:
    """配置验证测试"""

    def test_valid_v31_passes(self, v31_config):
        from src.cli.config_migration import validate_migrated_config

        is_valid, issues = validate_migrated_config(v31_config)
        assert is_valid is True
        assert len(issues) == 0

    def test_missing_required_sections(self):
        from src.cli.config_migration import validate_migrated_config

        is_valid, issues = validate_migrated_config({"crypto": {}})
        assert is_valid is False
        assert len(issues) > 0
        assert any("collision" in i for i in issues)

    def test_non_dict_root(self):
        from src.cli.config_migration import validate_migrated_config

        is_valid, issues = validate_migrated_config("not dict")
        assert is_valid is False
        assert any("JSON 对象" in i for i in issues)

    def test_crypto_type_errors(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {"backend": 123, "use_gpu": "not_bool"},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("crypto.backend" in i for i in issues)
        assert any("crypto.use_gpu" in i for i in issues)

    def test_logging_type_errors(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {"level": 123, "max_bytes": "not_int"},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("logging.level" in i for i in issues)
        assert any("logging.max_bytes" in i for i in issues)

    def test_gpu_memory_usage_ratio_bounds(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"memory_usage_ratio": 1.5},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("memory_usage_ratio" in i for i in issues)

    def test_gpu_valid_ratio_passes(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"memory_usage_ratio": 0.75},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is True

    def test_monitoring_type_errors(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {"enabled": "yes", "collection_interval": "slow"},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("monitoring.enabled" in i for i in issues)
        assert any("monitoring.collection_interval" in i for i in issues)

    def test_performance_monitoring_type_errors(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {
                "enabled": "not_bool",
                "max_records": "string",
                "slow_threshold_ms": "not_numeric",
            },
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("performance_monitoring.enabled" in i for i in issues)
        assert any("performance_monitoring.max_records" in i for i in issues)
        assert any("performance_monitoring.slow_threshold_ms" in i for i in issues)

    def test_section_not_dict(self):
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": "not_a_dict",
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("crypto 段" in i for i in issues)


# ============================================================================
# MIGRATION_RULES 测试
# ============================================================================


@pytest.mark.unit
class TestMigrationRules:
    """迁移规则结构测试"""

    def test_rules_have_expected_keys(self):
        from src.cli.config_migration import MIGRATION_RULES

        assert "2.x_to_3.0" in MIGRATION_RULES
        assert "3.0_to_3.1" in MIGRATION_RULES

    def test_rules_have_all_sections(self):
        from src.cli.config_migration import MIGRATION_RULES

        for rule_key, rule in MIGRATION_RULES.items():
            assert "add_sections" in rule
            assert "add_fields" in rule
            assert "rename_fields" in rule

    def test_2x_to_30_adds_gpu_monitoring(self):
        from src.cli.config_migration import MIGRATION_RULES

        rule = MIGRATION_RULES["2.x_to_3.0"]
        assert "gpu" in rule["add_sections"]
        assert "monitoring" in rule["add_sections"]

    def test_30_to_31_adds_performance_monitoring(self):
        from src.cli.config_migration import MIGRATION_RULES

        rule = MIGRATION_RULES["3.0_to_3.1"]
        assert "performance_monitoring" in rule["add_sections"]
        assert "per_device_config" in rule["add_fields"]["gpu"]


# ============================================================================
# migrate_config 边角场景
# ============================================================================


@pytest.mark.unit
class TestMigrateConfigEdges:
    """migrate_config 边界场景测试"""

    def test_rule_key_not_in_migration_rules(self):
        """migration_path 含不存在的规则 -> continue 跳过"""
        from src.cli.config_migration import MIGRATION_RULES, migrate_config

        config = {}
        saved = MIGRATION_RULES.copy()
        try:
            del MIGRATION_RULES["3.0_to_3.1"]
            result, changelog = migrate_config(config, target_version="3.1.0")
            assert isinstance(result, dict)
        finally:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)

    def test_rename_fields_in_migration(self):
        """rename_fields 规则 -> 字段重命名"""
        from src.cli.config_migration import MIGRATION_RULES, migrate_config

        config = {
            "crypto": {"old_field": "keep_me"},
            "collision": {},
            "logging": {},
        }
        saved = MIGRATION_RULES.copy()
        try:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)
            MIGRATION_RULES["2.x_to_3.0"]["rename_fields"] = {
                "crypto": {"old_field": "new_field"},
            }
            result, changelog = migrate_config(config, target_version="3.1.0")
            assert "new_field" in result["crypto"]
            assert result["crypto"]["new_field"] == "keep_me"
            assert "old_field" not in result["crypto"]
        finally:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)

    def test_rename_fields_section_not_in_result(self):
        """rename 目标段不存在 -> continue 跳过"""
        from src.cli.config_migration import MIGRATION_RULES, migrate_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
        }
        saved = MIGRATION_RULES.copy()
        try:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)
            MIGRATION_RULES["2.x_to_3.0"]["rename_fields"] = {
                "nonexistent_section": {"a": "b"},
            }
            result, _ = migrate_config(config, target_version="3.1.0")
            assert "nonexistent_section" not in result
        finally:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)

    def test_rename_fields_no_conflict_with_existing(self):
        """rename 目标字段已存在 -> 不覆盖"""
        from src.cli.config_migration import MIGRATION_RULES, migrate_config

        config = {
            "crypto": {"old_field": "old_val", "new_field": "existing_val"},
            "collision": {},
            "logging": {},
        }
        saved = MIGRATION_RULES.copy()
        try:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)
            MIGRATION_RULES["2.x_to_3.0"]["rename_fields"] = {
                "crypto": {"old_field": "new_field"},
            }
            result, _ = migrate_config(config, target_version="3.1.0")
            # new_field 已存在，不应被 old_field 覆盖
            assert result["crypto"]["new_field"] == "existing_val"
            assert "old_field" in result["crypto"]
        finally:
            MIGRATION_RULES.clear()
            MIGRATION_RULES.update(saved)


# ============================================================================
# migrate_config_file 测试
# ============================================================================


@pytest.mark.unit
class TestMigrateConfigFile:
    """migrate_config_file() 完整流程测试"""

    def test_file_not_found(self):
        """配置文件不存在 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=False), patch("builtins.print"):
            result = migrate_config_file("nonexistent.json")
            assert result is False

    def test_json_decode_error(self):
        """JSON 格式错误 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", side_effect=json.JSONDecodeError("bad", "{", 0)):
                with patch("builtins.print"):
                    result = migrate_config_file("bad.json")
                    assert result is False

    def test_unicode_decode_error(self):
        """文件编码错误 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")):
                with patch("builtins.print"):
                    result = migrate_config_file("bad_encoding.json")
                    assert result is False

    def test_os_error_on_read(self):
        """读取文件 OS 错误 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", side_effect=OSError("permission denied")):
                with patch("builtins.print"):
                    result = migrate_config_file("locked.json")
                    assert result is False

    def test_already_latest_version(self, v31_config):
        """v3.1 配置 -> 返回 True，无需迁移"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True):
            with patch("json.load", return_value=v31_config):
                with patch("builtins.open"):
                    with patch("builtins.print"):
                        result = migrate_config_file("latest.json")
                        assert result is True

    def test_backup_fails_os_error(self, v2_config):
        """备份失败 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True), patch("builtins.open"):
            with patch("json.load", return_value=v2_config):
                with patch(
                    "src.cli.config_migration.backup_config", side_effect=OSError("disk full")
                ):
                    with patch("builtins.print"):
                        result = migrate_config_file("config.json")
                        assert result is False

    def test_migrate_raises_exception(self, v2_config):
        """migrate_config 抛异常 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True), patch("builtins.open"):
            with patch("json.load", return_value=v2_config):
                with patch(
                    "src.cli.config_migration.backup_config", return_value="/tmp/backup.json"
                ):
                    with patch(
                        "src.cli.config_migration.migrate_config",
                        side_effect=RuntimeError("migrate crash"),
                    ):
                        with patch("builtins.print"):
                            result = migrate_config_file("config.json")
                            assert result is False

    def test_validation_fails(self, v2_config):
        """迁移后验证不通过 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        with patch.object(Path, "exists", return_value=True), patch("builtins.open"):
            with patch("json.load", return_value=v2_config):
                with patch(
                    "src.cli.config_migration.backup_config", return_value="/tmp/backup.json"
                ):
                    with patch(
                        "src.cli.config_migration.migrate_config", return_value=({}, ["changelog"])
                    ):
                        with patch(
                            "src.cli.config_migration.validate_migrated_config",
                            return_value=(False, ["缺少字段"]),
                        ):
                            with patch("builtins.print"):
                                result = migrate_config_file("config.json")
                                assert result is False

    def test_write_fails_os_error(self, v2_config):
        """写入迁移结果失败 -> 返回 False"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        mock_read = MagicMock()
        with patch.object(Path, "exists", return_value=True):
            with patch("json.load", return_value=v2_config):
                with patch(
                    "src.cli.config_migration.backup_config", return_value="/tmp/backup.json"
                ):
                    with patch(
                        "src.cli.config_migration.migrate_config",
                        return_value=(v2_config, ["changelog"]),
                    ):
                        with patch(
                            "src.cli.config_migration.validate_migrated_config",
                            return_value=(True, []),
                        ):
                            with patch(
                                "builtins.open", side_effect=[mock_read, OSError("write error")]
                            ):
                                with patch("builtins.print"):
                                    result = migrate_config_file("config.json")
                                    assert result is False

    def test_successful_migration(self, v2_config):
        """完整成功迁移流程 -> 返回 True"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        migrated = dict(v2_config)
        migrated["gpu"] = {}
        migrated["monitoring"] = {}
        migrated["performance_monitoring"] = {}

        with patch.object(Path, "exists", return_value=True):
            with patch("json.load", return_value=v2_config):
                with patch(
                    "src.cli.config_migration.backup_config", return_value="/tmp/backup.json"
                ):
                    with patch(
                        "src.cli.config_migration.migrate_config",
                        return_value=(migrated, ["迁移完成"]),
                    ):
                        with patch(
                            "src.cli.config_migration.validate_migrated_config",
                            return_value=(True, []),
                        ):
                            mock_file = MagicMock()
                            with patch("builtins.open", return_value=mock_file):
                                with patch("json.dump"):
                                    with patch("builtins.print"):
                                        result = migrate_config_file("config.json")
                                        assert result is True

    def test_unknown_version_warns(self):
        """unknown 版本 -> 打印警告但继续迁移"""
        from pathlib import Path

        from src.cli.config_migration import migrate_config_file

        config = {"unknown_section": {}}
        migrated = dict(config)
        migrated["gpu"] = {}
        migrated["monitoring"] = {}
        migrated["performance_monitoring"] = {}

        with patch.object(Path, "exists", return_value=True):
            with patch("json.load", return_value=config):
                with patch(
                    "src.cli.config_migration.backup_config", return_value="/tmp/backup.json"
                ):
                    with patch(
                        "src.cli.config_migration.migrate_config",
                        return_value=(migrated, ["迁移完成"]),
                    ):
                        with patch(
                            "src.cli.config_migration.validate_migrated_config",
                            return_value=(True, []),
                        ):
                            mock_file = MagicMock()
                            with patch("builtins.open", return_value=mock_file):
                                with patch("json.dump"):
                                    with patch("builtins.print"):
                                        result = migrate_config_file("config.json")
                                        assert result is True


# ============================================================================
# validate_migrated_config 边角
# ============================================================================


@pytest.mark.unit
class TestValidateMigratedConfigEdges:
    """validate_migrated_config 边界场景测试"""

    def test_logging_not_dict(self):
        """logging 段不是 dict"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": "not_a_dict",
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("logging 段" in i for i in issues)

    def test_gpu_not_dict(self):
        """gpu 段不是 dict"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": 123,
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("gpu 段" in i for i in issues)

    def test_monitoring_not_dict(self):
        """monitoring 段不是 dict"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": [],
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("monitoring 段" in i for i in issues)

    def test_performance_monitoring_not_dict(self):
        """performance_monitoring 段不是 dict"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "performance_monitoring": "bad_type",
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("performance_monitoring 段" in i for i in issues)

    def test_gpu_base_timeout_type_error(self):
        """gpu.base_timeout_seconds 类型错误"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"base_timeout_seconds": "not_numeric"},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("base_timeout_seconds" in i for i in issues)

    def test_gpu_memory_ratio_not_numeric(self):
        """gpu.memory_usage_ratio 非数值类型"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"memory_usage_ratio": "high"},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False
        assert any("memory_usage_ratio" in i for i in issues)

    def test_gpu_memory_ratio_negative(self):
        """memory_usage_ratio=-0.1 无效"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"memory_usage_ratio": -0.1},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is False

    def test_gpu_memory_ratio_zero_valid(self):
        """memory_usage_ratio=0.0 边界有效"""
        from src.cli.config_migration import validate_migrated_config

        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {"memory_usage_ratio": 0.0},
            "monitoring": {},
            "performance_monitoring": {},
        }
        is_valid, issues = validate_migrated_config(config)
        assert is_valid is True
