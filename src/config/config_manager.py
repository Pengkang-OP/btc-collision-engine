"""配置管理器"""

import copy
import json
import os
import threading
from collections.abc import Callable
from typing import Any, Optional

# 导入日志配置
from ..utils import get_configured_logger
from .config_watcher import ConfigWatcher  # noqa: F401 — type annotation reference

# 日志系统由CLI/main.py入口统一初始化
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
                    "checkpoint_interval": {"type": "integer", "minimum": -1},
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                    "checkpoint_interval": {"type": "integer", "minimum": -1},
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
        "patternProperties": {
            "^_comment": {"type": "string"}  # 允许 _comment / _comment_xxx 文档注解字段
        },
    }

    DEFAULT_CONFIG = {
        "engine": {
            "mode": "random",  # 碰撞模式: random, sequential, range, brute_force
            "batch_size": 1048576,  # 批次大小 (1M, Intel Arc A770 最优)
            "max_threads": 8,  # 最大线程数
            "checkpoint_interval": 300,  # 断点保存间隔(秒)
        },
        "collision": {
            "max_workers": None,  # 线程池最大工作线程数，None表示使用默认值
            "progress_interval": 1000,  # 进度回调间隔
            "checkpoint_interval": 30,  # 断点自动保存间隔（秒）
            "dedup_max_size": 1_000_000,  # 去重过滤器最大容量
            # v4.3.1: 补充 config.example.json 中的性能优化字段
            "use_performance_optimization": True,
            "precomputed_window_size": 8,
            "use_simd_hash": True,
            "use_memory_pool": True,
            # v5 修复: 补充 Schema 声明但 DEFAULT_CONFIG 缺失的 GPU 内存池字段
            "use_gpu_memory_pool": True,
            "gpu_pool_max_buffers": 100,
            "gpu_pool_max_memory_mb": 512,
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
            # v4.3.1: 补充 config.example.json 中的 GPU 高级配置字段
            "use_new_module": True,
            "async_execution": True,
            "seed_prefetch_size": 64,
            "timeout_protection": True,
            "base_timeout_seconds": 30,
            "max_error_retries": 100,
            "gpu_memory_pool": True,
            "max_buffers": 100,
            "max_memory_mb": 512,
            "mode": "auto",
            "device_indices": [-1],
            "load_balancing": "performance",
            "auto_tuning": False,
            # 审计修复: 补充 Schema 中声明但 DEFAULT_CONFIG 缺失的字段
            "work_group_size": 256,  # OpenCL work group size
            "use_fast_math": True,  # 启用 fast math 优化
            "use_uint32_workaround": False,  # Intel GPU uint32 兼容处理
            "compiler_flags": "",  # 自定义编译选项
            "driver_check": {},  # 驱动检查配置
            "per_device_config": {},  # 每设备独立配置
        },
        "monitoring": {
            "enabled": True,
            "collection_interval": 5,
            "storage_dir": "data_logs",
            "history_max_size": 1000,
            "error_max_size": 500,
            "anomaly_thresholds": {
                "speed": {"min": 100, "max": 1000000},
                "cpu_usage": {"max": 90},
                "memory_usage": {"max": 1024},
            },
            "auto_cleanup": {
                "enabled": True,
                "max_age_days": 30,
            },
        },
        "optimization": {
            "uint32_workaround": True,
            "disable_async_transfer": False,
            "conservative_memory_policy": False,
            "adaptive_timeout": True,
        },
        "performance_monitoring": {
            "enabled": True,  # 是否启用性能监控
            "track_slow_operations": True,  # 是否追踪慢操作
            "slow_threshold_ms": 30000,  # 慢操作阈值（毫秒），GPU内核编译通常10-30秒
            "max_records": 10000,  # 最大记录数
            "log_level": "INFO",  # 性能日志级别（INFO/DEBUG/WARNING）
        },
        "crypto": {
            "backend": "auto",
            "constant_time": False,
            "verify_checksums": True,
            "strict_wif_validation": True,
            # v4.3.1: 补充 config.example.json 中的 crypto 高级字段
            "use_gpu": True,
            "gpu_device_index": -1,
            "gpu_batch_size": 65536,  # GPU 批次大小 (crypto_config.py 回退默认值)
        },
        "i18n": {
            "language": "auto",
            "fallback_language": "en_US",
        },
        # 审计修复: 补充 Schema 中声明但 DEFAULT_CONFIG 缺失的 gui 配置
        "gui": {
            "theme": "dark",
            "font": "Consolas",
            "font_size": 12,
            "window_width": 1200,
            "window_height": 800,
        },
    }

    def __init__(self, config_file: str | None = None) -> None:
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

        # 配置热重载支持
        self._change_callbacks: list[Callable[[], None]] = []
        self._watcher = None  # type: Optional['ConfigWatcher']

    @property
    def config(self) -> dict[str, Any]:
        """延迟初始化配置属性"""
        if not self._config_initialized:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            self._config_initialized = True
        return self._config

    @config.setter
    def config(self, value: dict[str, Any]) -> None:
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
            with open(self.config_file, encoding="utf-8") as f:
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

    # ── 配置热重载 ──────────────────────────────────────────

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
            with open(self.config_file, encoding="utf-8") as f:
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

            # 通知所有变更回调
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
                self.config_file, config_copy, ensure_ascii=False, indent=2, fsync=True
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
            config: dict[str, Any] = self.config

            for _i, k in enumerate(keys[:-1]):
                if k not in config or not isinstance(config[k], dict):
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value
        return True

    def _merge_config(self, base: dict, update: dict) -> None:
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

    def _deep_copy_config(self, config: dict) -> dict:
        """
        深拷贝配置字典（避免在写文件时持有锁）

        参数:
            config: 要拷贝的配置字典

        返回:
            配置字典的深拷贝
        """
        # 一般问题修复: copy 已在文件顶部导入
        return copy.deepcopy(config)

    def validate(self, config: dict[str, Any] | None = None) -> dict[str, str]:
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

    def _validate_with_schema(self, config: dict[str, Any]) -> dict[str, str]:
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
                if cls._cached_validator is None and HAS_JSONSCHEMA:
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

    def _validate_mode(self, value: str, errors: dict[str, str], prefix: str = "") -> str | None:
        """验证模式配置

        自 v4.3.1: 添加 prefix 参数支持嵌套路径错误键。
        """
        valid_modes = {
            "random",
            "sequential",
            "range",
            "brute_force",
            "dictionary",
            "seed",
            "prng",
            "aes_ctr",
            "chacha20",
        }
        key = prefix + "mode"
        if value not in valid_modes:
            errors[key] = f"无效模式: {value}，有效值: {valid_modes}"
            return None
        return value

    def _validate_batch_size(self, value: int, errors: dict[str, str], prefix: str = "") -> int | None:
        """验证批次大小

        自 v4.3.1: 添加 prefix 参数支持嵌套路径错误键。
        """
        _gpu_max_batch_size = 0xFFFFFFFF  # GPU 硬件地址空间上限 (32-bit)
        _schema_max_batch_size = 16777216  # Schema maximum (16M, 与 CONFIG_SCHEMA 保持一致)
        key = prefix + "batch_size"
        if value < 1:
            errors[key] = f"batch_size 必须 >= 1, 当前值: {value}"
            return None
        if value >= _gpu_max_batch_size:
            errors[key] = f"batch_size {value} >= _gpu_max_batch_size({_gpu_max_batch_size})"
            return None
        if value > _schema_max_batch_size:
            errors[key] = f"batch_size {value} 超过 Schema 上限 {_schema_max_batch_size}"
            return None
        return value

    def _validate_positive_int(
        self,
        name: str,
        value: int,
        errors: dict[str, str],
        min_val: int = 1,
        nullable: bool = False,
        max_val: int | None = None,
    ) -> int | None:
        """验证正整数配置

        参数:
            name: 字段名（用于错误消息）
            value: 要验证的值
            errors: 错误字典
            min_val: 最小值（含）
            nullable: 是否允许 None 值
            max_val: 最大值（含），None 表示不限制
        """
        if nullable and value is None:
            return None
        if not isinstance(value, int) or value < min_val:
            errors[name] = f"{name} 必须 >= {min_val}, 当前值: {value} (类型: {type(value).__name__})"
            return None
        if max_val is not None and value > max_val:
            errors[name] = f"{name} 必须 <= {max_val}, 当前值: {value}"
            return None
        return value

    def _validate_positive_float(
        self, name: str, value: float, errors: dict[str, str], min_val: float = 0.0
    ) -> float | None:
        """验证正浮点数配置"""
        if not isinstance(value, (int, float)) or value < min_val:
            errors[name] = f"{name} 必须 >= {min_val}, 当前值: {value} (类型: {type(value).__name__})"
            return None
        return float(value)

    def _validate_bool(self, name: str, value: Any, errors: dict[str, str]) -> bool:
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

    def _validate_checkpoint_interval(
        self, value: int, errors: dict[str, str], prefix: str = ""
    ) -> int | None:
        """验证检查点间隔

        自 v4.3.1: 添加 prefix 参数支持嵌套路径错误键。
        """
        key = prefix + "checkpoint_interval"
        if value != -1 and (not isinstance(value, int) or value < 1):
            errors[key] = f"checkpoint_interval 必须为 -1 或 >= 1, 当前值: {value}"
            return None
        return value

    def _validate_log_level(self, value: str, errors: dict[str, str], prefix: str = "") -> str | None:
        """验证日志级别

        参数:
            value: 日志级别字符串
            errors: 错误字典
            prefix: 错误键前缀（如 "logging."）
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        key = prefix + "level"
        if value.upper() not in valid_levels:
            errors[key] = f"无效日志级别: {value}，有效值: {valid_levels}"
            return None
        return value.upper()

    # ========================================================================
    # _validate_manual 函数
    # ========================================================================

    def _validate_manual(self, config: dict[str, Any]) -> dict[str, str]:
        """
        手动验证配置字段（JSON Schema 不可用时的降级方案）

        v4.3.1: 清理 8 个死代码引用 (num_keys/num_workers/target_speed/
        enable_checkpoint/enable_stats/enable_monitoring/enable_progress_bar/
        use_colors)，所有校验路径对齐实际 CONFIG_SCHEMA 结构。
        保留所有 Schema 中有约束的字段校验，确保 JSON Schema 降级时
        覆盖度一致。

        参数:
            config: 配置字典（嵌套结构，与 CONFIG_SCHEMA 一致）

        返回:
            错误字典 {字段名: 错误信息}，空字典表示验证通过
        """
        errors: dict[str, str] = {}

        # 安全获取嵌套节（防御非 dict 类型输入）
        collision = config.get("collision", {}) if isinstance(config.get("collision"), dict) else {}
        gpu_cfg = config.get("gpu", {}) if isinstance(config.get("gpu"), dict) else {}
        logging_cfg = config.get("logging", {}) if isinstance(config.get("logging"), dict) else {}
        engine_cfg = config.get("engine", {}) if isinstance(config.get("engine"), dict) else {}
        crypto = config.get("crypto", {}) if isinstance(config.get("crypto"), dict) else {}
        perf_raw = config.get("performance_monitoring", {})
        perf_cfg = perf_raw if isinstance(perf_raw, dict) else {}

        # === collision 节 ===
        if "max_workers" in collision:
            self._validate_positive_int(
                "collision.max_workers",
                collision["max_workers"],
                errors,
                min_val=1,
                nullable=True,
                max_val=1024,
            )
        if "progress_interval" in collision:
            self._validate_positive_int(
                "collision.progress_interval", collision["progress_interval"], errors
            )
        if "checkpoint_interval" in collision:
            self._validate_checkpoint_interval(
                collision["checkpoint_interval"], errors, prefix="collision."
            )
        if "dedup_max_size" in collision:
            self._validate_positive_int("collision.dedup_max_size", collision["dedup_max_size"], errors)
        if "precomputed_window_size" in collision:
            self._validate_positive_int(
                "collision.precomputed_window_size",
                collision["precomputed_window_size"],
                errors,
                min_val=1,
                max_val=16,
            )
        bool_fields = [
            ("collision.use_performance_optimization", collision),
            ("collision.use_simd_hash", collision),
            ("collision.use_memory_pool", collision),
            ("collision.use_gpu_memory_pool", collision),
        ]
        for field_name, source in bool_fields:
            key = field_name.split(".", 1)[1] if "." in field_name else field_name
            if key in source:
                self._validate_bool(field_name, source[key], errors)

        # === logging 节 ===
        if "level" in logging_cfg:
            self._validate_log_level(logging_cfg["level"], errors, prefix="logging.")
        for key in ("format", "file", "rotation_when"):
            if key in logging_cfg and not isinstance(logging_cfg[key], str):
                errors[f"logging.{key}"] = (
                    f"logging.{key} 必须是字符串, 当前: {type(logging_cfg[key]).__name__}"
                )
        for key in ("max_bytes", "backup_count", "rotation_interval"):
            if key in logging_cfg:
                self._validate_positive_int(
                    f"logging.{key}",
                    logging_cfg[key],
                    errors,
                    min_val=1 if key != "backup_count" else 0,
                )
        for key in ("enable_console", "enable_file", "compress_backups"):
            if key in logging_cfg:
                self._validate_bool(f"logging.{key}", logging_cfg[key], errors)
        if "rotation_type" in logging_cfg:
            if logging_cfg["rotation_type"] not in ("size", "time"):
                errors["logging.rotation_type"] = (
                    f"无效 rotation_type: {logging_cfg['rotation_type']}，有效值: size, time"
                )
            elif logging_cfg["rotation_type"] == "size" and "max_bytes" not in logging_cfg:
                errors["logging.max_bytes"] = "rotation_type=size 需要设置 max_bytes"
            elif logging_cfg["rotation_type"] == "time" and "rotation_when" not in logging_cfg:
                errors["logging.rotation_when"] = "rotation_type=time 需要设置 rotation_when"

        # === engine 节 ===
        if "mode" in engine_cfg:
            self._validate_mode(engine_cfg["mode"], errors, prefix="engine.")
        if "batch_size" in engine_cfg:
            self._validate_batch_size(engine_cfg["batch_size"], errors, prefix="engine.")
        if "max_threads" in engine_cfg:
            self._validate_positive_int("engine.max_threads", engine_cfg["max_threads"], errors)
        if "checkpoint_interval" in engine_cfg:
            self._validate_checkpoint_interval(
                engine_cfg["checkpoint_interval"], errors, prefix="engine."
            )

        # === gpu 节 (类型 + 关键字段) ===
        gpu_top = config.get("gpu")
        if gpu_top is not None and not isinstance(gpu_top, dict):
            errors["gpu"] = f"gpu 必须是字典, 当前: {type(gpu_top).__name__}"
        else:
            if "batch_size" in gpu_cfg:
                self._validate_batch_size(gpu_cfg["batch_size"], errors, prefix="gpu.")
            if "memory_usage_ratio" in gpu_cfg:
                ratio = gpu_cfg["memory_usage_ratio"]
                if not isinstance(ratio, (int, float)) or not (0 < ratio <= 1):
                    errors["gpu.memory_usage_ratio"] = (
                        f"memory_usage_ratio 必须在(0, 1]范围内, 当前: {ratio}"
                    )
            if "mode" in gpu_cfg and gpu_cfg["mode"] not in ("auto", "single", "multi"):
                errors["gpu.mode"] = f"无效 gpu.mode: {gpu_cfg['mode']}，有效值: auto, single, multi"
            if "load_balancing" in gpu_cfg and gpu_cfg["load_balancing"] not in (
                "performance",
                "equal",
            ):
                errors["gpu.load_balancing"] = (
                    f"无效 load_balancing: {gpu_cfg['load_balancing']}，有效值: performance, equal"
                )
            for key in ("use_gpu", "auto_detect", "enable_vendor_optimizations"):
                if key in gpu_cfg:
                    self._validate_bool(f"gpu.{key}", gpu_cfg[key], errors)
            if "device_index" in gpu_cfg and not isinstance(gpu_cfg["device_index"], int):
                errors["gpu.device_index"] = (
                    f"gpu.device_index 必须是整数, 当前: {type(gpu_cfg['device_index']).__name__}"
                )

        # === crypto 节 ===
        if "backend" in crypto:
            valid_backends = (
                "auto",
                "pure_python",
                "pure_python_const_time",
                "openssl",
                "coincurve",
                "ecdsa",
            )
            if crypto["backend"] not in valid_backends:
                errors["crypto.backend"] = (
                    f"无效 crypto.backend: {crypto['backend']}，有效值: {valid_backends}"
                )
        for key in ("constant_time", "verify_checksums", "strict_wif_validation", "use_gpu"):
            if key in crypto:
                self._validate_bool(f"crypto.{key}", crypto[key], errors)
        if "gpu_device_index" in crypto and not isinstance(crypto["gpu_device_index"], int):
            errors["crypto.gpu_device_index"] = (
                f"gpu_device_index 必须是整数, 当前: {type(crypto['gpu_device_index']).__name__}"
            )

        # === performance_monitoring 节 ===
        for key in ("enabled", "track_slow_operations"):
            if key in perf_cfg:
                self._validate_bool(f"performance_monitoring.{key}", perf_cfg[key], errors)
        if "slow_threshold_ms" in perf_cfg:
            self._validate_positive_float(
                "performance_monitoring.slow_threshold_ms",
                perf_cfg["slow_threshold_ms"],
                errors,
                min_val=0,
            )
        if "max_records" in perf_cfg:
            self._validate_positive_int(
                "performance_monitoring.max_records", perf_cfg["max_records"], errors
            )
        if "log_level" in perf_cfg:
            self._validate_log_level(perf_cfg["log_level"], errors, prefix="performance_monitoring.log_")

        return errors
