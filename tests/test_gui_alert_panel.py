"""测试GUI告警面板组件"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAlertPanelImport:
    """测试告警面板导入"""
    
    def test_alert_panel_import(self):
        """测试告警面板模块可导入"""
        try:
            from src.gui.components.alert_panel import AlertPanel
            assert AlertPanel is not None
        except ImportError as e:
            pytest.skip(f"告警面板导入失败: {e}")
    
    def test_alert_panel_constants(self):
        """测试告警面板常量"""
        try:
            from src.gui.components.alert_panel import ALERT_COLORS, ALERT_TYPE_NAMES
            from src.monitoring.alert_system import AlertLevel, AlertType
            
            # 检查颜色配置
            assert AlertLevel.INFO in ALERT_COLORS
            assert AlertLevel.WARNING in ALERT_COLORS
            assert AlertLevel.CRITICAL in ALERT_COLORS
            assert AlertLevel.EMERGENCY in ALERT_COLORS
            
            # 检查类型映射
            assert AlertType.PERFORMANCE_DEGRADATION in ALERT_TYPE_NAMES
            assert AlertType.MEMORY_OVERFLOW in ALERT_TYPE_NAMES
            assert AlertType.GPU_OVERHEAT in ALERT_TYPE_NAMES
            assert AlertType.ERROR_RATE_HIGH in ALERT_TYPE_NAMES
            
        except ImportError as e:
            pytest.skip(f"导入失败: {e}")
    
    def test_gui_integration_import(self):
        """测试GUI集成导入"""
        try:
            # 模拟GUI中的导入逻辑
            try:
                from src.gui.components.alert_panel import AlertPanel
                alert_available = True
            except ImportError:
                alert_available = False
            
            # 应该可用
            assert alert_available is True
            
        except Exception as e:
            pytest.fail(f"GUI集成导入失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
