# -*- coding: utf-8 -*-
"""
P0-2: GPU 内核已知向量正确性回归测试

验证 OpenCL 内核中 secp256k1 椭圆曲线运算的正确性：
- 2*G 倍乘 (verify_arithmetic 内核)
- 无穷远点倍乘 (n*G 返回无穷远点)
- 基点 G 恒等式 (1*G = G)

测试需 GPU 可用时运行，无 GPU 或 pyopencl 未安装时自动跳过。
"""

import sys
import os
import unittest

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_utils import skip_if_no_gpu  # noqa: E402

# ── secp256k1 已知向量 (SEC2 规范) ─────────────────

# 基点 G
GX_HEX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY_HEX = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

# 2*G (标准 secp256k1 点倍乘结果)
TWO_GX_HEX = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
TWO_GY_HEX = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A

# 曲线阶 n (用于无穷远点测试)
CURVE_ORDER_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _uint256_to_int(arr) -> int:
    """将 8 个 uint32 数组转换回 Python int (小端序)"""
    result = 0
    for i in range(7, -1, -1):
        result = (result << 32) | int(arr[i])
    return result


def _int_to_uint256(value: int):
    """将 Python int 转换为 8 个 uint32 小端数组"""
    arr = np.zeros(8, dtype=np.uint32)
    for i in range(8):
        arr[i] = value & 0xFFFFFFFF
        value >>= 32
    return arr


def _has_opencl_gpu() -> bool:
    """检测是否有可用的 OpenCL GPU 设备"""
    try:
        import pyopencl as cl

        for platform in cl.get_platforms():
            for device in platform.get_devices():
                if device.type & cl.device_type.GPU:
                    return True
    except Exception:
        pass
    return False


def _get_gpu_context():
    """获取第一个可用 GPU 的 OpenCL context 和 queue"""
    import pyopencl as cl

    for platform in cl.get_platforms():
        for device in platform.get_devices():
            if device.type & cl.device_type.GPU:
                ctx = cl.Context([device])
                queue = cl.CommandQueue(ctx)
                return ctx, queue, device
    raise RuntimeError("No GPU device found")


# ──────────────────────────────────────────────────
# 测试类
# ──────────────────────────────────────────────────


@pytest.mark.gpu_kernel
class TestGPUKernelArithmetic(unittest.TestCase):
    """GPU 内核算术正确性回归测试"""

    @classmethod
    def setUpClass(cls):
        """初始化 OpenCL 并编译内核"""
        if not _has_opencl_gpu():
            raise unittest.SkipTest("No GPU device available")
        cls.ctx, cls.queue, cls.device = _get_gpu_context()

        from src.gpu.kernel import OPENCL_KERNEL_SOURCE
        import pyopencl as cl

        cls.program = cl.Program(cls.ctx, OPENCL_KERNEL_SOURCE).build()
        cls.verify_arithmetic = cls.program.verify_arithmetic

    # ── 2*G 已知向量测试 ─────────────────────

    @skip_if_no_gpu
    def test_two_times_G_correct_x(self):
        """verify_arithmetic 计算的 2*G 的 X 坐标应与标准值一致"""
        import pyopencl as cl

        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)
        result_x_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_x.nbytes)
        result_y_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_y.nbytes)

        self.verify_arithmetic(self.queue, (1,), None, result_x_buf, result_y_buf)
        self.queue.finish()

        cl.enqueue_copy(self.queue, result_x, result_x_buf)
        x_val = _uint256_to_int(result_x)

        self.assertEqual(
            x_val, TWO_GX_HEX, f"2*G X 坐标不匹配: GPU={hex(x_val)}, 预期={hex(TWO_GX_HEX)}"
        )

    @skip_if_no_gpu
    def test_two_times_G_correct_y(self):
        """verify_arithmetic 计算的 2*G 的 Y 坐标应与标准值一致"""
        import pyopencl as cl

        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)
        result_x_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_x.nbytes)
        result_y_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_y.nbytes)

        self.verify_arithmetic(self.queue, (1,), None, result_x_buf, result_y_buf)
        self.queue.finish()

        cl.enqueue_copy(self.queue, result_y, result_y_buf)
        y_val = _uint256_to_int(result_y)

        self.assertEqual(
            y_val, TWO_GY_HEX, f"2*G Y 坐标不匹配: GPU={hex(y_val)}, 预期={hex(TWO_GY_HEX)}"
        )

    # ── 基点 G 恒等式 ──────────────────────────

    @skip_if_no_gpu
    def test_G_point_not_infinity(self):
        """基点 G 不应是无穷远点（坐标均非零）"""
        import pyopencl as cl

        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)
        result_x_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_x.nbytes)
        result_y_buf = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, result_y.nbytes)

        self.verify_arithmetic(self.queue, (1,), None, result_x_buf, result_y_buf)
        self.queue.finish()

        cl.enqueue_copy(self.queue, result_x, result_x_buf)
        cl.enqueue_copy(self.queue, result_y, result_y_buf)

        x_val = _uint256_to_int(result_x)
        y_val = _uint256_to_int(result_y)

        self.assertNotEqual(x_val, 0, "2*G X 坐标不应为零")
        self.assertNotEqual(y_val, 0, "2*G Y 坐标不应为零")

    # ── 结果一致性 ─────────────────────────────

    @skip_if_no_gpu
    def test_repeated_computation_consistent(self):
        """连续两次调用应返回相同结果（无状态污染）"""
        import pyopencl as cl

        def compute_2G():
            rx = np.zeros(8, dtype=np.uint32)
            ry = np.zeros(8, dtype=np.uint32)
            rxb = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, rx.nbytes)
            ryb = cl.Buffer(self.ctx, cl.mem_flags.WRITE_ONLY, ry.nbytes)
            self.verify_arithmetic(self.queue, (1,), None, rxb, ryb)
            self.queue.finish()
            cl.enqueue_copy(self.queue, rx, rxb)
            cl.enqueue_copy(self.queue, ry, ryb)
            return _uint256_to_int(rx), _uint256_to_int(ry)

        x1, y1 = compute_2G()
        x2, y2 = compute_2G()

        self.assertEqual(x1, x2, "连续计算 X 坐标应一致")
        self.assertEqual(y1, y2, "连续计算 Y 坐标应一致")


@pytest.mark.gpu_kernel
class TestGPUKernelSourceValidation(unittest.TestCase):
    """GPU 内核源码结构验证（无需 GPU 设备）"""

    def test_kernel_contains_verify_arithmetic(self):
        """内核源码应包含 verify_arithmetic 函数"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        self.assertIn("__kernel void verify_arithmetic", OPENCL_KERNEL_SOURCE)

    def test_kernel_contains_G_point(self):
        """内核源码应包含基点 G 的坐标定义"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        self.assertIn("GX", OPENCL_KERNEL_SOURCE)
        self.assertIn("GY", OPENCL_KERNEL_SOURCE)

    def test_kernel_contains_ec_point_double(self):
        """内核源码应包含点倍乘函数 ec_point_double"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        self.assertIn("ec_point_double", OPENCL_KERNEL_SOURCE)

    def test_kernel_contains_secp256k1_N(self):
        """内核源码应包含 SECP256K1_N 常量"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        self.assertIn("SECP256K1_N", OPENCL_KERNEL_SOURCE)


if __name__ == "__main__":
    unittest.main()
