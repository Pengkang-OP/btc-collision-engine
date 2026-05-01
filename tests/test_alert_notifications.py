"""测试告警通知回调模块"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.alert_notifications import (
    BaseNotifier,
    EmailNotifier,
    WeComWebhookNotifier,
    DingTalkWebhookNotifier,
    SlackWebhookNotifier,
)
from src.monitoring.alert_system import AlertRecord, AlertLevel, AlertType


class TestBaseNotifier:
    """测试基础通知器"""

    def test_base_notifier_disabled(self):
        """测试禁用状态 — 通过子类验证"""

        # ABC 不可直接实例化，使用最小子类
        class MinimalNotifier(BaseNotifier):
            def _send_notification(self, alert):
                pass  # 最小实现，仅用于测试基类行为

        notifier = MinimalNotifier(enabled=False)

        # 禁用状态下send不应调用_send_notification
        alert = Mock()
        notifier.send(alert)

    def test_base_notifier_is_abstract(self):
        """测试基类不可直接实例化 (ABC)"""
        with pytest.raises(TypeError, match="abstract"):
            BaseNotifier(enabled=True)


class TestEmailNotifier:
    """测试邮件通知器"""

    def test_email_notifier_init(self):
        """测试初始化"""
        notifier = EmailNotifier(
            smtp_server="smtp.example.com",
            smtp_port=587,
            username="test@example.com",
            password="password",
            recipients=["admin@example.com"],
        )

        assert notifier.smtp_server == "smtp.example.com"
        assert notifier.smtp_port == 587
        assert notifier.username == "test@example.com"
        assert notifier.recipients == ["admin@example.com"]

    def test_email_notifier_no_recipients(self):
        """测试无收件人"""
        notifier = EmailNotifier(smtp_server="smtp.example.com", recipients=[])

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="测试告警",
            metrics={"throughput": 1000000},
        )

        # 不应抛出异常
        notifier.send(alert)

    @patch("smtplib.SMTP")
    def test_email_send_success(self, mock_smtp):
        """测试邮件发送成功"""
        notifier = EmailNotifier(
            smtp_server="smtp.example.com",
            smtp_port=587,
            username="test@example.com",
            password="password",
            recipients=["admin@example.com"],
        )

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value = mock_server

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="GPU性能退化超过20%",
            metrics={"throughput": 1000000, "degradation_rate": 25.0},
        )

        # 发送不应抛出异常
        notifier.send(alert)

        # 验证SMTP调用
        mock_smtp.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_email_create_subject(self):
        """测试邮件主题创建"""
        notifier = EmailNotifier(smtp_server="smtp.example.com", recipients=["admin@example.com"])

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            level=AlertLevel.WARNING,
            message="GPU性能退化超过20%",
            metrics={},
        )

        subject = notifier._create_subject(alert)
        assert "WARNING" in subject
        assert "GPU性能退化超过20%" in subject


class TestWeComWebhookNotifier:
    """测试企业微信Webhook通知器"""

    def test_wecom_notifier_init(self):
        """测试初始化"""
        notifier = WeComWebhookNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            mentioned_list=["@all"],
        )

        assert "qyapi.weixin.qq.com" in notifier.webhook_url
        assert notifier.mentioned_list == ["@all"]

    @patch("requests.post")
    def test_wecom_send_success(self, mock_post):
        """测试发送成功"""
        notifier = WeComWebhookNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.ERROR_RATE_HIGH,
            level=AlertLevel.CRITICAL,
            message="错误率超过5%",
            metrics={"error_rate": 0.08},
        )

        # 发送不应抛出异常
        notifier.send(alert)

        # 验证请求
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "markdown" in call_args.kwargs["json"]["msgtype"]

    @patch("requests.post")
    def test_wecom_send_failure(self, mock_post):
        """测试发送失败"""
        notifier = WeComWebhookNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        # Mock错误响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 93000, "errmsg": "invalid webhook url"}
        mock_post.return_value = mock_response

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.ERROR_RATE_HIGH,
            level=AlertLevel.CRITICAL,
            message="错误率超过5%",
            metrics={},
        )

        # 应捕获异常
        with pytest.raises(Exception):
            notifier._send_notification(alert)


class TestDingTalkWebhookNotifier:
    """测试钉钉Webhook通知器"""

    def test_dingtalk_notifier_init(self):
        """测试初始化"""
        notifier = DingTalkWebhookNotifier(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            at_mobiles=["13800138000"],
            at_all=True,
        )

        assert "oapi.dingtalk.com" in notifier.webhook_url
        assert notifier.at_mobiles == ["13800138000"]
        assert notifier.at_all is True

    @patch("requests.post")
    def test_dingtalk_send_success(self, mock_post):
        """测试发送成功"""
        notifier = DingTalkWebhookNotifier(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.GPU_OVERHEAT,
            level=AlertLevel.CRITICAL,
            message="GPU温度超过85°C",
            metrics={"gpu_temperature": 90.0},
        )

        # 发送不应抛出异常
        notifier.send(alert)

        # 验证请求
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "markdown" in call_args.kwargs["json"]["msgtype"]


class TestSlackWebhookNotifier:
    """测试Slack Webhook通知器"""

    def test_slack_notifier_init(self):
        """测试初始化"""
        notifier = SlackWebhookNotifier(
            webhook_url="https://hooks.slack.com/services/xxx",
            channel="#alerts",
            username="GPU Alert Bot",
        )

        assert "hooks.slack.com" in notifier.webhook_url
        assert notifier.channel == "#alerts"
        assert notifier.username == "GPU Alert Bot"

    @patch("requests.post")
    def test_slack_send_success(self, mock_post):
        """测试发送成功"""
        notifier = SlackWebhookNotifier(webhook_url="https://hooks.slack.com/services/xxx")

        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_post.return_value = mock_response

        alert = AlertRecord(
            timestamp="2026-04-21T22:00:00",
            alert_type=AlertType.THROUGHPUT_DROP,
            level=AlertLevel.CRITICAL,
            message="吞吐量下降超过50%",
            metrics={"throughput": 500000},
        )

        # 发送不应抛出异常
        notifier.send(alert)

        # 验证请求
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "attachments" in call_args.kwargs["json"]


class TestNotifierIntegration:
    """测试通知器集成"""

    def test_multiple_notifiers(self):
        """测试多个通知器"""
        notifiers = [
            EmailNotifier("smtp.example.com", recipients=["admin@example.com"]),
            WeComWebhookNotifier("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"),
            DingTalkWebhookNotifier("https://oapi.dingtalk.com/robot/send?access_token=xxx"),
            SlackWebhookNotifier("https://hooks.slack.com/services/xxx"),
        ]

        # 所有通知器都应初始化成功
        assert len(notifiers) == 4
        for notifier in notifiers:
            assert notifier.enabled is True

    def test_notifier_disabled(self):
        """测试禁用通知器"""
        notifier = EmailNotifier(smtp_server="smtp.example.com", enabled=False)

        assert notifier.enabled is False


class TestHealthCheck:
    """测试健康检查功能"""

    @patch("smtplib.SMTP")
    def test_email_health_check_success(self, mock_smtp):
        """测试邮件健康检查成功"""
        notifier = EmailNotifier(smtp_server="smtp.example.com", smtp_port=587)

        mock_server = Mock()
        mock_smtp.return_value = mock_server

        result = notifier.health_check()

        assert result is True
        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=5)
        mock_server.quit.assert_called_once()

    @patch("smtplib.SMTP")
    def test_email_health_check_failure(self, mock_smtp):
        """测试邮件健康检查失败"""
        notifier = EmailNotifier(smtp_server="invalid.smtp.com", smtp_port=587)

        mock_smtp.side_effect = Exception("Connection refused")

        result = notifier.health_check()

        assert result is False

    @patch("requests.post")
    def test_wecom_health_check_success(self, mock_post):
        """测试企业微信健康检查成功"""
        notifier = WeComWebhookNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = notifier.health_check()

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["timeout"] == 5

    @patch("requests.post")
    def test_wecom_health_check_failure(self, mock_post):
        """测试企业微信健康检查失败"""
        notifier = WeComWebhookNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        mock_post.side_effect = Exception("Connection timeout")

        result = notifier.health_check()

        assert result is False

    @patch("requests.post")
    def test_dingtalk_health_check_success(self, mock_post):
        """测试钉钉健康检查成功"""
        notifier = DingTalkWebhookNotifier(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = notifier.health_check()

        assert result is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_slack_health_check_success(self, mock_post):
        """测试Slack健康检查成功"""
        notifier = SlackWebhookNotifier(webhook_url="https://hooks.slack.com/services/xxx")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = notifier.health_check()

        assert result is True
        mock_post.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
