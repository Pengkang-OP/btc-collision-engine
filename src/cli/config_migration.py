#!/usr/bin/env python3
"""
配置版本迁移工具

支持从旧版本配置文件自动迁移到当前版本，
包含版本检测、备份、迁移和验证功能。
"""

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..i18n import _t

CONFIG_VERSION = "4.2.2"

# 必需的配置段（用于版本检测）
V3_1_REQUIRED_SECTIONS = {
    "crypto",
    "collision",
    "logging",
    "gpu",
    "monitoring",
    "performance_monitoring",
}
V3_0_REQUIRED_SECTIONS = {"crypto", "collision", "logging", "gpu", "monitoring"}
V2_SECTIONS = {"crypto", "collision", "logging"}

# 迁移规则
MIGRATION_RULES: dict[str, dict[str, Any]] = {
    "2.x_to_3.0": {
        "add_sections": {
            "gpu": {
                "use_new_module": True,
                "auto_detect": True,
                "memory_usage_ratio": 0.70,
                "enable_vendor_optimizations": True,
                "async_execution": True,
                "timeout_protection": True,
                "base_timeout_seconds": 30,
                "max_error_retries": 100,
                "mode": "auto",
                "device_indices": [-1],
                "load_balancing": "performance",
                "auto_tuning": True,
            },
            "monitoring": {
                "enabled": False,
                "collection_interval": 5,
                "storage_dir": "monitoring_data",
                "history_max_size": 1000,
                "auto_cleanup": {"enabled": True, "max_age_days": 30},
            },
        },
        "add_fields": {
            "collision": {
                "use_performance_optimization": True,
                "precomputed_window_size": 8,
                "use_simd_hash": True,
                "use_memory_pool": True,
                "use_gpu_memory_pool": True,
                "gpu_pool_max_buffers": 100,
                "gpu_pool_max_memory_mb": 512,
            }
        },
        "rename_fields": {},
    },
    "3.0_to_3.1": {
        "add_sections": {
            "performance_monitoring": {
                "enabled": True,
                "track_slow_operations": True,
                "slow_threshold_ms": 30000,
                "max_records": 10000,
            }
        },
        "add_fields": {"gpu": {"per_device_config": {}}},
        "rename_fields": {},
    },
}


def detect_config_version(config: dict) -> str:
    """
    根据存在的配置段推断配置文件版本。

    参数:
        config: 配置字典

    返回:
        版本字符串: CONFIG_VERSION (v4.x), "3.1.0", "3.0.0", "2.x" 或 "unknown"
    """
    if not isinstance(config, dict):
        return "unknown"

    keys = set(config.keys())

    # 过滤掉注释键（以 _comment 开头）
    actual_keys = {k for k in keys if not k.startswith("_comment")}

    # v4.2+: i18n 段是 v4.x 引入的新特性，用于区分 v3.1.0
    if "i18n" in actual_keys:
        return CONFIG_VERSION

    if "performance_monitoring" in actual_keys:
        return "3.1.0"

    if "gpu" in actual_keys and "monitoring" in actual_keys:
        return "3.0.0"

    # v2.x: 只有 crypto/collision/logging（可能还有 gui/engine 等老字段）
    if "crypto" in actual_keys and "collision" in actual_keys and "logging" in actual_keys:
        return "2.x"

    return "unknown"


def _build_migration_path(current_version: str, changelog: list[str]) -> list[str]:
    """根据当前版本构建迁移路径列表。"""
    if current_version == "2.x":
        return ["2.x_to_3.0", "3.0_to_3.1"]
    elif current_version == "3.0.0":
        return ["3.0_to_3.1"]
    elif current_version == "3.1.0":
        changelog.append("配置已是最新版本，无需迁移")
        return []
    else:
        changelog.append(f"无法识别版本 '{current_version}'，尝试应用全部迁移规则")
        return ["2.x_to_3.0", "3.0_to_3.1"]


def _apply_migration_rules(result: dict, migration_path: list[str], changelog: list[str]) -> None:
    """逐步应用迁移规则到配置字典。"""
    for rule_key in migration_path:
        if rule_key not in MIGRATION_RULES:
            continue

        rule = MIGRATION_RULES[rule_key]
        changelog.append(f"应用迁移规则: {rule_key}")

        # 添加整段
        for section_name, section_defaults in rule.get("add_sections", {}).items():
            if section_name not in result:
                result[section_name] = section_defaults
                changelog.append(f"  + 新增配置段: {section_name}")
            else:
                changelog.append(f"  ~ 配置段已存在，跳过: {section_name}")

        # 添加缺失字段
        for section_name, fields in rule.get("add_fields", {}).items():
            if section_name not in result:
                result[section_name] = fields
                changelog.append(f"  + 新增配置段（字段扩展）: {section_name}")
            else:
                for field_name, field_value in fields.items():
                    if field_name not in result[section_name]:
                        result[section_name][field_name] = field_value
                        changelog.append(f"  + 添加字段: {section_name}.{field_name}")
                    else:
                        changelog.append(f"  ~ 字段已存在，保留用户值: {section_name}.{field_name}")

        # 字段重命名
        for section_name, renames in rule.get("rename_fields", {}).items():
            if section_name not in result:
                continue
            for old_name, new_name in renames.items():
                if old_name in result[section_name] and new_name not in result[section_name]:
                    result[section_name][new_name] = result[section_name].pop(old_name)
                    changelog.append(f"  > 字段重命名: {section_name}.{old_name} -> {new_name}")


def migrate_config(
    config: dict,
    target_version: str = CONFIG_VERSION,
) -> tuple[dict, list[str]]:
    """
    逐步将配置从当前版本迁移到目标版本。

    仅添加不存在的字段，保留用户已有的自定义值。

    参数:
        config:         原始配置字典（不会被修改，返回深拷贝）
        target_version: 目标版本，默认为 CONFIG_VERSION

    返回:
        (迁移后配置, 变更日志列表)
    """
    import copy

    result = copy.deepcopy(config)
    changelog: list[str] = []

    current_version = detect_config_version(result)
    changelog.append(f"检测到当前配置版本: {current_version}")

    migration_path = _build_migration_path(current_version, changelog)
    if not migration_path:
        return result, changelog

    _apply_migration_rules(result, migration_path, changelog)
    changelog.append(f"迁移完成，目标版本: {target_version}")
    return result, changelog


def backup_config(config_path: str) -> str:
    """
    为配置文件创建时间戳备份。

    参数:
        config_path: 配置文件路径

    返回:
        备份文件路径字符串

    异常:
        FileNotFoundError: 源文件不存在
        OSError: 文件复制失败
    """
    source = Path(config_path)
    if not source.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    timestamp = int(time.time())
    backup_path = source.parent / f"{source.name}.bak.{timestamp}"
    shutil.copy2(str(source), str(backup_path))
    return str(backup_path)


def _check_section_is_dict(section_name: str, section: Any, issues: list[str]) -> dict | None:
    """检查配置段是否为字典类型。"""
    if not isinstance(section, dict):
        issues.append(f"配置段 {section_name} 必须是 JSON 对象，当前类型: {type(section).__name__}")
        return None
    return section


def _check_field_type(
    section: dict,
    section_name: str,
    field: str,
    expected_type: type | tuple[type, ...],
    type_desc: str,
    issues: list[str],
) -> None:
    """检查配置段中字段的类型。"""
    if field in section and not isinstance(section[field], expected_type):
        issues.append(f"{section_name}.{field} 必须是{type_desc}")


def _validate_crypto_fields(crypto: dict, issues: list[str]) -> None:
    """验证 crypto 段字段类型。"""
    _check_field_type(crypto, "crypto", "backend", str, "字符串", issues)
    _check_field_type(crypto, "crypto", "use_gpu", bool, "布尔值", issues)


def _validate_logging_fields(logging_cfg: dict, issues: list[str]) -> None:
    """验证 logging 段字段类型。"""
    _check_field_type(logging_cfg, "logging", "level", str, "字符串", issues)
    _check_field_type(logging_cfg, "logging", "max_bytes", int, "整数", issues)


def _validate_gpu_fields(gpu_cfg: dict, issues: list[str]) -> None:
    """验证 gpu 段字段类型。"""
    if "memory_usage_ratio" in gpu_cfg:
        ratio = gpu_cfg["memory_usage_ratio"]
        if not isinstance(ratio, (int, float)) or not (0.0 <= ratio <= 1.0):
            issues.append("gpu.memory_usage_ratio 必须是 0.0~1.0 之间的数值")
    _check_field_type(gpu_cfg, "gpu", "base_timeout_seconds", (int, float), "数值", issues)


def _validate_monitoring_fields(mon_cfg: dict, issues: list[str]) -> None:
    """验证 monitoring 段字段类型。"""
    _check_field_type(mon_cfg, "monitoring", "enabled", bool, "布尔值", issues)
    _check_field_type(mon_cfg, "monitoring", "collection_interval", (int, float), "数值", issues)


def _validate_perf_monitoring_fields(pm_cfg: dict, issues: list[str]) -> None:
    """验证 performance_monitoring 段字段类型。"""
    _check_field_type(pm_cfg, "performance_monitoring", "enabled", bool, "布尔值", issues)
    _check_field_type(pm_cfg, "performance_monitoring", "max_records", int, "整数", issues)
    _check_field_type(
        pm_cfg, "performance_monitoring", "slow_threshold_ms", (int, float), "数值", issues
    )


def validate_migrated_config(config: dict) -> tuple[bool, list[str]]:
    """验证迁移后的配置是否满足 v3.1 要求。

    返回:
        (是否有效, 问题列表)；问题列表为空表示验证通过
    """
    issues: list[str] = []

    if not isinstance(config, dict):
        return False, ["配置根节点不是有效的 JSON 对象"]

    for section in V3_1_REQUIRED_SECTIONS:
        if section not in config:
            issues.append(f"缺少必需配置段: {section}")

    section_rules: list[tuple[str, Callable]] = [
        ("crypto", _validate_crypto_fields),
        ("logging", _validate_logging_fields),
        ("gpu", _validate_gpu_fields),
        ("monitoring", _validate_monitoring_fields),
        ("performance_monitoring", _validate_perf_monitoring_fields),
    ]
    for section_name, validator in section_rules:
        if section_name in config:
            sec = _check_section_is_dict(section_name, config[section_name], issues)
            if sec is not None:
                validator(sec, issues)

    is_valid = len(issues) == 0
    return is_valid, issues


def migrate_config_file(config_path: str = "config.json") -> bool:
    """
    完整配置迁移流程：读取 -> 检测版本 -> 备份 -> 迁移 -> 验证 -> 写入。

    参数:
        config_path: 配置文件路径，默认为 "config.json"

    返回:
        True 表示迁移成功（或已是最新版本），False 表示迁移失败
    """
    from src.cli.constants import TAG_ERROR, TAG_OK, TAG_TIP

    print(f"\n{'=' * 60}")
    print("  " + _t("cli.migration.title") + f"  (目标版本: {CONFIG_VERSION})")
    print(f"{'=' * 60}")

    # ── 步骤 1: 读取配置文件 ────────────────────────────────────────────────
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"{TAG_ERROR} " + _t("errors.file_not_found", path=config_path))
        print(f"{TAG_TIP} " + _t("cli.migration.copy_example_tip"))
        return False

    try:
        with open(str(config_file), encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"{TAG_ERROR} " + _t("config.invalid", error=str(e)))
        return False
    except UnicodeDecodeError as e:
        print(f"{TAG_ERROR} " + _t("cli.migration.encoding_error", error=str(e)))
        return False
    except OSError as e:
        print(f"{TAG_ERROR} " + _t("errors.io_error", detail=str(e)))
        return False

    # ── 步骤 2: 检测当前版本 ────────────────────────────────────────────────
    current_version = detect_config_version(config)
    print("\n[Info] " + _t("cli.migration.current_version", version=current_version))
    print("[Info] " + _t("cli.migration.target_version", version=CONFIG_VERSION))

    if current_version == CONFIG_VERSION:
        print(f"\n{TAG_OK} " + _t("cli.migration.already_latest", version=CONFIG_VERSION))
        return True

    if current_version == "unknown":
        print("[Warn] " + _t("cli.migration.unknown_version_warn"))

    # ── 步骤 3: 备份原始配置 ────────────────────────────────────────────────
    try:
        backup_path = backup_config(config_path)
        print(f"\n{TAG_OK} " + _t("config.backup_created", path=backup_path))
    except OSError as e:
        print(f"{TAG_ERROR} " + _t("cli.migration.backup_failed", error=str(e)))
        print(f"{TAG_TIP} " + _t("cli.migration.backup_manual_tip", path=config_path))
        return False

    # ── 步骤 4: 执行迁移 ────────────────────────────────────────────────────
    try:
        migrated_config, changelog = migrate_config(config, target_version=CONFIG_VERSION)
    except Exception as e:
        print(f"{TAG_ERROR} " + _t("errors.unexpected", error=str(e)))
        return False

    print("\n[Info] " + _t("cli.migration.changelog_title") + ":")
    for entry in changelog:
        print(f"  {entry}")

    # ── 步骤 5: 验证迁移结果 ────────────────────────────────────────────────
    is_valid, issues = validate_migrated_config(migrated_config)
    if not is_valid:
        print(f"\n{TAG_ERROR} " + _t("cli.migration.validation_failed") + ":")
        for issue in issues:
            print(f"  - {issue}")
        print(f"{TAG_TIP} " + _t("cli.migration.backup_at", path=backup_path))
        return False

    # ── 步骤 6: 写入迁移结果 ────────────────────────────────────────────────
    try:
        with open(str(config_file), "w", encoding="utf-8") as f:
            json.dump(migrated_config, f, ensure_ascii=False, indent=2)
        print(f"\n{TAG_OK} " + _t("cli.migration.done", path=config_path))
        print(f"{TAG_TIP} " + _t("cli.migration.rollback_tip", path=backup_path))
    except OSError as e:
        print(f"{TAG_ERROR} " + _t("cli.migration.write_failed", error=str(e)))
        print(f"{TAG_TIP} " + _t("cli.migration.backup_at", path=backup_path))
        return False

    print(f"\n{'=' * 60}\n")
    return True
