"""范围扫描搜索模式 - RangeScanSearchMode

将 GPUCollisionEngine._range_scan() 迁移至此独立模块。
通过 self.engine 访问所有引擎状态，不复制状态。
"""

import logging

# P3-5: 统一日志获取
from ...utils import init_logging, get_configured_logger
from typing import TYPE_CHECKING, Tuple

from .base_search import BaseSearchMode

if TYPE_CHECKING:
    from ...collision.gpu_collision_engine import GPUCollisionEngine

logger = get_configured_logger("RangeScanSearch")


class RangeScanSearchMode(BaseSearchMode):
    """范围扫描搜索模式

    对应原 GPUCollisionEngine._range_scan() 方法。
    在指定范围 [start, end] 内按顺序扫描所有私钥，支持流水线预生成。
    """

    def execute(self, start: int, end: int) -> None:
        """执行范围扫描（ALG-2修复：委托给通用批处理循环）

        Args:
            start: 起始私钥整数值（含）
            end:   结束私钥整数值（含）
        """
        engine = self.engine
        logger.debug(f"范围扫描启动: start={start}, end={end}, total={end - start + 1}")

        current = start

        # ALG-2修复: 使用end而非end+1，避免边界重复
        batch_end = min(current + engine.batch_size, end)
        next_batch_size = batch_end - current
        next_private_keys = self._generate_sequential_keys(current, next_batch_size)

        def gen_keys() -> Tuple[bytes, int]:
            nonlocal current, next_private_keys, next_batch_size
            # 使用预生成的私钥
            keys = next_private_keys
            actual = next_batch_size
            current += actual
            engine._current_position = current
            # 预生成下一批（在 GPU 计算时进行）
            if current <= end:
                nb_end = min(current + engine.batch_size, end + 1)
                next_batch_size = nb_end - current
                next_private_keys = self._generate_sequential_keys(current, next_batch_size)
            return keys, actual

        def stop_cond() -> bool:
            return current > end

        batch_count = self._execute_batch_loop(
            key_generator_fn=gen_keys,
            mode_name="范围扫描",
            stop_condition_fn=stop_cond,
        )

        engine._running = False
        engine.stats.update(batch_count)  # type: ignore[attr-defined]
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())  # type: ignore[attr-defined]  # P1-2修复: 使用线程安全快照
