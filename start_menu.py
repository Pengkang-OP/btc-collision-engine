#!/usr/bin/env python3
"""BTC 碰撞引擎 — 双语启动菜单。

通过现有 i18n 系统实现中/英文自动切换，替代 start.bat 中的硬编码菜单。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── 确保 src/ 在 sys.path 中以支持直接运行 ────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# ── 语言检测 ──────────────────────────────────────────────────────
_FALLBACK_ZH = {
    "menu.title": "BTC 碰撞引擎 - 启动菜单",
    "menu.system_status": "系统状态:",
    "menu.venv_found": "  虚拟环境: [OK] 已找到",
    "menu.venv_not_found": "  虚拟环境: [WARN] 未找到",
    "menu.targets_found": "  目标文件: [OK] 已找到",
    "menu.targets_not_found": "  目标文件: [WARN] 未找到",
    "menu.prompt": "请选择操作:",
    "menu.option_1": "  1. 交互式向导 (推荐)",
    "menu.option_2": "  2. GPU 模式 (单 GPU)",
    "menu.option_3": "  3. 启动监控",
    "menu.option_4": "  4. 维护和清理",
    "menu.option_5": "  5. 显示帮助",
    "menu.option_6": "  6. 多 GPU 模式",
    "menu.option_exit": "  0. 退出",
    "menu.enter_option": "输入选项 (0-6): ",
    "menu.goodbye": "[INFO] 再见!",
    "menu.invalid_option": "[错误] 无效选项: {choice}",
    "menu.press_any_key": "按任意键返回主菜单...",
    "menu.cleanup_title": "维护和清理菜单",
    "menu.cleanup_option_1": "  1. 清理日志文件",
    "menu.cleanup_option_2": "  2. 清理检查点文件",
    "menu.cleanup_option_3": "  3. 清理所有临时文件",
    "menu.cleanup_back": "  0. 返回",
    "menu.cleanup_enter_option": "输入选项 (0-3): ",
    "menu.cleanup_clearing_logs": "[INFO] 清理日志文件中...",
    "menu.cleanup_clearing_checkpoints": "[INFO] 清理检查点文件中...",
    "menu.cleanup_done": "[OK] 完成",
    "menu.cleanup_deleted": "[OK] 已删除 {count} 个文件",
    "menu.cleanup_warning": "[WARNING] 这将删除所有日志、检查点和缓存文件!",
    "menu.cleanup_confirm": "确认删除? 输入 Y 确认: ",
    "menu.cleanup_cancelled": "[INFO] 操作已取消",
    "menu.cleanup_all_done": "[OK] 所有临时文件已清理",
    "menu.monitor_title": "监控菜单",
    "menu.monitor_option_1": "  1. 基础监控 (CPU 模式)",
    "menu.monitor_option_2": "  2. GPU 监控",
    "menu.monitor_option_3": "  3. 监控 + 报告",
    "menu.monitor_back": "  0. 返回",
    "menu.monitor_enter_option": "输入选项 (0-3): ",
    "menu.monitor_not_found": "[WARN] 未找到 start_monitoring.py，监控不可用",
    "menu.monitor_starting_cpu": "[INFO] 正在启动 CPU 监控...",
    "menu.monitor_starting_gpu": "[INFO] 正在启动 GPU 监控...",
    "menu.monitor_starting_report": "[INFO] 正在启动监控+报告...",
    "menu.gpu_starting": "[INFO] 正在启动 GPU 模式...",
    "menu.multi_gpu_starting": "[INFO] 正在启动多 GPU 模式...",
}

_FALLBACK_EN = {
    "menu.title": "BTC Collision Engine - Startup Menu",
    "menu.system_status": "System Status:",
    "menu.venv_found": "  Virtual Environment: [OK] Found",
    "menu.venv_not_found": "  Virtual Environment: [WARN] Not Found",
    "menu.targets_found": "  Targets File: [OK] Found",
    "menu.targets_not_found": "  Targets File: [WARN] Not Found",
    "menu.prompt": "Please select an option:",
    "menu.option_1": "  1. Interactive Wizard (Recommended)",
    "menu.option_2": "  2. GPU Mode (Single GPU)",
    "menu.option_3": "  3. Start Monitor",
    "menu.option_4": "  4. Maintenance and Cleanup",
    "menu.option_5": "  5. Show Help",
    "menu.option_6": "  6. Multi-GPU Mode (Multiple GPUs)",
    "menu.option_exit": "  0. Exit",
    "menu.enter_option": "Enter option (0-6): ",
    "menu.goodbye": "[INFO] Goodbye!",
    "menu.invalid_option": "[Error] Invalid option: {choice}",
    "menu.press_any_key": "Press any key to return to menu...",
    "menu.cleanup_title": "Maintenance and Cleanup Menu",
    "menu.cleanup_option_1": "  1. Clear log files",
    "menu.cleanup_option_2": "  2. Clear checkpoint files",
    "menu.cleanup_option_3": "  3. Clear all temporary files",
    "menu.cleanup_back": "  0. Back",
    "menu.cleanup_enter_option": "Enter option (0-3): ",
    "menu.cleanup_clearing_logs": "[INFO] Clearing log files...",
    "menu.cleanup_clearing_checkpoints": "[INFO] Clearing checkpoint files...",
    "menu.cleanup_done": "[OK] Done",
    "menu.cleanup_deleted": "[OK] Deleted {count} file(s)",
    "menu.cleanup_warning": "[WARNING] This will delete all logs, checkpoints, and cache files!",
    "menu.cleanup_confirm": "Confirm deletion? Enter Y to confirm: ",
    "menu.cleanup_cancelled": "[INFO] Operation cancelled",
    "menu.cleanup_all_done": "[OK] All temporary files cleaned",
    "menu.monitor_title": "Monitoring Menu",
    "menu.monitor_option_1": "  1. Basic Monitoring (CPU mode)",
    "menu.monitor_option_2": "  2. GPU Monitoring",
    "menu.monitor_option_3": "  3. Monitoring with Report",
    "menu.monitor_back": "  0. Back",
    "menu.monitor_enter_option": "Enter option (0-3): ",
    "menu.monitor_not_found": "[WARN] start_monitoring.py not found, monitoring unavailable",
    "menu.monitor_starting_cpu": "[INFO] Starting CPU monitoring...",
    "menu.monitor_starting_gpu": "[INFO] Starting GPU monitoring...",
    "menu.monitor_starting_report": "[INFO] Starting monitoring with report...",
    "menu.gpu_starting": "[INFO] Starting GPU mode...",
    "menu.multi_gpu_starting": "[INFO] Starting Multi-GPU mode...",
}

try:
    from src.i18n import _t as _i18n_t
    from src.i18n import set_language
    from src.i18n.language_detector import LanguageDetector

    _lang = LanguageDetector.detect()
    set_language(_lang)

    # 包装 i18n _t: 优先用 i18n 翻译，回退到内置菜单翻译
    _fallback = _FALLBACK_ZH if _lang == "zh" else _FALLBACK_EN

    def _t(key: str, **kwargs) -> str:
        text = _i18n_t(key)
        if text == key and key in _fallback:
            text = _fallback[key]
        return text.format(**kwargs) if kwargs else text
except Exception:
    # 回退: 使用内置中文翻译
    def _t(key: str, **kwargs) -> str:  # type: ignore[misc]
        text = _FALLBACK_ZH.get(key, key)
        return text.format(**kwargs) if kwargs else text


# ── 辅助函数 ──────────────────────────────────────────────────────


def _clear_screen() -> None:
    print("\033[H\033[J", end="")


def _wait_key() -> None:
    if os.name == "nt":
        os.system("pause >nul")
    else:
        input("")


def _venv_python() -> str:
    """返回 venv 中 python.exe 的路径，若不存在返回全局 python。"""
    candidates = [
        os.path.join(_SCRIPT_DIR, "venv", "Scripts", "python.exe"),
        os.path.join(_SCRIPT_DIR, "venv", "bin", "python"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return sys.executable


# ── 清理子菜单 ────────────────────────────────────────────────────


def cleanup_menu() -> bool:
    """清理子菜单，返回 True 表示留在子菜单，False 返回主菜单。"""
    while True:
        _clear_screen()
        print()
        print("=" * 64)
        print(f"          {_t('menu.cleanup_title')}")
        print("=" * 64)
        print()
        print(_t("menu.cleanup_option_1"))
        print(_t("menu.cleanup_option_2"))
        print(_t("menu.cleanup_option_3"))
        print(_t("menu.cleanup_back"))
        print()
        print("=" * 64)
        print()

        try:
            choice = input(_t("menu.cleanup_enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not choice:
            continue

        if choice == "1":
            print(_t("menu.cleanup_clearing_logs"))
            deleted = 0
            for f in Path(_SCRIPT_DIR).rglob("*.log"):
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass
            print(_t("menu.cleanup_deleted", count=deleted))
            _wait_key()
        elif choice == "2":
            print(_t("menu.cleanup_clearing_checkpoints"))
            deleted = 0
            for f in Path(_SCRIPT_DIR).rglob("*.ckpt"):
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass
            print(_t("menu.cleanup_deleted", count=deleted))
            _wait_key()
        elif choice == "3":
            print()
            print(_t("menu.cleanup_warning"))
            print()
            try:
                confirm = input(_t("menu.cleanup_confirm")).strip().upper()
            except (EOFError, KeyboardInterrupt):
                print(_t("menu.cleanup_cancelled"))
                _wait_key()
                continue
            if confirm != "Y":
                print(_t("menu.cleanup_cancelled"))
                _wait_key()
                continue
            # 清理 log
            total_deleted = 0
            for f in Path(_SCRIPT_DIR).rglob("*.log"):
                try:
                    f.unlink()
                    total_deleted += 1
                except OSError:
                    pass
            # 清理 ckpt
            for f in Path(_SCRIPT_DIR).rglob("*.ckpt"):
                try:
                    f.unlink()
                    total_deleted += 1
                except OSError:
                    pass
            # 清理 __pycache__（先收集再删除，避免 walk 副作用）
            pycache_dirs = [p for p in Path(_SCRIPT_DIR).rglob("__pycache__") if p.is_dir()]
            for p in pycache_dirs:
                try:
                    shutil.rmtree(str(p), ignore_errors=True)
                except OSError:
                    pass
            print(_t("menu.cleanup_deleted", count=total_deleted))
            print(_t("menu.cleanup_all_done"))
            _wait_key()
        elif choice == "0":
            return False
        else:
            print(_t("menu.invalid_option", choice=choice))
            _wait_key()

    return False


# ── 主菜单 ────────────────────────────────────────────────────────


def monitoring_menu() -> bool:
    """监控子菜单，返回 True 留子菜单，False 返回主菜单。"""
    while True:
        _clear_screen()
        print()
        print("=" * 64)
        print(f"          {_t('menu.monitor_title')}")
        print("=" * 64)
        print()
        print(_t("menu.monitor_option_1"))
        print(_t("menu.monitor_option_2"))
        print(_t("menu.monitor_option_3"))
        print(_t("menu.monitor_back"))
        print()
        print("=" * 64)
        print()

        try:
            choice = input(_t("menu.monitor_enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if not choice:
            continue

        monitor_script = os.path.join(_SCRIPT_DIR, "start_monitoring.py")
        if not os.path.isfile(monitor_script):
            print(_t("menu.monitor_not_found"))
            _wait_key()
            return False

        if choice == "1":
            print(_t("menu.monitor_starting_cpu"))
            subprocess.run(
                [sys.executable, "start_monitoring.py", "--mode", "cpu"],
                cwd=_SCRIPT_DIR,
                check=False,
            )
            _wait_key()
        elif choice == "2":
            print(_t("menu.monitor_starting_gpu"))
            subprocess.run(
                [sys.executable, "start_monitoring.py", "--mode", "gpu"],
                cwd=_SCRIPT_DIR,
                check=False,
            )
            _wait_key()
        elif choice == "3":
            print(_t("menu.monitor_starting_report"))
            subprocess.run(
                [sys.executable, "start_monitoring.py", "--mode", "cpu", "--report"],
                cwd=_SCRIPT_DIR,
                check=False,
            )
            _wait_key()
        elif choice == "0":
            return False
        else:
            print(_t("menu.invalid_option", choice=choice))
            _wait_key()

    return False


def _show_banner() -> None:
    _clear_screen()
    print()
    print("=" * 64)
    print(f"          {_t('menu.title')}")
    print("=" * 64)
    print()
    print(_t("menu.system_status"))
    if os.path.isfile(os.path.join(_SCRIPT_DIR, "venv", "Scripts", "activate.bat")) or os.path.isfile(
        os.path.join(_SCRIPT_DIR, "venv", "bin", "activate")
    ):
        print(_t("menu.venv_found"))
    else:
        print(_t("menu.venv_not_found"))
    if os.path.isfile(os.path.join(_SCRIPT_DIR, "targets.txt")):
        print(_t("menu.targets_found"))
    else:
        print(_t("menu.targets_not_found"))
    print()
    print(_t("menu.prompt"))
    print()
    print(_t("menu.option_1"))
    print(_t("menu.option_2"))
    print(_t("menu.option_3"))
    print(_t("menu.option_4"))
    print(_t("menu.option_5"))
    print(_t("menu.option_6"))
    print(_t("menu.option_exit"))
    print()
    print("=" * 64)
    print()


def main() -> None:
    """主入口：循环显示菜单直到退出。"""
    # Python 版本检查 (需要 >= 3.9)
    if sys.version_info < (3, 9):
        print("[ERROR] Python 3.9+ 是必需的，当前版本: " + sys.version)
        print("请升级 Python: https://www.python.org/downloads/")
        input("按回车键退出...")
        sys.exit(1)

    # 初始化日志安全过滤器（防止私钥泄露到日志文件）
    try:
        from src.utils.logging_config import _setup_security_filter

        _setup_security_filter()
    except Exception:
        pass  # 安全过滤器初始化失败不阻止菜单运行

    python_exe = _venv_python()
    script_dir = _SCRIPT_DIR

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
            # 交互式向导
            subprocess.run(
                [python_exe, "key_collision_cli.py", "--quick-start"],
                cwd=script_dir,
                check=False,
            )
            print()
            print(_t("menu.press_any_key"))
            _wait_key()
        elif choice == "2":
            # GPU 模式 (单 GPU)
            print(_t("menu.gpu_starting"))
            subprocess.run(
                [python_exe, "key_collision_cli.py", "--use-gpu"],
                cwd=script_dir,
                check=False,
            )
            print()
            print(_t("menu.press_any_key"))
            _wait_key()
        elif choice == "3":
            # 启动监控子菜单
            monitoring_menu()
        elif choice == "4":
            cleanup_menu()
        elif choice == "5":
            # 显示帮助
            subprocess.run(
                [python_exe, "key_collision_cli.py", "--help"],
                cwd=script_dir,
                check=False,
            )
            _wait_key()
        elif choice == "6":
            # 多 GPU 模式
            print(_t("menu.multi_gpu_starting"))
            subprocess.run(
                [python_exe, "key_collision_cli.py", "--multi-gpu"],
                cwd=script_dir,
                check=False,
            )
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
    main()
