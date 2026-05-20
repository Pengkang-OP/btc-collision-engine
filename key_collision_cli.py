#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞工具 - 命令行入口

用法:
    python key_collision_cli.py --help
    python key_collision_cli.py -t <地址> -m random
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF
"""
import logging
import os
import sys

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.i18n import _t
from src.cli.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + _t("cli.entry.keyboard_interrupt"))
        sys.exit(0)
    except Exception as e:
        logging.basicConfig(level=logging.CRITICAL)
        logger = logging.getLogger(__name__)
        logger.critical(_t("cli.entry.fatal_error", error=e), exc_info=True)
        print("\n" + _t("cli.entry.error_prefix", error=e) + "\n" + _t("cli.entry.check_log"), file=sys.stderr)
        sys.exit(1)