"""Entry point for ``python -m src``.

Delegates to the main CLI entry point.
"""
import sys

# ROADMAP #11: 保护 import 失败，在所有入口路径提供一致的兜底消息
try:
    from src.cli.main import main
except ImportError as _import_err:
    print(f"错误: 无法加载核心模块 — {_import_err}", file=sys.stderr)
    print("提示: 请确保已安装所有依赖 (pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
