# -*- coding: utf-8 -*-
"""安全私钥生成器 - 符合Bitcoin Core规范"""
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
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化私钥生成器
        
        参数:
            config: 配置字典
                - batch_size: 每批生成数量（默认1000）
                - rate_limit: 每秒生成速率（默认0=无限制）
                - key_format: 公钥格式（默认'both'）
        """
        config = config or {}
        self.batch_size = config.get('batch_size', 1000)
        self.rate_limit = config.get('rate_limit', 0)
        self.key_format = config.get('key_format', 'both')
        self.key_manager = SecureKeyManager()
        self._lock = threading.Lock()
        
        # 统计信息
        self._total_generated = 0
        self._start_time = datetime.utcnow()
        
        logger.info(
            "SecureKeyGenerator初始化: batch_size=%d, rate_limit=%d",
            self.batch_size, self.rate_limit
        )
    
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
            "批量生成完成: %d keys in %.2fs (%.0f keys/s)",
            len(private_keys), elapsed, rate
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
        key_int = int.from_bytes(key, 'big')
        
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
            
            return {
                'total_generated': self._total_generated,
                'elapsed_seconds': elapsed,
                'generation_rate': rate,
                'batch_size': self.batch_size,
                'rate_limit': self.rate_limit,
                'key_format': self.key_format
            }
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._total_generated = 0
            self._start_time = datetime.utcnow()
            logger.info("统计信息已重置")
