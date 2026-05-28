"""种子字节端序转换工具.

提供 _seed_bytes_to_u32_be_array 函数的单一权威实现，
消除 kernel_impl.py / async_executor.py / engine.py 中的三处重复定义。

v4.2.3 M5: 从 engine.py 提取为独立工具模块，统一端序转换逻辑。
"""

import numpy as np

__all__ = ["seed_bytes_to_u32_be_array"]


def seed_bytes_to_u32_be_array(seed: bytes) -> "np.ndarray":
    """将 32 字节 seed 按 big-endian 拆成 8*uint32，再转成本机端序.

    比特币私钥为 256-bit big-endian 整数，GPU Kernel 期望 native-endian uint32 数组。
    此函数确保从 BE bytes → native uint32 的正确转换，且在 LE 机器上透明高效。

    v4.2.3 M5: 从三处重复定义中提取为单一实现。
    原规范定义在 engine.py，现统一由此模块提供。

    Args:
        seed: 32 字节大端序私钥种子

    Returns:
        长度 8 的 np.uint32 数组（本机端序）

    Raises:
        ValueError: seed 长度不等于 32

    """
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    # >u4 = big-endian uint32; .astype(np.uint32) = 转本机端序
    # np.dtype('>u4').itemsize == 4 且 np.uint32 为 32-bit（显式校验，非 assert）
    be_u32 = np.frombuffer(seed, dtype=">u4")
    # v4.2.3: assert → 显式异常，避免 python -O 模式跳过校验
    if be_u32.dtype.itemsize != 4:
        raise RuntimeError(f">u4 dtype itemsize expected 4, got {be_u32.dtype.itemsize}")
    result = be_u32.astype(np.uint32)
    if result.dtype.itemsize != 4:
        raise RuntimeError(f"uint32 dtype itemsize expected 4, got {result.dtype.itemsize}")
    if len(result) != 8:
        raise RuntimeError(f"expected 8 uint32 values, got {len(result)}")
    return result


# 保留旧名称作为别名，兼容未迁移的外部调用
_seed_bytes_to_u32_be_array = seed_bytes_to_u32_be_array
