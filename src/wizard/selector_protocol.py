#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选择器协议基类

为所有向导选择器定义统一的接口规范，便于测试、扩展和依赖注入。
所有选择器（TargetSelector, ModeSelector, OptionSelector, GPUSelector）
必须实现 select(compact: bool) 方法。
"""

from abc import ABC, abstractmethod
from typing import Any


class SelectorProtocol(ABC):
    """选择器抽象基类

    所有向导选择器必须继承此类并实现 select() 方法。

    使用示例:
        class MyCustomSelector(SelectorProtocol):
            def select(self, compact: bool = False) -> Any:
                # 自定义选择逻辑
                return result
    """

    @abstractmethod
    def select(self, compact: bool = False) -> Any:
        """执行选择逻辑

        Args:
            compact: 是否使用紧凑模式（跳过交互提示）

        Returns:
            选择结果，具体类型由子类定义
        """
        ...

    def is_compact_supported(self) -> bool:
        """检查是否支持紧凑模式

        子类可重写以声明是否实现了 _select_compact()。
        默认返回 True（所有标准选择器均支持紧凑模式）。
        """
        return True
