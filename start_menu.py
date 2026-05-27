#!/usr/bin/env python3
"""BTC 碰撞引擎 — 启动菜单入口点（薄引导）。.

实现已拆分至 src/start_menu/ 包。
"""
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from src.start_menu import main  # noqa: E402

if __name__ == "__main__":
    main()
