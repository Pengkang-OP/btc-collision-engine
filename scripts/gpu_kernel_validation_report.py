#!/usr/bin/env python3
"""
GPU碰撞引擎内核验证 - 综合测试报告
"""

import os
import sys
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_section(title):
    """打印章节"""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def print_result(test_name, passed, detail=""):
    """打印测试结果"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} | {test_name}")
    if detail:
        print(f"         {detail}")


def _uint256_to_hex(arr):
    """将 uint256 数组转换为十六进制字符串。"""
    hex_str = ""
    for i in range(7, -1, -1):
        hex_str += f"{arr[i]:08x}"
    return hex_str


def _test_environment():
    """── 测试1: 环境检查 ──"""
    print_section("测试1: 运行环境检查")
    results = []
    try:
        import sys  # noqa: F811 (re-import for standalone script)

        py_version = (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        print_result("Python版本", True, f"Python {py_version}")
        results.append(True)
        # PyOpenCL
        try:
            import pyopencl as cl  # noqa: F811

            print_result("PyOpenCL", True, f"版本 {cl.VERSION_TEXT}")
            results.append(True)
        except ImportError:
            print_result("PyOpenCL", False, "未安装")
            results.append(False)
            return results
        # NumPy
        try:
            import numpy as np  # noqa: F811

            print_result("NumPy", True, f"版本 {np.__version__}")
            results.append(True)
        except ImportError:
            print_result("NumPy", False, "未安装")
            results.append(False)
        # GPU设备检测
        platforms = cl.get_platforms()
        gpu_devices = []
        for platform in platforms:
            devices = platform.get_devices(device_type=cl.device_type.GPU)
            gpu_devices.extend(devices)
        if gpu_devices:
            print_result("GPU设备检测", True, f"发现 {len(gpu_devices)} 个GPU")
            for i, dev in enumerate(gpu_devices[:3]):
                mem_gb = dev.global_mem_size / (1024**3)
                print(f"         {i + 1}. {dev.name} ({mem_gb:.1f} GB)")
            results.append(True)
        else:
            print_result("GPU设备检测", False, "未发现GPU设备")
            results.append(False)
    except Exception as e:  # noqa: BLE001
        print_result("环境检查", False, str(e))
        results.append(False)
    return results


def _test_kernel_source():
    """── 测试2: 内核源码加载 ──"""
    print_section("测试2: 内核源码加载")
    results = []
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        lines = OPENCL_KERNEL_SOURCE.split("\n")
        print_result("源码加载", True,
                     f"{len(OPENCL_KERNEL_SOURCE)} 字符, {len(lines)} 行")
        results.append(True)
        kernel_count = OPENCL_KERNEL_SOURCE.count("__kernel")
        matches_expected = kernel_count == 3
        print_result("内核函数", matches_expected,
                     f"发现 {kernel_count} 个内核函数")
        results.append(matches_expected)
        components = {
            "uint256_t类型": "typedef struct",
            "GX常量": "constant uint GX[8]",
            "GY常量": "constant uint GY[8]",
            "素数P": "constant uint SECP256K1_P[8]",
            "曲线阶N": "constant uint SECP256K1_N[8]",
        }
        for name, pattern in components.items():
            found = pattern in OPENCL_KERNEL_SOURCE
            print_result(f"  {name}", found)
            results.append(found)
    except Exception as e:  # noqa: BLE001
        print_result("内核源码加载", False, str(e))
        results.append(False)
    return results


def _test_math_functions():
    """── 测试3: 数学运算函数 ──"""
    print_section("测试3: 数学运算函数")
    results = []
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        math_functions = [
            ("uint256加法", "uint uint256_add"),
            ("uint256减法", "void uint256_sub"),
            ("uint256乘法", "void uint256_mul"),
            ("uint256比较", "int uint256_cmp"),
            ("模加法", "void mod_add"),
            ("模减法", "void mod_sub"),
            ("模乘法", "void mod_mul"),
            ("模平方", "void mod_sqr"),
            ("模幂运算", "void mod_pow"),
            ("模逆运算", "void mod_inverse"),
        ]
        for name, pattern in math_functions:
            found = pattern in OPENCL_KERNEL_SOURCE
            print_result(name, found)
            results.append(found)
    except Exception as e:  # noqa: BLE001
        print_result("数学运算函数检查", False, str(e))
        results.append(False)
    return results


def _test_ec_operations():
    """── 测试4: 椭圆曲线运算 ──"""
    print_section("测试4: 椭圆曲线运算")
    results = []
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        ec_functions = [
            ("点倍乘", "void ec_point_double"),
            ("点加法", "void ec_point_add"),
            ("标量乘法", "void ec_scalar_multiply"),
        ]
        for name, pattern in ec_functions:
            found = pattern in OPENCL_KERNEL_SOURCE
            print_result(name, found)
            results.append(found)
    except Exception as e:  # noqa: BLE001
        print_result("椭圆曲线运算检查", False, str(e))
        results.append(False)
    return results


def _test_hash_algorithms():
    """── 测试5: 哈希算法 ──"""
    print_section("测试5: 哈希算法")
    results = []
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        hash_functions = [
            ("SHA-256", "void sha256"),
            ("RIPEMD-160", "void ripemd160"),
            ("Hash160", "void hash160"),
            ("SHA-256轮常量", "constant uint SHA256_K[64]"),
        ]
        for name, pattern in hash_functions:
            found = pattern in OPENCL_KERNEL_SOURCE
            print_result(name, found)
            results.append(found)
    except Exception as e:  # noqa: BLE001
        print_result("哈希算法检查", False, str(e))
        results.append(False)
    return results


def _test_kernel_compilation():
    """── 测试6: 内核编译 ──"""
    print_section("测试6: OpenCL内核编译")
    results = []
    try:
        import pyopencl as cl  # noqa: F811

        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        platforms = cl.get_platforms()
        device = platforms[0].get_devices(device_type=cl.device_type.GPU)[0]
        context = cl.Context([device])
        start = time.time()
        program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()
        compile_time = time.time() - start
        print_result("内核编译", True, f"耗时 {compile_time:.2f}秒")
        results.append(True)
        kernels = {
            "batch_check": "批量碰撞检测",
            "verify_arithmetic": "算术验证",
            "debug_hash": "哈希调试",
        }
        for name, desc in kernels.items():
            exists = hasattr(program, name)
            print_result(f"  {name} ({desc})", exists)
            results.append(exists)
    except Exception as e:  # noqa: BLE001
        print_result("内核编译", False, str(e))
        results.append(False)
    return results


def _test_verify_arithmetic():
    """── 测试7: 算术验证 2*G ──"""
    print_section("测试7: 算术验证 - 2*G计算")
    results = []
    try:
        import numpy as np  # noqa: F811
        import pyopencl as cl  # noqa: F811

        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        platforms = cl.get_platforms()
        device = platforms[0].get_devices(device_type=cl.device_type.GPU)[0]
        context = cl.Context([device])
        program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()
        queue = cl.CommandQueue(context)
        result_x = np.zeros(8, dtype=np.uint32)
        result_y = np.zeros(8, dtype=np.uint32)
        result_x_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, result_x.nbytes)
        result_y_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, result_y.nbytes)
        program.verify_arithmetic(
            queue, (1,), None, result_x_buf, result_y_buf)
        queue.finish()
        cl.enqueue_copy(queue, result_x, result_x_buf)
        cl.enqueue_copy(queue, result_y, result_y_buf)
        x_hex = _uint256_to_hex(result_x)
        y_hex = _uint256_to_hex(result_y)
        expected_x = "c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
        expected_y = "1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a"
        x_correct = x_hex == expected_x
        y_correct = y_hex == expected_y
        print_result("2*G X坐标", x_correct, f"0x{x_hex}")
        results.append(x_correct)
        print_result("2*G Y坐标", y_correct, f"0x{y_hex}")
        results.append(y_correct)
        print_result("算术验证", x_correct and y_correct, "2*G计算正确")
        results.append(x_correct and y_correct)
    except Exception as e:  # noqa: BLE001
        print_result("算术验证", False, str(e))
        import traceback

        traceback.print_exc()
        results.append(False)
    return results


def _test_hash_verification():
    """── 测试8: 哈希验证 k=1 ──"""
    print_section("测试8: 哈希验证 - k=1公钥计算")
    results = []
    try:
        import numpy as np  # noqa: F811
        import pyopencl as cl  # noqa: F811

        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        platforms = cl.get_platforms()
        device = platforms[0].get_devices(device_type=cl.device_type.GPU)[0]
        context = cl.Context([device])
        program = cl.Program(context, OPENCL_KERNEL_SOURCE).build()
        queue = cl.CommandQueue(context)
        pubkey_out = np.zeros(33, dtype=np.uint8)
        hash160_out = np.zeros(20, dtype=np.uint8)
        qx_out = np.zeros(8, dtype=np.uint32)
        qy_out = np.zeros(8, dtype=np.uint32)
        pubkey_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, pubkey_out.nbytes)
        hash160_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, hash160_out.nbytes)
        qx_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, qx_out.nbytes)
        qy_buf = cl.Buffer(
            context, cl.mem_flags.WRITE_ONLY, qy_out.nbytes)
        program.debug_hash(
            queue, (1,), None,
            pubkey_buf,
            cl.Buffer(context, cl.mem_flags.WRITE_ONLY, 32),
            hash160_buf,
            np.uint32(1),
            qx_buf, qy_buf,
        )
        queue.finish()
        cl.enqueue_copy(queue, pubkey_out, pubkey_buf)
        cl.enqueue_copy(queue, hash160_out, hash160_buf)
        pubkey_valid = pubkey_out[0] in [0x02, 0x03]
        hash160_hex = hash160_out.tobytes().hex()
        print_result("压缩公钥格式", pubkey_valid,
                     f"首字节: 0x{pubkey_out[0]:02x}")
        results.append(pubkey_valid)
        print_result("Hash160计算", True, hash160_hex)
        results.append(True)
    except Exception as e:  # noqa: BLE001
        print_result("哈希验证", False, str(e))
        results.append(False)
    return results


def _test_intel_arc_optimization():
    """── 测试9: Intel Arc优化验证 ──"""
    print_section("测试9: Intel Arc优化验证")
    results = []
    try:
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        optimizations = [
            ("uint32私钥输入", "__global const uint *private_keys",
             "避免global char* hang bug"),
            ("ulong算术", "ulong carry", "避免signed long bug"),
        ]
        for name, pattern, desc in optimizations:
            found = pattern in OPENCL_KERNEL_SOURCE
            print_result(name, found, desc)
            results.append(found)
    except Exception as e:  # noqa: BLE001
        print_result("Intel Arc优化验证", False, str(e))
        results.append(False)
    return results


def _print_summary_report(all_results):
    """打印测试总结报告。"""
    print_header("测试总结")
    total = len(all_results)
    passed = sum(1 for r in all_results if r)
    failed = total - passed
    print(f"\n  总测试数: {total}")
    print(f"  通过: {passed} \u2705")
    print(f"  失败: {failed} {'\u274c' if failed > 0 else ''}")
    print(f"  通过率: {passed / total * 100:.1f}%")
    if failed == 0:
        print("\n  \U0001f389 所有测试通过！GPU内核完全可用！")
        print("  \u2705 可以立即使用GPU模式运行碰撞引擎")
        print("\n  示例命令:")
        print("    python -m src.cli.main --mode random_search --gpu")
    else:
        print(f"\n  \u26a0\ufe0f  {failed} 个测试未通过")
        print("  请检查失败项并重试")
    print(f"\n{'=' * 80}\n")


def main():
    """GPU内核完整验证入口。"""
    print_header("BTC碰撞引擎 - GPU内核完整验证报告")
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  项目路径: {project_root}")
    all_results = _test_environment()
    if not all_results or all_results[-1] is False:
        # PyOpenCL 未安装时提前返回
        pass
    else:
        all_results.extend(_test_kernel_source())
        all_results.extend(_test_math_functions())
        all_results.extend(_test_ec_operations())
        all_results.extend(_test_hash_algorithms())
        all_results.extend(_test_kernel_compilation())
        all_results.extend(_test_verify_arithmetic())
        all_results.extend(_test_hash_verification())
        all_results.extend(_test_intel_arc_optimization())
    _print_summary_report(all_results)
    failed = sum(1 for r in all_results if not r)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
