"""GPU 缓冲区安全清除工具.

提供 secure_clear_gpu_buffer 函数，在释放 OpenCL 缓冲区前用零覆盖其内容，
防止种子、匹配标志等敏感数据在 GPU 显存中残留。
"""

import logging
from typing import Any

from ._availability import PYOPENCL_AVAILABLE

if PYOPENCL_AVAILABLE:
    import pyopencl as cl
else:
    cl = None  # type: ignore[assignment]

logger = logging.getLogger("GPUSecureBuffer")

__all__ = ["secure_clear_gpu_buffer"]


def secure_clear_gpu_buffer(queue: Any, buf: Any, size: int) -> None:
    """在释放 OpenCL 缓冲区前用零覆盖其内容.

    防止敏感数据（种子、匹配标志等）在 GPU 显存中残留。
    此为 best-effort 操作：安全清除失败不会导致程序崩溃。

    前提条件：
        - size 必须是 4 的倍数（本项目中所有缓冲区均满足该条件）
        - queue 和 buf 必须是有效的 OpenCL 对象

    Args:
        queue: OpenCL 命令队列
        buf: OpenCL Buffer 对象
        size: 缓冲区大小（字节）

    """
    if not PYOPENCL_AVAILABLE or cl is None:
        return
    try:
        import numpy as np

        cl.enqueue_fill_buffer(queue, buf, np.int32(0), 0, size)
        queue.finish()
    except Exception:
        logger.debug(
            "安全清除 GPU 缓冲区失败 (size=%s): 敏感数据可能残留",
            size,
            exc_info=True,
        )


__all__ = ["secure_clear_gpu_buffer"]
