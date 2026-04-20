#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞工具 - 命令行入口

用法:
    python key_collision_cli.py --help
    python key_collision_cli.py -t <地址> -m random
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF
"""
import os
import sys

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.main import main

if __name__ == "__main__":
    main()
