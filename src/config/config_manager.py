"""配置管理器"""
import json
import os
import threading
from typing import Dict, Any, Optional

# 导入日志配置
from ..utils import init_logging, get_configured_logger

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("ConfigManager")


class ConfigManager:
    """配置管理器 - 统一管理应用配置"""
    
    DEFAULT_CONFIG = {
        "collision": {
            "max_workers": None,  # 线程池最大工作线程数，None表示使用默认值
            "progress_interval": 1000,  # 进度回调间隔
            "checkpoint_interval": 30,  # 断点自动保存间隔（秒）
            "dedup_max_size": 1_000_000,  # 去重过滤器最大容量
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/collision.log",
            "max_bytes": 10485760,
            "backup_count": 5,
            "enable_console": True,
            "enable_file": True,
            "rotation_type": "size",
            "rotation_when": "midnight",
            "rotation_interval": 1,
            "compress_backups": False
        },
        "gui": {
            "theme": "dark",
            "font": "Microsoft YaHei",
            "font_size": 10,
            "window_width": 800,
            "window_height": 600
        },
        "gpu": {
            "use_gpu": True,
            "device_index": -1,  # -1表示自动选择
            "batch_size": 65536,
            "auto_detect": True,
            "memory_usage_ratio": 0.5,
            "enable_vendor_optimizations": True
        },
        "performance_monitoring": {
            "enabled": True,  # 是否启用性能监控
            "track_slow_operations": True,  # 是否追踪慢操作
            "slow_threshold_ms": 1000,  # 慢操作阈值（毫秒）
            "max_records": 10000,  # 最大记录数
            "log_level": "INFO"  # 性能日志级别（INFO/DEBUG/WARNING）
        },
        "crypto": {
            "backend": "auto",
            "constant_time": False,
            "verify_checksums": True,
            "strict_wif_validation": True,
        }
    }
    
    def __init__(self, config_file: str = None):
        """
        初始化配置管理器
        
        参数:
            config_file: 配置文件路径，None表示使用默认配置
        """
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self._lock = threading.Lock()  # 线程锁保护配置读写
        
        if config_file and os.path.exists(config_file):
            self.load_config()
    
    def load_config(self) -> bool:
        """
        从文件加载配置（线程安全）
        
        返回:
            加载成功返回True，失败返回False
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            # 线程安全：在锁内合并配置
            with self._lock:
                self._merge_config(self.config, user_config)
            return True
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False
    
    def save_config(self) -> bool:
        """
        保存配置到文件（线程安全）
        
        返回:
            保存成功返回True，失败返回False
        """
        if not self.config_file:
            return False
        
        try:
            # 线程安全：在锁内复制配置，避免长时间持有锁
            with self._lock:
                config_copy = self._deep_copy_config(self.config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_copy, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（线程安全）
        
        参数:
            key: 配置键，支持点号分隔的路径，如 "collision.max_workers"
            default: 默认值
            
        返回:
            配置值
        """
        keys = key.split('.')
        # 线程安全：在锁内读取配置
        with self._lock:
            value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值（线程安全）
        
        参数:
            key: 配置键，支持点号分隔的路径
            value: 配置值
            
        返回:
            设置成功返回True，失败返回False
        """
        keys = key.split('.')
        # 线程安全：在锁内修改配置
        with self._lock:
            config = self.config
            
            for i, k in enumerate(keys[:-1]):
                if k not in config or not isinstance(config[k], dict):
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
        return True
    
    def _merge_config(self, base: Dict, update: Dict):
        """
        递归合并配置（必须在锁内调用）
        
        参数:
            base: 基础配置
            update: 更新配置
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _deep_copy_config(self, config: Dict) -> Dict:
        """
        深拷贝配置字典（避免在写文件时持有锁）
        
        参数:
            config: 要拷贝的配置字典
            
        返回:
            配置字典的深拷贝
        """
        import copy
        return copy.deepcopy(config)
    
    def validate(self) -> Dict[str, str]:
        """
        验证配置
        
        返回:
            验证失败的配置项和错误信息
        """
        errors = {}
        
        # 验证碰撞引擎配置
        max_workers = self.get("collision.max_workers")
        if max_workers is not None and (not isinstance(max_workers, int) or max_workers <= 0):
            errors["collision.max_workers"] = "必须是正整数"
        
        progress_interval = self.get("collision.progress_interval")
        if not isinstance(progress_interval, int) or progress_interval <= 0:
            errors["collision.progress_interval"] = "必须是正整数"
        
        checkpoint_interval = self.get("collision.checkpoint_interval")
        if not isinstance(checkpoint_interval, int) or checkpoint_interval <= 0:
            errors["collision.checkpoint_interval"] = "必须是正整数"
        
        dedup_max_size = self.get("collision.dedup_max_size")
        if not isinstance(dedup_max_size, int) or dedup_max_size <= 0:
            errors["collision.dedup_max_size"] = "必须是正整数"
        
        # 验证日志配置
        log_level = self.get("logging.level")
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level not in valid_levels:
            errors["logging.level"] = f"必须是以下值之一: {', '.join(valid_levels)}"
        
        # 验证GUI配置
        window_width = self.get("gui.window_width")
        if not isinstance(window_width, int) or window_width <= 0:
            errors["gui.window_width"] = "必须是正整数"
        
        window_height = self.get("gui.window_height")
        if not isinstance(window_height, int) or window_height <= 0:
            errors["gui.window_height"] = "必须是正整数"
        
        font_size = self.get("gui.font_size")
        if not isinstance(font_size, int) or font_size <= 0:
            errors["gui.font_size"] = "必须是正整数"
        
        # 验证GPU配置
        gpu_batch_size = self.get("gpu.batch_size")
        if not isinstance(gpu_batch_size, int) or gpu_batch_size <= 0:
            errors["gpu.batch_size"] = "必须是正整数"
        
        gpu_device_index = self.get("gpu.device_index")
        if not isinstance(gpu_device_index, int):
            errors["gpu.device_index"] = "必须是整数"
        
        gpu_memory_ratio = self.get("gpu.memory_usage_ratio")
        if not isinstance(gpu_memory_ratio, (int, float)) or not (0 < gpu_memory_ratio <= 1.0):
            errors["gpu.memory_usage_ratio"] = "必须在(0, 1]范围内"
        
        # 验证Crypto配置
        crypto_backend = self.get("crypto.backend")
        valid_backends = ["auto", "pure_python", "pure_python_const_time", "openssl", "coincurve", "ecdsa"]
        if crypto_backend not in valid_backends:
            errors["crypto.backend"] = f"必须是以下值之一: {', '.join(valid_backends)}"
        
        return errors
