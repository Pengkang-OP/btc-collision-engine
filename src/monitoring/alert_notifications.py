"""告警通知回调模块

实现多种告警通知方式:
- 邮件通知 (SMTP)
- 企业微信Webhook
- 钉钉Webhook
- Slack Webhook

使用示例:
    from src.monitoring.alert_notifications import (
        EmailNotifier,
        WeComWebhookNotifier,
        DingTalkWebhookNotifier
    )
    
    # 邮件通知
    email_notifier = EmailNotifier(
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="alert@example.com",
        password="password",
        recipients=["admin@example.com"]
    )
    alert_system.add_alert_callback(email_notifier.send)
    
    # 企业微信Webhook
    webhook_notifier = WeComWebhookNotifier(
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
    )
    alert_system.add_alert_callback(webhook_notifier.send)
"""

import logging
import smtplib
import json
import os
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
from datetime import datetime

from .alert_system import AlertRecord, AlertLevel, AlertType

logger = logging.getLogger(__name__)

# 通知系统常量
HEALTH_CHECK_TIMEOUT = 5  # 健康检查超时(秒)
DEFAULT_WEBHOOK_TIMEOUT = 10  # 默认Webhook超时(秒)


class BaseNotifier:
    """通知器基类"""
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: 是否启用
        """
        self.enabled = enabled
    
    def send(self, alert: AlertRecord):
        """发送告警通知
        
        Args:
            alert: 告警记录
        """
        if not self.enabled:
            return
        
        try:
            self._send_notification(alert)
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")
    
    def _send_notification(self, alert: AlertRecord):
        """实际发送通知(子类实现)
        
        Args:
            alert: 告警记录
        """
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """检查通知器是否正常工作
        
        Returns:
            是否正常
        """
        return True  # 默认实现,子类可覆盖


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(self,
                 smtp_server: str,
                 smtp_port: int = 587,
                 username: str = "",
                 password: Optional[str] = None,
                 recipients: Optional[List[str]] = None,
                 use_tls: bool = True,
                 enabled: bool = True):
        """
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口(587=TLS, 465=SSL, 25=普通)
            username: 用户名
            password: 密码(优先使用环境变量SMTP_PASSWORD)
            recipients: 收件人列表
            use_tls: 是否使用TLS
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        # 优先使用环境变量,避免密码明文存储
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.recipients = recipients or []
        self.use_tls = use_tls
        
        logger.info(f"邮件通知器初始化: {smtp_server}:{smtp_port}")
    
    def _send_notification(self, alert: AlertRecord):
        """发送邮件通知"""
        if not self.recipients:
            logger.warning("收件人列表为空,跳过邮件发送")
            return
        
        # 创建邮件
        msg = MIMEMultipart('alternative')
        msg['From'] = self.username
        msg['To'] = ', '.join(self.recipients)
        msg['Subject'] = self._create_subject(alert)
        
        # 纯文本版本
        text_content = self._create_text_content(alert)
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        
        # HTML版本
        html_content = self._create_html_content(alert)
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 发送邮件
        try:
            if self.smtp_port == 465:
                # SSL连接
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
                server.login(self.username, self.password)
            else:
                # TLS或普通连接
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
            
            server.sendmail(self.username, self.recipients, msg.as_string())
            server.quit()
            
            logger.info(f"邮件通知已发送: {alert.message}")
            
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            raise
    
    def health_check(self) -> bool:
        """检查SMTP服务器是否可连接
        
        Returns:
            是否正常
        """
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=HEALTH_CHECK_TIMEOUT)
            server.quit()
            logger.debug(f"邮件通知器健康检查通过: {self.smtp_server}:{self.smtp_port}")
            return True
        except Exception as e:
            logger.error(f"邮件通知器健康检查失败: {e}")
            return False
    
    def _create_subject(self, alert: AlertRecord) -> str:
        """创建邮件主题"""
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.EMERGENCY: "🚨"
        }
        emoji = level_emoji.get(alert.level, "📢")
        return f"{emoji} [{alert.level.value.upper()}] {alert.message}"
    
    def _create_text_content(self, alert: AlertRecord) -> str:
        """创建纯文本内容"""
        content = f"""GPU告警通知

告警类型: {alert.alert_type.value}
告警级别: {alert.level.value.upper()}
触发时间: {alert.timestamp}
告警消息: {alert.message}

性能指标:
"""
        for key, value in alert.metrics.items():
            content += f"  {key}: {value}\n"
        
        content += f"\n解决状态: {'已解决' if alert.resolved else '未解决'}\n"
        if alert.resolved_at:
            content += f"解决时间: {alert.resolved_at}\n"
        
        return content
    
    def _create_html_content(self, alert: AlertRecord) -> str:
        """创建HTML内容"""
        level_colors = {
            AlertLevel.INFO: "#4FC3F7",
            AlertLevel.WARNING: "#FFB74D",
            AlertLevel.CRITICAL: "#EF5350",
            AlertLevel.EMERGENCY: "#FF1744"
        }
        color = level_colors.get(alert.level, "#9E9E9E")
        
        html = f"""
<html>
<body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
        <h2 style="color: {color}; border-bottom: 2px solid {color}; padding-bottom: 10px;">
            GPU告警通知
        </h2>
        
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; font-weight: bold; width: 120px;">告警类型:</td>
                <td style="padding: 8px;">{alert.alert_type.value}</td>
            </tr>
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 8px; font-weight: bold;">告警级别:</td>
                <td style="padding: 8px; color: {color}; font-weight: bold;">{alert.level.value.upper()}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">触发时间:</td>
                <td style="padding: 8px;">{alert.timestamp}</td>
            </tr>
            <tr style="background-color: #f9f9f9;">
                <td style="padding: 8px; font-weight: bold;">告警消息:</td>
                <td style="padding: 8px;">{alert.message}</td>
            </tr>
        </table>
        
        <h3 style="margin-top: 20px;">性能指标</h3>
        <table style="width: 100%; border-collapse: collapse; background-color: #f9f9f9;">
"""
        for key, value in alert.metrics.items():
            html += f"""
            <tr>
                <td style="padding: 8px; font-weight: bold; width: 200px;">{key}:</td>
                <td style="padding: 8px;">{value}</td>
            </tr>
"""
        
        html += f"""
        </table>
        
        <p style="margin-top: 20px; color: #999; font-size: 12px;">
            BTC Collision Engine - 自动告警系统
        </p>
    </div>
</body>
</html>
"""
        return html


class WeComWebhookNotifier(BaseNotifier):
    """企业微信Webhook通知器"""
    
    def __init__(self,
                 webhook_url: str,
                 mentioned_list: Optional[List[str]] = None,
                 timeout: int = DEFAULT_WEBHOOK_TIMEOUT,
                 enabled: bool = True):
        """
        Args:
            webhook_url: 企业微信Webhook URL
            mentioned_list: @用户列表(["@all"]或["userid1", "userid2"])
            timeout: 请求超时时间(秒)
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list or []
        self.timeout = timeout
        
        logger.info(f"企业微信Webhook通知器初始化")
    
    def _send_notification(self, alert: AlertRecord):
        """发送企业微信通知"""
        # 构建消息
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.EMERGENCY: "🚨"
        }
        emoji = level_emoji.get(alert.level, "📢")
        
        content = f"{emoji} **GPU告警通知**\n\n"
        content += f"**告警级别**: {alert.level.value.upper()}\n"
        content += f"**告警类型**: {alert.alert_type.value}\n"
        content += f"**触发时间**: {alert.timestamp}\n"
        content += f"**告警消息**: {alert.message}\n\n"
        
        content += "**性能指标**:\n"
        for key, value in alert.metrics.items():
            content += f"- {key}: {value}\n"
        
        if self.mentioned_list:
            mentioned = "".join([f"<@{user}>" for user in self.mentioned_list])
            content += f"\n{mentioned}"
        
        # 发送请求
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        response = requests.post(
            self.webhook_url,
            json=data,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"企业微信通知已发送: {alert.message}")
            else:
                logger.error(f"企业微信发送失败: {result}")
                raise Exception(f"企业微信API错误: {result}")
        else:
            logger.error(f"企业微信HTTP错误: {response.status_code}")
            raise Exception(f"HTTP {response.status_code}")
    
    def health_check(self) -> bool:
        """检查Webhook是否可达
        
        Returns:
            是否正常
        """
        try:
            # 发送一个简单的测试消息
            data = {
                "msgtype": "text",
                "text": {"content": "健康检查"}
            }
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=HEALTH_CHECK_TIMEOUT
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"企业微信Webhook健康检查失败: {e}")
            return False


class DingTalkWebhookNotifier(BaseNotifier):
    """钉钉Webhook通知器"""
    
    def __init__(self,
                 webhook_url: str,
                 at_mobiles: Optional[List[str]] = None,
                 at_all: bool = False,
                 timeout: int = DEFAULT_WEBHOOK_TIMEOUT,
                 enabled: bool = True):
        """
        Args:
            webhook_url: 钉钉Webhook URL
            at_mobiles: @手机号列表
            at_all: 是否@所有人
            timeout: 请求超时时间(秒)
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url
        self.at_mobiles = at_mobiles or []
        self.at_all = at_all
        self.timeout = timeout
        
        logger.info(f"钉钉Webhook通知器初始化")
    
    def _send_notification(self, alert: AlertRecord):
        """发送钉钉通知"""
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.EMERGENCY: "🚨"
        }
        emoji = level_emoji.get(alert.level, "📢")
        
        title = f"{emoji} GPU告警: {alert.message}"
        
        content = f"{emoji} **GPU告警通知**\n\n"
        content += f"> 告警级别: {alert.level.value.upper()}\n\n"
        content += f"**告警类型**: {alert.alert_type.value}\n\n"
        content += f"**触发时间**: {alert.timestamp}\n\n"
        content += f"**告警消息**: {alert.message}\n\n"
        
        content += "### 性能指标\n"
        for key, value in alert.metrics.items():
            content += f"- **{key}**: {value}\n"
        
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {
                "atMobiles": self.at_mobiles,
                "isAtAll": self.at_all
            }
        }
        
        # 发送请求
        response = requests.post(
            self.webhook_url,
            json=data,
            timeout=self.timeout,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"钉钉通知已发送: {alert.message}")
            else:
                logger.error(f"钉钉发送失败: {result}")
                raise Exception(f"钉钉API错误: {result}")
        else:
            logger.error(f"钉钉HTTP错误: {response.status_code}")
            raise Exception(f"HTTP {response.status_code}")
    
    def health_check(self) -> bool:
        """检查Webhook是否可达
        
        Returns:
            是否正常
        """
        try:
            # 发送一个简单的测试消息
            data = {
                "msgtype": "text",
                "text": {"content": "健康检查", "mentioned_list": []}
            }
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=HEALTH_CHECK_TIMEOUT,
                headers={'Content-Type': 'application/json'}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"钉钉Webhook健康检查失败: {e}")
            return False


class SlackWebhookNotifier(BaseNotifier):
    """Slack Webhook通知器"""
    
    def __init__(self,
                 webhook_url: str,
                 channel: str = "#alerts",
                 username: str = "GPU Alert Bot",
                 timeout: int = DEFAULT_WEBHOOK_TIMEOUT,
                 enabled: bool = True):
        """
        Args:
            webhook_url: Slack Webhook URL
            channel: 频道名称
            username: 用户名
            timeout: 请求超时时间(秒)
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.timeout = timeout
        
        logger.info(f"Slack Webhook通知器初始化")
    
    def _send_notification(self, alert: AlertRecord):
        """发送Slack通知"""
        level_emoji = {
            AlertLevel.INFO: ":information_source:",
            AlertLevel.WARNING: ":warning:",
            AlertLevel.CRITICAL: ":red_circle:",
            AlertLevel.EMERGENCY: ":rotating_light:"
        }
        emoji = level_emoji.get(alert.level, ":bell:")
        
        # 构建附件
        color_map = {
            AlertLevel.INFO: "#4FC3F7",
            AlertLevel.WARNING: "#FFB74D",
            AlertLevel.CRITICAL: "#EF5350",
            AlertLevel.EMERGENCY: "#FF1744"
        }
        color = color_map.get(alert.level, "#9E9E9E")
        
        fields = []
        fields.append({"title": "告警级别", "value": alert.level.value.upper(), "short": True})
        fields.append({"title": "告警类型", "value": alert.alert_type.value, "short": True})
        fields.append({"title": "触发时间", "value": alert.timestamp, "short": True})
        fields.append({"title": "告警消息", "value": alert.message, "short": False})
        
        # 添加性能指标
        metrics_text = "\n".join([f"• {key}: {value}" for key, value in alert.metrics.items()])
        fields.append({"title": "性能指标", "value": metrics_text, "short": False})
        
        # 构建请求数据
        data = {
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": emoji,
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} GPU告警通知",
                    "fields": fields,
                    "footer": "BTC Collision Engine",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        
        # 发送请求
        response = requests.post(
            self.webhook_url,
            json=data,
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            logger.info(f"Slack通知已发送: {alert.message}")
        else:
            logger.error(f"Slack HTTP错误: {response.status_code}")
            raise Exception(f"HTTP {response.status_code}")
    
    def health_check(self) -> bool:
        """检查Webhook是否可达
        
        Returns:
            是否正常
        """
        try:
            # 发送一个简单的测试消息
            data = {
                "channel": self.channel,
                "username": self.username,
                "text": "健康检查"
            }
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=HEALTH_CHECK_TIMEOUT
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack Webhook健康检查失败: {e}")
            return False
