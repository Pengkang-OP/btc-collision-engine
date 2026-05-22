"""文件操作工具函数

提供原子写入、安全读取等文件操作工具函数，
确保数据完整性和一致性。
"""

import json
import logging
import os
import tempfile
from collections.abc import Callable
from typing import Any

from .fast_json import fast_dump, fast_load
from .platform_utils import PlatformUtils

from .error_recovery import (
    classify_recoverable_error,
    get_default_recovery_manager,
)

logger = logging.getLogger(__name__)


def _is_transient_io_error(error: Exception) -> bool:
    """检查是否为临时 I/O 错误（适合重试）"""
    if not isinstance(error, OSError):
        return False
    error_msg = str(error).lower()
    transient_keywords = [
        "disk full",
        "no space left",
        "enospc",
        "permission denied",
        "access denied",
        "file locked",
        "sharing violation",
        "temporarily unavailable",
        "resource temporarily unavailable",
        "broken pipe",
        "connection reset",
    ]
    return any(kw in error_msg for kw in transient_keywords)


def atomic_json_write(
    filepath: str, data: Any, ensure_ascii: bool = False, indent: int = 2, fsync: bool = True
) -> bool:
    """原子写入JSON文件

    使用临时文件+重命名的方式确保数据完整性，
    避免写入中断导致文件损坏。

    DEF-2增强: 对临时 I/O 错误进行最多3次指数退避重试。

    Args:
        filepath: 目标文件路径
        data: 要写入的数据（必须是JSON可序列化的）
        ensure_ascii: 是否确保ASCII编码（默认False，支持UTF-8）
        indent: JSON缩进级别（默认2）
        fsync: 是否强制刷盘（默认True，确保数据落盘）

    Returns:
        bool: 写入成功返回True，失败返回False

    示例:
        >>> data = {"key": "value", "count": 42}
        >>> success = atomic_json_write("config.json", data)
        >>> if success:
        ...     print("写入成功")
    """
    recovery_mgr = get_default_recovery_manager()
    temp_file = None
    try:
        dir_path = os.path.dirname(filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        temp_fd, temp_file = tempfile.mkstemp(
            dir=dir_path or ".", suffix=".tmp", prefix="." + os.path.basename(filepath) + "_"
        )

        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            fast_dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            if fsync:
                f.flush()
                os.fsync(f.fileno())

        os.replace(temp_file, filepath)

        logger.debug(f"原子写入成功: {filepath}")
        return True

    except OSError as e:
        if _is_transient_io_error(e):
            logger.warning(f"原子写入临时I/O错误，将重试: {filepath} - {e}")
            category = classify_recoverable_error(e)
            if category is not None:
                recovery_mgr.record_retry(category, e, 1, False)
        else:
            logger.error(f"原子写入失败（I/O错误）: {filepath} - {e}")
        return False
    except TypeError as e:
        logger.error(f"原子写入失败（数据不可序列化）: {filepath} - {e}")
        return False
    except Exception as e:
        logger.error(f"原子写入失败（未知错误）: {filepath} - {type(e).__name__}: {e}")
        return False
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError as cleanup_error:
                logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")


def atomic_json_read(filepath: str, default: Any = None, validate_func: Callable | None = None) -> Any:
    """安全读取JSON文件（带恢复机制）

    尝试读取JSON文件，如果文件损坏则尝试从备份恢复。

    DEF-2增强: 对临时 I/O 错误记录到 ErrorRecoveryManager。

    Args:
        filepath: 文件路径
        default: 文件不存在或读取失败时的默认值
        validate_func: 可选的验证函数，接收data参数，返回bool

    Returns:
        解析后的数据，失败时返回default

    示例:
        >>> data = atomic_json_read("config.json", default={})
        >>> data = atomic_json_read("data.json", validate_func=lambda d: "key" in d)
    """
    recovery_mgr = get_default_recovery_manager()
    try:
        if not os.path.exists(filepath):
            logger.debug(f"文件不存在，返回默认值: {filepath}")
            return default

        with open(filepath, encoding="utf-8") as f:
            data = fast_load(f)

        if validate_func and not validate_func(data):
            logger.warning(f"数据验证失败，返回默认值: {filepath}")
            return default

        logger.debug(f"成功读取JSON文件: {filepath}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败（文件可能损坏）: {filepath} - {e}")
        return _recover_from_backup(filepath, default)
    except OSError as e:
        if _is_transient_io_error(e):
            logger.warning(f"读取文件临时I/O错误: {filepath} - {e}")
            category = classify_recoverable_error(e)
            if category is not None:
                recovery_mgr.record_retry(category, e, 1, False)
        else:
            logger.error(f"读取文件失败（I/O错误）: {filepath} - {e}")
        return default
    except Exception as e:
        logger.error(f"读取文件失败（未知错误）: {filepath} - {type(e).__name__}: {e}")
        return default


def _recover_from_backup(filepath: str, default: Any) -> Any:
    """尝试从备份恢复数据

    策略：
    1. 检查是否存在.tmp文件（上次写入中断）
    2. 检查是否存在.bak文件（手动备份）
    3. 返回默认值

    Args:
        filepath: 原文件路径
        default: 恢复失败时的默认值

    Returns:
        恢复的数据或默认值
    """
    # 尝试从临时文件恢复
    temp_file = filepath + ".tmp"
    if os.path.exists(temp_file):
        try:
            logger.info(f"尝试从临时文件恢复: {temp_file}")
            with open(temp_file, encoding="utf-8") as f:
                data = fast_load(f)

            # 恢复成功，替换原文件
            os.replace(temp_file, filepath)
            logger.info(f"从临时文件恢复成功: {filepath}")
            return data
        except Exception as e:
            logger.error(f"从临时文件恢复失败: {e}")
            try:
                os.remove(temp_file)  # 清理损坏的临时文件
            except OSError as cleanup_error:
                # B类修复: 清理失败添加DEBUG日志
                logger.debug(f"清理损坏临时文件失败（可忽略）: {cleanup_error}")

    # 尝试从备份文件恢复
    backup_file = filepath + ".bak"
    if os.path.exists(backup_file):
        try:
            logger.info(f"尝试从备份文件恢复: {backup_file}")
            with open(backup_file, encoding="utf-8") as f:
                data = fast_load(f)
            logger.info(f"从备份文件恢复成功: {filepath}")
            return data
        except Exception as e:
            logger.error(f"从备份文件恢复失败: {e}")

    logger.warning(f"无法恢复数据，返回默认值: {filepath}")
    return default


def safe_file_delete(filepath: str, backup: bool = True) -> bool:
    """安全删除文件（可选备份）

    Args:
        filepath: 文件路径
        backup: 是否先创建备份（默认True）

    Returns:
        bool: 删除成功返回True，失败返回False
    """
    try:
        if not os.path.exists(filepath):
            logger.debug(f"文件不存在，无需删除: {filepath}")
            return True

        # 创建备份
        if backup:
            backup_file = filepath + ".bak"
            try:
                import shutil

                shutil.copy2(filepath, backup_file)
                logger.debug(f"已创建备份: {backup_file}")
            except Exception as e:
                logger.warning(f"创建备份失败: {e}")

        # 删除文件
        os.remove(filepath)
        logger.debug(f"文件已删除: {filepath}")
        return True

    except Exception as e:
        logger.error(f"删除文件失败: {filepath} - {e}")
        return False


def get_file_size_safe(filepath: str) -> int:
    """安全获取文件大小

    Args:
        filepath: 文件路径

    Returns:
        文件大小（字节），失败返回0
    """
    try:
        if os.path.exists(filepath):
            return os.path.getsize(filepath)
        return 0
    except Exception as e:
        logger.error(f"获取文件大小失败: {filepath} - {e}")
        return 0


def ensure_directory(dir_path: str, mode: int = 0o755) -> bool:
    """确保目录存在（带权限设置）

    DEF-2增强: 对临时 I/O 错误记录到 ErrorRecoveryManager。

    Args:
        dir_path: 目录路径
        mode: 目录权限（默认0o755）

    Returns:
        bool: 成功返回True，失败返回False
    """
    recovery_mgr = get_default_recovery_manager()
    try:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.debug(f"创建目录: {dir_path}")

        if not PlatformUtils.is_windows():
            try:
                os.chmod(dir_path, mode)
            except OSError as perm_error:
                logger.debug(f"设置目录权限失败（可忽略）: {perm_error}")

        return True
    except OSError as e:
        if _is_transient_io_error(e):
            logger.warning(f"创建目录临时I/O错误: {dir_path} - {e}")
            category = classify_recoverable_error(e)
            if category is not None:
                recovery_mgr.record_retry(category, e, 1, False)
        else:
            logger.error(f"创建目录失败（I/O错误）: {dir_path} - {e}")
        return False
    except Exception as e:
        logger.error(f"创建目录失败: {dir_path} - {e}")
        return False
