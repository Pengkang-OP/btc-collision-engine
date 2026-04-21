"""MonitorConfig单元测试

测试MonitorConfig配置对象的所有功能:
- 初始化和默认值
- validate()验证
- from_dict/to_dict序列化
- update()更新
- merge()合并
- __str__()字符串表示
- 预定义配置模板

创建日期: 2026-04-22
"""
import pytest
from src.monitoring.monitor_config import (
    MonitorConfig,
    DEFAULT_CONFIG,
    PRODUCTION_CONFIG,
    DEVELOPMENT_CONFIG,
    TESTING_CONFIG
)


class TestMonitorConfigInitialization:
    """测试MonitorConfig初始化"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = MonitorConfig()
        
        assert config.data_logging_enabled is True
        assert config.data_logging_interval == 1.0
        assert config.enable_monitoring_data is False
        assert config.collection_interval == 1.0
        assert config.alert_enabled is True
        assert config.alert_threshold == 0.9
        assert config.report_enabled is False
        assert config.report_interval == 3600.0
        assert config.enable_debug_mode is False
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = MonitorConfig(
            data_logging_enabled=False,
            collection_interval=5.0,
            alert_threshold=0.85
        )
        
        assert config.data_logging_enabled is False
        assert config.collection_interval == 5.0
        assert config.alert_threshold == 0.85
    
    def test_predefined_configs_exist(self):
        """测试预定义配置存在"""
        assert DEFAULT_CONFIG is not None
        assert PRODUCTION_CONFIG is not None
        assert DEVELOPMENT_CONFIG is not None
        assert TESTING_CONFIG is not None
    
    def test_production_config_values(self):
        """测试生产环境配置值"""
        assert PRODUCTION_CONFIG.data_logging_enabled is True
        assert PRODUCTION_CONFIG.data_logging_interval == 5.0
        assert PRODUCTION_CONFIG.enable_monitoring_data is True
        assert PRODUCTION_CONFIG.collection_interval == 5.0
        assert PRODUCTION_CONFIG.alert_threshold == 0.95
        assert PRODUCTION_CONFIG.report_enabled is True
        assert PRODUCTION_CONFIG.enable_debug_mode is False
    
    def test_testing_config_values(self):
        """测试环境配置值(最小化)"""
        assert TESTING_CONFIG.data_logging_enabled is False
        assert TESTING_CONFIG.enable_monitoring_data is False
        assert TESTING_CONFIG.alert_enabled is False
        assert TESTING_CONFIG.report_enabled is False
        assert TESTING_CONFIG.enable_performance_optimization is False


class TestMonitorConfigValidation:
    """测试MonitorConfig验证"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = MonitorConfig()
        assert config.validate() is True
    
    def test_invalid_alert_threshold_high(self):
        """测试alert_threshold过高"""
        config = MonitorConfig(alert_threshold=1.5)
        with pytest.raises(ValueError, match="alert_threshold必须在0.0-1.0之间"):
            config.validate()
    
    def test_invalid_alert_threshold_low(self):
        """测试alert_threshold过低"""
        config = MonitorConfig(alert_threshold=-0.1)
        with pytest.raises(ValueError, match="alert_threshold必须在0.0-1.0之间"):
            config.validate()
    
    def test_invalid_data_logging_interval(self):
        """测试data_logging_interval无效"""
        config = MonitorConfig(data_logging_interval=-1.0)
        with pytest.raises(ValueError, match="data_logging_interval必须大于0"):
            config.validate()
    
    def test_invalid_collection_interval(self):
        """测试collection_interval无效"""
        config = MonitorConfig(collection_interval=0)
        with pytest.raises(ValueError, match="collection_interval必须大于0"):
            config.validate()
    
    def test_invalid_gpu_monitoring_interval(self):
        """测试gpu_monitoring_interval无效"""
        config = MonitorConfig(gpu_monitoring_interval=-5.0)
        with pytest.raises(ValueError, match="gpu_monitoring_interval必须大于0"):
            config.validate()
    
    def test_invalid_alert_cooldown(self):
        """测试alert_cooldown无效"""
        config = MonitorConfig(alert_cooldown=0)
        with pytest.raises(ValueError, match="alert_cooldown必须大于0"):
            config.validate()
    
    def test_invalid_report_interval(self):
        """测试report_interval无效"""
        config = MonitorConfig(report_interval=-3600.0)
        with pytest.raises(ValueError, match="report_interval必须大于0"):
            config.validate()
    
    def test_invalid_max_alerts_per_hour(self):
        """测试max_alerts_per_hour无效"""
        config = MonitorConfig(max_alerts_per_hour=-10)
        with pytest.raises(ValueError, match="max_alerts_per_hour必须大于0"):
            config.validate()
    
    def test_valid_boundary_values(self):
        """测试边界值"""
        config = MonitorConfig(
            alert_threshold=0.0,  # 最小值
            data_logging_interval=0.001,  # 接近0
            max_alerts_per_hour=1  # 最小值
        )
        assert config.validate() is True


class TestMonitorConfigSerialization:
    """测试MonitorConfig序列化"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = MonitorConfig(
            data_logging_enabled=False,
            collection_interval=5.0
        )
        
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['data_logging_enabled'] is False
        assert config_dict['collection_interval'] == 5.0
        assert len(config_dict) == 20  # 所有配置项
    
    def test_from_dict(self):
        """测试从字典创建"""
        config_dict = {
            'data_logging_enabled': False,
            'collection_interval': 5.0,
            'alert_threshold': 0.85
        }
        
        config = MonitorConfig.from_dict(config_dict)
        
        assert config.data_logging_enabled is False
        assert config.collection_interval == 5.0
        assert config.alert_threshold == 0.85
    
    def test_from_dict_with_invalid_fields(self):
        """测试从字典创建时过滤无效字段"""
        config_dict = {
            'data_logging_enabled': True,
            'invalid_field': 'value',  # 无效字段
            'collection_interval': 5.0
        }
        
        config = MonitorConfig.from_dict(config_dict)
        
        assert config.data_logging_enabled is True
        assert config.collection_interval == 5.0
        assert not hasattr(config, 'invalid_field')
    
    def test_round_trip(self):
        """测试序列化往返"""
        original = MonitorConfig(
            data_logging_enabled=False,
            collection_interval=10.0,
            alert_threshold=0.8
        )
        
        config_dict = original.to_dict()
        restored = MonitorConfig.from_dict(config_dict)
        
        assert restored.data_logging_enabled == original.data_logging_enabled
        assert restored.collection_interval == original.collection_interval
        assert restored.alert_threshold == original.alert_threshold


class TestMonitorConfigUpdate:
    """测试MonitorConfig更新"""
    
    def test_update_single_field(self):
        """测试更新单个字段"""
        config = MonitorConfig()
        config.update(data_logging_interval=2.0)
        
        assert config.data_logging_interval == 2.0
    
    def test_update_multiple_fields(self):
        """测试更新多个字段"""
        config = MonitorConfig()
        config.update(
            data_logging_interval=2.0,
            alert_enabled=False,
            collection_interval=5.0
        )
        
        assert config.data_logging_interval == 2.0
        assert config.alert_enabled is False
        assert config.collection_interval == 5.0
    
    def test_update_returns_self(self):
        """测试update返回self支持链式调用"""
        config = MonitorConfig()
        result = config.update(data_logging_interval=2.0)
        
        assert result is config
    
    def test_update_chain(self):
        """测试链式调用"""
        config = MonitorConfig()
        config.update(data_logging_interval=2.0).update(alert_enabled=False)
        
        assert config.data_logging_interval == 2.0
        assert config.alert_enabled is False
    
    def test_update_invalid_field(self):
        """测试更新无效字段"""
        config = MonitorConfig()
        
        with pytest.raises(ValueError, match="未知配置项"):
            config.update(invalid_field='value')


class TestMonitorConfigMerge:
    """测试MonitorConfig合并"""
    
    def test_merge_basic(self):
        """测试基本合并"""
        config1 = MonitorConfig(alert_threshold=0.8)
        config2 = MonitorConfig(alert_threshold=0.9)
        
        merged = config1.merge(config2)
        
        assert merged.alert_threshold == 0.9
    
    def test_merge_all_fields(self):
        """测试所有字段合并"""
        config1 = MonitorConfig(
            data_logging_enabled=True,
            collection_interval=1.0
        )
        config2 = MonitorConfig(
            data_logging_enabled=False,
            collection_interval=5.0
        )
        
        merged = config1.merge(config2)
        
        assert merged.data_logging_enabled is False
        assert merged.collection_interval == 5.0
    
    def test_merge_returns_new_instance(self):
        """测试merge返回新实例"""
        config1 = MonitorConfig()
        config2 = MonitorConfig(collection_interval=5.0)
        
        merged = config1.merge(config2)
        
        assert merged is not config1
        assert merged is not config2
    
    def test_merge_with_defaults(self):
        """测试合并时默认值也会覆盖"""
        config1 = MonitorConfig(collection_interval=10.0)
        config2 = MonitorConfig()  # 使用默认值1.0
        
        merged = config1.merge(config2)
        
        # config2的默认值会覆盖config1
        assert merged.collection_interval == 1.0


class TestMonitorConfigString:
    """测试MonitorConfig字符串表示"""
    
    def test_default_config_str(self):
        """测试默认配置字符串"""
        config = MonitorConfig()
        str_repr = str(config)
        
        assert "默认配置" in str_repr
    
    def test_custom_config_str(self):
        """测试自定义配置字符串"""
        config = MonitorConfig(
            data_logging_interval=2.0,
            alert_threshold=0.85
        )
        str_repr = str(config)
        
        assert "data_logging_interval=2.0" in str_repr
        assert "alert_threshold=0.85" in str_repr
    
    def test_str_shows_only_non_defaults(self):
        """测试字符串只显示非默认值"""
        config = MonitorConfig(
            data_logging_enabled=True,  # 默认值
            collection_interval=5.0  # 非默认值
        )
        str_repr = str(config)
        
        assert "collection_interval=5.0" in str_repr
        # data_logging_enabled是默认值,不应该显示
        assert "data_logging_enabled" not in str_repr


class TestMonitorConfigPostInit:
    """测试MonitorConfig的__post_init__"""
    
    def test_post_init_validates(self, caplog):
        """测试__post_init__自动验证"""
        # 创建无效配置应该触发警告但不阻止创建
        config = MonitorConfig(alert_threshold=1.5)
        
        # 验证警告日志
        assert "配置验证警告" in caplog.text
        assert "alert_threshold" in caplog.text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
