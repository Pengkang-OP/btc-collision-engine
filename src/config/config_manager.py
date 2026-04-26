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

# DF-3修复: 添加JSON Schema验证
try:
    from jsonschema import Draft7Validator
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logger.debug("jsonschema库未安装，配置文件将跳过Schema验证")


class ConfigManager:
    """配置管理器 - 统一管理应用配置"""
    
    # 审查修复#5: 将Schema提取为类常量，避免每次验证都重新创建
    # 优化: 将Draft7Validator实例缓存为类变量，避免重复创建开销
    _cached_validator = None  # 类级缓存的Schema验证器实例
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "collision": {
                "type": "object",
                "properties": {
                    "max_workers": {"type": ["integer", "null"], "minimum": 1, "maximum": 1024},
                    "progress_interval": {"type": "integer", "minimum": 1},
                    "checkpoint_interval": {"type": "integer", "minimum": 1},
                    "dedup_max_size": {"type": "integer", "minimum": 1},
                    # D-2修复: 补充 config.example.json 中存在的性能优化字段
                    "use_performance_optimization": {"type": "boolean"},
                    "precomputed_window_size": {"type": "integer", "minimum": 1, "maximum": 16},
                    "use_simd_hash": {"type": "boolean"},
                    "use_memory_pool": {"type": "boolean"},
                    "use_gpu_memory_pool": {"type": "boolean"},
                    "gpu_pool_max_buffers": {"type": "integer", "minimum": 1},
                    "gpu_pool_max_memory_mb": {"type": "integer", "minimum": 1}
                },
                "additionalProperties": False  # 审查修复#3: 禁止额外属性
            },
            "logging": {
                "type": "object",
                "properties": {
                    "level": {"enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                    "format": {"type": "string"},
                    "file": {"type": "string"},
                    "max_bytes": {"type": "integer", "minimum": 1},
                    "backup_count": {"type": "integer", "minimum": 0},
                    "enable_console": {"type": "boolean"},
                    "enable_file": {"type": "boolean"},
                    "rotation_type": {"enum": ["size", "time"]},
                    "rotation_when": {"type": "string"},
                    "rotation_interval": {"type": "integer", "minimum": 1},
                    "compress_backups": {"type": "boolean"}
                },
                "additionalProperties": False  # 审查修复#3: 禁止额外属性
            },
            "gpu": {
                "type": "object",
                "properties": {
                    "use_gpu": {"type": "boolean"},
                    "device_index": {"type": "integer"},
                    "batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216},
                    "auto_detect": {"type": "boolean"},
                    "memory_usage_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                    "enable_vendor_optimizations": {"type": "boolean"},
                    # CFG-1修复: 添加缺失的GPU配置项
                    "async_execution": {"type": "boolean"},
                    "work_group_size": {"type": "integer", "minimum": 64, "maximum": 2048},
                    "use_fast_math": {"type": "boolean"},
                    "use_uint32_workaround": {"type": "boolean"},
                    "compiler_flags": {"type": "string"},
                    # D-2修复: 补充 config.example.json gpu区块字段
                    "use_new_module": {"type": "boolean"},
                    "mode": {"enum": ["auto", "single", "multi"]},
                    "device_indices": {"type": "array", "items": {"type": "integer"}},
                    "load_balancing": {"enum": ["performance", "equal"]},
                    "auto_tuning": {"type": "boolean"},
                    # 队列深度优化 v2.3.2: GPU 命令队列预提交批次数
                    "queue_depth": {"type": "integer", "minimum": 1, "maximum": 16},
                    # 内存池相关配置
                    "gpu_memory_pool": {"type": "boolean"},
                    "max_buffers": {"type": "integer", "minimum": 1},
                    "max_memory_mb": {"type": "integer", "minimum": 64},
                    # 超时保护配置
                    "timeout_protection": {"type": "boolean"},
                    "base_timeout_seconds": {"type": "number", "minimum": 1},
                    "max_error_retries": {"type": "integer", "minimum": 1},
                    # 种子预生成缓存
                    "seed_prefetch_size": {"type": "integer", "minimum": 1, "maximum": 64},
                    # 驱动检查配置
                    "driver_check": {"type": "object"},
                    # 每设备独立配置
                    "per_device_config": {"type": "object"}
                },
                "additionalProperties": False  # 审查修复#3: 禁止额外属性
            },
            "performance_monitoring": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "track_slow_operations": {"type": "boolean"},
                    "slow_threshold_ms": {"type": "number", "minimum": 0},
                    "max_records": {"type": "integer", "minimum": 1},
                    "log_level": {"enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]}
                },
                "additionalProperties": False  # 审查修复#3: 禁止额外属性
            },
            "crypto": {
                "type": "object",
                "properties": {
                    "backend": {"enum": ["auto", "pure_python", "pure_python_const_time", "openssl", "coincurve", "ecdsa"]},
                    "constant_time": {"type": "boolean"},
                    "verify_checksums": {"type": "boolean"},
                    "strict_wif_validation": {"type": "boolean"},
                    # D-2修复: 补充 config.example.json crypto区块字段
                    "use_gpu": {"type": "boolean"},
                    "gpu_device_index": {"type": "integer"},
                    "gpu_batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216}
                },
                "additionalProperties": False  # 审查修复#3: 禁止额外属性
            },
            # D-2修复: 补充 config.example.json 中的 monitoring 顶层区块
            "monitoring": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "collection_interval": {"type": "integer", "minimum": 1},
                    "storage_dir": {"type": "string"},
                    "history_max_size": {"type": "integer", "minimum": 1},
                    "error_max_size": {"type": "integer", "minimum": 1},
                    "anomaly_thresholds": {
                        "type": "object",
                        "properties": {
                            "speed": {
                                "type": "object",
                                "properties": {
                                    "min": {"type": "number"},
                                    "max": {"type": "number"}
                                },
                                "additionalProperties": False
                            },
                            "cpu_usage": {
                                "type": "object",
                                "properties": {"max": {"type": "number"}},
                                "additionalProperties": False
                            },
                            "memory_usage": {
                                "type": "object",
                                "properties": {"max": {"type": "number"}},
                                "additionalProperties": False
                            }
                        },
                        "additionalProperties": False
                    },
                    "auto_cleanup": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "max_age_days": {"type": "integer", "minimum": 1}
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            },
            # i18n 国际化配置节
            "i18n": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "fallback_language": {"type": "string"}
                },
                "additionalProperties": False
            },
            # CFG-2修复: 补充 config.json 中的 engine 区块
            "engine": {
                "type": "object",
                "properties": {
                    "mode": {"enum": ["random", "sequential", "range", "brute_force"]},
                    "batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216},
                    "max_threads": {"type": "integer", "minimum": 1, "maximum": 1024}
                },
                "additionalProperties": False
            },
            # CFG-2修复: 补充 config.json 中的 gui 区块
            "gui": {
                "type": "object",
                "properties": {
                    "theme": {"enum": ["dark", "light"]},
                    "font": {"type": "string"},
                    "font_size": {"type": "integer", "minimum": 8, "maximum": 72},
                    "window_width": {"type": "integer", "minimum": 400},
                    "window_height": {"type": "integer", "minimum": 300}
                },
                "additionalProperties": False
            },
            # CFG-2修复: 补充 config.json 中的 optimization 区块
            "optimization": {
                "type": "object",
                "properties": {
                    "uint32_workaround": {"type": "boolean"},
                    "disable_async_transfer": {"type": "boolean"},
                    "conservative_memory_policy": {"type": "boolean"},
                    "adaptive_timeout": {"type": "boolean"}
                },
                "additionalProperties": False
            }
        },
        "additionalProperties": False  # 审查修复#3: 顶层也禁止额外属性
    }
    
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
        "gpu": {
            "use_gpu": True,
            "device_index": -1,  # -1表示自动选择
            "batch_size": 65536,
            "auto_detect": True,
            "memory_usage_ratio": 0.5,
            "enable_vendor_optimizations": True,
            "queue_depth": 4  # GPU 命令队列预提交批次数，默认 4
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
        },
        "i18n": {
            "language": "auto",
            "fallback_language": "en_US",
        }
    }
    
    def __init__(self, config_file: str = None):
        """
        初始化配置管理器
        
        参数:
            config_file: 配置文件路径，None表示使用默认配置
        """
        self.config_file = config_file
        # P2修复：使用深拷贝避免浅拷贝导致的嵌套字典共享问题
        # 浅拷贝.copy()只会拷贝顶层字典，嵌套字典仍然是同一个引用
        # 这会导致一个实例修改配置影响其他实例
        import copy
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        self._lock = threading.Lock()  # 线程锁保护配置读写
        
        if config_file and os.path.exists(config_file):
            self.load_config()
    
    @staticmethod
    def _strip_comments(config: Any) -> Any:
        """D-2修复: 递归移除所有以 '_comment' 开头的注释键，使 config.example.json
        可直接作为合法配置使用（与 additionalProperties:False 的 JSON Schema 兼容）。

        参数:
            config: 配置字典或任意值

        返回:
            过滤后的配置字典（不修改原对象）
        """
        if isinstance(config, dict):
            return {
                k: ConfigManager._strip_comments(v)
                for k, v in config.items()
                if not k.startswith('_comment')
            }
        return config

    def load_config(self) -> bool:
        """
        从文件加载配置（线程安全）
        
        返回:
            加载成功返回True，失败返回False
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            # D-2修复: 过滤 _comment 注释键，兼容 config.example.json 直接使用
            user_config = self._strip_comments(raw_config)

            # DF-3修复: 配置文件格式校验（使用统一的validate方法）
            validation_errors = self.validate(user_config)
            if validation_errors:
                error_msgs = [f"{k}: {v}" for k, v in validation_errors.items()]
                logger.error(f"配置文件格式错误:\n" + "\n".join(error_msgs))
                return False
            
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
        # DF-1修复：整个遍历过程在锁内完成，确保真正的线程安全
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
    
    def validate(self, config: Dict[str, Any] = None) -> Dict[str, str]:
        """
        DF-3修复: 统一配置验证逻辑
        
        优先使用JSON Schema验证（如果可用），否则使用手动验证。
        
        参数:
            config: 要验证的配置字典，None表示验证当前配置
            
        返回:
            验证失败的配置项和错误信息字典
        """
        if config is None:
            config = self.config
        
        # DF-3修复: 统一验证逻辑
        if HAS_JSONSCHEMA:
            # 使用JSON Schema验证
            return self._validate_with_schema(config)
        else:
            # 降级为手动验证
            return self._validate_manual(config)
    
    def _validate_with_schema(self, config: Dict[str, Any]) -> Dict[str, str]:
        """DF-3修复: 使用JSON Schema验证配置
        
        参数:
            config: 用户配置字典
            
        返回:
            错误信息字典，空字典表示验证通过
        """
        if not HAS_JSONSCHEMA:
            return {}  # 没有jsonschema库，返回空
        
        # 优化: 使用缓存的验证器实例，避免每次验证都重新创建
        # 审查修复#5: 使用类常量Schema，避免重复创建
        # 审查修复#1: 使用Draft7Validator收集所有错误，而非只捕获第一个
        errors = {}
        validator = self._get_validator()
        if validator is None:
            return {}
        for error in sorted(validator.iter_errors(config), key=lambda e: e.path):
            path = '.'.join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            # 避免覆盖同一字段的多个错误
            if path not in errors:
                errors[path] = error.message
            else:
                errors[path] += f"; {error.message}"
        
        return errors
    
    @classmethod
    def _get_validator(cls):
        """获取缓存的Schema验证器实例（懒加载）"""
        if cls._cached_validator is None:
            if HAS_JSONSCHEMA:
                cls._cached_validator = Draft7Validator(cls.CONFIG_SCHEMA)
                logger.debug("Draft7Validator实例已初始化并缓存")
        return cls._cached_validator
    
    @staticmethod
    def _is_strict_bool(value: Any) -> bool:
        """审查修复#4: 严格布尔值检查，防止int被误认为bool
        
        在Python中，bool是int的子类，isinstance(True, int)返回True。
        此方法确保只接受真正的布尔值，不接受整数（但JSON解析的True/False是bool类型）。
        
        参数:
            value: 要检查的值
            
        返回:
            如果是严格的布尔值返回True，否则返回False
        """
        # JSON解析的True/False是bool类型，isinstance返回True
        # 但用户直接传入的1/0是int类型，应该拒绝
        return type(value) is bool
    
    def _validate_manual(self, config: Dict[str, Any]) -> Dict[str, str]:
        """DF-3修复: 手动验证配置（降级方案）
        
        参数:
            config: 用户配置字典
            
        返回:
            错误信息字典
        """
        errors = {}
        
        # 验证碰撞引擎配置
        max_workers = config.get("collision", {}).get("max_workers")
        if max_workers is not None and (not isinstance(max_workers, int) or max_workers <= 0):
            errors["collision.max_workers"] = "必须是正整数"
        elif max_workers is not None and max_workers > 1024:
            errors["collision.max_workers"] = "上限为 1024（避免线程过度创建导致系统和内存耗尽）"
        
        progress_interval = config.get("collision", {}).get("progress_interval")
        if progress_interval is not None and (not isinstance(progress_interval, int) or progress_interval <= 0):
            errors["collision.progress_interval"] = "必须是正整数"
        
        checkpoint_interval = config.get("collision", {}).get("checkpoint_interval")
        if checkpoint_interval is not None and (not isinstance(checkpoint_interval, int) or checkpoint_interval <= 0):
            errors["collision.checkpoint_interval"] = "必须是正整数"
        
        dedup_max_size = config.get("collision", {}).get("dedup_max_size")
        if dedup_max_size is not None and (not isinstance(dedup_max_size, int) or dedup_max_size <= 0):
            errors["collision.dedup_max_size"] = "必须是正整数"
        
        # 审查修复#2: 补充日志配置验证（之前缺失）
        logging_config = config.get("logging", {})
        
        log_level = logging_config.get("level")
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level is not None and log_level not in valid_levels:
            errors["logging.level"] = f"必须是以下值之一: {', '.join(valid_levels)}"
        
        log_format = logging_config.get("format")
        if log_format is not None and not isinstance(log_format, str):
            errors["logging.format"] = "必须是字符串"
        
        log_file = logging_config.get("file")
        if log_file is not None and not isinstance(log_file, str):
            errors["logging.file"] = "必须是字符串路径"
        
        log_max_bytes = logging_config.get("max_bytes")
        if log_max_bytes is not None and (not isinstance(log_max_bytes, int) or log_max_bytes <= 0):
            errors["logging.max_bytes"] = "必须是正整数"
        
        log_backup_count = logging_config.get("backup_count")
        if log_backup_count is not None and (not isinstance(log_backup_count, int) or log_backup_count < 0):
            errors["logging.backup_count"] = "必须是非负整数"
        
        log_enable_console = logging_config.get("enable_console")
        if log_enable_console is not None and not self._is_strict_bool(log_enable_console):
            errors["logging.enable_console"] = "必须是布尔值"
        
        log_enable_file = logging_config.get("enable_file")
        if log_enable_file is not None and not self._is_strict_bool(log_enable_file):
            errors["logging.enable_file"] = "必须是布尔值"
        
        log_rotation_type = logging_config.get("rotation_type")
        valid_rotation_types = ["size", "time"]
        if log_rotation_type is not None and log_rotation_type not in valid_rotation_types:
            errors["logging.rotation_type"] = f"必须是以下值之一: {', '.join(valid_rotation_types)}"
        
        log_rotation_when = logging_config.get("rotation_when")
        if log_rotation_when is not None and not isinstance(log_rotation_when, str):
            errors["logging.rotation_when"] = "必须是字符串"
        
        log_rotation_interval = logging_config.get("rotation_interval")
        if log_rotation_interval is not None and (not isinstance(log_rotation_interval, int) or log_rotation_interval <= 0):
            errors["logging.rotation_interval"] = "必须是正整数"
        
        log_compress_backups = logging_config.get("compress_backups")
        if log_compress_backups is not None and not self._is_strict_bool(log_compress_backups):
            errors["logging.compress_backups"] = "必须是布尔值"
        
        # 验证 GPU 配置
        gpu_config = config.get("gpu", {})
        
        gpu_batch_size = gpu_config.get("batch_size")
        if gpu_batch_size is not None and (not isinstance(gpu_batch_size, int) or gpu_batch_size <= 0):
            errors["gpu.batch_size"] = "必须是正整数"
        elif gpu_batch_size is not None and gpu_batch_size > 16777216:
            errors["gpu.batch_size"] = "上限为 16777216 (16M)，避免显存耗尽"
        
        gpu_device_index = gpu_config.get("device_index")
        if gpu_device_index is not None and not isinstance(gpu_device_index, int):
            errors["gpu.device_index"] = "必须是整数"
        
        gpu_memory_ratio = gpu_config.get("memory_usage_ratio")
        if gpu_memory_ratio is not None and (not isinstance(gpu_memory_ratio, (int, float)) or not (0 < gpu_memory_ratio <= 1.0)):
            errors["gpu.memory_usage_ratio"] = "必须在(0, 1]范围内"
        
        gpu_use_gpu = gpu_config.get("use_gpu")
        if gpu_use_gpu is not None and not self._is_strict_bool(gpu_use_gpu):
            errors["gpu.use_gpu"] = "必须是布尔值"
        
        gpu_auto_detect = gpu_config.get("auto_detect")
        if gpu_auto_detect is not None and not self._is_strict_bool(gpu_auto_detect):
            errors["gpu.auto_detect"] = "必须是布尔值"
        
        gpu_vendor_opts = gpu_config.get("enable_vendor_optimizations")
        if gpu_vendor_opts is not None and not self._is_strict_bool(gpu_vendor_opts):
            errors["gpu.enable_vendor_optimizations"] = "必须是布尔值"
        
        # 验证性能监控配置
        perf_config = config.get("performance_monitoring", {})
        
        perf_enabled = perf_config.get("enabled")
        if perf_enabled is not None and not self._is_strict_bool(perf_enabled):  # 审查修复#4: 严格布尔值检查
            errors["performance_monitoring.enabled"] = "必须是布尔值"
        
        perf_track_slow = perf_config.get("track_slow_operations")
        if perf_track_slow is not None and not self._is_strict_bool(perf_track_slow):
            errors["performance_monitoring.track_slow_operations"] = "必须是布尔值"
        
        perf_threshold = perf_config.get("slow_threshold_ms")
        if perf_threshold is not None:
            if not isinstance(perf_threshold, (int, float)) or perf_threshold < 0:
                errors["performance_monitoring.slow_threshold_ms"] = "必须是非负数（毫秒）"
        
        perf_max_records = perf_config.get("max_records")
        if perf_max_records is not None:
            if not isinstance(perf_max_records, int) or perf_max_records <= 0:
                errors["performance_monitoring.max_records"] = "必须是正整数"
        
        perf_log_level = perf_config.get("log_level")
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if perf_log_level is not None and perf_log_level not in valid_log_levels:
            errors["performance_monitoring.log_level"] = f"必须是以下值之一: {', '.join(valid_log_levels)}"
        
        # 验证Crypto配置
        crypto_config = config.get("crypto", {})
        
        crypto_backend = crypto_config.get("backend")
        valid_backends = ["auto", "pure_python", "pure_python_const_time", "openssl", "coincurve", "ecdsa"]
        if crypto_backend is not None and crypto_backend not in valid_backends:
            errors["crypto.backend"] = f"必须是以下值之一: {', '.join(valid_backends)}"
        
        # 审查修复#2: 补充Crypto配置验证（之前缺失）
        crypto_constant_time = crypto_config.get("constant_time")
        if crypto_constant_time is not None and not self._is_strict_bool(crypto_constant_time):
            errors["crypto.constant_time"] = "必须是布尔值"
        
        crypto_verify_checksums = crypto_config.get("verify_checksums")
        if crypto_verify_checksums is not None and not self._is_strict_bool(crypto_verify_checksums):
            errors["crypto.verify_checksums"] = "必须是布尔值"
        
        crypto_strict_wif = crypto_config.get("strict_wif_validation")
        if crypto_strict_wif is not None and not self._is_strict_bool(crypto_strict_wif):
            errors["crypto.strict_wif_validation"] = "必须是布尔值"
        
        # 审查修复#6: 添加配置依赖关系验证
        # 日志轮转依赖验证
        if log_rotation_type == "size" and "max_bytes" not in logging_config:
            errors["logging.max_bytes"] = "size轮转模式需要配置max_bytes"
        elif log_rotation_type == "time" and "rotation_when" not in logging_config:
            errors["logging.rotation_when"] = "time轮转模式需要配置rotation_when"
        
        return errors
