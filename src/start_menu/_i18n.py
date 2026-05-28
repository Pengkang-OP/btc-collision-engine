"""启动菜单国际化 — 翻译字典和 _t() 包装函数."""

from typing import Any

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
    from ..i18n import _t as _i18n_t
    from ..i18n import set_language
    from ..i18n.language_detector import LanguageDetector

    _lang = LanguageDetector.detect()
    set_language(_lang)
    _fallback = _FALLBACK_ZH if _lang == "zh" else _FALLBACK_EN

    def _t(key: str, **kwargs: Any) -> str:
        text = _i18n_t(key)
        if text == key and key in _fallback:
            text = _fallback[key]
        return text.format(**kwargs) if kwargs else text
except Exception:

    def _t(key: str, **kwargs: Any) -> str:
        text = _FALLBACK_ZH.get(key, key)
        return text.format(**kwargs) if kwargs else text
