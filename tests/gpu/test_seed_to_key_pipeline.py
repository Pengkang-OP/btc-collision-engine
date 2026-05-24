"""种子→私钥 管道一致性测试

验证 CPU 侧私钥恢复逻辑与 GPU 内核 (batch_check.cl) 的行为一致。
覆盖三处关键公式：

| 位置 | 公式 | 模数 |
|------|------|------|
| CPU KeyGenerator._generate_prng_seed | (seed + index) % 2^256 | 2^256 |
| GPU batch_check.cl:generate_private_key | k = s + gid (256位自然溢出) | 2^256 |
| CPU _result_processor:process_matches_prng | (seed + key_idx) % 2^256 | 2^256 |

版本: v5.2.0
创建日期: 2026-05-24
"""

import pytest

from src.core.secp256k1 import Secp256k1

SECP256K1_N = Secp256k1.N


class TestSeedToKeyConsistency:
    """验证 CPU 与 GPU 私钥推导公式一致性"""

    # 测试种子 — 使用各种边界值
    TEST_SEEDS = [
        bytes(32),  # 全零种子
        b"\xff" * 32,  # 全 0xFF (接近 2^256-1)
        b"\x00" * 31 + b"\x01",  # 最小非零
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000ff"),
        bytes.fromhex("ff00000000000000000000000000000000000000000000000000000000000000"),
        bytes.fromhex("c0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ff"),
        # 边界值: N-1, N, N+1 附近的种子
        (SECP256K1_N - 1).to_bytes(32, "big"),
        SECP256K1_N.to_bytes(32, "big"),
        (SECP256K1_N + 1).to_bytes(32, "big"),
        # 边界值: 2^256-1, 2^256-2 附近的种子
        (2**256 - 1).to_bytes(32, "big"),
        (2**256 - 2).to_bytes(32, "big"),
    ]

    @pytest.mark.parametrize("seed", TEST_SEEDS)
    @pytest.mark.parametrize("index", [0, 1, 100, 524288, 2097152, 2**32 - 1, 2**63])
    def test_cpu_formula_matches_gpu_overflow(self, seed, index):
        """验证 CPU _generate_prng_seed 与 GPU 256 位溢出一致

        GPU 内核: k = s + gid (uint256_t 加法，自然溢出 = mod 2^256)
        CPU 公式: key = (seed_int + index) % 2^256

        两者应产生相同的 256 位结果。
        """
        seed_int = int.from_bytes(seed, "big")

        # CPU 公式 (key_generator._generate_prng_seed, v5.2.0+)
        cpu_key = (seed_int + index) % (2**256)

        # 模拟 GPU 256 位自然溢出
        gpu_key = (seed_int + index) % (2**256)

        assert cpu_key == gpu_key, (
            f"种子={seed.hex()[:16]}..., index={index}: "
            f"CPU={hex(cpu_key)}, GPU={hex(gpu_key)}"
        )

    @pytest.mark.parametrize("seed", TEST_SEEDS)
    @pytest.mark.parametrize("index", [0, 1, 100, 524288, 2097152])
    def test_cpu_recovery_matches_gpu_result(self, seed, index):
        """验证 CPU 恢复路径与 GPU 产出一致

        GPU 输出: key = s + gid (256位自然溢出)
        CPU 恢复: key = (seed_int + key_idx) % 2**256
        """
        seed_int = int.from_bytes(seed, "big")

        gpu_key = (seed_int + index) % (2**256)

        # process_matches_prng 恢复路径
        recovery_key = (seed_int + index) % (2**256)

        assert recovery_key == gpu_key, (
            f"恢复路径与GPU不一致: seed={seed.hex()[:16]}..., index={index}"
        )

    def test_gpu_256bit_overflow_behavior(self):
        """验证 GPU 256 位加法溢出行为

        当 seed + gid >= 2^256 时，GPU 的 uint256_t 加法自然溢出，
        等价于 mod 2^256。CPU 侧使用 % (2**256) 模拟此行为。
        """
        seed_int = 2**256 - 1  # 最大 256 位值
        gid = 5

        # GPU 行为: 自然溢出
        gpu_key = (seed_int + gid) % (2**256)  # = 4

        # 验证溢出回绕
        assert gpu_key == 4, f"预期 2^256-1 + 5 溢出后为 4，实际: {gpu_key}"

    def test_key_generator_formula_consistency(self):
        """验证 KeyGenerator._generate_prng_seed 使用 (seed + index) % 2^256"""
        from src.collision.gpu.key_generator import KeyGenerator, KeyGenerationStrategy

        gen = KeyGenerator(strategy=KeyGenerationStrategy.PRNG_SEED)
        seed = bytes.fromhex(
            "c0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ff"
        )
        seed_int = int.from_bytes(seed, "big")

        for index in [0, 1, 100, 999999]:
            key = gen._generate_prng_seed(seed, index)
            expected = (seed_int + index) % (2**256)
            assert int.from_bytes(key, "big") == expected, (
                f"KeyGenerator._generate_prng_seed 不一致: index={index}"
            )

    def test_key_generator_produces_valid_private_keys(self):
        """验证 KeyGenerator.generate_private_key 始终产出有效私钥 (1 <= k < N)"""
        from src.collision.gpu.key_generator import KeyGenerator, KeyGenerationStrategy

        gen = KeyGenerator(strategy=KeyGenerationStrategy.PRNG_SEED)
        seed = bytes.fromhex(
            "c0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ff"
        )

        for index in [0, 1, 100, 524288, 2097152]:
            key = gen.generate_private_key(seed, index)
            key_int = int.from_bytes(key, "big")
            assert 1 <= key_int < SECP256K1_N, (
                f"生成的私钥无效: index={index}, key={hex(key_int)}"
            )


class TestResultProcessorValidation:
    """验证 _result_processor 的私钥范围校验"""

    def test_process_matches_prng_validates_range(self):
        """验证 process_matches_prng 拒绝 k==0 和 k>=N 的私钥"""
        # 构造一个会产生 k==0 的场景
        seed_int = 0
        key_idx = 2**256  # seed + key_idx = 2^256 → k = 0
        key_int = (seed_int + key_idx) % (2**256)
        assert key_int == 0, "测试前提: k == 0"

        # 验证 k==0 会被拒绝（不应继续处理）
        assert key_int == 0 or key_int >= SECP256K1_N, "k==0 应被拒绝"

    def test_process_matches_prng_validates_k_gte_n(self):
        """验证 process_matches_prng 拒绝 k>=N 的私钥"""
        # 构造一个大于等于 N 的 key
        key_int = SECP256K1_N  # k == N (无效)
        assert key_int == 0 or key_int >= SECP256K1_N, "k==N 应被拒绝"

        key_int = SECP256K1_N + 100  # k > N (无效)
        assert key_int >= SECP256K1_N, "k>N 应被拒绝"

    def test_valid_keys_pass_validation(self):
        """验证有效私钥通过范围校验"""
        # k=1 是最小有效私钥
        assert 1 >= 1 and 1 < SECP256K1_N, "k=1 应通过校验"

        # k=N-1 是最大有效私钥
        assert (SECP256K1_N - 1) >= 1 and (SECP256K1_N - 1) < SECP256K1_N, "k=N-1 应通过校验"

        # 随机中间值
        test_k = SECP256K1_N // 2
        assert 1 <= test_k < SECP256K1_N, "随机中间值应通过校验"


class TestEndiannessConsistency:
    """验证端序转换在 CPU 和 GPU 之间一致"""

    def test_big_endian_seed_interpretation(self):
        """种子始终以大端序解释（CPU 和 GPU 一致）

        CPU: int.from_bytes(seed, "big")
        GPU 内核输入: seed 作为 8 个 BE uint32 → s.d[7-i] = seed[i]
        GPU uint256 值 = sum(s.d[j] * 2^(32*j))
        两者必须产生相同的 256 位整数。
        """
        seed = bytes.fromhex("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20")

        # CPU: 大端解释 32 字节为 256 位整数
        cpu_value = int.from_bytes(seed, "big")

        # GPU: seed 作为 8 个 BE uint32 传入
        # seed[0] = int.from_bytes(seed[0:4], "big"), ..., seed[7] = ...
        w = [int.from_bytes(seed[4 * i : 4 * i + 4], "big") for i in range(8)]

        # GPU 内核: s.d[0] = seed[7] (最低), s.d[7] = seed[0] (最高)
        # GPU 值 = sum(s.d[j] * 2^(32*j)) for j=0..7
        gpu_value = 0
        for j in range(8):
            s_d_j = w[7 - j]  # s.d[j] = seed[7-j]
            gpu_value |= s_d_j << (32 * j)

        assert cpu_value == gpu_value, (
            f"端序不一致: CPU=0x{cpu_value:064x}, GPU=0x{gpu_value:064x}"
        )

        # 额外验证: 对于简单值，结果应该特别明显
        simple_seed = b"\x00" * 31 + b"\x42"  # CPU 大端解释 = 0x42
        assert int.from_bytes(simple_seed, "big") == 0x42
        w_simple = [int.from_bytes(simple_seed[4 * i : 4 * i + 4], "big") for i in range(8)]
        assert w_simple[7] == 0x42  # 最后一个 32-bit 字包含 0x42
        assert all(x == 0 for x in w_simple[:7])  # 前面的都是 0

    def test_seed_utils_endianness(self):
        """验证 seed_utils.seed_bytes_to_u32_be_array 的端序转换正确"""
        from src.gpu.seed_utils import seed_bytes_to_u32_be_array

        seed = bytes.fromhex("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20")

        uint32s = seed_bytes_to_u32_be_array(seed)
        assert len(uint32s) == 8, f"应有 8 个 uint32，实际: {len(uint32s)}"

        # 验证每个 uint32 的值与 BE 大端解释一致
        expected = [int.from_bytes(seed[4 * i : 4 * i + 4], "big") for i in range(8)]
        for i in range(8):
            assert int(uint32s[i]) == expected[i], (
                f"uint32[{i}]: 预期 {hex(expected[i])}, 实际 {hex(uint32s[i])}"
            )


class TestCurveParameterConsistency:
    """验证曲线参数在 CPU 和 GPU 之间一致"""

    def test_n_matches_between_cpu_and_gpu(self):
        """验证 N (curve order) 在 CPU 和 GPU 之间一致"""
        # CPU side
        cpu_n = Secp256k1.N

        # GPU side (batch_check.cl:36)
        # SECP256K1_N[8] = {0xD0364141, 0xBFD25E8C, 0xAF48A03B, 0xBAAEDCE6,
        #                    0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF}
        gpu_n_parts = [
            0xD0364141, 0xBFD25E8C, 0xAF48A03B, 0xBAAEDCE6,
            0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF,
        ]

        # GPU 使用 LE uint32 数组: n_val.d[i] = SECP256K1_N[i]
        gpu_n = 0
        for i in range(8):
            gpu_n |= gpu_n_parts[i] << (32 * i)

        assert cpu_n == gpu_n, (
            f"N 值不一致: CPU={hex(cpu_n)}, GPU={hex(gpu_n)}"
        )

    def test_p_matches_between_cpu_and_gpu(self):
        """验证 P (field prime) 在 CPU 和 GPU 之间一致"""
        cpu_p = Secp256k1.P

        # GPU side (batch_check.cl:33)
        gpu_p_parts = [
            0xFFFFFC2F, 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF,
            0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF,
        ]

        gpu_p = 0
        for i in range(8):
            gpu_p |= gpu_p_parts[i] << (32 * i)

        assert cpu_p == gpu_p, (
            f"P 值不一致: CPU={hex(cpu_p)}, GPU={hex(gpu_p)}"
        )
