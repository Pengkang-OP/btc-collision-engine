#!/usr/bin/env python3
"""
BTC碰撞引擎 - 引导界面模块

该模块专注于用户交互与流程引导，提供独立的交互式向导功能。

主要功能：
- 目标地址选择
- 碰撞模式选择
- 功能选项配置
- GPU设备选择
- 配置构建与执行

支持独立运行：
    python -m src.wizard

或者导入使用：
    from src.wizard import WizardEngine
    wizard = WizardEngine()
    result = wizard.run()
"""

__version__ = "1.0.0"
__author__ = "BTC Collision Engine Team"

from .events import WizardEvent
from .interfaces import WizardConfig, WizardMode, WizardResult
from .selector_protocol import SelectorProtocol
from .wizard_engine import WizardEngine

__all__ = [
    "WizardEngine",
    "WizardResult",
    "WizardConfig",
    "WizardMode",
    "WizardEvent",
    "SelectorProtocol",
]
