#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标选择器

负责目标地址的输入和验证。
"""

import sys
import os
from typing import Tuple, List, Optional, Dict, cast

from .selector_protocol import SelectorProtocol

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.collision import TargetResolver
except ImportError:
    from src.collision.targets.resolver import TargetResolver


class TargetSelector(SelectorProtocol):
    """目标地址选择器"""

    def __init__(self):
        self.resolver = TargetResolver()

    def select(self, compact: bool = False) -> Tuple[List[str], Optional[str]]:
        """选择目标地址

        Args:
            compact: 是否使用紧凑模式

        Returns:
            Tuple[目标地址列表, 目标文件路径或None]
        """
        if compact:
            return self._select_compact()

        print()
        print("─" * 60)
        print("  【步骤 1/4】 选择目标地址来源")
        print("─" * 60)
        print()
        print("    1. 单个比特币地址")
        print("    2. 从文件加载多个地址")
        print()

        while True:
            choice = input("    请选择 [1/2] (推荐: 1): ").strip()

            if choice == "":
                choice = "1"

            if choice == "1":
                return self._select_single()
            elif choice == "2":
                return self._select_from_file()
            else:
                print("    [ERROR] 无效选项，请重新选择")

    def _select_single(self) -> Tuple[List[str], None]:
        """选择单个地址"""
        print()
        print("    请输入比特币地址:", end=" ")

        address = input().strip()

        if not address:
            print("    [ERROR] 地址不能为空")
            return self._select_single()

        targets = cast(Dict[str, Optional[str]], self.resolver.resolve_multiple([address]))

        if not targets:
            print(f"    [ERROR] 无效的地址格式: {address}")
            return self._select_single()

        print("    [OK] 已加载 1 个地址")
        return list(targets), None

    def _select_from_file(self) -> Tuple[List[str], str]:
        """从文件加载地址"""
        print()
        default_file = "targets.txt"
        file_path = input(f"    请输入文件路径 (默认: {default_file}): ").strip()

        if not file_path:
            file_path = default_file

        if not os.path.exists(file_path):
            print(f"    [ERROR] 文件不存在: {file_path}")
            return self._select_from_file()

        targets = self.resolver.load_from_file(file_path)

        if not targets:
            print(f"    [ERROR] 文件中未找到有效地址: {file_path}")
            return self._select_from_file()

        print(f"    [OK] 已从文件加载 {len(targets)} 个地址")
        return list(targets), file_path

    def _select_compact(self) -> Tuple[List[str], Optional[str]]:
        """紧凑模式选择"""
        default_file = "targets.txt"

        if os.path.exists(default_file):
            targets = self.resolver.load_from_file(default_file)
            if targets:
                print(f"[OK] 已从 targets.txt 加载 {len(targets)} 个地址")
                return list(targets), default_file

        print("    请输入比特币地址:", end=" ")
        address = input().strip()

        if not address:
            print("[ERROR] 地址不能为空")
            return self._select_compact()

        targets = cast(Dict[str, Optional[str]], self.resolver.resolve_multiple([address]))

        if not targets:
            print(f"[ERROR] 无效的地址格式: {address}")
            return self._select_compact()

        return list(targets), None
