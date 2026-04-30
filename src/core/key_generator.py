# -*- coding: utf-8 -*-
"""安全私钥生成器 - 符合Bitcoin Core规范"""

import os
import secrets
import time
import threading
from typing import List, Dict, Optional
from datetime import datetime

from ..utils import init_logging, get_configured_logger
from .secp256k1 import Secp256k1
from .secure_key_manager import SecureKeyManager

# 初始化日志系统
init_logging()
logger = get_configured_logger("SecureKeyGenerator")


class SecureKeyGenerator:
    """
    安全私钥生成器 - 符合Bitcoin Core规范

    使用CSPRNG（密码学安全伪随机数生成器）生成私钥，
    确保生成的私钥符合加密货币行业安全标准。

    属性:
        batch_size: 每批生成数量
        rate_limit: 每秒生成速率（0=无限制）
        key_manager: 私钥管理器（用于安全清零）
        _lock: 线程安全锁

    示例:
        >>> config = {'batch_size': 1000, 'rate_limit': 0}
        >>> generator = SecureKeyGenerator(config)
        >>> keys = generator.generate_batch(1000)
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        初始化私钥生成器

        参数:
            config: 配置字典
                - batch_size: 每批生成数量（默认1000）
                - rate_limit: 每秒生成速率（默认0=无限制）
                - key_format: 公钥格式（默认'both'）
                - entropy_check_enabled: 是否启用熵池检查（默认True）
                - min_entropy_bits: 最小熵值阈值（默认1000）
        """
        config = config or {}
        self.batch_size = config.get("batch_size", 1000)
        self.rate_limit = config.get("rate_limit", 0)
        self.key_format = config.get("key_format", "both")
        self.key_manager = SecureKeyManager()
        self._lock = threading.Lock()

        # P1-3修复: 熵池检查配置
        self.entropy_check_enabled = config.get("entropy_check_enabled", True)
        self.min_entropy_bits = config.get("min_entropy_bits", 1000)

        # 统计信息
        self._total_generated = 0
        self._start_time = datetime.utcnow()
        self.stats: Dict = {"low_entropy_count": 0, "entropy_checks": 0, "warnings_issued": 0}

        logger.info(
            "SecureKeyGenerator初始化: batch_size=%d, rate_limit=%d, entropy_check=%s",
            self.batch_size,
            self.rate_limit,
            self.entropy_check_enabled,
        )

    def _check_entropy_health(self) -> bool:
        """检查系统熵池健康状态

        P1-3修复: 添加熵池健康检查,防止低熵环境下生成弱密钥

        返回:
            bool: 熵池是否健康
        """
        if not self.entropy_check_enabled:
            return True

        try:
            # Linux系统检查熵池
            entropy_file = "/proc/sys/kernel/random/entropy_avail"
            if os.path.exists(entropy_file):
                with open(entropy_file, "r") as f:
                    entropy = int(f.read().strip())

                self.stats["entropy_checks"] = self.stats.get("entropy_checks", 0) + 1

                if entropy < self.min_entropy_bits:
                    logger.warning(
                        f"系统熵池较低: {entropy} bits (< {self.min_entropy_bits}), "
                        f"建议安装haveged或rng-tools"
                    )
                    self.stats["low_entropy_count"] = self.stats.get("low_entropy_count", 0) + 1

                    # 仅在首次警告时发出详细提示
                    if self.stats["low_entropy_count"] == 1:
                        logger.warning(
                            "熵池不足可能导致密钥生成质量下降。\n"
                            "Linux解决方案:\n"
                            "  sudo apt-get install haveged\n"
                            "  sudo systemctl enable haveged\n"
                            "  sudo systemctl start haveged\n"
                            "或:\n"
                            "  sudo apt-get install rng-tools\n"
                            "  sudo systemctl enable rng-tools\n"
                            "  sudo systemctl start rng-tools"
                        )
                        self.stats["warnings_issued"] = self.stats.get("warnings_issued", 0) + 1

                    return False
                elif entropy < self.min_entropy_bits * 2:
                    logger.debug(f"系统熵池一般: {entropy} bits")
                    return True
                else:
                    logger.debug(f"系统熵池充足: {entropy} bits")
                    return True

            # Windows/macOS无法检查,假设健康
            # 这些系统使用CryptGenRandom/SecureRandom,不依赖熵池
            if self.stats.get("entropy_checks", 0) == 0:
                # 仅在首次检查时记录说明
                import platform

                system = platform.system()
                logger.debug(
                    f"{system}系统使用系统级CSPRNG (CryptGenRandom/SecureRandom)，"
                    f"不依赖/dev/random熵池，安全性由操作系统保证"
                )
                self.stats["entropy_checks"] = 1
            return True
        except Exception as e:
            logger.debug(f"无法检查熵池状态: {e}")
            return True  # 无法检查时假设健康

    def generate_batch(self, count: int) -> List[bytes]:
        """
        批量生成私钥 - 符合加密货币安全标准

        参数:
            count: 要生成的私钥数量

        返回:
            私钥列表（字节串）
        """
        if count <= 0:
            raise ValueError("生成数量必须大于0")

        # P1-3修复: 检查熵池健康状态
        if not self._check_entropy_health():
            logger.warning("熵池健康度低,生成的密钥可能存在安全风险")
            # 记录但不阻塞,避免影响性能

        private_keys = []
        start_time = time.time()

        for i in range(count):
            try:
                # 1. 使用CSPRNG生成32字节随机数
                private_key = secrets.token_bytes(32)

                # 2. 验证私钥有效性 (1 <= k < n)
                if not self._is_valid_private_key(private_key):
                    logger.debug("生成无效私钥，重新生成")
                    continue

                # 3. 添加到批量列表
                private_keys.append(private_key)

                # 4. 速率控制（如果配置）
                if self.rate_limit > 0:
                    elapsed = time.time() - start_time
                    expected_time = len(private_keys) / self.rate_limit
                    if elapsed < expected_time:
                        time.sleep(expected_time - elapsed)

            except Exception as e:
                logger.error("生成私钥 %d 失败: %s", i, str(e))
                continue

        # 更新统计
        with self._lock:
            self._total_generated += len(private_keys)

        elapsed = time.time() - start_time
        rate = len(private_keys) / elapsed if elapsed > 0 else 0

        logger.debug(
            "批量生成完成: %d keys in %.2fs (%.0f keys/s)", len(private_keys), elapsed, rate
        )

        # BL-2修复: 检查是否生成了任何有效私钥
        if len(private_keys) == 0 and count > 0:
            raise RuntimeError(
                f"无法生成任何有效私钥 (请求{count}个)。" f"这可能是系统熵池严重不足或CSPRNG故障。"
            )

        return private_keys

    def generate_single(self) -> bytes:
        """
        生成单个私钥

        返回:
            32字节私钥
        """
        max_attempts = 100

        for _ in range(max_attempts):
            private_key = secrets.token_bytes(32)

            if self._is_valid_private_key(private_key):
                with self._lock:
                    self._total_generated += 1
                return private_key

        raise RuntimeError("生成有效私钥失败（超过最大尝试次数）")

    def _is_valid_private_key(self, key: bytes) -> bool:
        """
        验证私钥是否符合secp256k1曲线规范

        参数:
            key: 32字节私钥

        返回:
            是否有效
        """
        if len(key) != 32:
            return False

        # 转换为整数
        key_int = int.from_bytes(key, "big")

        # 验证范围: 1 <= k < n
        return 1 <= key_int < Secp256k1.N

    def get_statistics(self) -> Dict:
        """
        获取生成统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            elapsed = (datetime.utcnow() - self._start_time).total_seconds()
            rate = self._total_generated / elapsed if elapsed > 0 else 0

            stats = {
                "total_generated": self._total_generated,
                "elapsed_seconds": elapsed,
                "generation_rate": rate,
                "batch_size": self.batch_size,
                "rate_limit": self.rate_limit,
                "key_format": self.key_format,
                # P1-3修复: 添加熵池统计
                "entropy_check_enabled": self.entropy_check_enabled,
                "min_entropy_bits": self.min_entropy_bits,
                "low_entropy_warnings": self.stats.get("low_entropy_count", 0),
                "entropy_checks": self.stats.get("entropy_checks", 0),
            }

            return stats

    def reset_statistics(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._total_generated = 0
            self._start_time = datetime.utcnow()
            logger.info("统计信息已重置")
