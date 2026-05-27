"""GPU 可用性检测模块.

提供 PYOPENCL_AVAILABLE 常量的唯一定义点。
所有需要检测 PyOpenCL 可用性的模块应从本模块导入。

版本: v5.0.1
创建日期: 2026-05-28
"""

PYOPENCL_AVAILABLE: bool

try:
    import pyopencl as cl  # noqa: F401

    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False
    cl = None  # type: ignore[assignment]
