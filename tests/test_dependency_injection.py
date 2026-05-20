#!/usr/bin/env python3
"""
测试依赖注入修复 - 验证空指针问题已解决
"""

import os
import sys
import tempfile
from unittest.mock import Mock

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.monitoring.monitoring_system import (  # noqa: E402
    AnomalyDetector,
    DataStorage,
    MonitoringData,
    MonitoringSystem,
    ReportGenerator,
)
from src.monitoring.monitoring_system import (
    MonitoringAlertAdapter as AlertSystem,
)


class TestDependencyInjectionFix:
    """测试依赖注入修复"""

    def test_anomaly_detector_without_storage(self):
        """测试AnomalyDetector在没有storage时正常工作"""
        # 不应抛出异常
        detector = AnomalyDetector()

        # 验证storage为None
        assert detector.storage is None

        # 检测功能应正常工作
        data = MonitoringData()
        data.performance["speed"] = 50  # 低于阈值
        data.engine["is_running"] = True

        anomalies = detector.detect_anomalies(data)

        # 应检测到异常
        assert len(anomalies) > 0
        assert any(a["metric"] == "speed" for a in anomalies)

    def test_anomaly_detector_with_storage(self):
        """测试AnomalyDetector在有storage时保存异常记录"""
        # 创建mock storage
        mock_storage = Mock(spec=DataStorage)
        mock_storage.save_error = Mock()

        detector = AnomalyDetector(storage=mock_storage)

        # 检测异常
        data = MonitoringData()
        data.performance["speed"] = 50
        data.engine["is_running"] = True

        anomalies = detector.detect_anomalies(data)

        # 应检测到异常
        assert len(anomalies) > 0

        # 应调用save_error保存异常记录
        mock_storage.save_error.assert_called_once()
        call_args = mock_storage.save_error.call_args[0][0]
        assert call_args["type"] == "anomaly_detection"
        assert call_args["level"] == "warning"

    def test_alert_system_without_storage(self):
        """测试AlertSystem在没有storage时正常工作"""
        # 不应抛出异常
        alert_system = AlertSystem()

        # 验证storage为None
        assert alert_system.storage is None

        # 告警功能应正常工作
        anomaly = {"type": "performance", "metric": "speed", "message": "检测速率过低: 50.00/s"}

        # 不应抛出异常
        alert_system.generate_alert(anomaly)

        # 告警历史应包含该告警
        assert len(alert_system.alert_history) == 1
        assert alert_system.alert_history[0]["message"] == anomaly["message"]

    def test_alert_system_with_storage(self):
        """测试AlertSystem在有storage时保存告警记录"""
        # 创建mock storage
        mock_storage = Mock(spec=DataStorage)
        mock_storage.save_error = Mock()

        alert_system = AlertSystem(storage=mock_storage)

        # 生成告警
        anomaly = {"type": "performance", "metric": "speed", "message": "检测速率过低: 50.00/s"}

        alert_system.generate_alert(anomaly)

        # 应调用save_error保存告警记录
        mock_storage.save_error.assert_called_once()
        call_args = mock_storage.save_error.call_args[0][0]
        assert call_args["type"] == "alert"
        assert call_args["level"] == "warning"

    def test_report_generator_without_dependencies(self):
        """测试ReportGenerator在没有依赖时返回错误而不是崩溃"""
        # 不应抛出异常
        generator = ReportGenerator()

        # 验证依赖为None
        assert generator.storage is None
        assert generator.detector is None

        # 生成报告应返回错误信息而不是崩溃
        result = generator.generate_daily_report()

        # 应返回错误信息
        assert "error" in result
        assert "storage未初始化" in result["error"]

    def test_report_generator_without_detector(self):
        """测试ReportGenerator在没有detector时使用降级方案"""
        # 创建临时目录作为storage
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = DataStorage(storage_dir=temp_dir)

            # 只传入storage，不传detector
            generator = ReportGenerator(storage=storage, detector=None)

            # 添加一些测试数据
            from datetime import datetime, timedelta

            # 创建今天的数据
            today = datetime.now()
            test_data = []
            for i in range(20):
                timestamp = (today - timedelta(hours=i)).timestamp()
                test_data.append(
                    {
                        "timestamp": timestamp,
                        "performance": {
                            "speed": 1000 + i * 10,
                            "total_checked": 10000 + i * 100,
                            "matches_found": 0,
                            "cpu_usage": 50.0,
                            "memory_usage": 256.0,
                        },
                    }
                )

            # 写入历史数据
            history_file = os.path.join(temp_dir, "history_data.json")
            import json

            with open(history_file, "w") as f:
                json.dump(test_data, f)

            # 生成报告 - 不应崩溃
            result = generator.generate_daily_report()

            # 应成功生成报告（使用降级方案）
            assert "error" not in result or result.get("message") == "今天暂无数据"
            if "date" in result:
                assert "trends" in result
                # 趋势分析应使用简单方案
                assert "speed" in result["trends"]

    def test_report_generator_with_all_dependencies(self):
        """测试ReportGenerator在所有依赖齐全时正常工作"""
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = DataStorage(storage_dir=temp_dir)
            detector = AnomalyDetector(storage=storage)

            # 所有依赖齐全
            generator = ReportGenerator(storage=storage, detector=detector)

            # 添加测试数据
            import json
            from datetime import datetime, timedelta

            today = datetime.now()
            test_data = []
            for i in range(20):
                timestamp = (today - timedelta(hours=i)).timestamp()
                test_data.append(
                    {
                        "timestamp": timestamp,
                        "performance": {
                            "speed": 1000 + i * 10,
                            "total_checked": 10000 + i * 100,
                            "matches_found": 0,
                            "cpu_usage": 50.0,
                            "memory_usage": 256.0,
                        },
                    }
                )

            # 写入历史数据
            history_file = os.path.join(temp_dir, "history_data.json")
            with open(history_file, "w") as f:
                json.dump(test_data, f)

            # 生成报告
            result = generator.generate_daily_report()

            # 应成功生成报告
            assert "error" not in result
            if "date" in result:
                assert "trends" in result
                assert "summary" in result
                assert "recommendations" in result

    def test_monitoring_system_integration(self):
        """测试MonitoringSystem正确集成所有依赖"""
        # MonitoringSystem应正确传递所有依赖
        monitoring = MonitoringSystem(engine=None, collection_interval=5)

        # 验证依赖已正确初始化
        assert monitoring.storage is not None
        assert monitoring.detector is not None
        assert monitoring.detector.storage is monitoring.storage  # 同一个实例
        assert monitoring.alert_system is not None
        assert monitoring.alert_system.storage is monitoring.storage  # 同一个实例
        assert monitoring.report_generator is not None
        assert monitoring.report_generator.storage is monitoring.storage
        assert monitoring.report_generator.detector is monitoring.detector


class TestOptionalTypeHints:
    """测试Optional类型提示"""

    def test_anomaly_detector_type_hint(self):
        """测试AnomalyDetector的类型提示"""
        import inspect

        sig = inspect.signature(AnomalyDetector.__init__)
        storage_param = sig.parameters.get("storage")

        # 参数应有默认值None
        assert storage_param is not None
        assert storage_param.default is None

    def test_alert_system_type_hint(self):
        """测试AlertSystem的类型提示"""
        import inspect

        sig = inspect.signature(AlertSystem.__init__)
        storage_param = sig.parameters.get("storage")

        assert storage_param is not None
        assert storage_param.default is None

    def test_report_generator_type_hints(self):
        """测试ReportGenerator的类型提示"""
        import inspect

        sig = inspect.signature(ReportGenerator.__init__)

        storage_param = sig.parameters.get("storage")
        detector_param = sig.parameters.get("detector")

        assert storage_param is not None
        assert storage_param.default is None
        assert detector_param is not None
        assert detector_param.default is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
