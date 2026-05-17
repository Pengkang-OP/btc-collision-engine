#!/usr/bin/env python3
"""
配置加载与验证模块

提供配置文件的加载、解析和基本验证功能。
"""

import json
import os
import sys
from pathlib import Path

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


from src.i18n import _t  # noqa: E402
from src.utils import get_configured_logger  # noqa: E402

logger = get_configured_logger("CLI")


def load_config_with_validation(config_file: str | None = None) -> dict | None:
    """
    加载并验证配置文件

    参数:
        config_file: 可选的配置文件路径，若为 None 则使用项目根目录的 config.json
    返回:
        配置字典，如果加载失败则返回None
    """
    if config_file:
        config_path = os.path.abspath(config_file)
        # 安全: 检测路径遍历，防止读取项目目录外的敏感文件
        # 使用pathlib进行严格的路径验证
        try:
            # W12修复: 使用 os.path.realpath 解析符号链接（兼容 Python 3.12/3.13）
            # Python 3.13+ 的 Path.resolve(follow_symlinks=True) 等效于 os.path.realpath
            config_path_obj = Path(os.path.realpath(config_path))
            project_root_obj = Path(os.path.realpath(_project_root))
            # 使用relative_to检查路径是否在项目目录内
            config_path_obj.relative_to(project_root_obj)
        except ValueError:
            # ValueError表示路径不在项目目录内
            logger.error(f"配置文件路径超出项目目录范围，拒绝加载: {config_file}")
            return None
    else:
        config_path = os.path.join(_project_root, "config.json")

    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在: {config_path}")
        logger.info(
            "请运行: copy config.example.json config.json (Windows) 或 cp config.example.json config.json (Linux/macOS)"  # noqa: E501
        )
        return None

    # 尝试加载JSON
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        logger.info(_t("config.loaded", path=config_path))

        # 基本验证
        if not isinstance(config, dict):
            logger.error(_t("config.invalid", error="根节点必须是JSON对象"))
            return None

        return config

    except json.JSONDecodeError as e:
        logger.error(_t("config.invalid", error=str(e)))
        logger.error(f"位置: 行{e.lineno}, 列{e.colno}")
        logger.error("请检查config.json语法，或从config.example.json重新复制")
        return None
    except UnicodeDecodeError as e:
        logger.error(_t("errors.io_error", detail=str(e)))
        logger.error("请确保配置文件使用UTF-8编码")
        return None
    except PermissionError as e:  # noqa: F841
        logger.error(_t("errors.permission_denied", path=config_path))
        logger.error("请检查文件读取权限")
        return None
    except Exception as e:
        logger.error(_t("errors.unexpected", error=str(e)))
        return None
