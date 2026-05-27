"""碰撞核心逻辑.

管理碰撞统计、断点续传、去重过滤、搜索模式协调，
是碰撞引擎的核心业务逻辑层。

职责:
- 碰撞统计管理
- 断点续传
- 去重过滤
- 搜索模式执行协调

版本: v4.2.2 Phase 6.1
创建日期: 2026-04-29
更新日期: 2026-05-23

线程安全说明:
- Phase 6.1: 添加状态锁保护运行状态标志(_running, _paused等)
- stats/checkpoint/dedup_filter等组件在初始化后只读，不需要锁
- start/stop/pause等状态修改操作使用线程锁保护
"""

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from src.utils import get_configured_logger

# 统一回调类型别名
from ..types import MatchCallback, ProgressCallback
from .protocols import ICollisionCore

if TYPE_CHECKING:
    from .engine import GPUCollisionEngine

logger = get_configured_logger(__name__)


class CollisionCore(ICollisionCore):
    """碰撞核心逻辑.

    职责:
    - 管理碰撞统计数据
    - 断点续传保存/恢复
    - 去重过滤（Bloom过滤器）
    - 搜索模式协调执行

    实现接口: ICollisionCore

    当前状态 (Phase 6):
    - GPUCollisionEngine 通过属性访问核心功能: .stats, .checkpoint, .dedup_filter
    - 所有弃用方法已于 v4.5.0 移除，请使用 GPUCollisionEngine API
    """

    def __init__(
        self,
        targets: set[str],
        config: dict[str, Any] | None = None,
        on_progress: ProgressCallback | None = None,
        on_match: MatchCallback | None = None,
        # 依赖注入（可选）
        engine: Optional["GPUCollisionEngine"] = None,
        stats_factory: Callable | None = None,
        checkpoint_factory: Callable | None = None,
        dedup_factory: Callable | None = None,
    ) -> None:
        """初始化碰撞核心.

        Args:
            targets: 目标地址集合
            config: 配置字典
            on_progress: 进度回调函数
            on_match: 匹配回调函数
            engine: GPUCollisionEngine实例 (Phase 4: 用于SearchModeCoordinator注入)
            stats_factory: 统计对象工厂函数 (可选)
            checkpoint_factory: 断点管理器工厂函数 (可选)
            dedup_factory: 去重过滤器工厂函数 (可选)

        """
        self.targets = targets
        self.config = config or {}
        self.on_progress = on_progress
        self.on_match = on_match
        self._engine = engine  # Phase 4: 引擎引用用于SearchModeCoordinator

        # 依赖注入工厂
        self._stats_factory = stats_factory
        self._checkpoint_factory = checkpoint_factory
        self._dedup_factory = dedup_factory

        # 核心组件（初始化为 None，start() 时初始化）
        self.stats = None
        self.checkpoint = None
        self.dedup_filter = None
        self.search_coordinator = None

        # 状态
        self._running = False
        self._paused = False
        self._start_time = 0.0
        self._last_checkpoint_time = 0.0
        self._last_progress_time = 0.0  # Phase 4: 进度节流时间戳
        # Phase 6.1: 状态锁保护运行状态标志
        self._state_lock = threading.RLock()

        # 配置参数
        self.checkpoint_interval = self.config.get("checkpoint_interval", 30)
        self.dedup_enabled = self.config.get("dedup_enabled", False)
        self.checkpoint_enabled = self.config.get("checkpoint_enabled", False)
        self.progress_interval = self.config.get(
            "progress_interval",
            1.0,
        )  # Phase 4: 进度回调间隔(秒)

        logger.debug("CollisionCore 初始化完成")

    def get_stats(self) -> dict[str, Any]:
        """获取碰撞统计.

        Returns:
            统计信息字典

        """
        if not self.stats:
            return {}

        stats_dict = self.stats.to_dict() if hasattr(self.stats, "to_dict") else {}

        # 添加额外信息
        elapsed_time = 0
        if hasattr(self, "_start_time") and self._start_time:
            elapsed_time = time.time() - self._start_time

        stats_dict.update(
            {
                "running": self._running,
                "elapsed_time": elapsed_time,
            },
        )

        return stats_dict

    def is_running(self) -> bool:
        """检查是否正在运行（线程安全）."""
        with self._state_lock:
            return self._running

    # ========== 私有方法 ==========

    def _init_stats(self):
        """初始化碰撞统计.

        初始化 CollisionStats 实例，用于跟踪引擎运行时的统计数据。
        优先使用依赖注入的工厂；工厂失败时回退到默认实现。
        """
        # 优先使用依赖注入的工厂
        if self._stats_factory:
            try:
                self.stats = self._stats_factory()
                logger.debug("使用注入的统计工厂初始化")
                return
            except Exception as e:
                logger.warning("注入的统计工厂初始化失败: %s，使用默认", e)

        # 默认实现
        try:
            from ..collision_stats import CollisionStats

            self.stats = CollisionStats()
        except Exception as e:
            logger.error("初始化碰撞统计失败: %s", e)
            raise

    def _init_checkpoint(self):
        """初始化断点管理器."""
        # 优先使用依赖注入的工厂
        if self._checkpoint_factory:
            try:
                self.checkpoint = self._checkpoint_factory()
                logger.debug("使用注入的断点工厂初始化")
                return
            except Exception as e:
                logger.warning("注入的断点工厂初始化失败: %s，使用默认", e)

        # 默认实现
        try:
            from ..checkpoint_manager import CheckpointManager

            self.checkpoint = CheckpointManager(auto_save_interval=self.checkpoint_interval)
        except Exception as e:
            logger.error("初始化断点管理器失败: %s", e)
            raise

    def _init_dedup_filter(self):
        """初始化去重过滤器."""
        # 优先使用依赖注入的工厂
        if self._dedup_factory:
            try:
                self.dedup_filter = self._dedup_factory()
                logger.debug("使用注入的去重工厂初始化")
                return
            except Exception as e:
                logger.warning("注入的去重工厂初始化失败: %s，使用默认", e)

        # 默认实现
        try:
            dedup_max_size = self.config.get("dedup_max_size", 1_000_000)
            from ..deduplication_filter import DeduplicationFilter

            self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size)
        except Exception as e:
            logger.error("初始化去重过滤器失败: %s", e)
            raise

    def _restore_checkpoint(self):
        """恢复断点.

        Phase 4实现:
        - 从断点数据恢复 total_checked 和 mode 到统计对象
        - 恢复 matches 列表到统计对象（仅包含安全字段）
        - 设置 current_position 到统计对象
        """
        if not self.checkpoint:
            return

        try:
            checkpoint_data = self.checkpoint.load()
            if checkpoint_data:
                mode = checkpoint_data.get("mode", "unknown")
                total_checked = checkpoint_data.get("total_checked", 0)
                current_position = checkpoint_data.get("current_position", 0)
                saved_matches = checkpoint_data.get("matches", [])

                logger.info(
                    f"断点恢复: mode={mode}, "
                    f"total_checked={total_checked}, "
                    f"position={current_position}, "
                    f"matches={len(saved_matches)}",
                )

                # 恢复统计对象
                if self.stats:
                    if hasattr(self.stats, "total_checked"):
                        self.stats.total_checked = total_checked
                    if hasattr(self.stats, "current_position"):
                        self.stats.current_position = current_position
                    if hasattr(self.stats, "mode"):
                        self.stats.mode = mode
                    # 恢复匹配记录（仅包含安全字段）
                    # Q8修复: 明确处理锁获取，避免使用 fallback 锁导致的逻辑混乱
                    if hasattr(self.stats, "matches") and saved_matches:
                        if hasattr(self.stats, "_lock") and self.stats._lock is not None:
                            with self.stats._lock:
                                self.stats.matches = saved_matches
                        else:
                            # 无锁时直接赋值（单线程场景）
                            self.stats.matches = saved_matches

                # 恢复配置中的mode
                self.config["mode"] = mode

            else:
                logger.info("未找到断点数据，从头开始")
        except Exception as e:
            logger.error("恢复断点失败: %s", e)

    def _save_checkpoint(self):
        """保存断点."""
        if not self.checkpoint or not self.stats:
            return

        try:
            mode = self.config.get("mode", "random")
            self.checkpoint.save(
                {
                    "mode": mode,
                    "targets": list(self.targets),
                    "current_position": getattr(self.stats, "total_checked", 0),
                    "total_checked": getattr(self.stats, "total_checked", 0),
                    "matches": [],  # 匹配数据通过回调单独处理
                },
            )
            logger.debug("断点已保存")
        except Exception as e:
            logger.error("保存断点失败: %s", e)
