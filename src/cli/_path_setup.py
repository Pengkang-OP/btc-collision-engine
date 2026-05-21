"""项目路径初始化模块

在 CLI 入口文件加载前确保项目根目录在 sys.path 中，
使 `from src.xxx` 绝对导入正常工作。

用法::

    from ._path_setup import ensure_project_root
    ensure_project_root()

v4.5.1: 抽取共享函数替代 5 个 CLI 文件中的重复 `sys.path.insert` 代码。
"""

import os
import sys


def _get_project_root() -> str:
    """返回本模块所在的项目根目录（src 的父目录）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_project_root: str = _get_project_root()
_initialized: bool = False


def ensure_project_root() -> None:
    """确保项目根目录在 sys.path 中（幂等）"""
    global _initialized
    if _initialized:
        return
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    _initialized = True
