import sys

sys.argv = ['key_collision_cli.py', '--help']

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入arg_parser
from src.cli import arg_parser

try:
    args = arg_parser.parse_args()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
