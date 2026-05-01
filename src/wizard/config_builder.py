#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置构建器

负责将用户选择构建为可执行的命令。
"""

import sys
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from .interfaces import WizardResult  # noqa: E402


class ConfigBuilder:
    """配置构建器"""

    VALID_MODES = frozenset({"random", "range", "brute_force"})

    def build(self, result: WizardResult) -> List[str]:
        """构建命令行

        Args:
            result: 向导结果

        Returns:
            命令列表

        Raises:
            ValueError: 输入参数不合法时抛出
        """
        # 输入校验
        if not result.targets and not result.target_file:
            raise ValueError("No targets specified: both targets and target_file are empty")

        if result.mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid mode '{result.mode}'. Valid modes: {', '.join(sorted(self.VALID_MODES))}"
            )

        if result.mode in ("range", "brute_force") and not result.start_key:
            raise ValueError(f"Mode '{result.mode}' requires a start_key")

        if result.mode == "range" and not result.end_key:
            raise ValueError("Mode 'range' requires an end_key")

        cmd = ["python", "key_collision_cli.py"]

        if result.target_file:
            cmd.extend(["-f", result.target_file])
        elif result.targets:
            for target in result.targets:
                cmd.extend(["-t", target])

        cmd.extend(["-m", result.mode])

        if result.mode in ("range", "brute_force"):
            if result.start_key:
                cmd.extend(["--start", result.start_key])
            if result.end_key:
                cmd.extend(["--end", result.end_key])

        if result.checkpoint:
            cmd.append("--checkpoint")
        if result.dedup:
            cmd.append("--dedup")

        if result.duration > 0:
            cmd.extend(["--duration", str(result.duration)])

        if result.gpu_indices:
            if result.use_multi_gpu:
                cmd.append("--multi-gpu")
            # Always use separate args for each index (better CLI compatibility)
            for idx in result.gpu_indices:
                cmd.extend(["--gpu-indices", str(idx)])

        return cmd

    def build_summary(self, result: WizardResult) -> str:
        """构建配置摘要

        Args:
            result: 向导结果

        Returns:
            格式化的摘要字符串
        """
        lines = []
        lines.append("─" * 60)
        lines.append("  生成的命令")
        lines.append("─" * 60)
        lines.append("  " + " ".join(self.build(result)))
        lines.append("─" * 60)
        return "\n".join(lines)

    def save_command(self, result: WizardResult, filepath: str) -> bool:
        """保存命令到文件

        Args:
            result: 向导结果
            filepath: 文件路径

        Returns:
            是否保存成功
        """
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n")
                f.write("# BTC Collision Engine - 启动命令\n")
                f.write("# 生成时间: \n")
                f.write("# " + "\n# ".join(self.build(result)) + "\n")
                f.write("\n")
                f.write(" ".join(self.build(result)))
                f.write("\n")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save command to {filepath}: {e}")
            return False
