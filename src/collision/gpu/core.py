"""碰撞核心逻辑

管理碰撞统计、断点续传、去重过滤、搜索模式协调，
是碰撞引擎的核心业务逻辑层。

职责:
- 碰撞统计管理
- 断点续传
- 去重过滤
- 搜索模式执行协调

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Set, Optional, Dict, Any, List, Callable
import logging
import time

from .protocols import ICollisionCore, CollisionResult

logger = logging.getLogger(__name__)


class CollisionCore:
    """碰撞核心逻辑
    
    职责:
    - 管理碰撞统计数据
    - 断点续传保存/恢复
    - 去重过滤（Bloom过滤器）
    - 搜索模式协调执行
    
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
        on_progress: Optional[Callable] = None,
        on_match: Optional[Callable] = None
    ):
        """初始化碰撞核心
        
        Args:
            targets: 目标地址集合
            config: 配置字典
            on_progress: 进度回调函数
            on_match: 匹配回调函数
        """
        self.targets = targets
        self.config = config or {}
        self.on_progress = on_progress
        self.on_match = on_match
        
        # 核心组件（延迟初始化）
        self.stats = None
        self.checkpoint = None
        self.dedup_filter = None
        self.search_coordinator = None
        
        # 状态
        self._running = False
        self._start_time = 0.0
        self._last_checkpoint_time = 0.0
        
        # 配置参数
        self.checkpoint_interval = self.config.get('checkpoint_interval', 30)
        self.dedup_enabled = self.config.get('dedup_enabled', False)
        self.checkpoint_enabled = self.config.get('checkpoint_enabled', False)
        
        logger.debug("CollisionCore 初始化完成")
    
    def start(self, mode: str = 'random', **kwargs) -> None:
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
        resume = kwargs.get('resume', False)
        if resume and self.checkpoint_enabled:
            self._restore_checkpoint()
        
        # 6. 启动搜索
        self._running = True
        self._start_time = time.time()
        self._last_checkpoint_time = time.time()
        
        logger.info(f"碰撞核心已启动: mode={mode}")
        
        # 委托给搜索协调器执行
        self.search_coordinator.start(mode, engine=self, **kwargs)
    
    def stop(self) -> None:
        """停止碰撞"""
        if not self._running:
            return
        
        self._running = False
        
        # 1. 停止搜索协调器
        if self.search_coordinator:
            self.search_coordinator.stop()
        
        # 2. 保存最终断点
        if self.checkpoint_enabled:
            self._save_checkpoint()
        
        # 3. 刷写去重过滤器
        if self.dedup_filter and hasattr(self.dedup_filter, 'flush'):
            self.dedup_filter.flush()
        
        logger.info("碰撞核心已停止")
    
    def on_batch_complete(
        self,
        matches: List[Dict[str, int]],
        batch_size: int
    ) -> None:
        """批次完成回调
        
        Args:
            matches: 匹配结果列表
            batch_size: 批次大小
        """
        if not self._running or not self.stats:
            return
        
        # 1. 更新统计
        self.stats.update(batch_size, matches)
        
        # 2. 去重过滤
        if self.dedup_filter and matches:
            unique_matches = self.dedup_filter.filter(matches)
            matches = unique_matches
        
        # 3. 处理匹配
        if matches and self.on_match:
            for match in matches:
                try:
                    self.on_match(match)
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
        
        stats_dict = self.stats.to_dict() if hasattr(self.stats, 'to_dict') else {}
        
        # 添加额外信息
        stats_dict.update({
            'running': self._running,
            'elapsed_time': time.time() - self._start_time if self._start_time else 0,
        })
        
        return stats_dict
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    # ========== 私有方法 ==========
    
    def _init_stats(self):
        """初始化碰撞统计"""
        # TODO: Phase 4实现 - 从现有CollisionStats适配
        try:
            from ..collision.collision_stats import CollisionStats
            self.stats = CollisionStats()
        except Exception as e:
            logger.error(f"初始化碰撞统计失败: {e}")
            raise
    
    def _init_checkpoint(self):
        """初始化断点管理器"""
        # TODO: Phase 4实现 - 从现有CheckpointManager适配
        try:
            from ..collision.checkpoint_manager import CheckpointManager
            self.checkpoint = CheckpointManager(
                auto_save_interval=self.checkpoint_interval
            )
        except Exception as e:
            logger.error(f"初始化断点管理器失败: {e}")
            raise
    
    def _init_dedup_filter(self):
        """初始化去重过滤器"""
        # TODO: Phase 4实现 - 从现有DeduplicationFilter适配
        try:
            dedup_max_size = self.config.get('dedup_max_size', 1_000_000)
            from ..collision.deduplication_filter import DeduplicationFilter
            self.dedup_filter = DeduplicationFilter(max_size=dedup_max_size)
        except Exception as e:
            logger.error(f"初始化去重过滤器失败: {e}")
            raise
    
    def _init_search_coordinator(self):
        """初始化搜索协调器"""
        # TODO: Phase 4实现 - 从现有SearchModeCoordinator适配
        try:
            from ..gpu.search_mode_coordinator import SearchModeCoordinator
            self.search_coordinator = SearchModeCoordinator()
        except Exception as e:
            logger.error(f"初始化搜索协调器失败: {e}")
            raise
    
    def _restore_checkpoint(self):
        """恢复断点"""
        if not self.checkpoint:
            return
        
        try:
            checkpoint_data = self.checkpoint.load()
            if checkpoint_data:
                logger.info(f"断点恢复: {checkpoint_data.get('mode', 'unknown')}")
                # TODO: 恢复统计和状态
        except Exception as e:
            logger.error(f"恢复断点失败: {e}")
    
    def _save_checkpoint(self):
        """保存断点"""
        if not self.checkpoint or not self.stats:
            return
        
        try:
            mode = self.config.get('mode', 'random')
            self.checkpoint.save(
                mode=mode,
                targets=self.targets,
                current_position=getattr(self.stats, 'total_checked', 0),
                total_checked=getattr(self.stats, 'total_checked', 0),
                matches=[]  # 匹配数据通过回调单独处理
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
        """节流调用进度回调"""
        # TODO: 实现进度回调节流逻辑
        pass
