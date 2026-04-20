#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI工具函数模块

提供GUI界面常用的工具函数，包括时间格式化、文本处理等。
"""

from datetime import datetime
from typing import Optional


def format_timestamp(timestamp: str, format_str: str = "%m-%d %H:%M") -> Optional[str]:
    """
    格式化时间戳字符串
    
    Args:
        timestamp: ISO格式的时间戳字符串
        format_str: 输出格式字符串，默认为 "%m-%d %H:%M"
        
    Returns:
        格式化后的时间字符串，如果解析失败返回None
    """
    if not timestamp:
        return None
    
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime(format_str)
    except (ValueError, TypeError):
        return None


def format_mode_name(mode: str) -> str:
    """
    将引擎模式名称转换为中文显示
    
    Args:
        mode: 引擎模式名称（random/range/brute_force/gpu）
        
    Returns:
        中文模式名称
    """
    mode_map = {
        "random": "随机",
        "range": "范围",
        "brute_force": "穷举",
        "gpu": "GPU"
    }
    return mode_map.get(mode, mode)


def format_number_with_commas(number: int) -> str:
    """
    格式化数字，添加千位分隔符
    
    Args:
        number: 要格式化的数字
        
    Returns:
        格式化后的数字字符串
    """
    return f"{number:,}"
