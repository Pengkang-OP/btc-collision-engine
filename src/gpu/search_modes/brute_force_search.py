"""暴力穷举搜索模式 - BruteForceSearchMode

将 GPUCollisionEngine._brute_force() 迁移至此独立模块。
通过 self.engine 访问所有引擎状态，不复制状态。
"""

# P3-5: 统一日志获取
from typing import TYPE_CHECKING, Any

from ...utils import get_configured_logger
from .base_search import BaseSearchMode

if TYPE_CHECKING:
    pass

logger = get_configured_logger("BruteForceSearch")


class BruteForceSearchMode(BaseSearchMode):
    """暴力穷举搜索模式

    对应原 GPUCollisionEngine._brute_force() 方法。
    从指定起始私钥开始，按顺序遍历所有私钥空间。
    """

    def execute(self, start: int) -> None:
        """执行暴力穷举搜索（委托给通用批处理循环）

        Args:
            start: 起始私钥整数值
        """
        engine = self.engine
        eng: Any = engine
        eng._range_start = start
        eng._current_position = start

        current = start

        def gen_keys() -> tuple[bytes, int]:
            nonlocal current
            batch_end = current + engine.batch_size
            private_keys = self._generate_sequential_keys(current, engine.batch_size)
            actual = engine.batch_size
            # 预先推进位置（在返回前更新，保持和原始逻辑一致）
            current = batch_end
            engine._current_position = current
            return private_keys, actual

        batch_count = self._execute_batch_loop(
            key_generator_fn=gen_keys,
            mode_name="暴力穷举",
        )

        eng._running = False
        eng.stats.update(batch_count)
        if eng.on_complete:
            eng.on_complete(eng.stats.snapshot())
