"""optimization_config.py 单元测试。

覆盖 OptimizationConfig 类及模块级便捷函数。
"""

import copy
import os
import unittest

from src.config.optimization_config import (
    OptimizationConfig,
    disable_feature,
    enable_feature,
    get_optimization_config,
    is_feature_enabled,
    optimization_config,
)

_ENV_KEYS = (
    "OPTIMIZE_DELTA_STATS",
    "OPTIMIZE_DISTRIBUTED",
    "OPTIMIZE_MONITOR",
    "DELTA_FLUSH_INTERVAL",
    "AGGREGATOR_INTERVAL",
    "MONITOR_INTERVAL",
)


def _save_and_clear_env():
    """保存并清除优化相关环境变量，返回保存的字典。"""
    saved = {}
    for k in _ENV_KEYS:
        saved[k] = os.environ.pop(k, None)
    return saved


def _restore_env(saved):
    """恢复环境变量。"""
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


class TestOptimizationConfigInit(unittest.TestCase):
    """测试 OptimizationConfig 初始化和环境变量加载。"""

    def setUp(self):
        """保存并清理相关环境变量。"""
        self._saved = _save_and_clear_env()

    def tearDown(self):
        """恢复环境变量。"""
        _restore_env(self._saved)

    def test_default_config_all_keys_present(self):
        """初始化后包含所有默认 key。"""
        cfg = OptimizationConfig()
        data = cfg.get_all()
        for key in (
            "delta_stats_enabled",
            "distributed_aggregator_enabled",
            "performance_monitor_enabled",
            "delta_stats_flush_interval",
            "aggregator_interval",
            "monitor_interval",
            "alert_thresholds",
        ):
            self.assertIn(key, data)

    def test_default_bool_values_are_true(self):
        """默认布尔开关均为 True。"""
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))
        self.assertTrue(cfg.get("distributed_aggregator_enabled"))
        self.assertTrue(cfg.get("performance_monitor_enabled"))

    def test_default_float_values(self):
        """默认浮点值为预设值。"""
        cfg = OptimizationConfig()
        self.assertEqual(cfg.get("delta_stats_flush_interval"), 0.1)
        self.assertEqual(cfg.get("aggregator_interval"), 0.1)
        self.assertEqual(cfg.get("monitor_interval"), 1.0)

    def test_default_alert_thresholds_present(self):
        """默认告警阈值字典包含所有 key 及正确默认值。"""
        cfg = OptimizationConfig()
        thresholds = cfg.get("alert_thresholds")
        self.assertIsInstance(thresholds, dict)
        self.assertEqual(thresholds["latency_ms"], 100.0)
        self.assertEqual(thresholds["lock_contention"], 0.5)
        self.assertEqual(thresholds["memory_mb"], 512.0)
        self.assertEqual(thresholds["cpu_usage"], 80.0)

    # ── 环境变量加载 ──────────────────────────────────────

    def test_env_bool_true(self):
        """环境变量 'true' 设置布尔开关为 True。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = "true"
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))

    def test_env_bool_true_1(self):
        """环境变量 '1' 设置布尔开关为 True。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = "1"
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))

    def test_env_bool_true_yes(self):
        """环境变量 'yes' 设置布尔开关为 True。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = "yes"
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))

    def test_env_bool_true_mixed_case(self):
        """环境变量大小写不敏感 (True → True)。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = "True"
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))

    def test_env_bool_false(self):
        """环境变量 'false' 设置布尔开关为 False。"""
        os.environ["OPTIMIZE_DISTRIBUTED"] = "false"
        cfg = OptimizationConfig()
        self.assertFalse(cfg.get("distributed_aggregator_enabled"))

    def test_env_bool_false_0(self):
        """环境变量 '0' 设置布尔开关为 False。"""
        os.environ["OPTIMIZE_DISTRIBUTED"] = "0"
        cfg = OptimizationConfig()
        self.assertFalse(cfg.get("distributed_aggregator_enabled"))

    def test_env_bool_unrecognized_is_false(self):
        """无法识别的字符串视为 False。"""
        os.environ["OPTIMIZE_MONITOR"] = "disabled"
        cfg = OptimizationConfig()
        self.assertFalse(cfg.get("performance_monitor_enabled"))

    def test_env_bool_whitespace_is_false(self):
        """前后带空格的 ' true ' 不被识别为 True（by design）。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = " true "
        cfg = OptimizationConfig()
        self.assertFalse(cfg.get("delta_stats_enabled"))

    def test_env_bool_empty_string_is_false(self):
        """空字符串环境变量视为 False。"""
        os.environ["OPTIMIZE_DELTA_STATS"] = ""
        cfg = OptimizationConfig()
        self.assertFalse(cfg.get("delta_stats_enabled"))

    def test_env_float_valid(self):
        """有效环境变量设置浮点值。"""
        os.environ["DELTA_FLUSH_INTERVAL"] = "0.5"
        cfg = OptimizationConfig()
        self.assertEqual(cfg.get("delta_stats_flush_interval"), 0.5)

    def test_env_float_invalid_keeps_default(self):
        """无效浮点环境变量保留默认值。"""
        os.environ["DELTA_FLUSH_INTERVAL"] = "not_a_float"
        cfg = OptimizationConfig()
        self.assertEqual(cfg.get("delta_stats_flush_interval"), 0.1)

    def test_env_missing_keeps_default(self):
        """未设置环境变量时保留默认值（布尔和浮点）。"""
        cfg = OptimizationConfig()
        self.assertTrue(cfg.get("delta_stats_enabled"))
        self.assertEqual(cfg.get("delta_stats_flush_interval"), 0.1)


class TestOptimizationConfigMethods(unittest.TestCase):
    """测试 OptimizationConfig 实例方法。"""

    def setUp(self):
        """清理环境变量以避免外部干扰。"""
        self._saved = _save_and_clear_env()
        self.cfg = OptimizationConfig()

    def tearDown(self):
        """恢复环境变量。"""
        _restore_env(self._saved)

    def test_get_existing_key(self):
        """获取已存在的 key 返回对应值。"""
        self.assertEqual(self.cfg.get("monitor_interval"), 1.0)

    def test_get_nonexistent_returns_default(self):
        """获取不存在的 key 返回指定的默认值。"""
        self.assertEqual(self.cfg.get("nonexistent", 42), 42)

    def test_get_nonexistent_no_default_returns_none(self):
        """获取不存在的 key 且无默认值时返回 None。"""
        self.assertIsNone(self.cfg.get("nonexistent"))

    def test_is_enabled_true(self):
        """已启用的功能返回 True。"""
        self.assertTrue(self.cfg.is_enabled("delta_stats"))

    def test_is_enabled_after_set_false(self):
        """set 为 False 后 is_enabled 返回 False。"""
        self.cfg.set("delta_stats_enabled", False)
        self.assertFalse(self.cfg.is_enabled("delta_stats"))

    def test_is_enabled_missing_feature(self):
        """未配置的功能返回 False。"""
        self.assertFalse(self.cfg.is_enabled("nonexistent_feature"))

    def test_set_new_key(self):
        """set 新 key 后可通过 get 获取。"""
        self.cfg.set("custom_key", "custom_value")
        self.assertEqual(self.cfg.get("custom_key"), "custom_value")

    def test_set_overwrite_existing(self):
        """set 覆盖已有 key。"""
        self.cfg.set("monitor_interval", 99.9)
        self.assertEqual(self.cfg.get("monitor_interval"), 99.9)

    def test_get_all_returns_copy(self):
        """get_all 返回副本，修改副本不影响原配置。"""
        data = self.cfg.get_all()
        data["delta_stats_enabled"] = False
        self.assertTrue(self.cfg.get("delta_stats_enabled"))

    def test_get_all_contains_alert_thresholds(self):
        """get_all 返回的数据包含告警阈值字典。"""
        data = self.cfg.get_all()
        self.assertIn("alert_thresholds", data)
        self.assertEqual(data["alert_thresholds"]["latency_ms"], 100.0)


class TestModuleLevelFunctions(unittest.TestCase):
    """测试模块级便捷函数。

    假设：环境变量不影响便捷函数的行为（仅操作 _config 字典本身）。
    """

    def setUp(self):
        """深拷贝保存全局配置状态以便恢复。"""
        self._saved = copy.deepcopy(optimization_config._config)

    def tearDown(self):
        """恢复全局配置状态。"""
        optimization_config._config = self._saved

    def test_get_optimization_config_returns_instance(self):
        """get_optimization_config 返回 OptimizationConfig 实例。"""
        cfg = get_optimization_config()
        self.assertIsInstance(cfg, OptimizationConfig)

    def test_get_optimization_config_returns_same_instance(self):
        """多次调用返回同一模块级实例。"""
        cfg1 = get_optimization_config()
        cfg2 = get_optimization_config()
        self.assertIs(cfg1, cfg2)

    def test_enable_feature(self):
        """enable_feature 将对应 _enabled 键设为 True。"""
        optimization_config.set("test_feature_enabled", False)
        enable_feature("test_feature")
        self.assertTrue(optimization_config.get("test_feature_enabled"))

    def test_disable_feature(self):
        """disable_feature 将对应 _enabled 键设为 False。"""
        optimization_config.set("test_feature_enabled", True)
        disable_feature("test_feature")
        self.assertFalse(optimization_config.get("test_feature_enabled"))

    def test_is_feature_enabled_true(self):
        """is_feature_enabled 对已启用的功能返回 True。"""
        optimization_config.set("delta_stats_enabled", True)
        self.assertTrue(is_feature_enabled("delta_stats"))

    def test_is_feature_enabled_false(self):
        """is_feature_enabled 对已禁用的功能返回 False。"""
        optimization_config.set("delta_stats_enabled", False)
        self.assertFalse(is_feature_enabled("delta_stats"))

    def test_enable_feature_then_verify(self):
        """启用→验证→禁用→验证完整流程。"""
        disable_feature("delta_stats")
        self.assertFalse(is_feature_enabled("delta_stats"))
        enable_feature("delta_stats")
        self.assertTrue(is_feature_enabled("delta_stats"))
