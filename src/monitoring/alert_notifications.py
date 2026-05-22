"""Alert notification system."""
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class AlertNotifier:
    """Sends alert notifications through configured channels."""

    def __init__(self, config: dict | None = None):
        self._config = config or {}

    def send_email(
        self,
        subject: str,
        body: str,
        to: str,
    ) -> bool:
        """Send email alert.

        Args:
            subject: Email subject
            body: Email body
            to: Recipient address

        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["To"] = to
            logger.info(
                f"Email alert sent to {to}: {subject}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send email alert: {e}"
            )
            return False

    def send_console(
        self, message: str
    ) -> None:
        """Send console alert.

        Args:
            message: Alert message
        """
        print(f"[ALERT] {message}")
