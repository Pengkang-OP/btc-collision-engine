"""日志配置管理模块

统一管理日志配置，支持从配置文件读取设置，
提供统一的日志记录器初始化接口。
"""
import os
import sys
import logging
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from .logger import ColoredFormatter, ThreadSafeLogger


class LoggingConfig:
    """日志配置管理器"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/collision.log",
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "enable_console": True,
        "enable_file": True,
        "rotation_type": "size",  # "size" 或 "time"
        "rotation_when": "midnight",  # 时间轮转间隔 (midnight, H, D, W0-W6)
        "rotation_interval": 1,  # 时间轮转间隔数
        "compress_backups": False,  # 是否压缩旧日志
    }
    
    _instance = None
    _config = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日志配置
        
        参数:
            config: 自定义配置字典，None则使用默认配置
        """
        if self._initialized:
            return
        
        if config is None:
            # 尝试从配置文件加载
            config = self._load_from_config_file()
        
        self._config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._ensure_log_directory()
        self._initialized = True
        
        # 配置根日志记录器
        self._setup_root_logger()
    
    def _load_from_config_file(self) -> Optional[Dict[str, Any]]:
        """从配置文件加载日志设置"""
        try:
            from ..config.config_manager import ConfigManager
            config_mgr = ConfigManager()
            
            logging_config = {}
            
            # 读取日志级别
            level = config_mgr.get("logging.level")
            if level:
                logging_config["level"] = level
            
            # 读取日志文件路径
            log_file = config_mgr.get("logging.file")
            if log_file:
                logging_config["file"] = log_file
            
            # 读取格式
            format_str = config_mgr.get("logging.format")
            if format_str:
                logging_config["format"] = format_str
            
            return logging_config
        except Exception:
            return None
    
    def _ensure_log_directory(self):
        """确保日志目录存在"""
        log_file = self._config.get("file")
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o750, exist_ok=True)
    
    def _setup_root_logger(self):
        """配置根日志记录器"""
        level = self._config.get("level", "INFO")
        format_str = self._config.get("format", self.DEFAULT_CONFIG["format"])
        
        # 设置根日志级别
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level))
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 控制台处理器
        if self._config.get("enable_console", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level))
            console_formatter = ColoredFormatter(format_str)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # 文件处理器
        if self._config.get("enable_file", True):
            log_file = self._config.get("file")
            if log_file:
                file_handler = self._create_file_handler(log_file, format_str)
                if file_handler:
                    root_logger.addHandler(file_handler)
    
    def _create_file_handler(self, log_file: str, format_str: str) -> Optional[logging.Handler]:
        """创建文件处理器"""
        rotation_type = self._config.get("rotation_type", "size")
        level = self._config.get("level", "INFO")
        
        try:
            if rotation_type == "time":
                # 基于时间的轮转
                handler = TimedRotatingFileHandler(
                    log_file,
                    when=self._config.get("rotation_when", "midnight"),
                    interval=self._config.get("rotation_interval", 1),
                    backupCount=self._config.get("backup_count", 5),
                    encoding='utf-8'
                )
            else:
                # 基于大小的轮转（默认）
                handler = RotatingFileHandler(
                    log_file,
                    maxBytes=self._config.get("max_bytes", 10*1024*1024),
                    backupCount=self._config.get("backup_count", 5),
                    encoding='utf-8'
                )
            
            handler.setLevel(getattr(logging, level))
            handler.setFormatter(logging.Formatter(format_str))
            
            # 设置日志文件权限为仅所有者可读写
            try:
                os.chmod(log_file, 0o600)
            except OSError:
                pass
            
            return handler
        except Exception as e:
            print(f"创建日志文件处理器失败: {e}", file=sys.stderr)
            return None
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        if not self._initialized:
            self.init()
        return self._config.copy()
    
    def get_logger(self, name: str, thread_safe: bool = False) -> logging.Logger:
        """
        获取配置好的日志记录器
        
        参数:
            name: 日志记录器名称
            thread_safe: 是否返回线程安全包装器
            
        返回:
            配置好的日志记录器
        """
        if not self._initialized:
            self.init()
        
        logger = logging.getLogger(name)
        
        if thread_safe:
            return ThreadSafeLogger(logger)
        return logger


# 全局日志配置实例
logging_config = LoggingConfig()


def init_logging(config: Optional[Dict[str, Any]] = None):
    """
    初始化日志系统
    
    参数:
        config: 自定义配置字典
    """
    logging_config.init(config)
    
    # 启用日志安全过滤器（P0-2修复）
    _setup_security_filter()


def get_configured_logger(name: str, thread_safe: bool = False) -> logging.Logger:
    """
    获取统一配置的日志记录器
    
    参数:
        name: 日志记录器名称
        thread_safe: 是否返回线程安全包装器
        
    返回:
        配置好的日志记录器
    """
    return logging_config.get_logger(name, thread_safe)
