#!/usr/bin/env python3
"""
日志安全过滤器

防止敏感信息（如私钥）泄露到日志文件中。
自动检测和屏蔽比特币私钥模式。
"""

import hashlib
import logging
import re


class SecurityLogFilter(logging.Filter):
    """安全日志过滤器

    自动检测并屏蔽日志消息中的敏感信息：
    - 比特币私钥（64位十六进制）
    - WIF格式私钥
    - 原始私钥字节
    - 比特币地址（P2PKH/P2SH/Bech32/Bech32m）
    """

    # 私钥模式匹配
    # 64位十六进制（32字节私钥），支持0x前缀
    # 增强：使用负向前瞻确保不在其他十六进制字符串中间匹配
    PRIVATE_KEY_HEX_PATTERN = re.compile(r"(?<![0-9a-fA-F])(?:0x)?[0-9a-fA-F]{64}(?![0-9a-fA-F])")

    # WIF格式 - 与 SensitiveDataFilter 保持精确一致
    # 非压缩WIF: 以5开头，总长51字符 (5 + 50后续字符)
    WIF_UNCOMPRESSED_PATTERN = re.compile(r"\b5[HJK][1-9A-HJ-NP-Za-km-z]{48,49}\b")
    # 压缩WIF: 以K或L开头，总长52字符 (K/L + 51后续字符)
    WIF_COMPRESSED_PATTERN = re.compile(r"\b[KL][1-9A-HJ-NP-Za-km-z]{50,51}\b")

    # 原始字节模式（32字节）
    RAW_KEY_PATTERN = re.compile(r"b'\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){31}'")

    # 比特币地址模式匹配
    # P2PKH: 以 1 开头，25-34 字符 Base58
    P2PKH_ADDRESS_PATTERN = re.compile(r"\b1[1-9A-HJ-NP-Za-km-z]{24,33}\b")
    # P2SH: 以 3 开头，25-34 字符 Base58
    P2SH_ADDRESS_PATTERN = re.compile(r"\b3[1-9A-HJ-NP-Za-km-z]{24,33}\b")
    # Bech32: 以 bc1 开头，42 或 62 字符（P2WPKH/P2WSH）
    BECH32_ADDRESS_PATTERN = re.compile(r"\bbc1[ac-hj-np-z02-9]{38,58}\b")
    # Bech32m (Taproot): 以 bc1p 开头，62 字符
    BECH32M_ADDRESS_PATTERN = re.compile(r"\bbc1p[ac-hj-np-z02-9]{58}\b")

    # BIP32 扩展密钥 (xprv/xpub/等)
    BIP32_EXTENDED_KEY_PATTERN = re.compile(r"\b[xXtT]prv[1-9A-HJ-NP-Za-km-z]{107,108}\b")
    BIP32_EXTENDED_PUBKEY_PATTERN = re.compile(r"\b[xXtT]pub[1-9A-HJ-NP-Za-km-z]{107,108}\b")

    # BIP39 种子短语上下文关键词 — 仅当消息包含这些上下文时才应用BIP39检测
    # 避免纯技术日志被误匹配（如 "the system encountered an unexpected error"）
    BIP39_CONTEXT_KEYWORDS = re.compile(
        r'\b(seed|mnemonic|recovery|phrase|bip39|助记词|种子短语|恢复短语)\b',
        re.IGNORECASE
    )
    # BIP39 种子短语 (12或24个英语助记词)
    # 词列表包含常见的 BIP39 英语助记词
    # 检测包含12或24个助记词的文本，每个词3-8个字母
    BIP39_PHRASE_12_PATTERN = re.compile(
        r"\b(?:[a-z]{3,8}\s+){11}[a-z]{3,8}\b", re.IGNORECASE
    )
    BIP39_PHRASE_24_PATTERN = re.compile(
        r"\b(?:[a-z]{3,8}\s+){23}[a-z]{3,8}\b", re.IGNORECASE
    )

    def __init__(
        self,
        name: str = "",
        mask_private_keys: bool = True,
        mask_wif: bool = True,
        mask_addresses: bool = True,
    ) -> None:
        """
        Args:
            name: 过滤器名称
            mask_private_keys: 是否屏蔽私钥十六进制
            mask_wif: 是否屏蔽WIF格式
            mask_addresses: 是否屏蔽比特币地址
        """
        super().__init__(name)
        self.mask_private_keys = mask_private_keys
        self.mask_wif = mask_wif
        self.mask_addresses = mask_addresses

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录，屏蔽敏感信息

        Args:
            record: 日志记录对象

        Returns:
            bool: 总是返回True（允许日志记录，但内容已被清理）
        """
        if not hasattr(record, "msg"):
            return True

        # 处理消息
        if isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)

        # 处理参数
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._sanitize_value(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    self._sanitize_value(v) if isinstance(v, str) else v for v in record.args
                )

        return True

    def _sanitize_message(self, message: str) -> str:
        """清理消息中的敏感信息

        Args:
            message: 原始消息

        Returns:
            str: 清理后的消息
        """
        if self.mask_private_keys:
            # 屏蔽64位十六进制私钥
            message = self.PRIVATE_KEY_HEX_PATTERN.sub(lambda m: self._mask_key(m.group()), message)

        if self.mask_wif:
            # 屏蔽WIF格式私钥 (使用与SensitiveDataFilter一致的精确模式)
            message = self.WIF_UNCOMPRESSED_PATTERN.sub("[WIF_UNCOMPRESSED_KEY]", message)
            message = self.WIF_COMPRESSED_PATTERN.sub("[WIF_COMPRESSED_KEY]", message)

        # 屏蔽原始字节模式
        message = self.RAW_KEY_PATTERN.sub("[RAW_PRIVATE_KEY]", message)

        # 屏蔽比特币地址
        if self.mask_addresses:
            message = self.P2PKH_ADDRESS_PATTERN.sub("[P2PKH_ADDRESS]", message)
            message = self.P2SH_ADDRESS_PATTERN.sub("[P2SH_ADDRESS]", message)
            message = self.BECH32_ADDRESS_PATTERN.sub("[BECH32_ADDRESS]", message)
            message = self.BECH32M_ADDRESS_PATTERN.sub("[BECH32M_ADDRESS]", message)

        # 屏蔽 BIP32 扩展密钥 (与 log_processor.SensitiveDataFilter 保持一致)
        message = self.BIP32_EXTENDED_KEY_PATTERN.sub("[BIP32_EXTENDED_KEY]", message)
        message = self.BIP32_EXTENDED_PUBKEY_PATTERN.sub("[BIP32_EXTENDED_PUBKEY]", message)

        # 屏蔽 BIP39 种子短语（仅在包含相关上下文时应用，避免技术日志误报）
        if self.mask_private_keys and self.BIP39_CONTEXT_KEYWORDS.search(message):
            # 注意: 24词模式必须在12词之前，否则24词短语的前12词会被误匹配为12词
            message = self.BIP39_PHRASE_24_PATTERN.sub("[BIP39_PHRASE_24_WORDS]", message)
            message = self.BIP39_PHRASE_12_PATTERN.sub("[BIP39_PHRASE_12_WORDS]", message)

        return message

    def _sanitize_value(self, value: str) -> str:
        """清理字符串值中的敏感信息

        Args:
            value: 原始字符串值

        Returns:
            str: 清理后的字符串
        """
        return self._sanitize_message(value)

    def _mask_key(self, key_hex: str) -> str:
        """掩码处理私钥

        保留前8位和后8位，中间用***替代

        Args:
            key_hex: 64位十六进制私钥

        Returns:
            str: 掩码后的私钥
        """
        if len(key_hex) != 64:
            return "[PRIVATE_KEY]"

        # 计算哈希用于调试（不暴露实际私钥）
        key_hash = hashlib.sha256(key_hex.encode()).hexdigest()[:16]

        return f"[PRIVATE_KEY:{key_hash}...]"


def setup_security_logging() -> None:
    """为所有日志记录器添加安全过滤器

    应在应用程序启动时调用，确保所有日志都经过安全过滤。
    """
    # 创建安全过滤器
    security_filter = SecurityLogFilter(
        name="security_filter", mask_private_keys=True, mask_wif=True, mask_addresses=True
    )

    # 添加到根日志记录器（子 logger 会继承根 logger 的过滤器）
    root_logger = logging.getLogger()
    root_logger.addFilter(security_filter)

    # 显式覆盖关键模块 logger（确保即使配置了 propagate=False 也能被保护）
    critical_module_loggers = [
        # 碰撞引擎（核心私钥处理）
        "KeyCollisionEngine",
        "MultiGPUEngine",
        "AsyncGPUExecutor",
        # GPU工作线程（处理私钥批量生成/匹配）
        "GPUWorker",
        "GPUKernel",
        "GPUDevice",
        # GPU搜索模式（批量私钥搜索）
        "RandomSearchMode",
        "BruteForceSearch",
        "RangeScanSearch",
        "BaseSearchMode",
        # 上下文管理
        "GPUContext",
        "GPUMemoryPool",
        "GPUBufferTracker",
        # 监控/日志
        "DataLogger",
        "MonitoringSystem",
        "GPUEngineMonitor",
    ]

    # 追踪已添加过滤器的 logger，避免重复
    _processed_loggers = set()
    _processed_loggers.add(None)  # root logger 已处理

    # 为显式列表中的模块添加过滤器
    for logger_name in critical_module_loggers:
        logger = logging.getLogger(logger_name)
        if id(logger) not in _processed_loggers:
            logger.addFilter(security_filter)
            _processed_loggers.add(id(logger))

    # 自动发现并保护所有已注册的 logger（覆盖显式列表之外的新模块）
    for logger_name, logger_ref in logging.Logger.manager.loggerDict.items():
        if isinstance(logger_ref, logging.Logger):
            if id(logger_ref) not in _processed_loggers:
                logger_ref.addFilter(security_filter)
                _processed_loggers.add(id(logger_ref))

    logging.info(
        "✅ 日志安全过滤器已启用 (显式模块: %d, 自动发现: %d, 总计: %d)",
        len(critical_module_loggers),
        len(_processed_loggers) - len(critical_module_loggers) - 1,
        len(_processed_loggers) - 1,
    )


def sanitize_private_key_for_log(private_key: bytes) -> str:
    """为日志记录安全处理私钥

    返回私钥的SHA256哈希前16位，用于调试而不泄露实际私钥。

    Args:
        private_key: 私钥字节（32字节）

    Returns:
        str: 私钥哈希（16位十六进制）
    """
    if not private_key:
        return "[EMPTY_KEY]"

    key_hash = hashlib.sha256(private_key).hexdigest()[:16]
    return f"[KEY_HASH:{key_hash}]"


# 便捷函数
def log_safe_error(logger: logging.Logger, message: str, **kwargs) -> None:
    """记录安全的错误日志（自动过滤敏感信息）

    Args:
        logger: 日志记录器
        message: 错误消息
        **kwargs: 额外参数
    """
    # 安全过滤器会自动处理，这里只是便捷封装
    logger.error(message, **kwargs)


def log_safe_debug(logger: logging.Logger, message: str, **kwargs) -> None:
    """记录安全的调试日志（自动过滤敏感信息）

    Args:
        logger: 日志记录器
        message: 调试消息
        **kwargs: 额外参数
    """
    logger.debug(message, **kwargs)


def log_safe_exception(
    logger: logging.Logger,
    message: str,
    exc: BaseException | None = None,
    **kwargs
) -> None:
    """安全记录异常（不泄露敏感堆栈信息）

    Args:
        logger: 日志记录器
        message: 错误消息
        exc: 异常对象（可选）
        **kwargs: 额外参数
    """
    if exc is None:
        logger.error(message, **kwargs)
    else:
        # 记录异常类型，不记录完整堆栈
        safe_error_msg = f"{message}: {type(exc).__name__}"
        logger.error(safe_error_msg, **kwargs)
        # 对于非严重错误，可以记录脱敏的异常信息到 debug
        logger.debug(f"[FULL_ERROR] {safe_error_msg}: {sanitize_private_key_for_log(str(exc).encode())}", **kwargs)
