"""国际化(i18n)支持模块。

提供多语言翻译功能，支持中英文切换。
通过设置环境变量 BTC_LANGUAGE 可覆盖自动检测的语言。

使用示例::

    from src.i18n import _t, set_language

    # 切换到中文
    set_language("zh_CN")

    # 翻译字符串
    msg = _t("common.success")
    msg_with_args = _t("errors.file_not_found", path="/tmp/file.txt")
"""

from .translator import Translator
from .language_detector import detect_system_language

# ------------------------------------------------------------------
# 全局翻译器实例（使用系统语言自动初始化）
# ------------------------------------------------------------------

_translator = Translator(language=detect_system_language())


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------


def _t(key: str, **kwargs) -> str:
    """
    翻译快捷函数。

    Args:
        key: 点分隔的翻译键，如 "cli.help.description"。
        **kwargs: 字符串格式化参数。

    Returns:
        翻译后的字符串。
    """
    return _translator.translate(key, **kwargs)


def set_language(lang: str) -> None:
    """
    设置当前语言。

    Args:
        lang: 语言代码，如 'zh_CN' 或 'en_US'。
    """
    _translator.set_language(lang)


def get_language() -> str:
    """
    获取当前语言代码。

    Returns:
        当前语言代码字符串。
    """
    return _translator.current_language


def get_supported_languages() -> list:
    """
    获取支持的语言列表。

    Returns:
        语言代码列表，如 ['zh_CN', 'en_US']。
    """
    return _translator.get_supported_languages()


__all__ = [
    "_t",
    "set_language",
    "get_language",
    "get_supported_languages",
    "Translator",
    "_translator",
]
