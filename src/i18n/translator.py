"""核心翻译器模块，提供多语言翻译功能。"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认回退语言
_FALLBACK_LANGUAGE = "en_US"

# 硬编码的最小默认值（当所有语言文件均无法加载时使用）
_HARDCODED_DEFAULTS: dict[str, str] = {
    "common.error": "Error",
    "common.success": "Success",
    "common.warning": "Warning",
    "errors.unexpected": "Unexpected error: {error}",
    "errors.file_not_found": "File not found: {path}",
}


class Translator:
    """
    核心翻译器类，支持多语言切换、嵌套键访问、参数替换与回退机制。

    特性：
    - 从 locales/ 目录加载 JSON 语言文件
    - 支持嵌套键访问（如 "cli.help.description"）
    - 支持参数替换（如 _t("greeting", name="World")）
    - 当前语言缺少某键时自动回退到英文
    - 通过环境变量 BTC_LANGUAGE 覆盖语言设置
    - 线程安全（使用 threading.Lock）
    - 缓存已加载的语言文件
    """

    def __init__(self, language: str | None = None) -> None:
        """
        初始化翻译器。

        Args:
            language: 初始语言代码，如 'zh_CN'、'en_US'。
                      若为 None，则优先读取环境变量 BTC_LANGUAGE，
                      否则使用回退语言 en_US。
        """
        self._lock = threading.Lock()
        # 语言文件缓存：{语言代码: 翻译字典}
        self._cache: dict[str, dict[str, Any]] = {}
        # locales 目录路径
        self._locales_dir = Path(__file__).parent / "locales"

        # 确定初始语言
        env_lang = os.environ.get("BTC_LANGUAGE", "").strip()
        if language:
            self._current_language = language
        elif env_lang:
            self._current_language = env_lang
        else:
            self._current_language = _FALLBACK_LANGUAGE

    # ------------------------------------------------------------------
    # 公开属性
    # ------------------------------------------------------------------

    @property
    def current_language(self) -> str:
        """返回当前语言代码。"""
        with self._lock:
            return self._current_language

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def set_language(self, lang: str) -> None:
        """
        切换当前语言。

        Args:
            lang: 语言代码，如 'zh_CN'、'en_US'。
        """
        with self._lock:
            self._current_language = lang
            # 预加载语言文件
            self._load_language(lang)

    def get_supported_languages(self) -> list:
        """
        返回所有支持的语言代码列表（即 locales/ 目录中的 JSON 文件名）。
        """
        try:
            return [p.stem for p in self._locales_dir.glob("*.json") if p.stem != "__init__"]
        except OSError:
            return [_FALLBACK_LANGUAGE]

    def translate(self, key: str, **kwargs) -> str:
        """
        翻译指定键。

        Args:
            key: 点分隔的键路径，如 "cli.help.description"。
            **kwargs: 用于字符串格式化的参数。

        Returns:
            翻译后的字符串。若键不存在则返回键名本身。
        """
        with self._lock:
            lang = self._current_language

        # 先尝试当前语言
        value = self._get_value(lang, key)

        # 当前语言缺失时回退到英文
        if value is None and lang != _FALLBACK_LANGUAGE:
            value = self._get_value(_FALLBACK_LANGUAGE, key)

        # 仍未找到时使用硬编码默认值
        if value is None:
            value = _HARDCODED_DEFAULTS.get(key, key)

        # 执行参数替换
        if kwargs and isinstance(value, str):
            try:
                value = value.format(**kwargs)
            except (KeyError, ValueError) as exc:
                logger.warning("翻译参数替换失败 key=%s: %s", key, exc)

        return value if isinstance(value, str) else key

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_value(self, lang: str, key: str) -> str | None:
        """
        从指定语言的翻译字典中获取键值。

        Args:
            lang: 语言代码。
            key: 点分隔的键路径。

        Returns:
            翻译字符串，若不存在返回 None。
        """
        data = self._load_language(lang)
        if data is None:
            return None

        # 按点分隔逐层查找
        parts = key.split(".")
        node: Any = data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None

        return node if isinstance(node, str) else None

    def _load_language(self, lang: str) -> dict[str, Any] | None:
        """
        加载并缓存指定语言的翻译文件。

        Args:
            lang: 语言代码。

        Returns:
            翻译字典，若加载失败返回 None。
        """
        # 已缓存则直接返回
        if lang in self._cache:
            return self._cache[lang]

        lang_file = self._locales_dir / f"{lang}.json"
        if not lang_file.exists():
            logger.warning("语言文件不存在: %s", lang_file)
            return None

        try:
            with open(lang_file, encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            self._cache[lang] = data
            logger.debug("已加载语言文件: %s", lang_file)
            return data
        except json.JSONDecodeError as exc:
            logger.error("语言文件 JSON 解析失败 %s: %s，回退到硬编码默认值", lang_file, exc)
            # 使用空字典占位，避免重复读取损坏文件
            self._cache[lang] = {}
            return None
        except OSError as exc:
            logger.error("语言文件读取失败 %s: %s", lang_file, exc)
            return None
