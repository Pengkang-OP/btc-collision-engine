"""secp256k1 预计算表生成模块

为 GPU 内核提供基点倍数表 [1G, 2G, ..., 31G]。
表布局：31 个点，每点 16 个 uint32（x:8 + y:8），共 496 个 uint32。
小端序存储：d[0]=LSB, d[7]=MSB，与内核 uint256_t 的 uint d[8] 一致。
"""

from typing import cast

import numpy as np

# secp256k1 曲线参数
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

# 已知 2G 值（SEC2 标准向量，用于验证）
_EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
_EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A

# 已知 3G 值（SEC2 标准向量，扩展验证）
_EXPECTED_3G_X = 0xF9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9
_EXPECTED_3G_Y = 0x388F7B0F632DE8140FE337E62A37F3566500A99934C2231B6CB9FD7584B8E672

# 已知 10G 值（SEC2 标准向量，扩展验证）
_EXPECTED_10G_X = 0xA0434D9E47F3C86235477C7B1AE6AE5D3442D49B1943C2B752A68E2A47E247C7
_EXPECTED_10G_Y = 0x893ABA425419BC27A3B6C7E693A24C696F794C2ED877A1593CBEE53B037368D7


def _point_add(p1: tuple[int, int] | None, p2: tuple[int, int] | None) -> tuple[int, int] | None:
    """仿射坐标下的椭圆曲线点加法 (secp256k1)

    Args:
        p1: 第一个点 (x1, y1)，使用 None 表示无穷远点
        p2: 第二个点 (x2, y2)，使用 None 表示无穷远点

    Returns:
        相加结果点 (x, y)，或 None 表示无穷远点

    """
    if p1 is None:
        return p2
    if p2 is None:
        return p1

    x1, y1 = p1
    x2, y2 = p2

    if x1 == x2:
        if y1 != y2:
            # P + (-P) = 无穷远点
            return None
        # P + P = 点倍乘（切线公式）
        lam_num = (3 * x1 * x1) % _P
        lam_den = (2 * y1) % _P
    else:
        # 一般加法
        lam_num = (y2 - y1) % _P
        lam_den = (x2 - x1) % _P

    lam = (lam_num * pow(lam_den, _P - 2, _P)) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _int_to_uint32_le(value: int) -> np.ndarray:
    """将 256-bit 整数转为 8 个 uint32 小端序数组

    小端序：limb[0] 为最低有效 32 位，limb[7] 为最高有效 32 位。
    与 OpenCL 内核中 uint256_t.d[0]=LSB 保持一致。

    Args:
        value: 256-bit 无符号整数

    Returns:
        np.ndarray: dtype=np.uint32, shape=(8,)

    """
    limbs = np.zeros(8, dtype=np.uint32)
    for i in range(8):
        limbs[i] = np.uint32(value & 0xFFFFFFFF)
        value >>= 32
    return limbs


def generate_secp256k1_precomp_table() -> np.ndarray:
    """计算 secp256k1 基点 G 的倍数表 [1G, 2G, 3G, ..., 31G]

    Returns:
        np.ndarray: dtype=np.uint32, shape=(496,)
        布局: [G1x_d0..d7, G1y_d0..d7, G2x_d0..d7, G2y_d0..d7, ..., G31x_d0..d7, G31y_d0..d7]
        小端序: d[0]=LSB, d[7]=MSB

    Raises:
        RuntimeError: 如果生成的 1G 或 2G 值与已知值不符

    """
    table = np.zeros(496, dtype=np.uint32)  # 31 * 2 * 8 = 496

    _g_point = (_GX, _GY)
    current = _g_point  # 从 1G 开始

    for i in range(31):
        if current is None:
            raise RuntimeError(f"点 {i + 1}G 为无穷远点，这不应发生")

        x, y = current
        offset = i * 16  # 每个点占 16 个 uint32

        table[offset : offset + 8] = _int_to_uint32_le(x)  # x 坐标
        table[offset + 8 : offset + 16] = _int_to_uint32_le(y)  # y 坐标

        # 下一个点
        current = cast("tuple[int, int]", _point_add(current, _g_point))

    # === 验证 ===
    # P3-9: 验证本地常量与 secp256k1 参考实现一致
    from ..core.secp256k1 import Secp256k1 as _Secp256k1

    _ref_p = _Secp256k1.P  # noqa: N806
    _ref_gx = _Secp256k1.Gx  # noqa: N806
    _ref_gy = _Secp256k1.Gy  # noqa: N806
    if _P != _ref_p:
        raise RuntimeError(f"p 参数不一致: precompute.P=0x{_P:X}, secp256k1.P=0x{_ref_p:X}")
    if _GX != _ref_gx:
        raise RuntimeError(f"Gx 参数不一致: precompute.Gx=0x{_GX:X}, secp256k1.Gx=0x{_ref_gx:X}")
    if _GY != _ref_gy:
        raise RuntimeError(f"Gy 参数不一致: precompute.Gy=0x{_GY:X}, secp256k1.Gy=0x{_ref_gy:X}")

    # 验证 1G
    g1x_reconstructed = sum(int(table[j]) << (32 * j) for j in range(8))
    g1y_reconstructed = sum(int(table[8 + j]) << (32 * j) for j in range(8))

    if g1x_reconstructed != _GX:
        raise RuntimeError(f"1G.x 验证失败: got {hex(g1x_reconstructed)}, expected {hex(_GX)}")
    if g1y_reconstructed != _GY:
        raise RuntimeError(f"1G.y 验证失败: got {hex(g1y_reconstructed)}, expected {hex(_GY)}")

    # 验证 2G
    g2_offset = 16  # 第 2 个点的偏移
    g2x_reconstructed = sum(int(table[g2_offset + j]) << (32 * j) for j in range(8))
    g2y_reconstructed = sum(int(table[g2_offset + 8 + j]) << (32 * j) for j in range(8))

    if g2x_reconstructed != _EXPECTED_2G_X:
        raise RuntimeError(
            f"2G.x 验证失败: got {hex(g2x_reconstructed)}, expected {hex(_EXPECTED_2G_X)}",
        )
    if g2y_reconstructed != _EXPECTED_2G_Y:
        raise RuntimeError(
            f"2G.y 验证失败: got {hex(g2y_reconstructed)}, expected {hex(_EXPECTED_2G_Y)}",
        )

    # 验证 3G (SEC2 标准向量)
    g3_offset = 32  # 第 3 个点的偏移
    g3x_reconstructed = sum(int(table[g3_offset + j]) << (32 * j) for j in range(8))
    g3y_reconstructed = sum(int(table[g3_offset + 8 + j]) << (32 * j) for j in range(8))

    if g3x_reconstructed != _EXPECTED_3G_X:
        raise RuntimeError(
            f"3G.x 验证失败: got {hex(g3x_reconstructed)}, expected {hex(_EXPECTED_3G_X)}",
        )
    if g3y_reconstructed != _EXPECTED_3G_Y:
        raise RuntimeError(
            f"3G.y 验证失败: got {hex(g3y_reconstructed)}, expected {hex(_EXPECTED_3G_Y)}",
        )

    # 验证 10G (SEC2 标准向量)
    g10_offset = 144  # 第 10 个点的偏移 (9 * 16)
    g10x_reconstructed = sum(int(table[g10_offset + j]) << (32 * j) for j in range(8))
    g10y_reconstructed = sum(int(table[g10_offset + 8 + j]) << (32 * j) for j in range(8))

    if g10x_reconstructed != _EXPECTED_10G_X:
        raise RuntimeError(
            f"10G.x 验证失败: got {hex(g10x_reconstructed)}, expected {hex(_EXPECTED_10G_X)}",
        )
    if g10y_reconstructed != _EXPECTED_10G_Y:
        raise RuntimeError(
            f"10G.y 验证失败: got {hex(g10y_reconstructed)}, expected {hex(_EXPECTED_10G_Y)}",
        )

    return table


# 模块级缓存（避免重复计算）
_cached_table: np.ndarray | None = None


def get_precomp_table() -> np.ndarray:
    """获取预计算表（带缓存，模块首次调用时计算一次）

    Returns:
        np.ndarray: dtype=np.uint32, shape=(496,)，同 generate_secp256k1_precomp_table()

    """
    global _cached_table
    if _cached_table is None:
        _cached_table = generate_secp256k1_precomp_table()
    return _cached_table
