#!/usr/bin/env python3
"""验证OpenCL内核文件完整性"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def verify_kernel_files():
    """验证内核文件"""

    kernel_dir = os.path.join(project_root, "src", "gpu", "kernels")

    print("=" * 70)
    print("OpenCL内核文件验证")
    print("=" * 70)

    # 1. 检查文件存在性
    print("\n1. 文件存在性检查:")
    required_files = ["btc_collision.cl", "README.md"]

    for filename in required_files:
        filepath = os.path.join(kernel_dir, filename)
        exists = os.path.exists(filepath)
        status = "✓" if exists else "✗"
        print(f"   {status} {filename}")
        if not exists:
            print(f"     错误: 文件不存在: {filepath}")
            return False

    # 2. 验证内核文件内容
    print("\n2. 内核文件内容验证:")
    cl_file = os.path.join(kernel_dir, "btc_collision.cl")
    with open(cl_file, encoding="utf-8") as f:
        content = f.read()

    # 检查关键元素
    checks = [
        ("uint256_t类型定义", "typedef struct"),
        ("GX常量", "constant uint GX[8]"),
        ("GY常量", "constant uint GY[8]"),
        ("SECP256K1_P常量", "constant uint SECP256K1_P[8]"),
        ("uint256_add函数", "uint uint256_add"),
        ("uint256_sub函数", "void uint256_sub"),
        ("mod_mul函数", "void mod_mul"),
        ("mod_inverse函数", "void mod_inverse"),
        ("ec_point_double函数", "void ec_point_double"),
        ("ec_point_add函数", "void ec_point_add"),
        ("ec_scalar_multiply函数", "void ec_scalar_multiply"),
        ("sha256函数", "void sha256"),
        ("ripemd160函数", "void ripemd160"),
        ("hash160函数", "void hash160"),
        ("batch_check内核", "__kernel void batch_check"),
        ("verify_arithmetic内核", "__kernel void verify_arithmetic"),
        ("debug_hash内核", "__kernel void debug_hash"),
    ]

    all_passed = True
    for name, pattern in checks:
        found = pattern in content
        status = "✓" if found else "✗"
        print(f"   {status} {name}")
        if not found:
            print(f"     警告: 未找到 '{pattern}'")
            all_passed = False

    # 3. 统计信息
    print("\n3. 内核文件统计:")
    lines = content.split("\n")
    print(f"   总行数: {len(lines)}")
    print(f"   总字符数: {len(content)}")
    print(f"   文件大小: {os.path.getsize(cl_file)} 字节")
    print(f"   注释行数: {sum(1 for line in lines if line.strip().startswith('//'))}")
    print(f"   空行数: {sum(1 for line in lines if not line.strip())}")
    print(f"   内核函数数: {content.count('__kernel')}")

    # 4. 与kernel.py中的内嵌源码对比
    print("\n4. 与kernel.py内嵌源码对比:")
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        match = content.strip() == OPENCL_KERNEL_SOURCE.strip()
        status = "✓" if match else "✗"
        print(f"   {status} 源码一致性: {'完全匹配' if match else '不匹配'}")
        if not match:
            print(f"     文件长度: {len(content)}")
            print(f"     内嵌长度: {len(OPENCL_KERNEL_SOURCE)}")
    except ImportError as e:
        print(f"   ⚠ 无法导入kernel.py: {e}")

    # 5. 验证PyOpenCL可用性（可选）
    print("\n5. PyOpenCL环境检查:")
    try:
        import pyopencl as cl

        print(f"   ✓ PyOpenCL版本: {cl.VERSION_TEXT}")

        # 尝试获取GPU设备
        platforms = cl.get_platforms()
        print(f"   ✓ OpenCL平台数: {len(platforms)}")

        gpu_devices = []
        for platform in platforms:
            devices = platform.get_devices(device_type=cl.device_type.GPU)
            gpu_devices.extend(devices)

        if gpu_devices:
            print(f"   ✓ GPU设备数: {len(gpu_devices)}")
            for i, device in enumerate(gpu_devices[:3]):  # 只显示前3个
                print(f"     - {i + 1}. {device.name}")
                print(f"       厂商: {device.vendor}")
                print(f"       全局内存: {device.global_mem_size // (1024**2)} MB")
        else:
            print("   ⚠ 未检测到GPU设备")

    except ImportError:
        print("   ⚠ PyOpenCL未安装")
        print("     安装命令: pip install pyopencl")
    except Exception as e:
        print(f"   ⚠ OpenCL检查失败: {e}")

    # 总结
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 验证通过: 所有内核文件完整且正确")
    else:
        print("❌ 验证失败: 部分检查未通过")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = verify_kernel_files()
    sys.exit(0 if success else 1)
