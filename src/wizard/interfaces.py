#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引导模块接口定义

定义引导界面模块的数据结构、配置和事件类型。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class WizardMode(Enum):
    """引导模式"""
    INTERACTIVE = "interactive"  # 交互式
    COMPACT = "compact"          # 紧凑模式
    AUTO = "auto"               # 自动模式（使用默认值）


@dataclass
class WizardConfig:
    """向导配置"""
    mode: WizardMode = WizardMode.INTERACTIVE
    show_intro: bool = True
    show_summary: bool = True
    validate_input: bool = True
    auto_continue: bool = False
    countdown_seconds: int = 3


@dataclass
class WizardResult:
    """引导结果数据结构"""
    success: bool = False
    targets: List[str] = field(default_factory=list)
    target_file: Optional[str] = None
    mode: str = "random"
    start_key: Optional[str] = None
    end_key: Optional[str] = None
    checkpoint: bool = True
    dedup: bool = True
    duration: int = 0
    gpu_indices: List[int] = field(default_factory=list)
    use_multi_gpu: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    command: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'targets': self.targets,
            'target_file': self.target_file,
            'mode': self.mode,
            'start_key': self.start_key,
            'end_key': self.end_key,
            'checkpoint': self.checkpoint,
            'dedup': self.dedup,
            'duration': self.duration,
            'gpu_indices': self.gpu_indices,
            'use_multi_gpu': self.use_multi_gpu,
            'config': self.config,
            'command': self.command,
            'error_message': self.error_message,
        }

    def build_command(self) -> List[str]:
        """构建命令行"""
        cmd = ["python", "key_collision_cli.py"]

        if self.target_file:
            cmd.extend(["-f", self.target_file])
        elif self.targets:
            for target in self.targets:
                cmd.extend(["-t", target])

        cmd.extend(["-m", self.mode])

        if self.mode in ("range", "brute_force"):
            if self.start_key:
                cmd.extend(["--start", self.start_key])
            if self.end_key:
                cmd.extend(["--end", self.end_key])

        if self.checkpoint:
            cmd.append("--checkpoint")
        if self.dedup:
            cmd.append("--dedup")

        if self.duration > 0:
            cmd.extend(["--duration", str(self.duration)])

        if self.use_multi_gpu and self.gpu_indices:
            cmd.append("--multi-gpu")
            cmd.extend(["--gpu-indices"] + [str(i) for i in self.gpu_indices])
        elif self.gpu_indices:
            cmd.extend(["--gpu-indices", " ".join(map(str, self.gpu_indices))])

        return cmd

    def save_to_file(self, filepath: str) -> bool:
        """保存结果到文件"""
        import json
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def load_from_file(cls, filepath: str) -> Optional['WizardResult']:
        """从文件加载结果"""
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except Exception:
            return None
