#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重试机制工具模块

为文件操作提供带重试的包装函数
"""

import time
from pathlib import Path
from typing import Optional


def read_with_retry(
    file_path: Path,
    max_retries: int = 3,
    delay: float = 0.1,
    encoding: str = 'utf-8'
) -> Optional[str]:
    """带重试的文件读取

    Args:
        file_path: 文件路径
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        encoding: 文件编码

    Returns:
        文件内容，失败返回None
    """
    for attempt in range(max_retries):
        try:
            return file_path.read_text(encoding=encoding, errors='ignore')
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # 指数退避
                continue
            # 最后一次重试失败
            return None


def write_with_retry(
    file_path: Path,
    content: str,
    max_retries: int = 3,
    delay: float = 0.1,
    encoding: str = 'utf-8'
) -> bool:
    """带重试的文件写入

    Args:
        file_path: 文件路径
        content: 写入内容
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        encoding: 文件编码

    Returns:
        True表示成功，False表示失败
    """
    for attempt in range(max_retries):
        try:
            file_path.write_text(content, encoding=encoding)
            return True
        except (OSError, PermissionError):
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
                continue
            return False
    return False
