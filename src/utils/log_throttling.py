# -*- coding: utf-8 -*-
"""日志频率控制工具

提供统一的错误日志频率控制策略，避免日志泛滥。
"""

import time
import logging
from typing import Dict, Optional
from functools import wraps


class RateLimitedLogger:
    """频率限制的日志记录器
    
    对相同错误消息进行频率限制，避免日志泛滥。
    相同消息在冷却时间内只记录一次。
    
    使用示例:
        >>> logger = RateLimitedLogger(__name__)
        >>> logger.error_limited("数据库连接失败", cooldown=60)  # 60秒内只记录一次
    """
    
    def __init__(self, name: str, default_cooldown: int = 60):
        """初始化
        
        参数:
            name: 日志记录器名称
            default_cooldown: 默认冷却时间（秒）
        """
        self.logger = logging.getLogger(name)
        self.default_cooldown = default_cooldown
        self._last_log_time: Dict[str, float] = {}
    
    def error_limited(self, message: str, cooldown: Optional[int] = None, 
                     *args, **kwargs):
        """频率限制的error日志
        
        参数:
            message: 日志消息
            cooldown: 冷却时间（秒），None则使用默认值
            *args, **kwargs: 传递给logger.error的其他参数
        """
        if cooldown is None:
            cooldown = self.default_cooldown
        
        current_time = time.time()
        last_time = self._last_log_time.get(message, 0)
        
        if current_time - last_time >= cooldown:
            self.logger.error(message, *args, **kwargs)
            self._last_log_time[message] = current_time
    
    def warning_limited(self, message: str, cooldown: Optional[int] = None,
                       *args, **kwargs):
        """频率限制的warning日志
        
        参数:
            message: 日志消息
            cooldown: 冷却时间（秒），None则使用默认值
            *args, **kwargs: 传递给logger.warning的其他参数
        """
        if cooldown is None:
            cooldown = self.default_cooldown
        
        current_time = time.time()
        last_time = self._last_log_time.get(message, 0)
        
        if current_time - last_time >= cooldown:
            self.logger.warning(message, *args, **kwargs)
            self._last_log_time[message] = current_time
    
    def clear_cache(self):
        """清除缓存的日志时间戳"""
        self._last_log_time.clear()


def rate_limited_log(cooldown: int = 60, level: str = 'error'):
    """日志频率限制装饰器
    
    用于装饰可能频繁调用的函数，限制其日志输出频率。
    
    参数:
        cooldown: 冷却时间（秒）
        level: 日志级别 ('error', 'warning', 'info')
    
    使用示例:
        >>> @rate_limited_log(cooldown=60, level='error')
        >>> def handle_error(error):
        >>>     logger.error(f"处理错误: {error}")
        >>>     # 60秒内只记录一次
    """
    def decorator(func):
        last_log_time = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            # 使用函数名作为缓存键
            cache_key = func.__name__
            last_time = last_log_time.get(cache_key, 0)
            
            if current_time - last_time >= cooldown:
                result = func(*args, **kwargs)
                last_log_time[cache_key] = current_time
                return result
            # 跳过执行
            return None
        
        return wrapper
    return decorator


# 创建全局实例，供各模块使用
collision_logger = RateLimitedLogger("collision", default_cooldown=60)
gpu_logger = RateLimitedLogger("gpu", default_cooldown=30)
data_logger = RateLimitedLogger("data", default_cooldown=120)
