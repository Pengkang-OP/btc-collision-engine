"""P1-3 修复验证：GPU内核 batch_check k>=N 验证

验证要点：
1. batch_check 内核包含 uint256_cmp(&k, &n_val) >= 0 检查
2. batch_check_local_mem 内核包含同样的检查
3. SECP256K1_N 常量被正确使用
4. .cl 文件和 kernel.py 保持同步
"""

import unittest

from src.gpu.kernel import OPENCL_KERNEL_SOURCE


class TestP1_3_KeyRangeValidation:
    """P1-3: GPU 内核 k>=N 范围验证"""

    def test_kernel_source_contains_n_check_batch_check(self):
        """P1-3-A: batch_check 包含 k >= N 验证"""
        source = OPENCL_KERNEL_SOURCE

        # 检查包含 SECP256K1_N 的使用
        assert source in "SECP256K1_N", "内核源码中应使用 SECP256K1_N 常量"

        # 检查包含 uint256_cmp 与 N 的比较
        assert source in "uint256_cmp(&k, &n_val) >= 0", "batch_check 应使用 uint256_cmp 检查 k >= N"

        # 检查 uint256_is_zero 和 k>=N 在同一条件中
        assert source in "uint256_is_zero(&k) || uint256_cmp(&k, &n_val) >= 0", "应组合检查 k==0 和 k>=N"

        print("\n[P1-3-A ✓] batch_check: k>=N 验证代码存在")

    def test_kernel_source_no_old_k_zero_only(self):
        """P1-3-B: 确认旧代码（仅检查k==0）已被替换"""
        source = OPENCL_KERNEL_SOURCE

        lines = source.split("\n")

        # 寻找所有包含 "uint256_is_zero(&k)" 的行及其上下文
        for i, line in enumerate(lines):
            if "uint256_is_zero(&k)" in line:
                # 获取上下文（前后各2行）
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                context = "\n".join(lines[start:end])  # noqa: F841

                # 确认它不是单独的条件（应该包含 || uint256_cmp）
                stripped = line.strip()
                # 如果包含了 || 则新的正确格式
                # 如果只有 uint256_is_zero 没有 ||，则是旧代码
                if (
                    "uint256_is_zero(&k)" in stripped
                    and "||" not in stripped
                    and i + 1 < len(lines)
                    and "||" not in lines[i + 1]
                ):
                    # 可能是旧代码，但可能是注释
                    pass  # 在下面的检查中处理

        # 直接检查：确保旧的条件语句模式已被移除
        # 旧模式: "if (uint256_is_zero(&k)) {" (独占条件)
        import re

        old_pattern = re.findall(r"if\s*\(\s*uint256_is_zero\(&k\)\s*\)\s*\{", source)

        assert len(old_pattern) == 0, f"旧代码 'if (uint256_is_zero(&k)) {{{{' 应已被替换，但仍找到 {len(old_pattern)} 处"  # noqa: E501

        print("\n[P1-3-B ✓] 旧独占条件已全部替换")

    def test_n_val_loaded_from_constant(self):
        """P1-3-C: n_val 从 SECP256K1_N 常量正确加载"""
        source = OPENCL_KERNEL_SOURCE

        # 检查 n_val 的声明和加载
        assert source in "uint256_t n_val;", "应声明 n_val 局部变量"

        assert source in "n_val.d[i] = SECP256K1_N[i]", "应从 SECP256K1_N 常量加载 N 值"

        # 应该有循环加载
        import re

        load_loops = re.findall(
            r"for\s*\(\s*int\s+i\s*=\s*0\s*;\s*i\s*<\s*8\s*;\s*i\+\+\s*\)\s*n_val\.d\[i\]\s*=\s*SECP256K1_N\[i\]",  # noqa: E501
            source,
        )
        # 应该有4处（kernel.py和.cl各两个内核）
        assert len(load_loops) >= 2, f"不应少于2处N值加载循环，找到{len(load_loops)}处"

        print(f"\n[P1-3-C ✓] n_val加载正确 (找到{len(load_loops)}处)")

    def test_both_kernel_variants_fixed(self):
        """P1-3-D: batch_check 和 batch_check_local_mem 均已修复"""
        source = OPENCL_KERNEL_SOURCE

        # 找出所有 __kernel void 的定义
        import re

        kernels = re.findall(r"__kernel\s+void\s+(\w+)", source)

        assert kernels in "batch_check"
        assert kernels in "batch_check_local_mem"

        # 对于每个包含 batch_check 的内核，检查是否都有 N 验证
        # 通过在 batch_check 之后到下一个 __kernel 之间搜索
        for kernel_name in ["batch_check", "batch_check_local_mem"]:
            kernel_pos = source.find(f"__kernel void {kernel_name}")
            if kernel_pos >= 0:
                # 找下一个 __kernel 的位置
                next_kernel = source.find("__kernel void", kernel_pos + 1)
                if next_kernel < 0:
                    next_kernel = len(source)

                kernel_body = source[kernel_pos:next_kernel]

                assert kernel_body in "uint256_cmp(&k, &n_val) >= 0", f"{kernel_name} 内核应包含 k>=N 验证"

                assert kernel_body in "SECP256K1_N", f"{kernel_name} 内核应引用 SECP256K1_N"

                print(f"  [{kernel_name}] ✓ k>=N 验证存在")

        print("\n[P1-3-D ✓] 所有batch_check变体均已修复")

    def test_n_boundary_values(self):
        """P1-3-F: 验证 N 常量值正确性"""
        source = OPENCL_KERNEL_SOURCE

        # 提取 SECP256K1_N 的值
        import re

        n_match = re.search(r"SECP256K1_N\[8\]\s*=\s*\{([^}]+)\}", source)
        assert n_match is not None, "未找到 SECP256K1_N 定义"

        n_values_str = n_match.group(1)
        n_values = [int(x.strip(), 0) for x in n_values_str.split(",")]

        # 验证 SECP256K1_N 的值
        expected_n = [
            0xD0364141,
            0xBFD25E8C,
            0xAF48A03B,
            0xBAAEDCE6,
            0xFFFFFFFE,
            0xFFFFFFFF,
            0xFFFFFFFF,
            0xFFFFFFFF,
        ]

        assert len(n_values) == 8, f"N应有8个值，实际{len(n_values)}"

        for i, (actual, expected) in enumerate(zip(n_values, expected_n, strict=False)):
            assert actual == expected, f"N[{i}] = {hex(actual)} 不等于预期 {hex(expected)}"

        print("\n[P1-3-F ✓] SECP256K1_N 常量值正确")


if __name__ == "__main__":
    unittest.main(verbosity=2)
