#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模式选择器

负责碰撞模式的选择和配置。
"""

import sys
import os
from typing import Tuple, Optional

from .selector_protocol import SelectorProtocol

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class ModeSelector(SelectorProtocol):
    """碰撞模式选择器"""

    MODES = {
        "1": {"name": "random", "desc": "随机碰撞（推荐新手）"},
        "2": {"name": "range", "desc": "范围扫描（需要指定起始/结束私钥）"},
        "3": {"name": "brute_force", "desc": "暴力穷举（研究用途）"},
    }

    def select(self, compact: bool = False) -> Tuple[str, Optional[str], Optional[str]]:
        """选择碰撞模式

        Args:
            compact: 是否使用紧凑模式

        Returns:
            Tuple[模式名称, 起始私钥或None, 结束私钥或None]
        """
        if compact:
            return self._select_compact()

        print()
        print("─" * 60)
        print("  【步骤 2/4】 选择碰撞模式")
        print("─" * 60)
        print()
        print("    1. random    - 随机碰撞（推荐新手）")
        print("    2. range     - 范围扫描（需要指定起始/结束私钥）")
        print("    3. brute_force - 暴力穷举（研究用途）")
        print()
        print("    [?] 模式说明:")
        print("       - random: 随机生成私钥，适合未知范围的地址 (推荐新手)")
        print("       - range: 扫描指定的私钥范围，需要起始和结束值")
        print("       - brute_force: 从指定位置开始顺序搜索")
        print()

        while True:
            choice = input("    请选择 [1/2/3] (推荐: 1): ").strip()

            if choice == "":
                choice = "1"

            if choice in self.MODES:
                mode_name = self.MODES[choice]["name"]
                break
            else:
                print("    [ERROR] 无效选项，请重新选择")

        if mode_name == "random":
            return mode_name, None, None
        elif mode_name == "range":
            return self._select_range()
        elif mode_name == "brute_force":
            return self._select_brute_force()

        return mode_name, None, None

    def _select_range(self) -> Tuple[str, str, str]:
        """选择范围模式参数"""
        print()
        start_key = input("    请输入起始私钥 (十六进制): ").strip()
        end_key = input("    请输入结束私钥 (十六进制): ").strip()

        if not start_key:
            print("    [ERROR] 起始私钥不能为空")
            return self._select_range()

        if not end_key:
            print("    [ERROR] 结束私钥不能为空")
            return self._select_range()

        try:
            int(start_key, 16)
            int(end_key, 16)
        except ValueError:
            print("    [ERROR] 无效的十六进制格式")
            return self._select_range()

        return "range", start_key, end_key

    def _select_brute_force(self) -> Tuple[str, str, None]:
        """选择暴力穷举模式参数"""
        print()
        start_key = input("    请输入起始私钥 (十六进制): ").strip()

        if not start_key:
            print("    [ERROR] 起始私钥不能为空")
            return self._select_brute_force()

        try:
            int(start_key, 16)
        except ValueError:
            print("    [ERROR] 无效的十六进制格式")
            return self._select_brute_force()

        return "brute_force", start_key, None

    def _select_compact(self) -> Tuple[str, Optional[str], Optional[str]]:
        """紧凑模式选择"""
        return "random", None, None
