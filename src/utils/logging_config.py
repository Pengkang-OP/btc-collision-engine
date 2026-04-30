"""日志配置管理模块

统一管理日志配置，支持从配置文件读取设置，
提供统一的日志记录器初始化接口。
"""

import os
import sys
import time
import logging
import shutil
import platform
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from .logger import ColoredFormatter, SafeStreamHandler  # ThreadSafeLogger已弃用


class SafeRotatingFileHandler(RotatingFileHandler):
    """Windows 安全的日志轮转处理器，处理多线程文件锁冲突（WinError 32）

    仅在 Windows 平台启用重试逻辑；Linux/macOS 行为与原生 RotatingFileHandler 完全相同。
    """

    def __init__(self, *args, **kwargs) -> None:
        self._retry_count = kwargs.pop("retry_count", 3)
        self._retry_delay = kwargs.pop("retry_delay", 0.1)
        self._is_windows = platform.system() == "Windows"
        super().__init__(*args, **kwargs)

    def doRollover(self) -> None:
        """带重试机制的日志轮转（Windows 专用）"""
        if not self._is_windows:
            super().doRollover()
            return
        for attempt in range(self._retry_count):
            try:
                super().doRollover()
                return
            except PermissionError:
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                # 最后一次重试仍失败：静默跳过轮转，继续写入当前文件，不影响主程序


# 导入安全过滤器（P0-2修复）
from .security_log_filter import SecurityLogFilter

# 幂等守卫：防止多次 import 重复执行安全过滤器初始化
_security_filter_initialized: bool = False


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

    def __new__(cls) -> "LoggingConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化日志配置

        参数:
            config: 自定义配置字典，None则使用默认配置
        """
        if self._initialized:
            # 修复: 添加调试日志，避免静默失败
            import logging

            logging.getLogger(__name__).debug("日志系统已初始化，跳过重复调用")
            return

        if config is None:
            # 尝试从配置文件加载
            config = self._load_from_config_file()

        self._config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._ensure_log_directory()
        self.check_disk_space()  # M12: 初始化时主动检查磁盘空间
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
        except (OSError, ImportError):
            return None

    def _ensure_log_directory(self) -> None:
        """确保日志目录存在"""
        assert self._config is not None
        log_file = self._config.get("file")
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o750, exist_ok=True)
        else:
            # 使用平台特定的日志目录
            from .log_platform_adapter import ensure_log_directory

            ensure_log_directory()

    def check_disk_space(self, min_free_mb: int = 200) -> bool:
        """主动检查日志目录所在磁盘的可用空间

        Args:
            min_free_mb: 最小可用空间（MB），低于此值发出 WARNING

        Returns:
            True 表示磁盘空间充足，False 表示空间不足
        """
        log_file = (
            self._config.get("file", "logs/collision.log") if self._config else "logs/collision.log"
        )
        log_dir = os.path.dirname(os.path.abspath(log_file)) or "."
        # 若目录不存在，退化到当前工作目录
        check_path = log_dir if os.path.exists(log_dir) else "."
        try:
            usage = shutil.disk_usage(check_path)
            free_mb = usage.free / (1024 * 1024)
            total_mb = usage.total / (1024 * 1024)
            used_pct = (usage.used / usage.total) * 100
            if free_mb < min_free_mb:
                # 使用 print 而非 logging，避免递归初始化
                print(
                    f"[磁盘警告] 日志目录 '{check_path}' 可用空间不足 "
                    f"{free_mb:.0f} MB（阈值 {min_free_mb} MB，"
                    f"总计 {total_mb:.0f} MB，已用 {used_pct:.1f}%）",
                    file=sys.stderr,
                )
                return False
            return True
        except Exception as e:
            # 磁盘检查失败不应阻止程序启动
            print(f"[磁盘检查] 无法获取磁盘空间信息: {e}", file=sys.stderr)
            return True

    def _setup_root_logger(self) -> None:
        """配置根日志记录器"""
        assert self._config is not None
        level = self._config.get("level", "INFO")
        format_str = self._config.get("format", self.DEFAULT_CONFIG["format"])

        # 设置根日志级别
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level))

        # 清除现有处理器
        root_logger.handlers.clear()

        # 检查环境变量是否禁用控制台日志
        disable_console = os.environ.get("DISABLE_CONSOLE_LOG", "").lower() in ("1", "true", "yes")

        # 控制台处理器（使用 SafeStreamHandler 以兼容 Windows GBK 编码）
        if self._config.get("enable_console", True) and not disable_console:
            console_handler = SafeStreamHandler(sys.stdout)
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
        assert self._config is not None
        rotation_type = self._config.get("rotation_type", "size")
        level = self._config.get("level", "INFO")

        try:
            handler: logging.Handler
            if rotation_type == "time":
                # 基于时间的轮转
                handler = TimedRotatingFileHandler(
                    log_file,
                    when=self._config.get("rotation_when", "midnight"),
                    interval=self._config.get("rotation_interval", 1),
                    backupCount=self._config.get("backup_count", 5),
                    encoding="utf-8-sig",  # 修复: 使用UTF-8-BOM解决Windows中文乱码
                )
            else:
                # 基于大小的轮转（默认）
                handler = SafeRotatingFileHandler(
                    log_file,
                    maxBytes=self._config.get("max_bytes", 10 * 1024 * 1024),
                    backupCount=self._config.get("backup_count", 5),
                    encoding="utf-8-sig",  # 修复: 使用UTF-8-BOM解决Windows中文乱码
                )

            handler.setLevel(getattr(logging, level))
            handler.setFormatter(logging.Formatter(format_str))

            # M10: 包装文件处理器，捕获磁盘满 OSError
            class _DiskSafeHandler(logging.Handler):
                """OSError（磁盘满）安全包装层"""

                def __init__(self, inner: logging.Handler) -> None:
                    super().__init__(inner.level)
                    self._inner = inner
                    self._disk_full_warned = False

                def setFormatter(self, fmt) -> None:
                    self._inner.setFormatter(fmt)

                def emit(self, record: logging.LogRecord) -> None:
                    try:
                        self._inner.emit(record)
                        self._disk_full_warned = False  # 恢复后重置警告状态
                    except OSError as os_err:
                        if not self._disk_full_warned:
                            self._disk_full_warned = True
                            print(
                                f"[日志警告] 日志文件写入失败（磁盘可能已满）: {os_err}"
                                f" 请清理磁盘或调整 logging.file 路径",
                                file=sys.stderr,
                            )

                def close(self) -> None:
                    self._inner.close()
                    super().close()

            # 设置日志文件权限为仅所有者可读写
            try:
                os.chmod(log_file, 0o600)
            except OSError:
                pass  # Windows 系统可能不支持 chmod

            return _DiskSafeHandler(handler)
        except Exception as e:
            print(f"创建日志文件处理器失败: {e}", file=sys.stderr)
            return None

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        if not self._initialized:
            self.init()
        assert self._config is not None
        return self._config.copy()

    def get_logger(self, name: str, thread_safe: bool = False) -> logging.Logger:
        """
        获取配置好的日志记录器

        参数:
            name: 日志记录器名称
            thread_safe: 已弃用，Python的logging.Logger本身是线程安全的

        返回:
            配置好的日志记录器
        """
        if not self._initialized:
            self.init()

        logger = logging.getLogger(name)

        # v2.2.1修复: Python的logging.Logger本身是线程安全的（内部使用RLock）
        # thread_safe参数已弃用，直接返回原生logger
        if thread_safe:
            import warnings

            warnings.warn(
                f"get_logger(thread_safe=True)已弃用。Python的logging.Logger本身是线程安全的，"
                f"请直接使用 get_logger('{name}', thread_safe=False) 或省略该参数。",
                DeprecationWarning,
                stacklevel=2,
            )

        return logger


# 全局日志配置实例
logging_config = LoggingConfig()


def init_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """
    初始化日志系统

    参数:
        config: 自定义配置字典
    """
    logging_config.init(config)

    # 启用日志安全过滤器（P0-2修复）
    _setup_security_filter()


def _setup_security_filter() -> None:
    """设置日志安全过滤器（P0-2修复）

    自动检测并屏蔽日志中的敏感信息：
    - 比特币私钥（64位十六进制）
    - WIF格式私钥
    - 原始私钥字节

    注：幂等设计，多次调用只执行一次。
    """
    global _security_filter_initialized
    if _security_filter_initialized:
        return
    try:
        # 创建安全过滤器
        security_filter = SecurityLogFilter(
            name="security_filter", mask_private_keys=True, mask_wif=True, mask_addresses=True
        )

        # 添加到根日志记录器
        root_logger = logging.getLogger()
        root_logger.addFilter(security_filter)

        # 添加到主要模块日志记录器（处理私钥/敏感数据的模块）
        module_loggers = [
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

        for logger_name in module_loggers:
            logger = logging.getLogger(logger_name)
            logger.addFilter(security_filter)

        # 注意：这里不使用logging.info，因为日志系统可能还未完全初始化
        print("[INFO] 日志安全过滤器已启用（防止私钥泄露）")
        _security_filter_initialized = True

    except Exception as e:
        # 安全过滤器初始化失败不应阻止日志系统工作
        print(f"[WARNING] 日志安全过滤器初始化失败: {e}")
        print("[WARNING] 日志系统将继续工作，但可能不会屏蔽敏感信息")


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
