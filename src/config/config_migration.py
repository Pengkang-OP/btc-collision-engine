"""配置迁移工具 (ARCH-2修复)

提供配置文件版本检测、迁移和兼容性检查功能。
支持从旧版本配置格式自动迁移到最新格式。
"""

import json
import os
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("ConfigMigration")


# 配置版本标识: 当 DEFAULT_CONFIG 结构性变更时递增
CONFIG_VERSION_KEY = "_config_version"
CURRENT_CONFIG_VERSION = 2


class ConfigMigration:
    """配置迁移管理器"""

    @staticmethod
    def detect_config_version(config: dict[str, Any]) -> int:
        """检测配置文件版本

        Args:
            config: 配置字典

        Returns:
            配置版本号，无版本标识返回 0
        """
        return config.get(CONFIG_VERSION_KEY, 0)

    @staticmethod
    def needs_migration(config: dict[str, Any]) -> bool:
        """检查是否需要迁移

        Args:
            config: 配置字典

        Returns:
            需要迁移返回 True
        """
        return ConfigMigration.detect_config_version(config) < CURRENT_CONFIG_VERSION

    @staticmethod
    def migrate(config: dict[str, Any]) -> dict[str, Any]:
        """执行配置迁移到最新版本

        Args:
            config: 旧版本配置

        Returns:
            迁移后的配置
        """
        version = ConfigMigration.detect_config_version(config)
        migrated = dict(config)

        if version < 1:
            migrated = ConfigMigration._migrate_v0_to_v1(migrated)
        if version < 2:
            migrated = ConfigMigration._migrate_v1_to_v2(migrated)

        migrated[CONFIG_VERSION_KEY] = CURRENT_CONFIG_VERSION
        logger.info(
            f"配置已从 v{version} 迁移到 v{CURRENT_CONFIG_VERSION}: "
            f"{len(migrated)} 个配置项"
        )
        return migrated

    @staticmethod
    def _migrate_v0_to_v1(config: dict[str, Any]) -> dict[str, Any]:
        """v0 → v1: 统一 engine/collision 节，补充缺失字段"""
        result = dict(config)
        # 合并 collision → engine（如果两者都存在）
        collision = result.pop("collision", {}) or {}
        engine = result.get("engine", {})
        if collision and not engine:
            result["engine"] = collision
        elif collision and engine:
            # 合并，collision 覆盖 engine
            merged = dict(engine)
            merged.update(collision)
            result["engine"] = merged
        return result

    @staticmethod
    def _migrate_v1_to_v2(config: dict[str, Any]) -> dict[str, Any]:
        """v1 → v2: 标准化 monitoring 配置结构"""
        result = dict(config)
        monitoring = result.get("monitoring", {})
        if isinstance(monitoring, dict):
            if "storage_dir" not in monitoring:
                monitoring["storage_dir"] = "data_logs"
            if "auto_cleanup" not in monitoring:
                monitoring["auto_cleanup"] = {
                    "enabled": True,
                    "max_age_days": 30,
                }
            result["monitoring"] = monitoring
        return result


def migrate_config_file(config_path: str) -> bool:
    """迁移指定配置文件到最新版本（原地更新）

    Args:
        config_path: 配置文件路径

    Returns:
        迁移成功返回 True，无需迁移也返回 True
    """
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在，跳过迁移: {config_path}")
        return False

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        if not ConfigMigration.needs_migration(config):
            logger.debug(f"配置文件已是最新版本: {config_path}")
            return True

        migrated = ConfigMigration.migrate(config)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(migrated, f, ensure_ascii=False, indent=2)

        logger.info(f"配置文件迁移完成: {config_path}")
        return True

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"配置迁移失败: {config_path}: {e}")
        return False
