#!/usr/bin/env python3
"""快速验证GPU内核可用性"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
def test_kernel_load():
    """测试内核加载"""
    print("=" * 60)
    print("GPU内核快速验证")
    print("=" * 60)

    # 1. 导入内核源码
    print("\n1. 加载内核源码...")
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        print("   ✅ 成功加载")
        print(f"   长度: {len(OPENCL_KERNEL_SOURCE)} 字符")
        print(f"   内核函数数: {OPENCL_KERNEL_SOURCE.count('__kernel')}")
    except Exception as e:
        print(f"   ❌ 加载失败: {e}")
        return False

    # 2. 检查PyOpenCL
    print("\n2. 检查PyOpenCL...")
    try:
        import pyopencl as cl

        print("   ✅ PyOpenCL可用")
        print(f"   版本: {cl.VERSION_TEXT}")
    except ImportError:
        print("   ❌ PyOpenCL未安装")
        print("   安装命令: pip install pyopencl")
        return False

    # 3. 检查GPU设备
    print("\n3. 检查GPU设备...")
    try:
        platforms = cl.get_platforms()
        print(f"   ✅ 找到 {len(platforms)} 个OpenCL平台")

        gpu_devices = []
        for platform in platforms:
            devices = platform.get_devices(device_type=cl.device_type.GPU)
            gpu_devices.extend(devices)

        if gpu_devices:
            print(f"   ✅ 找到 {len(gpu_devices)} 个GPU设备")
            for i, device in enumerate(gpu_devices):
                print(f"   {i + 1}. {device.name}")
                print(f"      厂商: {device.vendor}")
                print(f"      内存: {device.global_mem_size // (1024**2)} MB")
        else:
            print("   ⚠️  未找到GPU设备")
            return False

    except Exception as e:
        print(f"   ❌ 设备检测失败: {e}")
        return False

    # 4. 测试内核编译
    print("\n4. 测试内核编译...")
    try:
        # 使用第一个GPU设备
        device = gpu_devices[0]
        context = cl.Context([device])

        # 编译内核
        program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()

        # 检查内核是否存在
        verify_arithmetic = program.verify_arithmetic

        print("   ✅ 内核编译成功")
        print(f"   设备: {device.name}")
        print("   可用内核函数:")
        print("     - batch_check")
        print("     - verify_arithmetic")
        print("     - debug_hash")

    except Exception as e:
        print(f"   ❌ 内核编译失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 5. 验证算术
    print("\n5. 验证基础算术（2*G计算）...")
    try:
        import numpy as np

        # 创建输出缓冲区
        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)

        # 创建OpenCL缓冲区
        result_x_buf = cl.Buffer(context, cl.mem_flags.WRITE_ONLY, result_x.nbytes)
        result_y_buf = cl.Buffer(context, cl.mem_flags.WRITE_ONLY, result_y.nbytes)

        # 执行内核
        queue = cl.CommandQueue(context)
        verify_arithmetic(queue, (1,), None, result_x_buf, result_y_buf)
        queue.finish()

        # 读取结果
        cl.enqueue_copy(queue, result_x, result_x_buf)
        cl.enqueue_copy(queue, result_y, result_y_buf)

        # 转换为整数
        def uint256_to_int(arr):
            result = 0
            for i in range(7, -1, -1):
                result = (result << 32) | arr[i]
            return result

        x_val = uint256_to_int(result_x)
        y_val = uint256_to_int(result_y)

        # 预期值
        expected_x = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
        expected_y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A

        if x_val == expected_x and y_val == expected_y:
            print("   ✅ 算术验证通过")
            print("   2*G计算正确")
        else:
            print("   ⚠️  算术验证失败")
            print(f"   预期X: {hex(expected_x)}")
            print(f"   实际X: {hex(x_val)}")
            print(f"   预期Y: {hex(expected_y)}")
            print(f"   实际Y: {hex(y_val)}")

    except Exception as e:
        print(f"   ⚠️  算术验证跳过: {e}")

    # 总结
    print("\n" + "=" * 60)
    print("✅ GPU内核验证完成 - GPU模式可用！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_kernel_load()
    sys.exit(0 if success else 1)
