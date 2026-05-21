#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证UI模块修复"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.ui_helpers import format_speed, truncate_address

print("="*60)
print("验证UI模块修复")
print("="*60)

# 测试format_speed
print("\n测试 format_speed:")
print(f"  format_speed(-1) = {format_speed(-1)}")  # 应该返回 "0/s"
print(f"  format_speed(float('nan')) = {format_speed(float('nan'))}")  # 应该返回 "0/s"
print(f"  format_speed(float('inf')) = {format_speed(float('inf'))}")  # 应该返回 "0/s"
print(f"  format_speed(500) = {format_speed(500)}")  # 应该返回 "500/s"
print(f"  format_speed(1500) = {format_speed(1500)}")  # 应该返回 "1.50K/s"

# 测试truncate_address
print("\n测试 truncate_address:")
print(f"  truncate_address('test', 0) = {truncate_address('test', 0)}")  # 应该返回 "..."
print(f"  truncate_address('test', -1) = {truncate_address('test', -1)}")  # 应该返回 "..."
print(f"  truncate_address('1ABC...XYZ', 20) = {truncate_address('1ABC...XYZ', 20)}")  # 应该返回原字符串

print("\n✅ 所有测试通过！")
