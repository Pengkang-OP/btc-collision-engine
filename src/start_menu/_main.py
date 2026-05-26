"""启动菜单主入口 — main() 函数和 __main__ 守卫。"""
import sys

from src.start_menu._i18n import _t
from src.start_menu._ui import (
    _run_cli,
    _show_banner,
    cleanup_menu,
    monitoring_menu,
)
from src.start_menu._utils import _wait_key


def main() -> None:
    """主入口：循环显示菜单直到退出。"""
    if sys.version_info < (3, 10):
        print("[ERROR] Python 3.10+ 是必需的，推荐 3.12，当前版本: " + sys.version)
        print("请升级 Python: https://www.python.org/downloads/")
        input("按回车键退出...")
        sys.exit(1)

    try:
        from src.utils.logging_config import _setup_security_filter
        _setup_security_filter()
    except Exception:
        pass

    while True:
        _show_banner()
        try:
            choice = input(_t("menu.enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_t('menu.goodbye')}")
            sys.exit(0)

        if not choice:
            continue

        if choice == "1":
            _run_cli(["--quick-start"], label="Quick Start wizard")
            print()
            print(_t("menu.press_any_key"))
            _wait_key()
        elif choice == "2":
            print(_t("menu.gpu_starting"))
            _run_cli(["--use-gpu"], label="GPU mode")
            print()
            print(_t("menu.press_any_key"))
            _wait_key()
        elif choice == "3":
            monitoring_menu()
        elif choice == "4":
            cleanup_menu()
        elif choice == "5":
            _run_cli(["--help"], label="Help")
            _wait_key()
        elif choice == "6":
            print(_t("menu.multi_gpu_starting"))
            _run_cli(["--multi-gpu"], label="Multi-GPU mode")
            print()
            print(_t("menu.press_any_key"))
            _wait_key()
        elif choice == "0":
            print(_t("menu.goodbye"))
            sys.exit(0)
        else:
            print(_t("menu.invalid_option", choice=choice))
            _wait_key()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{_t('menu.goodbye')}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error: {exc}")
        sys.exit(1)
