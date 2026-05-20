"""密钥安全审计模块

提供密钥相关操作的安全审计功能，包括:
- 密钥显示审计
- 密钥访问日志
- 敏感操作追踪
"""

import hashlib
import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class KeyOperationType(Enum):
    """密钥操作类型"""

    DISPLAY = "display"  # 显示密钥
    HASH = "hash"  # 生成哈希
    VALIDATE = "validate"  # 验证密钥
    EXPORT = "export"  # 导出密钥
    CLEAR = "clear"  # 清零密钥


class KeyAuditLevel(Enum):
    """审计级别"""

    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    CRITICAL = "critical"  # 严重
    EMERGENCY = "emergency"  # 紧急


class KeyAuditLogger:
    """密钥安全审计日志器

    追踪所有密钥相关操作，确保敏感信息不被泄露。
    """

    def __init__(self, log_file: str | None = None):
        """
        初始化审计日志器

        Args:
            log_file: 审计日志文件路径，None表示仅输出到控制台
        """
        self._lock = threading.Lock()
        self._operation_count: dict[str, int] = {}
        self._log_file = log_file

        # 设置日志处理器
        if log_file:
            try:
                import os

                os.makedirs(os.path.dirname(log_file), exist_ok=True)

                # 检查是否已存在相同文件的处理器
                existing_handler = None
                for handler in logger.handlers:
                    if isinstance(handler, logging.FileHandler) and (
                        handler.baseFilename == os.path.abspath(log_file)
                    ):
                        existing_handler = handler
                        break

                if not existing_handler:
                    handler = logging.FileHandler(log_file, encoding="utf-8")
                    handler.setFormatter(
                        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                    )
                    logger.addHandler(handler)
            except Exception as e:
                logger.warning(f"无法创建审计日志文件: {e}")

    def log_operation(
        self,
        operation: KeyOperationType,
        level: KeyAuditLevel,
        address: str | None = None,
        key_hash: str | None = None,
        display_mode: str | None = None,
        details: str | None = None,
    ) -> None:
        """
        记录密钥操作

        Args:
            operation: 操作类型
            level: 审计级别
            address: 比特币地址（如果有）
            key_hash: 密钥哈希（用于追踪，不暴露实际密钥）
            display_mode: 显示模式（masked/hash_only/full）
            details: 额外详情
        """
        with self._lock:
            # 更新统计
            op_name = operation.value
            self._operation_count[op_name] = self._operation_count.get(op_name, 0) + 1

            # 构建审计消息
            timestamp = datetime.now().isoformat()
            message_parts = [
                f"[KEY_AUDIT] {timestamp}",
                f"Operation: {op_name}",
                f"Level: {level.value}",
            ]

            if address:
                message_parts.append(f"Address: {self._mask_address(address)}")

            if key_hash:
                message_parts.append(f"KeyHash: {key_hash[:16]}...")

            if display_mode:
                message_parts.append(f"DisplayMode: {display_mode}")

            if details:
                message_parts.append(f"Details: {details}")

            message = " | ".join(message_parts)

            # 根据级别选择日志方法
            if level == KeyAuditLevel.EMERGENCY:
                logger.critical(message)
            elif level == KeyAuditLevel.CRITICAL:
                logger.error(message)
            elif level == KeyAuditLevel.WARNING:
                logger.warning(message)
            else:
                logger.info(message)

    def _mask_address(self, address: str) -> str:
        """掩码地址，仅显示前6和后4位"""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address

    def get_statistics(self) -> dict[str, Any]:
        """
        获取审计统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                "total_operations": sum(self._operation_count.values()),
                "operations_by_type": dict(self._operation_count),
            }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._operation_count.clear()


# 全局审计日志器实例
_audit_logger: KeyAuditLogger | None = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> KeyAuditLogger:
    """获取全局审计日志器实例"""
    global _audit_logger
    with _audit_logger_lock:
        if _audit_logger is None:
            _audit_logger = KeyAuditLogger(log_file="data_logs/key_audit.log")
        return _audit_logger


def log_key_display(
    address: str,
    private_key: bytes,
    display_mode: str = "masked",
) -> None:
    """
    记录密钥显示操作

    Args:
        address: 比特币地址
        private_key: 私钥字节
        display_mode: 显示模式
    """
    # 生成密钥哈希用于追踪
    key_hash = hashlib.sha256(private_key).hexdigest()

    # 根据显示模式决定审计级别
    if display_mode == "full":
        level = KeyAuditLevel.CRITICAL
        details = "完整私钥已显示，风险极高！"
    elif display_mode == "masked":
        level = KeyAuditLevel.INFO
        details = "私钥已脱敏显示"
    else:  # hash_only
        level = KeyAuditLevel.WARNING
        details = "仅显示哈希值"

    audit_logger = get_audit_logger()
    audit_logger.log_operation(
        operation=KeyOperationType.DISPLAY,
        level=level,
        address=address,
        key_hash=key_hash,
        display_mode=display_mode,
        details=details,
    )
