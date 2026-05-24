"""项目路径初始化模块

在 CLI 入口文件加载前确保项目根目录在 sys.path 中，
使 `from src.xxx` 绝对导入正常工作。

用法::

    from ._path_setup import ensure_project_root
    ensure_project_root()

v5.0.1: 使用 pip install -e . 后此模块为兼容性保留的 no-op。
"""

import os
import sys


def _get_project_root() -> str:
    """返回本模块所在的项目根目录（src 的父目录）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_project_root: str = _get_project_root()
_initialized: bool = False


def ensure_project_root() -> None:
    """确保项目根目录在 sys.path 中（幂等）。

    v5.0.1: 使用 pip install -e . 可编辑安装后，
    src 包自动在 site-packages 中可用，此函数作为 fallback 保留。
    """
    global _initialized
    if _initialized:
        return
    # 回退: 仅在可编辑安装不可用时才插入 sys.path
    try:
        from src.cli import main  # noqa: F401
    except ImportError:
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
    _initialized = True
