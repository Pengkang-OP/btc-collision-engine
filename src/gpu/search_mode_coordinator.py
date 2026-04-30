"""搜索模式协调器

负责管理所有搜索模式的创建、切换和执行。
"""

import logging

# P3-5: 统一日志获取
from ..utils import init_logging, get_configured_logger
from typing import Dict, Optional, List, Any, TYPE_CHECKING, cast

from ..gpu.search_modes import RandomSearchMode, BruteForceSearchMode, RangeScanSearchMode
from ..collision.checkpoint_manager import CheckpointManager
from ..collision.collision_stats import CollisionStats

if TYPE_CHECKING:
    # 避免循环导入：仅在类型检查时引用引擎
    from ..collision.gpu_collision_engine import GPUCollisionEngine

_logger = get_configured_logger("SearchModeCoordinator")


class SearchModeCoordinator:
    """搜索模式协调器

    负责管理所有搜索模式的创建、切换和执行。
    """

    # 支持的搜索模式
    MODE_RANDOM = "random"
    MODE_BRUTE_FORCE = "brute_force"
    MODE_RANGE_SCAN = "range_scan"

    def __init__(self, engine: "GPUCollisionEngine", logger: Optional[Any] = None) -> None:
        """
        Args:
            engine: GPUCollisionEngine实例
            logger: 日志记录器
        """
        self.engine = engine
        self.logger = logger or _logger

        self._current_mode: Optional[str] = None
        self._modes: Dict[str, Any] = {}

        # 初始化搜索模式
        self._init_modes()

    def _init_modes(self):
        """初始化所有搜索模式"""
        # 从配置读取seed_prefetch_size
        cfg_gpu = (
            self.engine.config.get("gpu", {})
            if hasattr(self.engine, "config") and self.engine.config
            else {}
        )
        seed_prefetch_size = cfg_gpu.get("seed_prefetch_size", 5)

        self._modes[self.MODE_RANDOM] = RandomSearchMode(
            self.engine, seed_prefetch_size=seed_prefetch_size
        )
        self._modes[self.MODE_BRUTE_FORCE] = BruteForceSearchMode(self.engine)
        self._modes[self.MODE_RANGE_SCAN] = RangeScanSearchMode(self.engine)

        self.logger.info(f"已初始化搜索模式: {list(self._modes.keys())}")

    def get_available_modes(self) -> List[str]:
        """获取可用的搜索模式列表"""
        return list(self._modes.keys())

    def start(self, mode: str, resume: bool = False, **kwargs) -> None:
        """启动指定的搜索模式

        Args:
            mode: 搜索模式名称
            resume: 是否从检查点恢复
            **kwargs: 模式特定的参数
        """
        if mode not in self._modes:
            available = ", ".join(self.get_available_modes())
            raise ValueError(f"未知的搜索模式: {mode}。可用模式: {available}")

        self._current_mode = mode
        search_mode = self._modes[mode]

        self.logger.info(f"启动搜索模式: {mode}")

        # 处理检查点恢复
        if resume:
            self._resume_from_checkpoint()

        # 执行搜索
        if mode == self.MODE_RANDOM:
            self._execute_random_search(search_mode, **kwargs)
        elif mode == self.MODE_BRUTE_FORCE:
            start = kwargs.get("start", 0)
            search_mode.execute(start)
        elif mode == self.MODE_RANGE_SCAN:
            start = kwargs.get("start", 0)
            end = kwargs.get("end", 2**256 - 1)
            search_mode.execute(start, end)

    def _execute_random_search(self, search_mode: RandomSearchMode, **kwargs):
        """执行随机搜索"""
        resume = kwargs.get("resume", False)

        # 调用RandomSearchMode的execute方法，它会自动选择同步或异步模式
        search_mode.execute()

    def _resume_from_checkpoint(self):
        """从检查点恢复"""
        if self.engine.checkpoint_mgr:
            checkpoint = self.engine.checkpoint_mgr.load()
            if checkpoint:
                self.engine._current_position = checkpoint.get("position", 0)
                self.engine.stats = checkpoint.get("stats", CollisionStats())
                self.logger.info(f"从检查点恢复: position={self.engine._current_position}")
            else:
                self.logger.warning("未找到检查点，从头开始")
        else:
            self.logger.warning("检查点管理器未启用，无法恢复")

    def switch_mode(self, new_mode: str, **kwargs) -> None:
        """切换到新的搜索模式

        Args:
            new_mode: 新的搜索模式
            **kwargs: 模式特定的参数
        """
        if self._current_mode == new_mode:
            self.logger.warning(f"已经是 {new_mode} 模式，无需切换")
            return

        self.logger.info(f"切换搜索模式: {self._current_mode} -> {new_mode}")

        # 停止当前模式
        if self._current_mode and self._current_mode in self._modes:
            # 保存当前状态
            self._save_current_state()

        # 启动新模式
        self.start(new_mode, resume=False, **kwargs)

    def _save_current_state(self):
        """保存当前模式的状态"""
        if self.engine.checkpoint_mgr:
            try:
                self.engine._save_checkpoint(self.engine.stats.total_keys)  # type: ignore[attr-defined]  # 动态属性，已知存在  # 动态属性，已知存在
                self.logger.info("当前状态已保存到检查点")
            except Exception as e:
                self.logger.error(f"保存检查点失败: {e}")

    def stop(self) -> None:
        """停止当前搜索模式"""
        if self._current_mode:
            self.logger.info(f"停止搜索模式: {self._current_mode}")
            # 保存当前状态
            self._save_current_state()
            # 停止当前模式的执行
            if self._current_mode in self._modes:
                search_mode = self._modes[self._current_mode]
                if hasattr(search_mode, "stop"):
                    search_mode.stop()
            # 清除当前模式
            self._current_mode = None

    def get_current_mode(self) -> Optional[str]:
        """获取当前搜索模式"""
        return self._current_mode

    def get_mode_instance(self, mode: str) -> Optional[Any]:
        """获取指定搜索模式的实例

        Args:
            mode: 搜索模式名称

        Returns:
            搜索模式实例，不存在则返回None
        """
        return self._modes.get(mode)

    def get_mode_status(self, mode: str) -> Dict[str, Any]:
        """获取指定搜索模式的状态

        Args:
            mode: 搜索模式名称

        Returns:
            状态字典
        """
        search_mode = self._modes.get(mode)
        if not search_mode:
            return {"error": "搜索模式不存在"}

        try:
            # 检查搜索模式是否有status方法
            if hasattr(search_mode, "get_status"):
                return cast(Dict[str, Any], search_mode.get_status())
            else:
                return {
                    "mode": mode,
                    "status": "available",
                    "engine_running": (
                        self.engine.is_running() if hasattr(self.engine, "is_running") else False
                    ),
                }
        except Exception as e:
            self.logger.error(f"获取搜索模式状态失败: {e}")
            return {"error": str(e)}

    def get_all_modes_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有搜索模式的状态

        Returns:
            状态字典，键为模式名称，值为状态字典
        """
        status_dict = {}
        for mode in self.get_available_modes():
            status_dict[mode] = self.get_mode_status(mode)
        return status_dict
