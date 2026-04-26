"""跨平台语言检测模块。

优先级：
1. 环境变量 BTC_LANGUAGE
2. 系统语言检测（Windows / Linux / macOS）
3. 回退到 en_US
"""

import locale
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# 支持的语言代码列表
_SUPPORTED_LANGUAGES = ["zh_CN", "en_US"]

# 系统语言代码到标准化代码的映射
_LANG_MAP = {
    # 中文简体
    "zh_cn": "zh_CN",
    "zh": "zh_CN",
    "chinese (simplified)": "zh_CN",
    "chs": "zh_CN",
    # 英文
    "en_us": "en_US",
    "en_gb": "en_US",
    "en": "en_US",
    "english": "en_US",
    # Windows 语言代码（十六进制）
    "2052": "zh_CN",   # 中文（中国）
    "1028": "zh_CN",   # 中文（台湾）
    "3076": "zh_CN",   # 中文（香港）
    "1033": "en_US",   # 英语（美国）
    "2057": "en_US",   # 英语（英国）
}

# 默认回退语言
_DEFAULT_LANGUAGE = "en_US"


def detect_system_language() -> str:
    """
    检测当前系统语言。

    检测顺序：
    1. 环境变量 BTC_LANGUAGE
    2. 系统语言（Windows 使用 WinAPI，其他系统使用 LANG/LC_ALL 环境变量）
    3. Python locale 模块
    4. 回退到 en_US

    Returns:
        标准化语言代码，如 'zh_CN' 或 'en_US'。
    """
    # 1. 优先读取环境变量 BTC_LANGUAGE
    env_lang = os.environ.get("BTC_LANGUAGE", "").strip()
    if env_lang:
        normalized = _normalize_language_code(env_lang)
        if normalized:
            logger.debug("从环境变量 BTC_LANGUAGE 检测到语言: %s -> %s", env_lang, normalized)
            return normalized

    # 2. 系统平台检测
    detected: Optional[str] = None

    if sys.platform == "win32":
        detected = _detect_windows_language()
    else:
        detected = _detect_unix_language()

    if detected:
        logger.debug("系统语言检测结果: %s", detected)
        return detected

    # 3. Python locale 回退
    try:
        locale_code, _ = locale.getdefaultlocale()
        if locale_code:
            normalized = _normalize_language_code(locale_code)
            if normalized:
                logger.debug("从 Python locale 检测到语言: %s -> %s", locale_code, normalized)
                return normalized
    except Exception as exc:
        logger.debug("Python locale 检测失败: %s", exc)

    # 4. 最终回退
    logger.debug("语言检测失败，使用默认语言: %s", _DEFAULT_LANGUAGE)
    return _DEFAULT_LANGUAGE


# ------------------------------------------------------------------
# Windows 语言检测
# ------------------------------------------------------------------

def _detect_windows_language() -> Optional[str]:
    """
    通过 Windows API 检测用户界面语言。

    Returns:
        标准化语言代码，失败时返回 None。
    """
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # Windows LANGID 十六进制字符串映射
        lang_str = str(lang_id)
        normalized = _LANG_MAP.get(lang_str)
        if normalized:
            return normalized

        # 尝试主语言 ID（低字节）
        primary = lang_id & 0xFF
        primary_str = str(primary)
        normalized = _LANG_MAP.get(primary_str)
        if normalized:
            return normalized

        # 通过 locale.windows_locale 获取 IETF 格式
        locale_name = locale.windows_locale.get(lang_id, "")
        if locale_name:
            return _normalize_language_code(locale_name)

    except Exception as exc:
        logger.debug("Windows API 语言检测失败: %s", exc)

    # 回退：读取环境变量
    return _detect_env_language()


# ------------------------------------------------------------------
# Unix/Linux/macOS 语言检测
# ------------------------------------------------------------------

def _detect_unix_language() -> Optional[str]:
    """
    通过 LANG / LC_ALL / LC_MESSAGES 环境变量检测语言。

    Returns:
        标准化语言代码，失败时返回 None。
    """
    for env_var in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        value = os.environ.get(env_var, "").strip()
        if value:
            # 去除编码部分，如 "zh_CN.UTF-8" -> "zh_CN"
            lang_part = value.split(".")[0].split("@")[0]
            normalized = _normalize_language_code(lang_part)
            if normalized:
                logger.debug("从环境变量 %s 检测到语言: %s -> %s", env_var, value, normalized)
                return normalized
    return None


def _detect_env_language() -> Optional[str]:
    """
    通用环境变量语言检测（跨平台备用）。
    """
    for env_var in ("LANG", "LC_ALL", "LANGUAGE"):
        value = os.environ.get(env_var, "").strip()
        if value:
            lang_part = value.split(".")[0].split("@")[0]
            normalized = _normalize_language_code(lang_part)
            if normalized:
                return normalized
    return None


# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------

def _normalize_language_code(code: str) -> Optional[str]:
    """
    将各种格式的语言代码标准化为已知的语言代码。

    Args:
        code: 语言代码字符串，如 'zh_CN'、'zh-CN'、'zh'。

    Returns:
        标准化语言代码，若不在支持列表中返回 None。
    """
    if not code:
        return None

    # 统一转换：zh-CN -> zh_CN，然后查映射表
    normalized = code.replace("-", "_").strip()
    lower = normalized.lower()

    # 精确匹配映射
    result = _LANG_MAP.get(lower)
    if result:
        return result

    # 前缀匹配：zh_CN_xxx -> zh_CN
    for key, val in _LANG_MAP.items():
        if lower.startswith(key):
            return val

    return None


def is_language_supported(lang: str) -> bool:
    """
    检查语言代码是否在支持列表中。

    Args:
        lang: 语言代码。

    Returns:
        True 表示支持，False 表示不支持。
    """
    return lang in _SUPPORTED_LANGUAGES
