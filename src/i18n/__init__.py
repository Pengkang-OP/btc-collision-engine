"""Internationalization (i18n) support package."""

from .translator import Translator

_translator = Translator()


def _t(key: str, default: str = "", **kwargs) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key
        default: Default text if key not found
        **kwargs: Additional arguments (ignored)

    Returns:
        Translated text
    """
    return _translator.translate(key, default)
