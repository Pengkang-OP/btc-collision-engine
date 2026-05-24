"""Configuration migration utilities.

Migrates old config.json formats to the latest schema version,
automatically backing up the original file.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def migrate_config_file(config_path: str | None = None) -> bool:
    """Migrate config.json to the latest format.

    Args:
        config_path: Path to config file, defaults to 'config.json' in project root.

    Returns:
        True if migration was performed, False if already up to date.
    """
    if config_path is None:
        config_path = str(Path(__file__).parent.parent.parent / "config.json")

    src = Path(config_path)
    if not src.exists():
        logger.error("配置文件不存在: %s", src)
        print(f"[ERROR] 配置文件不存在: {src}")  # noqa: T201
        return False

    try:
        with open(src, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("无法读取配置文件: %s — %s", src, e)
        print(f"[ERROR] 配置文件读取失败: {e}")  # noqa: T201
        return False

    # Check if migration is needed (based on version or missing keys)
    version = config.get("version", "0.0.0")
    needs_migration = False

    # Add any missing sections that are required in the latest schema
    required_sections = [
        "engine",
        "collision",
        "logging",
        "monitoring",
        "gpu",
        "optimization",
        "crypto",
    ]

    for section in required_sections:
        if section not in config:
            config[section] = {}
            needs_migration = True
            logger.info("添加缺失配置节: %s", section)

    if not needs_migration:
        logger.info("配置已是最新格式 (version=%s)", version)
        print(f"[INFO] 配置文件已是最新格式 (version={version}), 无需迁移")  # noqa: T201
        return False

    # Backup original
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = src.parent / f"config.backup.{timestamp}.json"
    shutil.copy2(src, backup_path)
    logger.info("已备份原配置: %s", backup_path)
    print(f"[OK] 原配置已备份至: {backup_path}")  # noqa: T201

    # Update version
    config["version"] = "5.0.0"

    # Write migrated config
    with open(src, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info("配置迁移完成: %s", src)
    print("[完成] 配置已迁移至最新格式")  # noqa: T201
    return True
