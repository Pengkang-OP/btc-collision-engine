"""配置管理器"""

import copy
import json
import os
import threading
from typing import Dict, Any, List, Callable, Optional

# 导入日志配置
from ..utils import init_logging, get_configured_logger
from .config_watcher import ConfigWatcher  # noqa: F401 — type annotation reference

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("ConfigManager")

# DF-3修复: 添加JSON Schema验证
try:
    from jsonschema import Draft7Validator

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logger.debug("jsonschema库未安装，配置文件将跳过Schema验证")

class ConfigManager:
    """配置管理器 - 统一管理应用配置"""

    # 审查修复#5: 将Schema提取为类常量，避免每次验证都重新创建
    # 优化: 将Draft7Validator实例缓存为类变量，避免重复创建开销
    _cached_validator = None  # 类级缓存的Schema验证器实例
    _validator_lock = threading.Lock()  # 类级锁，保护验证器初始化
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
                    "gpu_pool_max_memory_mb": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,  # 审查修复#3: 禁止额外属性
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
                    "compress_backups": {"type": "boolean"},
                },
                "additionalProperties": False,  # 审查修复#3: 禁止额外属性
            },
            "gpu": {
                "type": "object",
                "properties": {
                    "use_gpu": {"type": "boolean"},
                    "device_index": {"type": "integer"},
                    "batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216},
                    "auto_detect": {"type": "boolean"},
                    "memory_usage_ratio": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
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
                    "per_device_config": {"type": "object"},
                },
                "additionalProperties": False,  # 审查修复#3: 禁止额外属性
            },
            "performance_monitoring": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "track_slow_operations": {"type": "boolean"},
                    "slow_threshold_ms": {"type": "number", "minimum": 0},
                    "max_records": {"type": "integer", "minimum": 1},
                    "log_level": {"enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                },
                "additionalProperties": False,  # 审查修复#3: 禁止额外属性
            },
            "crypto": {
                "type": "object",
                "properties": {
                    "backend": {
                        "enum": [
                            "auto",
                            "pure_python",
                            "pure_python_const_time",
                            "openssl",
                            "coincurve",
                            "ecdsa",
                        ]
                    },
                    "constant_time": {"type": "boolean"},
                    "verify_checksums": {"type": "boolean"},
                    "strict_wif_validation": {"type": "boolean"},
                    # D-2修复: 补充 config.example.json crypto区块字段
                    "use_gpu": {"type": "boolean"},
                    "gpu_device_index": {"type": "integer"},
                    "gpu_batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216},
                },
                "additionalProperties": False,  # 审查修复#3: 禁止额外属性
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
                                    "max": {"type": "number"},
                                },
                                "additionalProperties": False,
                            },
                            "cpu_usage": {
                                "type": "object",
                                "properties": {"max": {"type": "number"}},
                                "additionalProperties": False,
                            },
                            "memory_usage": {
                                "type": "object",
                                "properties": {"max": {"type": "number"}},
                                "additionalProperties": False,
                            },
                        },
                        "additionalProperties": False,
                    },
                    "auto_cleanup": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "max_age_days": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
            # i18n 国际化配置节
            "i18n": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "fallback_language": {"type": "string"},
                },
                "additionalProperties": False,
            },
            # CFG-2修复: 补充 config.json 中的 engine 区块
            "engine": {
                "type": "object",
                "properties": {
                    "mode": {"enum": ["random", "sequential", "range", "brute_force"]},
                    "batch_size": {"type": "integer", "minimum": 1, "maximum": 16777216},
                    "max_threads": {"type": "integer", "minimum": 1, "maximum": 1024},
                },
                "additionalProperties": False,
            },
            # CFG-2修复: 补充 config.json 中的 gui 区块
            "gui": {
                "type": "object",
                "properties": {
                    "theme": {"enum": ["dark", "light"]},
                    "font": {"type": "string"},
                    "font_size": {"type": "integer", "minimum": 8, "maximum": 72},
                    "window_width": {"type": "integer", "minimum": 400},
                    "window_height": {"type": "integer", "minimum": 300},
                },
                "additionalProperties": False,
            },
            # CFG-2修复: 补充 config.json 中的 optimization 区块
            "optimization": {
                "type": "object",
                "properties": {
                    "uint32_workaround": {"type": "boolean"},
                    "disable_async_transfer": {"type": "boolean"},
                    "conservative_memory_policy": {"type": "boolean"},
                    "adaptive_timeout": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,  # 审查修复#3: 顶层也禁止额外属性
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
            "compress_backups": False,
        },
        "gpu": {
            "use_gpu": True,
            "device_index": -1,  # -1表示自动选择
            "batch_size": 1048576,  # C-06: 与 config.example.json 同步 (1M)
            "auto_detect": True,
            "memory_usage_ratio": 0.7,  # C-06: Intel Arc 推荐值 (70%)
            "enable_vendor_optimizations": True,
            "queue_depth": 4,  # GPU 命令队列预提交批次数，默认 4
        },
        "performance_monitoring": {
            "enabled": True,  # 是否启用性能监控
            "track_slow_operations": True,  # 是否追踪慢操作
            "slow_threshold_ms": 1000,  # 慢操作阈值（毫秒）
            "max_records": 10000,  # 最大记录数
            "log_level": "INFO",  # 性能日志级别（INFO/DEBUG/WARNING）
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
        },
    }

    def __init__(self, config_file: Optional[str] = None) -> None:
        """
        初始化配置管理器

        参数:
            config_file: 配置文件路径，None表示使用默认配置
        """
        self.config_file = config_file
        self._lock = threading.Lock()  # 线程锁保护配置读写

        # M-6修复: 延迟深拷贝，只有在加载配置时才拷贝默认配置
        # 避免每次实例化都执行不必要的深拷贝操作
        self._config_initialized = False

        if config_file and os.path.exists(config_file):
            self.load_config()

        # P2-4: 配置热重载支持
        self._change_callbacks: List[Callable[[], None]] = []
        self._watcher = None  # type: Optional['ConfigWatcher']

    @property
    def config(self) -> Dict[str, Any]:
        """延迟初始化配置属性"""
        if not self._config_initialized:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            self._config_initialized = True
        return self._config

    @config.setter
    def config(self, value: Dict[str, Any]) -> None:
        """设置配置属性（线程安全）"""
        # SUGGESTION-8: 添加锁保护以保持与getter的线程安全一致性
        with self._lock:
            self._config = value
            self._config_initialized = True

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
                if not k.startswith("_comment")
            }
        return config

    def load_config(self) -> bool:
        """
        从文件加载配置（线程安全）

        返回:
            加载成功返回True，失败返回False
        """
        try:
            if not self.config_file:
                logger.warning("配置文件路径未设置，跳过加载")
                return False
            with open(self.config_file, "r", encoding="utf-8") as f:
                raw_config = json.load(f)

            # D-2修复: 过滤 _comment 注释键，兼容 config.example.json 直接使用
            user_config = self._strip_comments(raw_config)

            # DF-3修复: 配置文件格式校验（使用统一的validate方法）
            validation_errors = self.validate(user_config)
            if validation_errors:
                error_msgs = [f"{k}: {v}" for k, v in validation_errors.items()]
                logger.error("配置文件格式错误:\n" + "\n".join(error_msgs))
                return False

            # 线程安全：在锁内合并配置
            with self._lock:
                self._merge_config(self.config, user_config)
            return True
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False

    # ── P2-4: 配置热重载 ──────────────────────────────────────────

    def reload_config(self) -> bool:
        """安全重载配置 (P2-4): 验证新配置后才应用，失败则回滚到原配置

        与 load_config() 不同，reload_config() 会:
        1. 先验证新配置文件是否合法
        2. 验证失败时保持当前配置不变
        3. 成功重载后通知所有 on_config_changed 回调
        4. 应用过程中异常则回滚到原配置

        返回:
            重载成功返回 True，失败返回 False
        """
        if not self.config_file:
            return False

        old_config_backup = None
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                raw_config = json.load(f)

            new_config = self._strip_comments(raw_config)

            # 验证新配置
            validation_errors = self.validate(new_config)
            if validation_errors:
                error_msgs = [f"{k}: {v}" for k, v in validation_errors.items()]
                logger.error(
                    "配置热重载失败 — 新配置验证未通过 (保留原配置):\n%s",
                    "\n".join(error_msgs),
                )
                return False

            # 优化: 先获取配置引用，在锁外执行深拷贝，减少锁持有时间
            # 一般问题修复: copy 已在文件顶部导入
            old_config_backup = copy.deepcopy(self.config)

            # W5修复: 合并为单次锁获取
            with self._lock:
                self._merge_config(self.config, new_config)

            logger.info("配置热重载成功: %s", self.config_file)

            # P2-4: 通知所有变更回调
            self._notify_change_callbacks()

            return True
        except Exception as e:
            # W4修复: 利用备份回滚配置，确保"保留原配置"的承诺真实可信
            if old_config_backup is not None:
                with self._lock:
                    self.config = old_config_backup
            logger.error("配置热重载失败: %s (已回滚到原配置)", e)
            return False

    def on_config_changed(self, callback: Callable[[], None]) -> None:
        """注册配置变更回调 (P2-4)

        当配置文件通过 reload_config() 成功重载后，所有注册的回调都会被调用。
        回调在触发 reload 的线程中同步执行（后台线程）。

        参数:
            callback: 无参数的可调用对象
        """
        self._change_callbacks.append(callback)

    def _notify_change_callbacks(self) -> None:
        """通知所有配置变更回调 (P2-4)

        每个回调都有独立的异常保护，单个回调失败不影响其他回调。
        """
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                # C1修复: 使用 getattr 安全获取名称，避免 callable class 无 __name__ 导致 AttributeError
                cb_name = getattr(callback, "__name__", str(callback))
                logger.error("配置变更回调 %s 执行失败: %s", cb_name, e)

    def start_watching(self, debounce_seconds: float = 2.0, poll_interval: float = 2.0) -> bool:
        """启动配置文件热重载监听 (P2-4)

        自动选择最佳后端:
        - watchdog (事件驱动, 响应快)
        - polling  (定期检查 mtime, 无需外部依赖)

        参数:
            debounce_seconds: 防抖间隔 (秒)，避免连续写入触发多次重载
            poll_interval: 轮询模式下的检查间隔 (秒)，仅 polling 后端使用

        返回:
            启动成功返回 True
        """
        if not self.config_file:
            logger.warning("无法启动配置监听: 未设置配置文件路径")
            return False

        from .config_watcher import ConfigWatcher  # noqa: F811

        # C2修复: 加锁保护 _watcher 的读写，防止并发 start/stop 竞态
        with self._lock:
            if self._watcher is not None:
                self._watcher.stop()

            self._watcher = ConfigWatcher(
                config_path=self.config_file,
                on_reload=lambda: (self.reload_config(), None)[1],
                debounce_seconds=debounce_seconds,
                poll_interval=poll_interval,
            )
            return self._watcher.start()

    def stop_watching(self) -> None:
        """停止配置文件热重载监听 (P2-4)"""
        # C2修复: 加锁保护 _watcher 的读写
        with self._lock:
            if self._watcher is not None:
                self._watcher.stop()
                self._watcher = None

    def __del__(self) -> None:
        """析构时自动停止配置监听 (P2-4)

        注意：建议使用上下文管理器或显式调用cleanup()方法，
        以确保资源能够被正确释放。
        """
        try:
            self.stop_watching()
        except Exception as e:
            # 记录警告日志，但不抛出异常
            import sys
            print(f"WARNING: ConfigManager清理失败: {type(e).__name__}: {e}", file=sys.stderr)

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

            # 使用原子写入确保数据完整性
            # 避免写入中断导致配置文件损坏
            from ..utils.file_utils import atomic_json_write
            success = atomic_json_write(
                self.config_file,
                config_copy,
                ensure_ascii=False,
                indent=2,
                fsync=True
            )
            if success:
                logger.debug(f"配置文件已保存: {self.config_file}")
            return success
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
        keys = key.split(".")
        # DF-1修复：整个遍历过程在锁内完成，确保真正的线程安全
        with self._lock:
            value: Any = self.config
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
        keys = key.split(".")
        # 线程安全：在锁内修改配置
        with self._lock:
            config: Dict[str, Any] = self.config

            for i, k in enumerate(keys[:-1]):
                if k not in config or not isinstance(config[k], dict):
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value
        return True

    def _merge_config(self, base: Dict, update: Dict) -> None:
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
        # 一般问题修复: copy 已在文件顶部导入
        return copy.deepcopy(config)

    def validate(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
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
            path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            # 避免覆盖同一字段的多个错误
            if path not in errors:
                errors[path] = error.message
            else:
                errors[path] += f"; {error.message}"

        return errors

    @classmethod
    def _get_validator(cls) -> Optional["Draft7Validator"]:
        """获取缓存的Schema验证器实例（懒加载，双重检查锁定）"""
        if cls._cached_validator is None:
            with cls._validator_lock:
                # 双重检查：持有锁后再次检查
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

    def _validate_mode(self, value: str, errors: Dict[str, str]) -> Optional[str]:
        """验证模式配置"""
        valid_modes = {
            "random", "sequential", "range", "brute_force",
            "dictionary", "seed", "prng", "aes_ctr", "chacha20"
        }
        if value not in valid_modes:
            errors["mode"] = f"无效模式: {value}，有效值: {valid_modes}"
            return None
        return value

    def _validate_batch_size(self, value: int, errors: Dict[str, str]) -> Optional[int]:
        """验证批次大小"""
        GPU_MAX_BATCH_SIZE = 0xFFFFFFFF
        if value < 1:
            errors["batch_size"] = f"batch_size 必须 >= 1, 当前值: {value}"
            return None
        if value >= GPU_MAX_BATCH_SIZE:
            errors["batch_size"] = f"batch_size {value} >= GPU_MAX_BATCH_SIZE({GPU_MAX_BATCH_SIZE})"
            return None
        return value

    def _validate_positive_int(self, name: str, value: int, errors: Dict[str, str], 
                               min_val: int = 1) -> Optional[int]:
        """验证正整数配置"""
        if not isinstance(value, int) or value < min_val:
            errors[name] = f"{name} 必须 >= {min_val}, 当前值: {value} (类型: {type(value).__name__})"
            return None
        return value

    def _validate_positive_float(self, name: str, value: float, errors: Dict[str, str],
                                min_val: float = 0.0) -> Optional[float]:
        """验证正浮点数配置"""
        if not isinstance(value, (int, float)) or value < min_val:
            errors[name] = f"{name} 必须 >= {min_val}, 当前值: {value} (类型: {type(value).__name__})"
            return None
        return float(value)

    def _validate_bool(self, name: str, value: Any, errors: Dict[str, str]) -> bool:
        """验证布尔值配置"""
        if not isinstance(value, bool):
            # 尝试自动转换
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes", "on"):
                    return True
                elif value.lower() in ("false", "0", "no", "off"):
                    return False
            errors[name] = f"需要布尔值，当前: {value} (类型: {type(value).__name__})"
            return False
        return value

    def _validate_checkpoint_interval(self, value: int, errors: Dict[str, str]) -> Optional[int]:
        """验证检查点间隔"""
        if value != -1 and (not isinstance(value, int) or value < 1):
            errors["checkpoint_interval"] = f"checkpoint_interval 必须为 -1 或 >= 1, 当前值: {value}"
            return None
        return value

    def _validate_log_level(self, value: str, errors: Dict[str, str]) -> Optional[str]:
        """验证日志级别"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value.upper() not in valid_levels:
            errors["log_level"] = f"无效日志级别: {value}，有效值: {valid_levels}"
            return None
        return value.upper()

    def _validate_targets(self, targets: Any, errors: Dict[str, str]) -> Optional[List[str]]:
        """验证目标地址列表"""
        if targets is None:
            return None
        if not isinstance(targets, list):
            errors["targets"] = f"targets 必须是列表, 当前: {type(targets).__name__}"
            return None
        if len(targets) == 0:
            errors["targets"] = "targets 列表不能为空"
            return None
        return targets

    def _validate_gpu_config(self, config: Any, errors: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """验证GPU配置"""
        if config is None:
            return None
        if not isinstance(config, dict):
            errors["gpu"] = f"gpu 必须是字典, 当前: {type(config).__name__}"
            return None
        # 验证 device_id
        if "device_id" in config:
            device_id = config["device_id"]
            if not isinstance(device_id, int) or device_id < 0:
                errors["gpu.device_id"] = f"gpu.device_id 必须是 >= 0 的整数, 当前: {device_id}"
                return None
        return config

    def _validate_performance_config(self, config: Any, errors: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """验证性能配置"""
        if config is None:
            return None
        if not isinstance(config, dict):
            errors["performance"] = f"performance 必须是字典, 当前: {type(config).__name__}"
            return None
        return config

    def _validate_monitoring_config(self, config: Any, errors: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """验证监控配置"""
        if config is None:
            return None
        if not isinstance(config, dict):
            errors["monitoring"] = f"monitoring 必须是字典, 当前: {type(config).__name__}"
            return None
        return config

    def _validate_security_config(self, config: Any, errors: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """验证安全配置"""
        if config is None:
            return None
        if not isinstance(config, dict):
            errors["security"] = f"security 必须是字典, 当前: {type(config).__name__}"
            return None
        return config

    def _validate_strategy_params(self, params: Any, errors: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """验证策略参数"""
        if params is None:
            return None
        if not isinstance(params, dict):
            errors["strategy_params"] = f"strategy_params 必须是字典, 当前: {type(params).__name__}"
            return None
        return params

    # ========================================================================
    # 简化后的 _validate_manual 函数
    # ========================================================================

    def _validate_manual(self, config: Dict[str, Any]) -> Dict[str, str]:
        """
        手动验证配置字段（JSON Schema 无法表达的复杂规则）

        参数:
            config: 配置字典

        返回:
            错误字典 {字段名: 错误信息}，空字典表示验证通过
        """
        errors: Dict[str, str] = {}

        # 1. 基础类型验证
        self._validate_mode(config.get("mode", "random"), errors)
        self._validate_batch_size(config.get("batch_size", 1024), errors)

        # 2. 数值范围验证
        self._validate_positive_int("num_keys", config.get("num_keys", 1000), errors)
        self._validate_positive_int("num_workers", config.get("num_workers", 4), errors)
        self._validate_positive_float("target_speed", config.get("target_speed", 0), errors)
        self._validate_checkpoint_interval(config.get("checkpoint_interval", 600), errors)

        # 3. 布尔值验证
        for field in ["enable_checkpoint", "enable_stats", "enable_monitoring",
                      "enable_progress_bar", "use_colors"]:
            if field in config:
                self._validate_bool(field, config[field], errors)

        # 4. 日志级别验证
        if "log_level" in config:
            self._validate_log_level(config["log_level"], errors)

        # 5. 嵌套对象验证
        for field, validator in [
            ("targets", self._validate_targets),
            ("gpu", self._validate_gpu_config),
            ("performance", self._validate_performance_config),
            ("monitoring", self._validate_monitoring_config),
            ("security", self._validate_security_config),
            ("strategy_params", self._validate_strategy_params),
        ]:
            if field in config and config[field] is not None:
                validator(config[field], errors)

        return errors

