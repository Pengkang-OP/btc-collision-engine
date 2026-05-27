"""启动菜单主入口 — main() 函数和 __main__ 守卫."""

from __future__ import annotations

import sys

from ._i18n import _t as _translate  # pyright: ignore[reportPrivateUsage]
from ._ui import (  # pyright: ignore[reportPrivateUsage]
    _run_cli,
    _show_banner,
    cleanup_menu,
    monitoring_menu,
)
from ._utils import _wait_key  # pyright: ignore[reportPrivateUsage]

# 将下划线私有引用包装为模块级函数的公开别名
t = _translate
wait_key = _wait_key


def main() -> None:
    """主入口：循环显示菜单直到退出."""
    if sys.version_info < (3, 12):
        print("[ERROR] Python 3.12+ 是必需的，当前版本: " + sys.version)  # pyright: ignore[reportUnreachable]
        print("请升级 Python: https://www.python.org/downloads/")
        _ = input("按回车键退出...")
        sys.exit(1)

    try:
        # pyright: ignore[reportPrivateUsage]
        from ..utils.logging_config import _setup_security_filter

        _setup_security_filter()
    except Exception:
        pass

    while True:
        _show_banner()
        try:
            choice = input(t("menu.enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{t('menu.goodbye')}")
            sys.exit(0)

        if not choice:
            continue

        if choice == "1":
            _ = _run_cli(["--quick-start"], label="Quick Start wizard")
            print()
            print(t("menu.press_any_key"))
            wait_key()
        elif choice == "2":
            print(t("menu.gpu_starting"))
            _ = _run_cli(["--use-gpu"], label="GPU mode")
            print()
            print(t("menu.press_any_key"))
            wait_key()
        elif choice == "3":
            _ = monitoring_menu()
        elif choice == "4":
            _ = cleanup_menu()
        elif choice == "5":
            _ = _run_cli(["--help"], label="Help")
            wait_key()
        elif choice == "6":
            print(t("menu.multi_gpu_starting"))
            _ = _run_cli(["--multi-gpu"], label="Multi-GPU mode")
            print()
            print(t("menu.press_any_key"))
            wait_key()
        elif choice == "0":
            print(t("menu.goodbye"))
            sys.exit(0)
        else:
            print(t("menu.invalid_option", choice=choice))
            wait_key()


def _check_python_version() -> None:  # pyright: ignore[reportUnusedFunction]
    """检查 Python 版本并在不满足时退出。"""
    print("[ERROR] Python 3.12+ 是必需的，当前版本: " + sys.version)
    print("请升级 Python: https://www.python.org/downloads/")
    _ = input("按回车键退出...")
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{t('menu.goodbye')}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error: {exc}")
        sys.exit(1)
