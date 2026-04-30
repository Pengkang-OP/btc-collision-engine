"""碰撞核心逻辑

管理碰撞统计、断点续传、去重过滤、搜索模式协调，
是碰撞引擎的核心业务逻辑层。

职责:
- 碰撞统计管理
- 断点续传
- 去重过滤
- 搜索模式执行协调

版本: v2.0 (Phase 4)
创建日期: 2026-04-29
更新日期: 2026-04-30
"""

from typing import Set, Optional, Dict, Any, List, Callable, TYPE_CHECKING, cast
import logging
import time

# P3-3: 统一回调类型别名
from ..types import ProgressCallback, MatchCallback

from .protocols import ICollisionCore, CollisionResult, MatchResult

if TYPE_CHECKING:
    from ..gpu_collision_engine import GPUCollisionEngine

logger = logging.getLogger(__name__)


class CollisionCore(ICollisionCore):
    """碰撞核心逻辑

    职责:
    - 管理碰撞统计数据
    - 断点续传保存/恢复
    - 去重过滤（Bloom过滤器）
    - 搜索模式协调执行

    实现接口: ICollisionCore

    使用示例:
        >>> core = CollisionCore(targets, config)
        >>> core.start(mode='random')
        >>> core.on_batch_complete(matches, batch_size)
        >>> stats = core.get_stats()
        >>> core.stop()
    """

    def __init__(
        self,
        targets: Set[str],
        config: Optional[Dict[str, Any]] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_match: Optional[MatchCallback] = None,
        # 依赖注入（可选）
        engine: Optional["GPUCollisionEngine"] = None,
        stats_factory: Optional[Callable] = None,
        checkpoint_factory: Optional[Callable] = None,
        dedup_factory: Optional[Callable] = None,
    ) -> None:
        """初始化碰撞核心

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

        # 核心组件（延迟初始化）
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

        # 配置参数
        self.checkpoint_interval = self.config.get("checkpoint_interval", 30)
        self.dedup_enabled = self.config.get("dedup_enabled", False)
        self.checkpoint_enabled = self.config.get("checkpoint_enabled", False)
        self.progress_interval = self.config.get("progress_interval", 1.0)  # Phase 4: 进度回调间隔(秒)

        logger.debug("CollisionCore 初始化完成")

    def start(self, mode: str = "random", **kwargs) -> None:
        """启动碰撞

        Args:
            mode: 碰撞模式 (random/range/brute_force)
            **kwargs: 其他参数 (start_key, end_key, resume等)
        """
        if self._running:
            logger.warning("碰撞核心已在运行，跳过重复启动")
            return

        # 1. 初始化统计
        self._init_stats()

        # 2. 初始化断点管理器
        if self.checkpoint_enabled:
            self._init_checkpoint()

        # 3. 初始化去重过滤器
        if self.dedup_enabled:
            self._init_dedup_filter()

        # 4. 初始化搜索协调器
        self._init_search_coordinator()

        # 5. 检查是否恢复断点
        resume = kwargs.pop("resume", False)
        if resume and self.checkpoint_enabled:
            self._restore_checkpoint()

        # 6. 启动搜索
        self._running = True
        self._start_time = time.time()
        self._last_checkpoint_time = time.time()
        self._last_progress_time = time.time()  # Phase 4: 重置进度节流时间

        logger.info(f"碰撞核心已启动: mode={mode}")

        # 委托给搜索协调器执行
        if self.search_coordinator:
            assert self.search_coordinator is not None  # 上方 if 已保证
            self.search_coordinator.start(mode, resume=resume, **kwargs)

    def stop(self) -> None:
        """停止碰撞"""
        if not self._running:
            return

        self._running = False
        self._paused = False

        # 1. 停止搜索协调器
        if self.search_coordinator:
            self.search_coordinator.stop()

        # 2. 保存最终断点
        if self.checkpoint_enabled:
            self._save_checkpoint()

        # 3. 刷写去重过滤器
        if self.dedup_filter and hasattr(self.dedup_filter, "flush"):
            self.dedup_filter.flush()

        logger.info("碰撞核心已停止")

    def pause(self) -> None:
        """暂停碰撞"""
        if not self._running or self._paused:
            return

        self._paused = True
        logger.info("碰撞核心已暂停")

        if self.search_coordinator and hasattr(self.search_coordinator, "pause"):
            self.search_coordinator.pause()

    def resume(self) -> None:
        """恢复碰撞"""
        if not self._running or not self._paused:
            return

        self._paused = False
        logger.info("碰撞核心已恢复")

        if self.search_coordinator and hasattr(self.search_coordinator, "resume"):
            self.search_coordinator.resume()

    def reset(self) -> None:
        """重置统计"""
        if self.stats and hasattr(self.stats, "reset"):
            self.stats.reset()
            logger.info("碰撞统计已重置")

    def on_batch_complete(self, matches: List[MatchResult], batch_size: int) -> None:
        """批次完成回调

        Args:
            matches: 匹配结果列表
            batch_size: 批次大小
        """
        if not self._running or self._paused or not self.stats:
            return

        # 1. 更新统计 (CollisionStats.update 接收 checked_count 和 optional total_range)
        self.stats.update(batch_size)

        # 2. 去重过滤 (DeduplicationFilter 使用 check_and_add 逐键检查)
        if self.dedup_filter and matches:
            unique_matches = []
            for match in matches:
                pk_bytes = match.get("private_key")
                if pk_bytes:
                    # 将hex字符串转为bytes（如果必要）
                    if isinstance(pk_bytes, str):
                        try:
                            pk_bytes = bytes.fromhex(pk_bytes)
                        except (ValueError, TypeError):
                            continue
                    if self.dedup_filter.check_and_add(pk_bytes):
                        unique_matches.append(match)
                else:
                    unique_matches.append(match)
            matches = unique_matches

        # 3. 处理匹配
        if matches and self.on_match:
            for match in matches:
                try:
                    address = match.get("address", "")
                    private_key = match.get("private_key", "")
                    if isinstance(private_key, str):
                        try:
                            private_key_bytes = bytes.fromhex(private_key)
                        except (ValueError, TypeError):
                            private_key_bytes = b""
                    else:
                        private_key_bytes = private_key if isinstance(private_key, bytes) else b""
                    wif = match.get("wif", "")
                    self.on_match(private_key_bytes, address, wif)
                except Exception as e:
                    logger.error(f"处理匹配回调失败: {e}")

        # 4. 进度回调（节流）
        if self.on_progress:
            self._maybe_call_progress()

        # 5. 检查是否需要保存断点
        if self.checkpoint_enabled:
            self._maybe_save_checkpoint()

    def get_stats(self) -> Dict[str, Any]:
        """获取碰撞统计

        Returns:
            统计信息字典
        """
        if not self.stats:
            return {}

        stats_dict = self.stats.to_dict() if hasattr(self.stats, "to_dict") else {}

        # 添加额外信息
        stats_dict.update(
            {
                "running": self._running,
                "elapsed_time": time.time() - self._start_time if self._start_time else 0,
            }
        )

        return stats_dict

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    # ========== 私有方法 ==========

    def _init_stats(self):
        """初始化碰撞统计"""
        # 优先使用依赖注入的工厂
        if self._stats_factory:
            try:
                self.stats = self._stats_factory()
                logger.debug("使用注入的统计工厂初始化")
                return
            except Exception as e:
                logger.warning(f"注入的统计工厂初始化失败: {e}，使用默认")

        # 默认实现
        try:
            from ..collision_stats import CollisionStats

            self.stats = CollisionStats()
        except Exception as e:
            logger.error(f"初始化碰撞统计失败: {e}")
            raise

    def _init_checkpoint(self):
        """初始化断点管理器"""
        # 优先使用依赖注入的工厂
        if self._checkpoint_factory:
            try:
                self.checkpoint = self._checkpoint_factory()
                logger.debug("使用注入的断点工厂初始化")
                return
            except Exception as e:
                logger.warning(f"注入的断点工厂初始化失败: {e}，使用默认")

        # 默认实现
        try:
            from ..checkpoint_manager import CheckpointManager

            self.checkpoint = CheckpointManager(auto_save_interval=self.checkpoint_interval)
        except Exception as e:
            logger.error(f"初始化断点管理器失败: {e}")
            raise

    def _init_dedup_filter(self):
        """初始化去重过滤器"""
        # 优先使用依赖注入的工厂
        if self._dedup_factory:
            try:
                self.dedup_filter = self._dedup_factory()
                logger.debug("使用注入的去重工厂初始化")
                return
            except Exception as e:
                logger.warning(f"注入的去重工厂初始化失败: {e}，使用默认")

        # 默认实现
        try:
            dedup_max_size = self.config.get("dedup_max_size", 1_000_000)
            from ..deduplication_filter import DeduplicationFilter

            self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size)
        except Exception as e:
            logger.error(f"初始化去重过滤器失败: {e}")
            raise

    def _init_search_coordinator(self):
        """初始化搜索协调器

        Phase 4实现:
        - 从现有 SearchModeCoordinator 适配 (src/gpu/ → ....gpu/)
        - 需要通过 engine 引用注入 (SearchModeCoordinator 需要 GPUCollisionEngine)
        - 无 engine 时创建无操作存根，仅记录日志
        """
        try:
            if self._engine is not None:
                from ...gpu.search_mode_coordinator import SearchModeCoordinator
                self.search_coordinator = SearchModeCoordinator(self._engine)
                logger.debug("搜索协调器已初始化 (通过engine注入)")
            else:
                # 无engine时创建简单的存根，支持start/stop/pause/resume空操作
                logger.info("无引擎引用，搜索协调器使用存根模式")
                self.search_coordinator = self._create_search_stub()
        except Exception as e:
            logger.error(f"初始化搜索协调器失败: {e}")
            self.search_coordinator = self._create_search_stub()

    def _create_search_stub(self):
        """创建搜索协调器存根 (无engine时的降级方案)

        存根实现了 start/stop/pause/resume/get_current_mode 等基本接口，
        所有操作均为无操作，确保 CollisionCore 可以正常运行统计/断点/去重功能。
        """
        class _SearchCoordinatorStub:
            def __init__(self):
                self._current_mode = None

            def start(self, mode, resume=False, **kwargs):
                self._current_mode = mode
                logger.info(f"存根搜索协调器: 模式={mode}, resume={resume}")

            def stop(self):
                logger.debug("存根搜索协调器: 停止")
                self._current_mode = None

            def pause(self):
                logger.debug("存根搜索协调器: 暂停")

            def resume(self):
                logger.debug("存根搜索协调器: 恢复")

            def get_current_mode(self):
                return self._current_mode

            def switch_mode(self, new_mode, **kwargs):
                self._current_mode = new_mode
                logger.info(f"存根搜索协调器: 切换到 {new_mode}")

        return _SearchCoordinatorStub()

    def _restore_checkpoint(self):
        """恢复断点

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
                    f"matches={len(saved_matches)}"
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
                    if hasattr(self.stats, "matches") and saved_matches:
                        with getattr(self.stats, "_lock", None) or __import__("threading").Lock():
                            self.stats.matches = saved_matches

                # 恢复配置中的mode
                self.config["mode"] = mode

            else:
                logger.info("未找到断点数据，从头开始")
        except Exception as e:
            logger.error(f"恢复断点失败: {e}")

    def _save_checkpoint(self):
        """保存断点"""
        if not self.checkpoint or not self.stats:
            return

        try:
            mode = self.config.get("mode", "random")
            self.checkpoint.save(
                mode=mode,
                targets=self.targets,
                current_position=getattr(self.stats, "total_checked", 0),
                total_checked=getattr(self.stats, "total_checked", 0),
                matches=[],  # 匹配数据通过回调单独处理
            )
            logger.debug("断点已保存")
        except Exception as e:
            logger.error(f"保存断点失败: {e}")

    def _maybe_save_checkpoint(self):
        """检查是否需要保存断点"""
        current_time = time.time()
        if current_time - self._last_checkpoint_time >= self.checkpoint_interval:
            self._save_checkpoint()
            self._last_checkpoint_time = current_time

    def _maybe_call_progress(self):
        """节流调用进度回调

        Phase 4实现:
        - 基于 progress_interval 配置进行时间节流
        - 仅在间隔时间到达时调用 on_progress 回调
        - 通过 CollisionStats.snapshot() 获取线程安全的统计快照
        """
        if not self.on_progress or not self.stats:
            return

        current_time = time.time()
        if current_time - self._last_progress_time >= self.progress_interval:
            self._last_progress_time = current_time
            try:
                # 使用 snapshot 获取线程安全的统计快照
                if hasattr(self.stats, "snapshot"):
                    stats_snapshot = self.stats.snapshot()
                else:
                    stats_snapshot = self.stats
                self.on_progress(stats_snapshot)
            except Exception as e:
                logger.error(f"进度回调执行失败: {e}")
