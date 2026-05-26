"""数据监控器测试

测试DataMonitor类的功能:
- 数据报告
- 质量验证
- 异常检测
- 统计收集
"""

import time

import pytest

from src.gpu.data_monitor import DataMonitor, DataQualityIssue


class TestDataMonitor:
    """测试数据监控器"""

    def setUp(self):
        """设置测试环境"""
        self.monitor = DataMonitor(
            config={
                "check_interval": 0.5,  # 加快测试
                "throughput_threshold": 0.5,
                "error_rate_threshold": 0.1,
                "stale_data_timeout": 2.0,
            },
        )

    def tearDown(self):
        """清理测试环境"""
        self.monitor.stop()

    def test_monitor_start_stop(self):
        """测试监控器启动和停止"""
        self.monitor.start()
        assert self.monitor._running

        self.monitor.stop()
        assert not self.monitor._running

    def test_report_keys_generated(self):
        """测试报告私钥生成"""
        self.monitor.start()

        self.monitor.report_keys_generated(device_idx=0, count=1000, key_range=(0, 1000))

        stats = self.monitor.get_stats()
        assert stats["total_keys_monitored"]  ==  1000
        assert stats["devices"][0]["total_keys"]  ==  1000

    def test_report_match(self):
        """测试报告匹配结果"""
        self.monitor.start()

        match_data = {
            "private_key": "a" * 64,
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "hash": "b" * 64,
            "target_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        self.monitor.report_match(device_idx=0, match_data=match_data)

        stats = self.monitor.get_stats()
        assert stats["total_matches_verified"]  ==  1
        assert stats["devices"][0]["total_matches"]  ==  1

    def test_report_error(self):
        """测试报告错误"""
        self.monitor.start()

        self.monitor.report_error(device_idx=0, error_msg="测试错误", error_type="test_error")

        stats = self.monitor.get_stats()
        assert stats["devices"][0]["total_errors"]  ==  1

    def test_detect_duplicate_key(self):
        """测试检测重复私钥"""
        self.monitor.start()

        match_data = {
            "private_key": "a" * 64,
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        # 第一次报告
        self.monitor.report_match(device_idx=0, match_data=match_data)

        # 第二次报告(重复)
        self.monitor.report_match(device_idx=0, match_data=match_data)

        # 应该检测到重复
        issues = self.monitor.get_issues()
        duplicate_issues = [i for i in issues if i["issue_type"] == DataQualityIssue.DUPLICATE_KEY]

        assert len(duplicate_issues)  >  0

    def test_detect_invalid_key(self):
        """测试检测无效私钥"""
        self.monitor.start()

        match_data = {
            "private_key": "short",  # 长度不正确
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        self.monitor.report_match(device_idx=0, match_data=match_data)

        issues = self.monitor.get_issues()
        invalid_issues = [i for i in issues if i["issue_type"] == DataQualityIssue.INVALID_KEY]

        assert len(invalid_issues)  >  0

    def test_detect_stale_data(self):
        """测试检测过期数据"""
        self.monitor.start()

        # 报告一次数据
        self.monitor.report_keys_generated(device_idx=0, count=100)

        # 等待超过stale_data_timeout
        time.sleep(3)

        # 监控器应该检测到数据过期
        issues = self.monitor.get_issues()
        stale_issues = [i for i in issues if i["issue_type"] == DataQualityIssue.STALE_DATA]

        assert len(stale_issues)  >  0

    def test_throughput_tracking(self):
        """测试吞吐量跟踪"""
        self.monitor.start()

        # 报告多次数据生成
        for _i in range(10):
            self.monitor.report_keys_generated(device_idx=0, count=1000)
            time.sleep(0.1)

        stats = self.monitor.get_stats()
        avg_throughput = stats["devices"][0]["avg_throughput"]

        # 应该有正的吞吐量
        assert avg_throughput  >  0

    def test_anomaly_callback(self):
        """测试异常回调"""
        anomalies = []

        def callback(device_idx, issue):
            anomalies.append((device_idx, issue))

        self.monitor.start(anomaly_callback=callback)

        # 触发一个异常
        match_data = {
            "private_key": "invalid",
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        self.monitor.report_match(device_idx=0, match_data=match_data)

        # 等待回调执行
        time.sleep(0.5)

        assert len(anomalies)  >  0
        assert anomalies[0][0]  ==  0

    def test_get_issues_filter(self):
        """测试问题过滤"""
        self.monitor.start()

        # 触发不同类型的问题
        # _validate_match 检查 private_key_hash (SHA256 hexdigest: 64 chars)，而非 private_key
        self.monitor.report_match(
            device_idx=0,
            match_data={
                "private_key_hash": "short",  # 5 chars，不符合 64 字符要求
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            },
        )

        self.monitor.report_match(
            device_idx=1,
            match_data={
                "private_key_hash": "a" * 64,  # 64 chars 有效 hex
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            },
        )

        # 按设备过滤
        issues_device0 = self.monitor.get_issues(device_idx=0)
        issues_device1 = self.monitor.get_issues(device_idx=1)

        assert len(issues_device0)  >  0
        assert len(issues_device1)  ==  0  # 设备1没有问题

    def test_validation_statistics(self):
        """测试验证统计"""
        self.monitor.start()

        self.monitor.report_validation_result(device_idx=0, passed=True)
        self.monitor.report_validation_result(device_idx=0, passed=True)
        self.monitor.report_validation_result(device_idx=0, passed=False)

        stats = self.monitor.get_stats()
        assert stats["total_validations"]  ==  3
        assert stats["validation_pass_rate"] == pytest.approx(2 / 3, abs=10**-2)

    def test_monitor_thread_runs_independently(self):
        """测试监控线程独立运行"""
        self.monitor.start()

        # 主线程不应该被阻塞
        start_time = time.time()

        for _i in range(100):
            self.monitor.report_keys_generated(device_idx=0, count=1)

        elapsed = time.time() - start_time

        # 应该非常快(<0.1秒)
        assert elapsed  <  0.1

    def test_issue_severity_levels(self):
        """测试问题严重级别"""
        self.monitor.start()

        # 创建不同严重级别的问题
        issue_low = DataQualityIssue(issue_type="test", severity="low", message="低级别", device_idx=0)

        issue_critical = DataQualityIssue(
            issue_type="test",
            severity="critical",
            message="严重级别",
            device_idx=0,
        )

        self.monitor._record_issue(issue_low)
        self.monitor._record_issue(issue_critical)

        # 按严重级别过滤
        low_issues = self.monitor.get_issues(severity="low")
        critical_issues = self.monitor.get_issues(severity="critical")

        assert len(low_issues)  ==  1
        assert len(critical_issues)  ==  1


class TestDataQualityIssue:
    """测试数据质量问题类"""

    def test_issue_creation(self):
        """测试问题创建"""
        issue = DataQualityIssue(
            issue_type=DataQualityIssue.INVALID_KEY,
            severity="high",
            message="测试问题",
            device_idx=0,
            details={"key": "value"},
        )

        assert issue.issue_type  ==  DataQualityIssue.INVALID_KEY
        assert issue.severity  ==  "high"
        assert issue.device_idx  ==  0
        assert issue.timestamp is not None
        assert issue.datetime is not None

    def test_issue_to_dict(self):
        """测试问题转字典"""
        issue = DataQualityIssue(issue_type="test", severity="medium", message="测试", device_idx=1)

        issue_dict = issue.to_dict()

        assert isinstance(issue_dict, dict)
        assert issue_dict["issue_type"]  ==  "test"
        assert issue_dict["severity"]  ==  "medium"
        assert issue_dict["device_idx"]  ==  1
        assert issue_dict  in  "timestamp"
        assert issue_dict  in  "datetime"

