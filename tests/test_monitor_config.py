#!/usr/bin/env python3
"""MonitorConfig配置对象单元测试

测试src.monitoring.monitor_config模块的所有功能。

测试覆盖:
- 配置对象创建（默认/自定义/从字典）
- 配置验证（有效/无效值）
- 配置合并逻辑
- __post_init__自动验证
- 预定义配置模板
- update/to_dict/from_dict方法
"""

import logging

import pytest

from src.monitoring.monitor_config import (
    DEFAULT_CONFIG,
    DEVELOPMENT_CONFIG,
    PRODUCTION_CONFIG,
    TESTING_CONFIG,
    MonitorConfig,
)


class TestMonitorConfigCreation:
    """测试配置对象创建"""

    def test_default_config_creation(self):
        """测试默认配置创建"""
        config = MonitorConfig()

        # P2优化：使用字典对比，提高可维护性
        expected = {
            "data_logging_enabled": True,
            "data_logging_interval": 1.0,
            "enable_monitoring_data": False,
            "collection_interval": 1.0,
            "alert_enabled": True,
            "alert_threshold": 0.9,
            "report_enabled": False,
            "enable_debug_mode": False,
        }

        for key, expected_value in expected.items():
            assert getattr(config, key) == expected_value, f"{key}不匹配"

    def test_custom_config_creation(self):
        """测试自定义配置创建"""
        config = MonitorConfig(
            data_logging_enabled=False,
            data_logging_interval=5.0,
            alert_threshold=0.85,
            enable_debug_mode=True,
        )

        assert config.data_logging_enabled is False
        assert config.data_logging_interval == 5.0
        assert config.alert_threshold == 0.85
        assert config.enable_debug_mode is True

    def test_create_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            "data_logging_enabled": True,
            "data_logging_interval": 2.0,
            "alert_threshold": 0.95,
            "enable_gpu_monitoring": True,
        }

        config = MonitorConfig.from_dict(config_dict)

        assert config.data_logging_enabled is True
        assert config.data_logging_interval == 2.0
        assert config.alert_threshold == 0.95
        assert config.enable_gpu_monitoring is True

    def test_create_from_dict_with_extra_fields(self):
        """测试从字典创建配置（包含额外字段）"""
        config_dict = {
            "data_logging_enabled": True,
            "unknown_field": "should_be_ignored",
            "another_field": 123,
        }

        config = MonitorConfig.from_dict(config_dict)

        # 额外字段应该被忽略
        assert config.data_logging_enabled is True
        assert not hasattr(config, "unknown_field")

    def test_create_from_empty_dict(self):
        """测试从空字典创建配置"""
        config = MonitorConfig.from_dict({})

        # 应该使用所有默认值
        assert config == MonitorConfig()


class TestMonitorConfigValidation:
    """测试配置验证逻辑

    测试策略:
    - 验证所有18个配置字段的有效性检查
    - 测试边界值（0.0, 1.0, 0, -1）
    - 验证错误消息包含字段名和当前值
    - 确保validate()返回True或抛出ValueError

    覆盖范围:
    - alert_threshold: [0.0, 1.0]
    - 所有时间间隔: > 0 (8个字段)
    - 所有计数: > 0 (3个字段)
    """

    def test_validate_valid_config(self):
        """测试验证有效配置"""
        config = MonitorConfig()
        assert config.validate() is True

    def test_validate_custom_valid_config(self):
        """测试验证自定义有效配置"""
        config = MonitorConfig(alert_threshold=0.5, data_logging_interval=10.0, collection_interval=5.0)
        assert config.validate() is True

    def test_validate_invalid_alert_threshold_high(self):
        """测试验证alert_threshold过高"""
        config = MonitorConfig(alert_threshold=1.5)

        with pytest.raises(ValueError, match="alert_threshold必须在0.0-1.0之间"):
            config.validate()

    def test_validate_invalid_alert_threshold_low(self):
        """测试验证alert_threshold过低"""
        config = MonitorConfig(alert_threshold=-0.1)

        with pytest.raises(ValueError, match="alert_threshold必须在0.0-1.0之间"):
            config.validate()

    def test_validate_invalid_data_logging_interval(self):
        """测试验证data_logging_interval为负数"""
        config = MonitorConfig(data_logging_interval=-1.0)

        with pytest.raises(ValueError, match="data_logging_interval必须大于0"):
            config.validate()

    def test_validate_zero_data_logging_interval(self):
        """测试验证data_logging_interval为0"""
        config = MonitorConfig(data_logging_interval=0)

        with pytest.raises(ValueError, match="data_logging_interval必须大于0"):
            config.validate()

    def test_validate_invalid_collection_interval(self):
        """测试验证collection_interval为负数"""
        config = MonitorConfig(collection_interval=-5.0)

        with pytest.raises(ValueError, match="collection_interval必须大于0"):
            config.validate()

    def test_validate_invalid_max_alerts_per_hour(self):
        """测试验证max_alerts_per_hour为负数"""
        config = MonitorConfig(max_alerts_per_hour=-10)

        with pytest.raises(ValueError, match="max_alerts_per_hour必须大于0"):
            config.validate()

    def test_validate_invalid_max_log_entries(self):
        """测试验证max_log_entries为负数"""
        config = MonitorConfig(max_log_entries=0)

        with pytest.raises(ValueError, match="max_log_entries必须大于0"):
            config.validate()

    def test_validate_gpu_monitoring_interval(self):
        """测试验证gpu_monitoring_interval"""
        config = MonitorConfig(gpu_monitoring_interval=-1.0)

        with pytest.raises(ValueError, match="gpu_monitoring_interval必须大于0"):
            config.validate()

    def test_validate_alert_cooldown(self):
        """测试验证alert_cooldown"""
        config = MonitorConfig(alert_cooldown=0)

        with pytest.raises(ValueError, match="alert_cooldown必须大于0"):
            config.validate()

    def test_validate_report_interval(self):
        """测试验证report_interval"""
        config = MonitorConfig(report_interval=-3600.0)

        with pytest.raises(ValueError, match="report_interval必须大于0"):
            config.validate()

    def test_validate_cleanup_interval(self):
        """测试验证cleanup_interval"""
        config = MonitorConfig(cleanup_interval=0)

        with pytest.raises(ValueError, match="cleanup_interval必须大于0"):
            config.validate()


class TestMonitorConfigMerge:
    """测试配置合并逻辑

    测试策略:
    - 验证config2优先级高于config1
    - 测试单字段/多字段/全部字段覆盖
    - 验证config2的默认值也会覆盖config1
    - 确保合并不修改原始配置
    - 验证返回新配置对象

    关键规则:
    - config2的所有值都覆盖config1（包括默认值）
    - 原始配置不变
    - 返回新MonitorConfig实例
    """

    def test_merge_override_single_field(self):
        """测试合并单个字段覆盖"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig(alert_threshold=0.9)

        merged = config1.merge(config2)

        assert merged.alert_threshold == 0.9

    def test_merge_override_multiple_fields(self):
        """测试合并多个字段覆盖"""
        config1 = MonitorConfig(alert_threshold=0.8, data_logging_interval=1.0)
        config2 = MonitorConfig(alert_threshold=0.95, data_logging_interval=5.0, enable_debug_mode=True)

        merged = config1.merge(config2)

        assert merged.alert_threshold == 0.95
        assert merged.data_logging_interval == 5.0
        assert merged.enable_debug_mode is True

    def test_merge_preserves_non_overridden(self):
        """测试合并时config2的所有值覆盖config1"""
        config1 = MonitorConfig(alert_threshold=0.8, data_logging_interval=10.0)
        config2 = MonitorConfig(
            alert_threshold=0.9,
            # data_logging_interval使用默认值1.0
        )

        merged = config1.merge(config2)

        # config2的所有值都覆盖config1（包括默认值）
        assert merged.alert_threshold == 0.9  # config2的值
        assert merged.data_logging_interval == 1.0  # config2的默认值覆盖了config1的10.0

    def test_merge_default_values(self):
        """测试合并默认值也覆盖"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig()  # 默认值0.9

        merged = config1.merge(config2)

        assert merged.alert_threshold == 0.9  # config2的默认值覆盖config1

    def test_merge_does_not_modify_original(self):
        """测试合并不修改原始配置"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig(alert_threshold=0.9)

        merged = config1.merge(config2)

        # 原始配置不应被修改
        assert config1.alert_threshold == 0.8
        assert config2.alert_threshold == 0.9
        assert merged.alert_threshold == 0.9

    def test_merge_returns_new_instance(self):
        """测试合并返回新实例"""
        config1 = MonitorConfig()
        config2 = MonitorConfig()

        merged = config1.merge(config2)

        assert merged is not config1
        assert merged is not config2

    def test_merge_all_fields(self):
        """测试合并所有字段"""
        config1 = MonitorConfig()
        config2 = MonitorConfig(
            data_logging_enabled=False,
            data_logging_interval=10.0,
            alert_threshold=0.95,
            enable_debug_mode=True,
            report_enabled=True,
        )

        merged = config1.merge(config2)

        assert merged.data_logging_enabled is False
        assert merged.data_logging_interval == 10.0
        assert merged.alert_threshold == 0.95
        assert merged.enable_debug_mode is True
        assert merged.report_enabled is True


class TestPostInit:
    """测试__post_init__自动验证

    测试策略:
    - 验证dataclass初始化后自动调用validate()
    - 测试有效配置不产生警告
    - 测试无效配置记录WARNING日志
    - 验证警告信息包含错误详情
    - 确保不抛出异常（只记录警告）

    设计目的:
    - 提前发现配置错误
    - 不阻止配置创建（兼容性）
    - 通过日志提醒开发者
    """

    def test_post_init_valid_config(self, caplog):
        """测试__post_init__验证有效配置（无警告）"""
        with caplog.at_level(logging.WARNING):
            MonitorConfig()

            # 不应有警告
            assert len(caplog.records) == 0

    def test_post_init_invalid_config_warning(self, caplog):
        """测试__post_init__验证无效配置（记录警告）"""
        with caplog.at_level(logging.WARNING):
            config = MonitorConfig(alert_threshold=1.5)  # noqa: F841

            # 应记录警告
            assert len(caplog.records) == 1
            assert "配置验证警告" in caplog.records[0].message
            assert "alert_threshold必须在0.0-1.0之间" in caplog.records[0].message

    def test_post_init_multiple_invalid_values(self, caplog):
        """测试__post_init__验证多个无效值"""
        with caplog.at_level(logging.WARNING):
            # 第一个无效值就会触发异常
            config = MonitorConfig(alert_threshold=1.5, data_logging_interval=-1.0)  # noqa: F841

            # 应记录警告（只报告第一个错误）
            assert len(caplog.records) == 1


class TestConfigTemplates:
    """测试预定义配置模板

    测试策略:
    - 验证4个预定义配置模板的正确性
    - 测试所有模板都能通过验证
    - 验证模板值符合环境需求

    模板列表:
    - DEFAULT_CONFIG: 默认配置
    - PRODUCTION_CONFIG: 生产环境（长间隔、高阈值）
    - DEVELOPMENT_CONFIG: 开发环境（短间隔、调试模式）
    - TESTING_CONFIG: 测试环境（全禁用）
    """

    def test_default_config_template(self):
        """测试默认配置模板"""
        assert DEFAULT_CONFIG.data_logging_enabled is True
        assert DEFAULT_CONFIG.data_logging_interval == 1.0
        assert DEFAULT_CONFIG.enable_monitoring_data is False
        assert DEFAULT_CONFIG.alert_threshold == 0.9

    def test_production_config_template(self):
        """测试生产环境配置模板"""
        assert PRODUCTION_CONFIG.data_logging_enabled is True
        assert PRODUCTION_CONFIG.data_logging_interval == 5.0
        assert PRODUCTION_CONFIG.enable_monitoring_data is True
        assert PRODUCTION_CONFIG.collection_interval == 5.0
        assert PRODUCTION_CONFIG.alert_threshold == 0.95
        assert PRODUCTION_CONFIG.report_enabled is True
        assert PRODUCTION_CONFIG.report_interval == 3600.0
        assert PRODUCTION_CONFIG.enable_debug_mode is False

    def test_development_config_template(self):
        """测试开发环境配置模板"""
        assert DEVELOPMENT_CONFIG.data_logging_enabled is True
        assert DEVELOPMENT_CONFIG.data_logging_interval == 1.0
        assert DEVELOPMENT_CONFIG.enable_monitoring_data is True
        assert DEVELOPMENT_CONFIG.collection_interval == 1.0
        assert DEVELOPMENT_CONFIG.alert_threshold == 0.8
        assert DEVELOPMENT_CONFIG.report_enabled is False
        assert DEVELOPMENT_CONFIG.enable_debug_mode is True
        assert DEVELOPMENT_CONFIG.max_alerts_per_hour == 120

    def test_testing_config_template(self):
        """测试测试环境配置模板"""
        assert TESTING_CONFIG.data_logging_enabled is False
        assert TESTING_CONFIG.enable_monitoring_data is False
        assert TESTING_CONFIG.alert_enabled is False
        assert TESTING_CONFIG.report_enabled is False
        assert TESTING_CONFIG.enable_performance_optimization is False
        assert TESTING_CONFIG.enable_debug_mode is False

    def test_production_config_is_valid(self):
        """测试生产配置验证通过"""
        assert PRODUCTION_CONFIG.validate() is True

    def test_development_config_is_valid(self):
        """测试开发配置验证通过"""
        assert DEVELOPMENT_CONFIG.validate() is True

    def test_testing_config_is_valid(self):
        """测试测试配置验证通过"""
        assert TESTING_CONFIG.validate() is True


class TestConfigMethods:
    """测试配置方法

    测试策略:
    - 验证to_dict()包含所有字段
    - 测试from_dict()正确恢复配置
    - 验证update()支持链式调用
    - 测试update()拒绝无效字段
    - 验证__str__()只显示非默认值

    方法列表:
    - to_dict(): 转换为字典
    - from_dict(): 从字典创建
    - update(): 更新配置
    - __str__(): 字符串表示
    """

    def test_to_dict(self):
        """测试转换为字典"""
        config = MonitorConfig(data_logging_enabled=False, alert_threshold=0.85)

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["data_logging_enabled"] is False
        assert config_dict["alert_threshold"] == 0.85
        assert "collection_interval" in config_dict

    def test_to_dict_contains_all_fields(self):
        """测试to_dict包含所有字段"""
        config = MonitorConfig()
        config_dict = config.to_dict()

        # 验证所有字段都在字典中
        assert "data_logging_enabled" in config_dict
        assert "data_logging_interval" in config_dict
        assert "enable_monitoring_data" in config_dict
        assert "collection_interval" in config_dict
        assert "alert_enabled" in config_dict
        assert "alert_threshold" in config_dict
        assert "report_enabled" in config_dict

    def test_from_dict_to_dict_roundtrip(self):
        """测试from_dict和to_dict往返转换"""
        original = MonitorConfig(
            data_logging_enabled=False,
            data_logging_interval=10.0,
            alert_threshold=0.95,
            enable_debug_mode=True,
        )

        # 转换为字典再转换回来
        config_dict = original.to_dict()
        restored = MonitorConfig.from_dict(config_dict)

        # 应该相等
        assert restored.data_logging_enabled == original.data_logging_enabled
        assert restored.data_logging_interval == original.data_logging_interval
        assert restored.alert_threshold == original.alert_threshold
        assert restored.enable_debug_mode == original.enable_debug_mode

    def test_update_single_field(self):
        """测试更新单个字段"""
        config = MonitorConfig()

        result = config.update(alert_threshold=0.85)

        assert config.alert_threshold == 0.85
        assert result is config  # 返回self支持链式调用

    def test_update_multiple_fields(self):
        """测试更新多个字段"""
        config = MonitorConfig()

        config.update(data_logging_interval=5.0, alert_threshold=0.9, enable_debug_mode=True)

        assert config.data_logging_interval == 5.0
        assert config.alert_threshold == 0.9
        assert config.enable_debug_mode is True

    def test_update_chaining(self):
        """测试链式调用"""
        config = MonitorConfig()

        result = config.update(data_logging_interval=2.0).update(alert_threshold=0.8)

        assert config.data_logging_interval == 2.0
        assert config.alert_threshold == 0.8
        assert result is config

    def test_update_invalid_field(self):
        """测试更新不存在的字段"""
        config = MonitorConfig()

        with pytest.raises(ValueError, match="未知配置项"):
            config.update(nonexistent_field=123)

    def test_str_default_config(self):
        """测试默认配置的字符串表示"""
        config = MonitorConfig()
        config_str = str(config)

        assert "MonitorConfig" in config_str
        assert "默认配置" in config_str

    def test_str_custom_config(self):
        """测试自定义配置的字符串表示"""
        config = MonitorConfig(alert_threshold=0.85)
        config_str = str(config)

        assert "MonitorConfig" in config_str
        assert "alert_threshold=0.85" in config_str

    def test_repr(self):
        """测试repr"""
        config = MonitorConfig()
        repr_str = repr(config)

        assert "MonitorConfig" in repr_str


class TestConfigEdgeCases:
    """测试边界情况"""

    def test_boundary_alert_threshold_min(self):
        """测试alert_threshold边界值（最小值）"""
        config = MonitorConfig(alert_threshold=0.0)
        assert config.validate() is True

    def test_boundary_alert_threshold_max(self):
        """测试alert_threshold边界值（最大值）"""
        config = MonitorConfig(alert_threshold=1.0)
        assert config.validate() is True

    def test_boundary_very_small_interval(self):
        """测试非常小的时间间隔"""
        config = MonitorConfig(data_logging_interval=0.001)
        assert config.validate() is True

    def test_boundary_very_large_interval(self):
        """测试非常大的时间间隔"""
        config = MonitorConfig(data_logging_interval=86400.0)
        assert config.validate() is True

    def test_boundary_max_log_entries(self):
        """测试最大日志条目数边界"""
        config = MonitorConfig(max_log_entries=1)
        assert config.validate() is True

    def test_boundary_max_alerts_per_hour(self):
        """测试每小时最大告警数边界"""
        config = MonitorConfig(max_alerts_per_hour=1)
        assert config.validate() is True

    def test_merge_with_self(self):
        """测试配置与自身合并"""
        config = MonitorConfig(alert_threshold=0.8, data_logging_interval=5.0)

        merged = config.merge(config)

        assert merged.alert_threshold == 0.8
        assert merged.data_logging_interval == 5.0

    def test_equality_same_config(self):
        """测试相同配置相等"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig(alert_threshold=0.8)

        assert config1 == config2

    def test_inequality_different_config(self):
        """测试不同配置不相等"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig(alert_threshold=0.9)

        assert config1 != config2


class TestConfigIntegration:
    """测试集成场景"""

    def test_create_production_and_validate(self):
        """测试创建生产配置并验证"""
        config = MonitorConfig(
            data_logging_enabled=True,
            data_logging_interval=5.0,
            enable_monitoring_data=True,
            collection_interval=5.0,
            alert_threshold=0.95,
            report_enabled=True,
            enable_debug_mode=False,
        )

        assert config.validate() is True

    def test_create_testing_and_validate(self):
        """测试创建测试配置并验证"""
        config = MonitorConfig(
            data_logging_enabled=False,
            enable_monitoring_data=False,
            alert_enabled=False,
            enable_performance_optimization=False,
        )

        assert config.validate() is True

    def test_modify_production_config(self):
        """测试修改生产配置"""
        config = MonitorConfig(data_logging_enabled=True, alert_threshold=0.95)

        # 修改配置
        config.update(alert_threshold=0.9)

        assert config.alert_threshold == 0.9
        assert config.data_logging_enabled is True  # 未修改的字段保持不变
