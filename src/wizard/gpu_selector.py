#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU选择器

负责GPU设备的选择和配置。
"""

import sys
import os
import time
from typing import Tuple, List

from .selector_protocol import SelectorProtocol

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class GPUSelector(SelectorProtocol):
    """GPU设备选择器"""

    def select(self, compact: bool = False) -> Tuple[List[int], bool]:
        """选择GPU设备

        Args:
            compact: 是否使用紧凑模式

        Returns:
            Tuple[GPU索引列表, 是否使用多GPU]
        """
        if compact:
            return self._select_compact()

        print()
        print("─" * 60)
        print("  【步骤 4/4】 GPU加速")
        print("─" * 60)

        gpu_info = self._detect_gpus()

        if not gpu_info:
            print()
            print("    [INFO] 未检测到GPU设备，将使用CPU模式")
            return [], False

        print()
        print("    1. CPU 模式")
        print("    2. 单GPU 加速")
        print("    3. 多GPU 加速")
        print()

        while True:
            choice = input("    请选择 [1/2/3]: ").strip()

            if choice == "":
                choice = "2"

            if choice == "1":
                return [], False
            elif choice == "2":
                return self._select_single_gpu(gpu_info)
            elif choice == "3":
                return self._select_multi_gpu(gpu_info)
            else:
                print("    [ERROR] 无效选项，请重新选择")

    def _detect_gpus(self) -> List[dict]:
        """检测可用GPU设备"""
        try:
            from src.gpu.device import GPUDeviceDetector

            devices = GPUDeviceDetector.detect_devices()
            return [{"index": i, "name": d.get("name", "Unknown")} for i, d in enumerate(devices)]
        except Exception as e:
            print(f"    [WARN] GPU检测失败: {e}")
            return []

    def _select_single_gpu(self, gpu_info: List[dict]) -> Tuple[List[int], bool]:
        """选择单个GPU"""
        print()
        print("    检测到以下 GPU 设备:")
        for i, gpu in enumerate(gpu_info):
            print(f"      {i+1}. {gpu['name']}")
        print()

        while True:
            choice = input("    请选择要使用的 GPU 设备编号: ").strip()

            if not choice:
                print("    [ERROR] 请输入有效的编号")
                continue

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(gpu_info):
                    return [idx], False
                else:
                    print("    [ERROR] 无效的编号")
            except ValueError:
                print("    [ERROR] 请输入有效的数字")

    def _select_multi_gpu(self, gpu_info: List[dict]) -> Tuple[List[int], bool]:
        """选择多个GPU"""
        print()
        print("    检测到以下 GPU 设备:")
        for i, gpu in enumerate(gpu_info):
            print(f"      {i+1}. {gpu['name']}")
        print()

        print("    请选择要使用的 GPU 设备编号（空格分隔，如 1 2，直接回车=全部）:")

        choice = input("    ").strip()

        if not choice:
            indices = list(range(len(gpu_info)))
            print(f"    [OK] 已选择所有 {len(indices)} 个 GPU")
            return indices, True

        try:
            indices = [int(x.strip()) - 1 for x in choice.split()]
            if all(0 <= i < len(gpu_info) for i in indices):
                print(f"    [OK] 已选择: {', '.join(gpu_info[i]['name'] for i in indices)}")
                return indices, True
            else:
                print("    [ERROR] 包含无效的编号")
        except ValueError:
            print("    [ERROR] 无效的输入格式")

        return self._select_multi_gpu(gpu_info)

    def _select_compact(self) -> Tuple[List[int], bool]:
        """紧凑模式选择"""
        gpu_info = self._detect_gpus()

        if not gpu_info:
            return [], False

        if len(gpu_info) > 1:
            return list(range(len(gpu_info))), True
        else:
            return [0], False
