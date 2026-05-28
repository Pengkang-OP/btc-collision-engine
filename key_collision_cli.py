#!/usr/bin/env python3
"""比特币私钥对撞工具 - 统一命令行入口.

此为项目的**唯一根级 CLI 入口**。逻辑委托至 src/cli/main.py。
安装后也可通过 `btc-collision` 命令直接调用。

用法:
    python key_collision_cli.py --help
    python key_collision_cli.py -t <地址> -m random
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF
"""

import os
import sys

# 确保项目根目录在路径中（必须在 src 导入之前执行）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.main import main  # 架构必要：sys.path.insert 后立即导入

if __name__ == "__main__":
    main()
