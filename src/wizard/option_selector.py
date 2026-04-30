#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选项选择器

负责功能选项的配置。
"""

import sys
import os
from typing import Tuple

from .selector_protocol import SelectorProtocol


class OptionSelector(SelectorProtocol):
    """功能选项选择器"""

    def select(self, compact: bool = False) -> Tuple[bool, bool, int]:
        """选择功能选项

        Args:
            compact: 是否使用紧凑模式

        Returns:
            Tuple[是否启用断点续传, 是否启用去重, 运行时长(秒)]
        """
        if compact:
            return self._select_compact()

        print()
        print("─" * 60)
        print("  【步骤 3/4】 功能选项")
        print("─" * 60)
        print()
        print("    [?] 功能说明:")
        print("       - checkpoint: 保存进度，中断后可继续 (强烈推荐)")
        print("       - dedup: 避免重复检查相同的私钥 (推荐)")
        print("       - duration: 设置最大运行时间，0表示不限制")
        print()

        checkpoint = self._ask_checkpoint()
        dedup = self._ask_dedup()
        duration = self._ask_duration()

        return checkpoint, dedup, duration

    def _ask_checkpoint(self) -> bool:
        """询问是否启用断点续传"""
        while True:
            response = input("    启用断点续传? [y/n] (推荐: Y): ").strip().lower()

            if response == "":
                return True

            if response in ('y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            else:
                print("    [ERROR] 无效选项，请输入 y 或 n")

    def _ask_dedup(self) -> bool:
        """询问是否启用去重"""
        while True:
            response = input("    启用去重过滤? [y/n] (推荐: Y): ").strip().lower()

            if response == "":
                return True

            if response in ('y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            else:
                print("    [ERROR] 无效选项，请输入 y 或 n")

    def _ask_duration(self) -> int:
        """询问运行时长"""
        print()
        print("    运行时长选项:")
        print("    1. 无限（默认）")
        print("    2. 指定小时")
        print("    3. 指定天")
        print()

        while True:
            choice = input("    请选择 [1/2/3] (推荐: 1): ").strip()

            if choice == "":
                return 0

            if choice == "1":
                return 0
            elif choice == "2":
                return self._ask_hours()
            elif choice == "3":
                return self._ask_days()
            else:
                print("    [ERROR] 无效选项，请重新选择")

    def _ask_hours(self) -> int:
        """询问小时数"""
        while True:
            try:
                hours = input("    请输入小时数: ").strip()
                if not hours:
                    return 0
                h = int(hours)
                if h > 0:
                    return h * 3600
                else:
                    print("    [ERROR] 小时数必须大于0")
            except ValueError:
                print("    [ERROR] 请输入有效的数字")

    def _ask_days(self) -> int:
        """询问天数"""
        while True:
            try:
                days = input("    请输入天数: ").strip()
                if not days:
                    return 0
                d = int(days)
                if d > 0:
                    return d * 86400
                else:
                    print("    [ERROR] 天数必须大于0")
            except ValueError:
                print("    [ERROR] 请输入有效的数字")

    def _select_compact(self) -> Tuple[bool, bool, int]:
        """紧凑模式选择（使用默认值）"""
        return True, True, 0
