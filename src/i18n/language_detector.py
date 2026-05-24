"""Language detection utilities."""
import locale
import os


class LanguageDetector:
    """Detects system language for i18n."""

    @staticmethod
    def detect() -> str:
        """Detect system language.

        Returns:
            Language code (e.g. 'en', 'zh')

        """
        lang, _ = locale.getdefaultlocale()
        if lang:
            return lang.split("_")[0]
        return os.environ.get("LANG", "en")[:2]
