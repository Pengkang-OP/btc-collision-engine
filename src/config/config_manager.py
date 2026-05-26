"""Configuration manager."""

import copy
import json
import pathlib
import threading
from collections.abc import Callable
from typing import Any, Optional

# 导入日志配置
from ..i18n import _t
from ..utils import get_configured_logger
from ..utils.logging_config import LOG_DEFAULT_MAX_BYTES
from .config_watcher import ConfigWatcher  # noqa: F401 — type annotation reference

# v4.2.2 M3: 日志初始化统一由 CLI 入口 (main.py) 和 utils/__init__.py 处理

# 获取模块日志记录器
logger = get_configured_logger("ConfigManager")

# DF-3修复: 添加JSON Schema验证 — 从 config.schema.json 文件加载（单一真相源）
try:
    from jsonschema import Draft202012Validator

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logger.debug("jsonschema库未安装，配置文件将跳过Schema验证")


class ConfigManager:
    """配置管理器 - 统一管理应用配置"""

    # 审查修复#5: 将Schema提取为类常量，避免每次验证都重新创建
    # 优化: 将Draft202012Validator实例缓存为类变量，避免重复创建开销
    _cached_validator = None  # 类级缓存的Schema验证器实例
    _validator_lock = threading.Lock()  # 类级锁，保护验证器初始化
    # ROADMAP #5: CONFIG_SCHEMA 已迁移至 config.schema.json（单一真相源）
    # 内联字典已删除，由 _get_validator() 从文件加载
    _CONFIG_SCHEMA_PATH = str(
        pathlib.Path(__file__).resolve().parent.parent.parent / "config.schema.json"
    )

    DEFAULT_CONFIG = {
        "version": "5.0.0",
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
            "max_bytes": LOG_DEFAULT_MAX_BYTES,
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
            "memory_usage_ratio": 0.7,  # v5.0.0 PARAM-2: 与 auto_config.py NVIDIA 基线保持一致
            "enable_vendor_optimizations": True,
            "queue_depth": 8,  # GPU 命令队列预提交批次数 (NVIDIA 建议 4-8，Intel Arc 建议 12-16)
            # v4.3.1: 补充 config.example.json 中的 GPU 高级配置字段
            "use_new_module": True,
            "async_execution": True,
            "seed_prefetch_size": 64,
            "timeout_protection": True,
            "base_timeout_seconds": 30,
            "max_error_retries": 100,
            "gpu_memory_pool": True,
            "max_buffers": 100,
            "max_memory_mb": 8192,  # 与 config.json 保持一致
            "mode": "auto",
            "device_indices": [-1],
            "load_balancing": "performance",
            "auto_tuning": False,
            # 审计修复: 补充 Schema 中声明但 DEFAULT_CONFIG 缺失的字段
            "work_group_size": 256,  # OpenCL work group size
            "use_fast_math": True,  # 启用 fast math 优化
            "use_uint32_workaround": False,  # Intel Arc 必须启用，其他 GPU 保持 False
            "compiler_flags": "",  # 自定义编译选项
            "driver_check": {},  # 驱动检查配置
            "per_device_config": {},  # 每设备独立配置
            # 异步日志配置 (来自 config.example.json)
            "use_async_logging": False,
            "async_log_file": "logs/gpu_async.log",
            "async_log_max_bytes": LOG_DEFAULT_MAX_BYTES,
            "async_log_backup_count": 5,
            # 非压缩地址检查
            "check_uncompressed": None,
            # 私钥生成策略
            "key_generation_strategy": "PRNG_SEED",
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
    }

    def __init__(self, config_file: str | None = None) -> None:
        """初始化配置管理器

        Args:
            config_file: 配置文件路径，None表示使用默认配置
        """
        self.config_file = config_file
        self._lock = threading.Lock()  # 线程锁保护配置读写

        # M-6修复: 延迟深拷贝，只有在加载配置时才拷贝默认配置
        # 避免每次实例化都执行不必要的深拷贝操作
        self._config_initialized = False

        if config_file and pathlib.Path(config_file).exists():
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

        Args:
            config: 配置字典或任意值

        Returns:
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
        """从文件加载配置（线程安全）

        Returns:
            加载成功返回True，失败返回False
        """
        try:
            if not self.config_file:
                logger.warning("配置文件路径未设置，跳过加载")
                return False
            with pathlib.Path(self.config_file).open(encoding="utf-8") as f:
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
            logger.error("加载配置文件失败: %s", e)
            return False

    # ── 配置热重载 ──────────────────────────────────────────

    def reload_config(self) -> bool:
        """安全重载配置 (P2-4): 验证新配置后才应用，失败则回滚到原配置

        与 load_config() 不同，reload_config() 会:
        1. 先验证新配置文件是否合法
        2. 验证失败时保持当前配置不变
        3. 成功重载后通知所有 on_config_changed 回调
        4. 应用过程中异常则回滚到原配置

        Returns:
            重载成功返回 True，失败返回 False
        """
        if not self.config_file:
            return False

        old_config_backup = None
        try:
            with pathlib.Path(self.config_file).open(encoding="utf-8") as f:
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

        Args:
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

        Args:
            debounce_seconds: 防抖间隔 (秒)，避免连续写入触发多次重载
            poll_interval: 轮询模式下的检查间隔 (秒)，仅 polling 后端使用

        Returns:
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

            sys.stderr.write(f"WARNING: ConfigManager清理失败: {type(e).__name__}: {e}\n")

    def save_config(self) -> bool:
        """保存配置到文件（线程安全）

        Returns:
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
            try:
                from ..utils.file_utils import atomic_json_write
            except ImportError:
                logger.warning("atomic_json_write 不可用，使用标准 json.dump 写入")
                with pathlib.Path(self.config_file).open("w", encoding="utf-8") as f:
                    json.dump(config_copy, f, ensure_ascii=False, indent=2)
                return True

            atomic_json_write(
                self.config_file,
                config_copy,
                ensure_ascii=False,
                indent=2,
            )
            success = True
            if success:
                logger.debug(f"配置文件已保存: {self.config_file}")
            return success
        except Exception as e:
            logger.error("保存配置文件失败: %s", e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（线程安全）

        Args:
            key: 配置键，支持点号分隔的路径，如 "collision.max_workers"
            default: 默认值

        Returns:
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
        """设置配置值（线程安全）

        Args:
            key: 配置键，支持点号分隔的路径
            value: 配置值

        Returns:
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

    def _merge_config(self, base: dict[str, Any], update: dict[str, Any]) -> None:
        """递归合并配置（必须在锁内调用）

        Args:
            base: 基础配置
            update: 更新配置
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _deep_copy_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """深拷贝配置字典（避免在写文件时持有锁）

        Args:
            config: 要拷贝的配置字典

        Returns:
            配置字典的深拷贝
        """
        # 一般问题修复: copy 已在文件顶部导入
        return copy.deepcopy(config)

    def validate(self, config: dict[str, Any] | None = None) -> dict[str, str]:
        """DF-3修复: 统一配置验证逻辑

        优先使用JSON Schema验证（如果可用），否则使用手动验证。

        Args:
            config: 要验证的配置字典，None表示验证当前配置

        Returns:
            验证失败的配置项和错误信息字典
        """
        if config is None:
            config = self.config

        # DF-3修复: 统一验证逻辑
        if HAS_JSONSCHEMA:
            # 使用JSON Schema验证
            return self._validate_with_schema(config)
        # 降级为手动验证
        return self._validate_manual(config)

    def _validate_with_schema(self, config: dict[str, Any]) -> dict[str, str]:
        """DF-3修复: 使用JSON Schema验证配置

        Args:
            config: 用户配置字典

        Returns:
            错误信息字典，空字典表示验证通过
        """
        if not HAS_JSONSCHEMA:
            return {}  # 没有jsonschema库，返回空

        # 优化: 使用缓存的验证器实例，避免每次验证都重新创建
        # ROADMAP #5: Schema 从 config.schema.json 文件加载
        # 审查修复#1: 使用 Draft202012Validator 收集所有错误，而非只捕获第一个
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
    def _get_validator(cls) -> Optional["Draft202012Validator"]:
        """获取缓存的Schema验证器实例（懒加载，双重检查锁定）

        从 config.schema.json 文件加载 Schema（ROADMAP #5: 单一真相源）。
        """
        if cls._cached_validator is None:
            with cls._validator_lock:
                # 双重检查：持有锁后再次检查
                if cls._cached_validator is None and HAS_JSONSCHEMA:
                    schema_path = pathlib.Path(cls._CONFIG_SCHEMA_PATH)
                    if not schema_path.exists():
                        logger.error("Schema文件不存在: %s", cls._CONFIG_SCHEMA_PATH)
                        return None
                    try:
                        with schema_path.open(encoding="utf-8") as f:
                            schema = json.load(f)
                        cls._cached_validator = Draft202012Validator(schema)
                        logger.debug(
                            "Draft202012Validator实例已从 %s 初始化并缓存",
                            cls._CONFIG_SCHEMA_PATH,
                        )
                    except Exception as e:
                        logger.error("加载Schema文件失败: %s", e)
                        return None
        return cls._cached_validator

    @staticmethod
    def _is_strict_bool(value: Any) -> bool:
        """审查修复#4: 严格布尔值检查，防止int被误认为bool

        在Python中，bool是int的子类，isinstance(True, int)返回True。
        此方法确保只接受真正的布尔值，不接受整数（但JSON解析的True/False是bool类型）。

        Args:
            value: 要检查的值

        Returns:
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
            errors[key] = _t("config.validation.invalid_mode", value=value, valid_values=valid_modes)
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
            errors[key] = _t("config.validation.batch_size_min", name=key, min_val=1, value=value)
            return None
        if value >= _gpu_max_batch_size:
            errors[key] = _t(
                "config.validation.batch_size_max_gpu",
                value=value,
                max=_gpu_max_batch_size,
            )
            return None
        if value > _schema_max_batch_size:
            errors[key] = _t(
                "config.validation.batch_size_max_schema",
                value=value,
                max=_schema_max_batch_size,
            )
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

        Args:
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
            errors[name] = _t(
                "config.validation.batch_size_min",
                name=name,
                min_val=min_val,
                value=value,
            )
            return None
        if max_val is not None and value > max_val:
            errors[name] = _t(
                "config.validation.int_min_max",
                name=name,
                min_val=min_val,
                max_val=max_val,
                value=value,
            )
            return None
        return value

    def _validate_positive_float(
        self,
        name: str,
        value: float,
        errors: dict[str, str],
        min_val: float = 0.0,
    ) -> float | None:
        """验证正浮点数配置"""
        if not isinstance(value, (int, float)) or value < min_val:
            errors[name] = _t("config.validation.float_min", name=name, min_val=min_val, value=value)
            return None
        return float(value)

    def _validate_bool(self, name: str, value: Any, errors: dict[str, str]) -> bool:
        """验证布尔值配置"""
        if not isinstance(value, bool):
            # 尝试自动转换
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes", "on"):
                    return True
                if value.lower() in ("false", "0", "no", "off"):
                    return False
            errors[name] = _t(
                "config.validation.bool_expected",
                value=value,
                type_name=type(value).__name__,
            )
            return False
        return value

    def _validate_checkpoint_interval(
        self,
        value: int,
        errors: dict[str, str],
        prefix: str = "",
    ) -> int | None:
        """验证检查点间隔

        自 v4.3.1: 添加 prefix 参数支持嵌套路径错误键。
        """
        key = prefix + "checkpoint_interval"
        if value != -1 and (not isinstance(value, int) or value < 1):
            errors[key] = _t("config.validation.checkpoint_interval_invalid", value=value)
            return None
        return value

    def _validate_log_level(self, value: str, errors: dict[str, str], prefix: str = "") -> str | None:
        """验证日志级别

        Args:
            value: 日志级别字符串
            errors: 错误字典
            prefix: 错误键前缀（如 "logging."）
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        key = prefix + "level"
        if value.upper() not in valid_levels:
            errors[key] = _t(
                "config.validation.invalid_log_level",
                value=value,
                valid_values=valid_levels,
            )
            return None
        return value.upper()

    # ========================================================================
    # _validate_manual 函数
    # ========================================================================

    def _validate_manual(self, config: dict[str, Any]) -> dict[str, str]:
        """手动验证配置字段（JSON Schema 不可用时的降级方案）

        v4.3.1: 清理 8 个死代码引用，所有校验路径对齐实际 CONFIG_SCHEMA 结构。

        Args:
            config: 配置字典（嵌套结构，与 CONFIG_SCHEMA 一致）

        Returns:
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

        self._validate_collision_section(collision, errors)
        self._validate_logging_section(logging_cfg, errors)
        self._validate_engine_section(engine_cfg, errors)
        self._validate_gpu_section(config.get("gpu"), gpu_cfg, errors)
        self._validate_crypto_section(crypto, errors)
        self._validate_perf_section(perf_cfg, errors)

        # 手动验证是 JSON Schema 验证的降级子集
        if errors:
            logger.warning(
                "手动配置验证发现 %d 个问题（降级模式，部分字段未覆盖）。"
                "建议安装 jsonschema 以获得完整验证能力。",
                len(errors),
            )

        return errors

    def _validate_collision_section(self, collision: dict[str, Any], errors: dict[str, str]) -> None:
        """验证 collision 配置节"""
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
                "collision.progress_interval",
                collision["progress_interval"],
                errors,
            )
        if "checkpoint_interval" in collision:
            self._validate_checkpoint_interval(
                collision["checkpoint_interval"],
                errors,
                prefix="collision.",
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
            key = field_name.split(".", 1)[1]
            if key in source:
                self._validate_bool(field_name, source[key], errors)

    def _validate_logging_section(self, logging_cfg: dict[str, Any], errors: dict[str, str]) -> None:
        """验证 logging 配置节"""
        if "level" in logging_cfg:
            self._validate_log_level(logging_cfg["level"], errors, prefix="logging.")
        for key in ("format", "file", "rotation_when"):
            if key in logging_cfg and not isinstance(logging_cfg[key], str):
                errors[f"logging.{key}"] = _t(
                    "config.validation.type_mismatch",
                    name=f"logging.{key}",
                    expected_type="字符串/string",
                    actual_type=type(logging_cfg[key]).__name__,
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
            rt = logging_cfg["rotation_type"]
            if rt not in ("size", "time"):
                errors["logging.rotation_type"] = _t("config.validation.invalid_rotation_type", value=rt)
            elif rt == "size" and "max_bytes" not in logging_cfg:
                errors["logging.max_bytes"] = _t("config.validation.rotation_needs_max_bytes")
            elif rt == "time" and "rotation_when" not in logging_cfg:
                errors["logging.rotation_when"] = _t("config.validation.rotation_needs_when")

    def _validate_engine_section(self, engine_cfg: dict[str, Any], errors: dict[str, str]) -> None:
        """验证 engine 配置节"""
        if "mode" in engine_cfg:
            self._validate_mode(engine_cfg["mode"], errors, prefix="engine.")
        if "batch_size" in engine_cfg:
            self._validate_batch_size(engine_cfg["batch_size"], errors, prefix="engine.")
        if "max_threads" in engine_cfg:
            self._validate_positive_int("engine.max_threads", engine_cfg["max_threads"], errors)
        if "checkpoint_interval" in engine_cfg:
            self._validate_checkpoint_interval(
                engine_cfg["checkpoint_interval"],
                errors,
                prefix="engine.",
            )

    def _validate_gpu_section(
        self,
        gpu_top: Any,
        gpu_cfg: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        """验证 gpu 配置节"""
        if gpu_top is not None and not isinstance(gpu_top, dict):
            errors["gpu"] = _t(
                "config.validation.field_must_be_dict",
                name="gpu",
                actual_type=type(gpu_top).__name__,
            )
            return
        if "batch_size" in gpu_cfg:
            self._validate_batch_size(gpu_cfg["batch_size"], errors, prefix="gpu.")
        if "memory_usage_ratio" in gpu_cfg:
            ratio = gpu_cfg["memory_usage_ratio"]
            if not isinstance(ratio, (int, float)) or not (0 < ratio <= 1):
                errors["gpu.memory_usage_ratio"] = _t(
                    "config.validation.memory_ratio_range",
                    value=ratio,
                )
        if "mode" in gpu_cfg and gpu_cfg["mode"] not in ("auto", "single", "multi"):
            errors["gpu.mode"] = _t("config.validation.gpu_mode_invalid", value=gpu_cfg["mode"])
        if "load_balancing" in gpu_cfg and gpu_cfg["load_balancing"] not in (
            "performance",
            "equal",
        ):
            errors["gpu.load_balancing"] = _t(
                "config.validation.load_balancing_invalid",
                value=gpu_cfg["load_balancing"],
            )
        for key in ("use_gpu", "auto_detect", "enable_vendor_optimizations"):
            if key in gpu_cfg:
                self._validate_bool(f"gpu.{key}", gpu_cfg[key], errors)
        if "device_index" in gpu_cfg and not isinstance(gpu_cfg["device_index"], int):
            errors["gpu.device_index"] = _t(
                "config.validation.device_index_type",
                actual_type=type(gpu_cfg["device_index"]).__name__,
            )

    def _validate_crypto_section(self, crypto: dict[str, Any], errors: dict[str, str]) -> None:
        """验证 crypto 配置节"""
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
                errors["crypto.backend"] = _t(
                    "config.validation.backend_invalid",
                    value=crypto["backend"],
                    valid_values=valid_backends,
                )
        for key in ("constant_time", "verify_checksums", "strict_wif_validation", "use_gpu"):
            if key in crypto:
                self._validate_bool(f"crypto.{key}", crypto[key], errors)
        if "gpu_device_index" in crypto and not isinstance(crypto["gpu_device_index"], int):
            errors["crypto.gpu_device_index"] = _t(
                "config.validation.device_index_type",
                actual_type=type(crypto["gpu_device_index"]).__name__,
            )

    def _validate_perf_section(self, perf_cfg: dict[str, Any], errors: dict[str, str]) -> None:
        """验证 performance_monitoring 配置节"""
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
                "performance_monitoring.max_records",
                perf_cfg["max_records"],
                errors,
            )
        if "log_level" in perf_cfg:
            self._validate_log_level(perf_cfg["log_level"], errors, prefix="performance_monitoring.log_")
