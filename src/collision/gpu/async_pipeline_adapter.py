"""异步执行管道适配器

将现有AsyncGPUExecutor适配为IAsyncExecutionPipeline接口。

版本: v4.2.2 (Phase 2)
创建日期: 2026-04-29
更新日期: 2026-04-30
"""

import hashlib
import logging
import time
from typing import Any

from .protocols import GPUKernel, IAsyncExecutionPipeline, MatchResult

logger = logging.getLogger(__name__)


class AsyncPipelineAdapter(IAsyncExecutionPipeline):
    """异步执行管道适配器

    适配现有AsyncGPUExecutor到IAsyncExecutionPipeline接口。
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化适配器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._pipeline: Any = None
        self._kernel: Any = None  # 保存kernel引用
        self._batch_size = 0

    def initialize(self, kernel: GPUKernel, batch_size: int) -> None:
        """初始化异步管道

        Args:
            kernel: GPU内核对象
            batch_size: 批次大小

        Raises:
            RuntimeError: 初始化失败
        """
        try:
            from ...gpu.async_executor import AsyncGPUExecutor

            # 保存kernel引用
            self._kernel = kernel
            self._batch_size = batch_size

            # 从kernel获取context和device
            if not kernel.context or not kernel.context.context_obj:
                raise RuntimeError("GPU上下文未初始化")

            if not kernel.context.device:
                raise RuntimeError("GPU设备未初始化")

            # 创建异步执行器
            # 注意：AsyncGPUExecutor需要GPUDevice对象，而不是context
            self._pipeline = AsyncGPUExecutor(
                gpu_device=kernel.context.device,
                max_batch_size=batch_size,
                queue_depth=self.config.get("queue_depth", 4),
            )

            # 初始化缓冲区池
            self._pipeline.initialize_buffers(context=kernel.context.context_obj, num_keys=batch_size)

            _qd = self._pipeline.queue_depth
            logger.info(
                f"异步管道初始化完成: batch_size={batch_size:,}, queue_depth={_qd}"
            )

        except Exception as e:
            logger.error(f"异步管道初始化失败: {e}")
            raise RuntimeError(f"异步管道初始化失败: {e}") from e

    def run_batch(self, seed: bytes, batch_size: int) -> tuple[list[MatchResult], float]:
        """运行单个批次

        Args:
            seed: 随机种子（32字节）
            batch_size: 批次大小

        Returns:
            (匹配结果列表, 执行时间ms)

        Raises:
            RuntimeError: 管道未初始化或执行失败
        """
        if not self._pipeline:
            raise RuntimeError("异步管道未初始化，请先调用initialize()")

        if not self._kernel or not self._kernel.kernel_obj:
            raise RuntimeError("GPU内核未初始化")

        start_time = time.time()

        try:
            # 调用现有AsyncGPUExecutor的run_batch_async方法
            # 注意：需要传递kernel对象
            raw_matches, exec_time_ms = self._pipeline.run_batch_async(
                kernel=self._kernel.kernel_obj, seed=seed, batch_size=batch_size
            )

            # 转换为MatchResult格式
            matches = self._convert_matches(raw_matches)

            total_elapsed_ms = (time.time() - start_time) * 1000

            logger.debug(
                "异步批次执行完成: "
                f"batch_size={batch_size:,}, "
                f"matches={len(matches)}, "
                f"gpu_time={exec_time_ms:.0f}ms, "
                f"total_time={total_elapsed_ms:.0f}ms"
            )

            return matches, total_elapsed_ms

        except Exception as e:
            logger.error(f"异步批次执行失败: {e}")
            raise RuntimeError(f"异步批次执行失败: {e}") from e

    def is_ready(self) -> bool:
        """检查管道是否就绪

        Returns:
            管道已初始化且内核可用时返回 True
        """
        return (
            self._pipeline is not None
            and self._kernel is not None
            and self._kernel.kernel_obj is not None
        )

    def prefetch_next_batch(self, seed: bytes, num_keys: int) -> None:
        """预取下一批次种子

        Args:
            seed: 32字节随机种子
            num_keys: 密钥数量
        """
        if not self._pipeline:
            logger.debug("异步管道未初始化，跳过预取")
            return

        try:
            self._pipeline.prefetch_next_batch(seed, num_keys)
        except Exception as e:
            logger.warning(f"预取下一批失败: {e}")

    def flush_pending(self) -> list:
        """收集所有尚未取回的异步执行结果

        Returns:
            List[Tuple[bytes, List[Dict]]]: 每个元素为 (seed, matches)
        """
        if not self._pipeline:
            return []

        try:
            return self._pipeline.flush_pending()
        except Exception as e:
            logger.error(f"刷写待处理结果失败: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """获取异步执行统计

        Returns:
            统计信息字典
        """
        if not self._pipeline:
            return {"status": "not_initialized"}

        try:
            return self._pipeline.get_stats()
        except Exception as e:
            logger.error(f"获取异步统计失败: {e}")
            return {"status": "error", "message": str(e)}

    def cleanup(self) -> None:
        """清理异步管道资源"""
        if not self._pipeline:
            return

        try:
            self._pipeline.cleanup()
            self._pipeline = None
            self._kernel = None
            self._batch_size = 0
            logger.debug("异步管道资源已清理")
        except Exception as e:
            logger.error(f"异步管道清理失败: {e}")

    def _convert_matches(self, raw_matches: list[dict]) -> list[MatchResult]:
        """转换匹配结果格式

        Args:
            raw_matches: 原始匹配结果列表

        Returns:
            MatchResult格式列表
        """
        matches = []

        for match in raw_matches:
            match_result: MatchResult = {
                "address": match.get("address", ""),
                "private_key": match.get("private_key", ""),
                "private_key_hash": hashlib.sha256(
                    str(match.get("private_key", "")).encode()
                ).hexdigest(),
                "public_key": match.get("public_key", ""),
                "hash160": match.get("hash160", ""),
                "index": match.get("index", 0),
                "seed": match.get("seed", ""),
            }
            matches.append(match_result)

        return matches
