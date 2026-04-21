#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTF-8编码支持工具模块

提供Windows控制台UTF-8编码设置的统一接口，避免在多个脚本中重复相同的代码。

使用示例:
    >>> from tools.utf8_helper import setup_windows_utf8
    >>> setup_windows_utf8()
    >>> print("✅ 中文和emoji现在可以正常显示")

功能:
    - 自动检测Windows平台
    - 设置控制台代码页为UTF-8 (65001)
    - 重新包装stdout/stderr使用UTF-8编码
    - 跨平台安全（不影响Linux/Mac）

版本: 1.0.0
日期: 2026-04-21
作者: BTC Collision Engine Team
"""

from __future__ import annotations

import sys
import io
import ctypes
import logging
from typing import Optional

__version__ = "1.0.0"
__author__ = "BTC Collision Engine Team"
__date__ = "2026-04-21"


def setup_windows_utf8() -> None:
    """设置Windows控制台UTF-8编码。
    
    在Windows系统上设置控制台代码页为UTF-8 (65001)，
    并重新包装stdout/stderr使用UTF-8编码。
    
    在非Windows平台调用此函数不会有任何副作用。
    
    Raises:
        OSError: Windows API调用失败（会被捕获，不会抛出）
        AttributeError: ctypes.windll不存在（会被捕获，不会抛出）
    
    Example:
        >>> from tools.utf8_helper import setup_windows_utf8
        >>> setup_windows_utf8()
        >>> print("✅ 中文正常显示")
    """
    if sys.platform == 'win32':
        try:
            # 设置控制台代码页为UTF-8
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except (OSError, AttributeError) as e:
            # 记录debug级别日志，不影响程序运行
            logging.debug(f"Failed to set console code page: {e}")
        
        # 重新包装stdout/stderr以确保UTF-8输出
        # errors='replace' 确保无法编码的字符不会导致崩溃
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8', 
                errors='replace'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding='utf-8', 
                errors='replace'
            )
        except (AttributeError, OSError) as e:
            # stdout.buffer不存在（重定向到文件时）
            logging.debug(f"Failed to wrap stdout/stderr: {e}")


def is_utf8_setup_needed() -> bool:
    """检查是否需要设置UTF-8编码。
    
    Returns:
        bool: 如果在Windows平台且当前编码不是UTF-8，返回True。
    
    Example:
        >>> if is_utf8_setup_needed():
        ...     setup_windows_utf8()
    """
    if sys.platform != 'win32':
        return False
    
    # 检查当前stdout编码
    current_encoding = getattr(sys.stdout, 'encoding', None)
    return current_encoding is not None and current_encoding.lower() != 'utf-8'


def get_console_encoding() -> Optional[str]:
    """获取当前控制台编码。
    
    Returns:
        Optional[str]: 当前编码名称，如果无法确定则返回None。
    
    Example:
        >>> encoding = get_console_encoding()
        >>> print(f"当前编码: {encoding}")
    """
    return getattr(sys.stdout, 'encoding', None)
