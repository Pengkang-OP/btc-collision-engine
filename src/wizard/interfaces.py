#!/usr/bin/env python3
"""
引导模块接口定义

定义引导界面模块的数据结构、配置和事件类型。
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WizardMode(Enum):
    """引导模式"""

    INTERACTIVE = "interactive"  # 交互式
    COMPACT = "compact"  # 紧凑模式
    AUTO = "auto"  # 自动模式（使用默认值）


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
    targets: list[str] = field(default_factory=list)
    target_file: str | None = None
    mode: str = "random"
    start_key: str | None = None
    end_key: str | None = None
    checkpoint: bool = True
    dedup: bool = True
    duration: int = 0
    gpu_indices: list[int] = field(default_factory=list)
    use_multi_gpu: bool = False
    config: dict[str, Any] = field(default_factory=dict)
    command: list[str] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "targets": self.targets,
            "target_file": self.target_file,
            "mode": self.mode,
            "start_key": self.start_key,
            "end_key": self.end_key,
            "checkpoint": self.checkpoint,
            "dedup": self.dedup,
            "duration": self.duration,
            "gpu_indices": self.gpu_indices,
            "use_multi_gpu": self.use_multi_gpu,
            "config": self.config,
            "command": self.command,
            "error_message": self.error_message,
        }

    def build_command(self) -> list[str]:
        """构建命令行

        委托 ConfigBuilder 统一构建逻辑，避免与 config_builder.py 重复实现。
        """
        from .config_builder import ConfigBuilder

        return ConfigBuilder().build(self)

    def save_to_file(self, filepath: str) -> bool:
        """保存结果到文件"""
        import json

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Failed to save wizard result to {filepath}: {e}")
            return False

    @classmethod
    def load_from_file(cls, filepath: str) -> Optional["WizardResult"]:
        """从文件加载结果"""
        import json

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to load wizard result from {filepath}: {e}")
            return None
