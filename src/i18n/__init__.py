"""Internationalization (i18n) support package."""

import locale
import os
import threading

from .translator import Translator

_translator = Translator()
_lang_loaded = False
_load_lock = threading.Lock()


def _auto_load_language() -> None:
    """Auto-detect system language and load translations."""
    global _lang_loaded
    if _lang_loaded:
        return
    with _load_lock:
        if _lang_loaded:
            return
        _lang_loaded = True

    # Priority: LANG env > system locale
    lang_env = os.environ.get("LANG", os.environ.get("LC_ALL", ""))
    if lang_env.lower().startswith("zh"):
        _translator.load("zh")
        return

    try:
        sys_locale = locale.getdefaultlocale()[0] or ""
        if sys_locale.lower().startswith("zh"):
            _translator.load("zh")
            return
    except (ValueError, locale.Error):
        pass

    # Default: try zh, fall back to empty
    _translator.load("zh")


def _t(key: str, default: str = "", **kwargs) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key
        default: Default text if key not found
        **kwargs: Format arguments for the translation string

    Returns:
        Translated text

    """
    _auto_load_language()
    text = _translator.translate(key, default)
    if kwargs and text:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def set_language(lang: str) -> None:
    """Set the active language for translations.

    Args:
        lang: Language code (e.g. 'en', 'zh')

    """
    _translator.load(lang)
