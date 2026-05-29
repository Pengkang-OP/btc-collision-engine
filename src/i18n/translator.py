"""Translation engine for multi-language support."""

import json
from pathlib import Path


class Translator:
    """Simple translation engine using JSON locale files."""

    def __init__(
        self,
        locale_dir: str | Path = "",
    ):
        """Initialize the translator."""
        self._locale_dir = Path(locale_dir or (Path(__file__).parent / "locales"))
        self._translations: dict = {}

    def load(self, lang: str) -> None:
        """Load translations for a language.

        Args:
            lang: Language code (e.g. 'en', 'zh')

        """
        filepath = self._locale_dir / f"{lang}.json"
        if filepath.exists():
            with Path(filepath).open(encoding="utf-8") as f:
                self._translations = json.load(f)

    def translate(
        self,
        key: str,
        default: str = "",
    ) -> str:
        """Translate a key.

        Args:
            key: Translation key
            default: Default text if key not found

        Returns:
            Translated text

        """
        return self._translations.get(
            key,
            default or key,
        )  # type: ignore[no-any-return]
