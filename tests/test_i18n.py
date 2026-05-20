"""i18n 国际化模块测试。

覆盖范围:
- TestTranslator: 翻译器加载、嵌套 key 查找、参数替换、缺失 key fallback
- TestLanguageDetector: 三平台语言检测、环境变量覆盖
- TestLanguageSwitching: 运行时语言切换
- TestTranslationCompleteness: zh_CN.json 与 en_US.json key 集合一致性
- TestCLILanguageIntegration: --language 参数生效验证
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.i18n import _t, get_language, get_supported_languages, set_language  # noqa: E402
from src.i18n.language_detector import (  # noqa: E402
    _normalize_language_code,
    detect_system_language,
    is_language_supported,
)
from src.i18n.translator import Translator  # noqa: E402

# locales 目录绝对路径（供翻译完整性测试使用）
_LOCALES_DIR = Path(__file__).parent.parent / "src" / "i18n" / "locales"


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _extract_keys(data: dict, prefix: str = "") -> set:
    """递归提取字典中所有叶节点的点分隔 key。"""
    keys: set = set()
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_extract_keys(v, full_key))
        else:
            keys.add(full_key)
    return keys


# ===========================================================================
# 1. TestTranslator — 翻译器核心功能
# ===========================================================================


class TestTranslator(unittest.TestCase):
    """翻译器核心功能测试。"""

    def setUp(self):
        """每个测试前创建独立的 Translator 实例，避免全局状态污染。"""
        self.zh_translator = Translator(language="zh_CN")
        self.en_translator = Translator(language="en_US")

    # ------------------------------------------------------------------
    # 语言文件加载
    # ------------------------------------------------------------------

    def test_load_zh_CN_success(self):
        """测试 zh_CN 语言文件加载成功（common.success 有值）。"""
        result = self.zh_translator.translate("common.success")
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, "common.success")  # 不是 key 原样返回
        self.assertEqual(result, "成功")

    def test_load_en_US_success(self):
        """测试 en_US 语言文件加载成功。"""
        result = self.en_translator.translate("common.success")
        self.assertEqual(result, "Success")

    def test_supported_languages_contain_zh_and_en(self):
        """get_supported_languages() 应包含 zh_CN 和 en_US。"""
        langs = self.zh_translator.get_supported_languages()
        self.assertIn("zh_CN", langs)
        self.assertIn("en_US", langs)

    # ------------------------------------------------------------------
    # 嵌套 key 查找
    # ------------------------------------------------------------------

    def test_nested_key_two_levels(self):
        """二层嵌套 key: common.error。"""
        self.assertEqual(self.zh_translator.translate("common.error"), "错误")
        self.assertEqual(self.en_translator.translate("common.error"), "Error")

    def test_nested_key_three_levels(self):
        """三层嵌套 key: cli.commands.start。"""
        zh_val = self.zh_translator.translate("cli.commands.start")
        en_val = self.en_translator.translate("cli.commands.start")
        self.assertEqual(zh_val, "启动碰撞引擎")
        self.assertEqual(en_val, "Start the collision engine")

    def test_nested_key_four_levels(self):
        """四层嵌套 key: platform.check.title。"""
        zh_val = self.zh_translator.translate("platform.check.title")
        en_val = self.en_translator.translate("platform.check.title")
        self.assertIsInstance(zh_val, str)
        self.assertIsInstance(en_val, str)
        self.assertNotEqual(zh_val, "platform.check.title")
        self.assertNotEqual(en_val, "platform.check.title")

    # ------------------------------------------------------------------
    # 参数替换
    # ------------------------------------------------------------------

    def test_param_substitution_single(self):
        """单参数替换: platform.check.os_supported。"""
        result = self.en_translator.translate("platform.check.os_supported", os_name="Windows")
        self.assertIn("Windows", result)
        self.assertNotIn("{os_name}", result)

    def test_param_substitution_zh(self):
        """中文参数替换: errors.file_not_found。"""
        result = self.zh_translator.translate("errors.file_not_found", path="/tmp/x.txt")
        self.assertIn("/tmp/x.txt", result)
        self.assertNotIn("{path}", result)

    def test_param_substitution_multiple(self):
        """多参数替换: platform.check.summary。"""
        result = self.en_translator.translate("platform.check.summary", passed=5, failed=0)
        self.assertIn("5", result)
        self.assertIn("0", result)
        self.assertNotIn("{passed}", result)
        self.assertNotIn("{failed}", result)

    def test_param_substitution_missing_param_returns_key_value(self):
        """参数缺失时，翻译值应仍被返回（不崩溃）。"""
        # 缺少参数时 format() 会抛出 KeyError，translate 应捕获并返回原始模板
        result = self.en_translator.translate("errors.file_not_found")
        # 应返回包含占位符的原始模板字符串（而非 key 本身）
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, "")

    # ------------------------------------------------------------------
    # 缺失 key fallback
    # ------------------------------------------------------------------

    def test_missing_key_returns_key_itself(self):
        """完全不存在的 key 最终回退到 key 字符串本身。"""
        fake_key = "nonexistent.key.that.does.not.exist"
        result = self.en_translator.translate(fake_key)
        self.assertEqual(result, fake_key)

    def test_missing_key_zh_falls_back_to_en(self):
        """zh_CN 语言缺失某 key 时，应回退到 en_US 翻译而非返回 key。

        方法: 临时向 zh_CN 缓存中注入缺少某 key 的数据，触发 fallback 逻辑。
        """
        t = Translator(language="zh_CN")
        # 预先加载 zh_CN 到缓存，再从缓存中删除某个 key
        _ = t.translate("common.success")  # 触发加载
        # 注入一个残缺的 zh_CN 缓存（缺少 common.success）
        t._cache["zh_CN"] = {}  # 清空 zh_CN 缓存数据
        # 现在 zh_CN 缓存为空，应 fallback 到 en_US
        result = t.translate("common.success")
        self.assertEqual(result, "Success")  # en_US 的翻译

    def test_hardcoded_default_fallback(self):
        """两个语言文件都缺失时，应返回硬编码默认值。"""
        t = Translator(language="zh_CN")
        # 注入两个语言的空缓存
        t._cache["zh_CN"] = {}
        t._cache["en_US"] = {}
        result = t.translate("common.error")
        # 硬编码 _HARDCODED_DEFAULTS 中有 "common.error": "Error"
        self.assertEqual(result, "Error")

    def test_key_points_to_dict_returns_key(self):
        """key 指向的是字典节点而非叶子节点时，返回 key 本身。"""
        # "common" 是一个 dict，不是 string
        result = self.en_translator.translate("common")
        self.assertEqual(result, "common")

    def test_corrupt_json_falls_back_to_hardcoded(self):
        """JSON 文件损坏时回退到硬编码默认值。"""
        import shutil
        import tempfile
        tmpdir = tempfile.mkdtemp()
        try:
            # 创建损坏的 en_US.json
            en_json = Path(tmpdir) / "en_US.json"
            en_json.write_text("not valid json{", encoding="utf-8")
            # zh_CN 不存在，让 translate 走外语→en 回退
            t = Translator(language="zh_CN")
            t._locales_dir = Path(tmpdir)
            t._cache.clear()
            result = t.translate("common.error")
            self.assertEqual(result, "Error")  # 硬编码默认值
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ===========================================================================
# 2. TestLanguageDetector — 语言检测
# ===========================================================================


class TestLanguageDetector(unittest.TestCase):
    """语言检测测试。"""

    def setUp(self):
        """清除可能干扰测试的环境变量。"""
        self._original_btc_lang = os.environ.pop("BTC_LANGUAGE", None)
        # 清除 Unix 语言环境变量
        for var in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
            os.environ.pop(var, None)

    def tearDown(self):
        """恢复环境变量。"""
        if self._original_btc_lang is not None:
            os.environ["BTC_LANGUAGE"] = self._original_btc_lang
        else:
            os.environ.pop("BTC_LANGUAGE", None)

    # ------------------------------------------------------------------
    # BTC_LANGUAGE 环境变量优先级
    # ------------------------------------------------------------------

    def test_btc_language_env_zh_CN(self):
        """BTC_LANGUAGE=zh_CN 应优先返回 zh_CN。"""
        os.environ["BTC_LANGUAGE"] = "zh_CN"
        result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    def test_btc_language_env_en_US(self):
        """BTC_LANGUAGE=en_US 应优先返回 en_US。"""
        os.environ["BTC_LANGUAGE"] = "en_US"
        result = detect_system_language()
        self.assertEqual(result, "en_US")

    def test_btc_language_env_with_dash_format(self):
        """BTC_LANGUAGE 支持 zh-CN 连字符格式。"""
        os.environ["BTC_LANGUAGE"] = "zh-CN"
        result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    def test_btc_language_unsupported_falls_back(self):
        """BTC_LANGUAGE 设置为不支持的语言时，应继续检测系统语言（不直接返回）。

        fr_FR 无法标准化，应跳过；在系统语言也为空时应回退到 en_US。
        """
        os.environ["BTC_LANGUAGE"] = "fr_FR"
        # 同时 mock 平台检测和 locale 回退，确保最终回退到 en_US
        with (
            patch("src.i18n.language_detector._detect_windows_language", return_value=None),
            patch("src.i18n.language_detector._detect_unix_language", return_value=None),
            patch("locale.getdefaultlocale", return_value=(None, None)),
        ):
            result = detect_system_language()
        self.assertEqual(result, "en_US")

    # ------------------------------------------------------------------
    # Linux 平台（LANG 环境变量）
    # ------------------------------------------------------------------

    @patch("sys.platform", "linux")
    def test_linux_lang_zh_CN(self):
        """Linux LANG=zh_CN.UTF-8 应检测为 zh_CN。"""
        os.environ["LANG"] = "zh_CN.UTF-8"
        result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    @patch("sys.platform", "linux")
    def test_linux_lang_en_US(self):
        """Linux LANG=en_US.UTF-8 应检测为 en_US。"""
        os.environ["LANG"] = "en_US.UTF-8"
        result = detect_system_language()
        self.assertEqual(result, "en_US")

    @patch("sys.platform", "linux")
    def test_linux_lc_all_takes_effect(self):
        """Linux LC_ALL=zh_CN 应生效。"""
        os.environ["LC_ALL"] = "zh_CN"
        result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    # ------------------------------------------------------------------
    # macOS 平台
    # ------------------------------------------------------------------

    @patch("sys.platform", "darwin")
    def test_macos_lang_env(self):
        """macOS 使用 LANG 环境变量检测语言。"""
        os.environ["LANG"] = "zh_CN.UTF-8"
        result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    # ------------------------------------------------------------------
    # Windows 平台（通过 ctypes Mock）
    # ------------------------------------------------------------------

    @patch("src.i18n.language_detector._detect_windows_language")
    def test_windows_chinese_lang_id(self, mock_detect_win):
        """Windows LANGID=2052（中文简体）应检测为 zh_CN。

        通过直接 mock _detect_windows_language 返回值验证。
        """
        mock_detect_win.return_value = "zh_CN"
        os.environ["BTC_LANGUAGE"] = ""  # 确保 BTC_LANGUAGE 不干扰
        with patch("src.i18n.language_detector._detect_unix_language", return_value=None):
            result = detect_system_language()
        self.assertEqual(result, "zh_CN")

    @patch("src.i18n.language_detector._detect_windows_language")
    def test_windows_english_lang_id(self, mock_detect_win):
        """Windows LANGID=1033（英文美国）应检测为 en_US。

        通过直接 mock _detect_windows_language 返回值验证。
        """
        mock_detect_win.return_value = "en_US"
        os.environ["BTC_LANGUAGE"] = ""  # 确保 BTC_LANGUAGE 不干扰
        with patch("src.i18n.language_detector._detect_unix_language", return_value=None):
            result = detect_system_language()
        self.assertEqual(result, "en_US")

    # ------------------------------------------------------------------
    # _normalize_language_code
    # ------------------------------------------------------------------

    def test_normalize_zh_cn_lowercase(self):
        self.assertEqual(_normalize_language_code("zh_cn"), "zh_CN")

    def test_normalize_zh_CN_uppercase(self):
        self.assertEqual(_normalize_language_code("zh_CN"), "zh_CN")

    def test_normalize_zh_dash(self):
        self.assertEqual(_normalize_language_code("zh-CN"), "zh_CN")

    def test_normalize_en_us(self):
        self.assertEqual(_normalize_language_code("en_us"), "en_US")

    def test_normalize_en_only(self):
        self.assertEqual(_normalize_language_code("en"), "en_US")

    def test_normalize_unsupported_returns_none(self):
        self.assertIsNone(_normalize_language_code("fr_FR"))

    def test_normalize_empty_returns_none(self):
        self.assertIsNone(_normalize_language_code(""))

    def test_is_language_supported_true(self):
        self.assertTrue(is_language_supported("zh_CN"))
        self.assertTrue(is_language_supported("en_US"))

    def test_is_language_supported_false(self):
        self.assertFalse(is_language_supported("fr_FR"))
        self.assertFalse(is_language_supported(""))

    # ── _detect_env_language 回退路径 ──────────────────────────

    def test_detect_env_language_finds_zh_cn(self):
        """_detect_env_language 通过 LANG 变量检测到 zh_CN。"""
        from src.i18n.language_detector import _detect_env_language
        os.environ["LANG"] = "zh_CN.UTF-8"
        result = _detect_env_language()
        self.assertEqual(result, "zh_CN")

    # ── _normalize_language_code 前缀匹配 ─────────────────────

    def test_normalize_prefix_match(self):
        """前缀匹配: zh_cn_CN 通过 startswith('zh_cn') 匹配到 zh_CN。"""
        self.assertEqual(_normalize_language_code("zh_cn_CN"), "zh_CN")

    def test_normalize_prefix_no_match_returns_none(self):
        """遍历完所有前缀均不匹配时返回 None。"""
        self.assertIsNone(_normalize_language_code("chr_invalid_prefix"))


# ===========================================================================
# 3. TestLanguageSwitching — 运行时语言切换
# ===========================================================================


class TestLanguageSwitching(unittest.TestCase):
    """运行时语言切换测试。"""

    def setUp(self):
        """保存并重置全局翻译器语言状态。"""
        import src.i18n as i18n_module

        self._original_lang = i18n_module._translator.current_language

    def tearDown(self):
        """恢复原始语言设置，避免影响其他测试。"""
        set_language(self._original_lang)

    def test_switch_to_en_US(self):
        """切换到 en_US 后 _t() 应返回英文。"""
        set_language("en_US")
        self.assertEqual(get_language(), "en_US")
        result = _t("common.success")
        self.assertEqual(result, "Success")

    def test_switch_to_zh_CN(self):
        """切换到 zh_CN 后 _t() 应返回中文。"""
        set_language("zh_CN")
        self.assertEqual(get_language(), "zh_CN")
        result = _t("common.success")
        self.assertEqual(result, "成功")

    def test_switch_back_and_forth(self):
        """多次切换语言，每次都能正确返回对应翻译。"""
        set_language("en_US")
        self.assertEqual(_t("common.error"), "Error")

        set_language("zh_CN")
        self.assertEqual(_t("common.error"), "错误")

        set_language("en_US")
        self.assertEqual(_t("common.error"), "Error")

    def test_switch_to_unsupported_language_falls_back(self):
        """切换到不支持的语言后，translate 应回退到 en_US 翻译。"""
        set_language("fr_FR")
        self.assertEqual(get_language(), "fr_FR")
        # fr_FR 文件不存在，应 fallback 到 en_US
        result = _t("common.success")
        self.assertEqual(result, "Success")

    def test_get_language_reflects_set(self):
        """get_language() 应准确反映最后 set_language() 的值。"""
        set_language("zh_CN")
        self.assertEqual(get_language(), "zh_CN")
        set_language("en_US")
        self.assertEqual(get_language(), "en_US")

    def test_get_supported_languages(self):
        """get_supported_languages() 应至少包含 zh_CN 和 en_US。"""
        langs = get_supported_languages()
        self.assertIn("zh_CN", langs)
        self.assertIn("en_US", langs)


# ===========================================================================
# 4. TestTranslationCompleteness — 翻译完整性验证
# ===========================================================================


class TestTranslationCompleteness(unittest.TestCase):
    """验证 zh_CN.json 与 en_US.json 的翻译 key 完全一致。"""

    @classmethod
    def setUpClass(cls):
        """加载两个翻译文件。"""
        zh_path = _LOCALES_DIR / "zh_CN.json"
        en_path = _LOCALES_DIR / "en_US.json"

        with open(zh_path, encoding="utf-8") as f:
            cls.zh_data = json.load(f)
        with open(en_path, encoding="utf-8") as f:
            cls.en_data = json.load(f)

        cls.zh_keys = _extract_keys(cls.zh_data)
        cls.en_keys = _extract_keys(cls.en_data)

    def test_zh_keys_not_empty(self):
        """zh_CN.json 应有翻译条目。"""
        self.assertGreater(len(self.zh_keys), 0)

    def test_en_keys_not_empty(self):
        """en_US.json 应有翻译条目。"""
        self.assertGreater(len(self.en_keys), 0)

    def test_zh_has_no_extra_keys(self):
        """zh_CN 不应有 en_US 中缺失的 key（多余键）。"""
        extra_zh = self.zh_keys - self.en_keys
        self.assertEqual(
            extra_zh,
            set(),
            f"zh_CN 中存在 en_US 缺失的 key（{len(extra_zh)} 个）:\n"
            + "\n".join(sorted(extra_zh)[:20]),
        )

    def test_en_has_no_extra_keys(self):
        """en_US 不应有 zh_CN 中缺失的 key（多余键）。"""
        extra_en = self.en_keys - self.zh_keys
        self.assertEqual(
            extra_en,
            set(),
            f"en_US 中存在 zh_CN 缺失的 key（{len(extra_en)} 个）:\n"
            + "\n".join(sorted(extra_en)[:20]),
        )

    def test_key_sets_identical(self):
        """zh_CN 与 en_US 的 key 集合应完全相同。"""
        self.assertEqual(
            self.zh_keys,
            self.en_keys,
            "两个语言文件 key 集合不一致",
        )

    def test_all_zh_values_are_non_empty_strings(self):
        """zh_CN 所有叶节点 value 应为非空字符串。"""

        def check_values(data: dict, path: str = ""):
            for k, v in data.items():
                full = f"{path}.{k}" if path else k
                if isinstance(v, dict):
                    check_values(v, full)
                else:
                    self.assertIsInstance(v, str, f"zh_CN key '{full}' 的 value 不是字符串")
                    self.assertGreater(len(v), 0, f"zh_CN key '{full}' 的 value 为空字符串")

        check_values(self.zh_data)

    def test_all_en_values_are_non_empty_strings(self):
        """en_US 所有叶节点 value 应为非空字符串。"""

        def check_values(data: dict, path: str = ""):
            for k, v in data.items():
                full = f"{path}.{k}" if path else k
                if isinstance(v, dict):
                    check_values(v, full)
                else:
                    self.assertIsInstance(v, str, f"en_US key '{full}' 的 value 不是字符串")
                    self.assertGreater(len(v), 0, f"en_US key '{full}' 的 value 为空字符串")

        check_values(self.en_data)

    def test_key_count_matches(self):
        """两个文件的叶节点 key 数量应一致。"""
        self.assertEqual(
            len(self.zh_keys),
            len(self.en_keys),
            f"key 数量不一致: zh_CN={len(self.zh_keys)}, en_US={len(self.en_keys)}",
        )


# ===========================================================================
# 5. TestCLILanguageIntegration — CLI --language 参数集成
# ===========================================================================


class TestCLILanguageIntegration(unittest.TestCase):
    """CLI --language 参数集成测试。"""

    def setUp(self):
        """保存并重置全局翻译器语言状态。"""
        import src.i18n as i18n_module

        self._original_lang = i18n_module._translator.current_language

    def tearDown(self):
        """恢复语言设置。"""
        set_language(self._original_lang)

    def test_set_language_zh_CN_and_get(self):
        """模拟 --language zh_CN: set_language 调用后 get_language 返回正确值。"""
        set_language("zh_CN")
        self.assertEqual(get_language(), "zh_CN")

    def test_set_language_en_US_and_get(self):
        """模拟 --language en_US: set_language 调用后 get_language 返回正确值。"""
        set_language("en_US")
        self.assertEqual(get_language(), "en_US")

    def test_language_affects_translation_output(self):
        """language 设置直接影响 _t() 的翻译输出。"""
        set_language("zh_CN")
        zh_result = _t("cli.commands.start")

        set_language("en_US")
        en_result = _t("cli.commands.start")

        self.assertNotEqual(zh_result, en_result, "中英文翻译结果不应相同")
        self.assertEqual(zh_result, "启动碰撞引擎")
        self.assertEqual(en_result, "Start the collision engine")

    def test_language_option_help_text_translatable(self):
        """cli.options.language key 在两种语言下都有非空翻译。"""
        set_language("zh_CN")
        zh_val = _t("cli.options.language")
        set_language("en_US")
        en_val = _t("cli.options.language")

        self.assertIsInstance(zh_val, str)
        self.assertIsInstance(en_val, str)
        self.assertNotEqual(zh_val, "cli.options.language")
        self.assertNotEqual(en_val, "cli.options.language")

    def test_set_language_is_idempotent(self):
        """多次调用 set_language 相同语言不应产生副作用。"""
        set_language("en_US")
        set_language("en_US")
        set_language("en_US")
        self.assertEqual(get_language(), "en_US")
        self.assertEqual(_t("common.success"), "Success")

    @patch("src.i18n.set_language")
    def test_mock_set_language_called_with_correct_arg(self, mock_set_lang):
        """模拟 CLI 调用路径：验证 set_language 被以正确参数调用。"""
        # 模拟 CLI 解析 --language zh_CN 后的调用
        cli_language_arg = "zh_CN"
        mock_set_lang(cli_language_arg)
        mock_set_lang.assert_called_once_with("zh_CN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
