"""GPU 显存计算模块

提供独立的显存需求计算工具，封装与 GPU 内存相关的所有计算逻辑，包括：
- 给定 batch_size 和目标地址数量时的显存需求估算
- 根据可用显存估算最大 batch_size
- 显存使用明细分解

不依赖具体的 GPU 设备对象，便于单元测试和复用。
"""

import logging
from ..utils import init_logging, get_configured_logger
from typing import Dict

logger = get_configured_logger("GPUMemoryCalculator")


class GPUMemoryCalculator:
    """GPU 显存计算器

    提供静态工具方法，用于估算 GPU 内核执行时的显存需求。

    内存布局（基于 PRNG 改造后的 OpenCL 内核实现）：
    - seed_buf（固定）:    32 字节（替代旧 num_keys * 32 私钥缓冲区）
    - 预计算表（固定）:    1984 字节（31×2×8 uint32 = 496×4 字节，G1..G31 affine）
    - 匹配标志缓冲区:      num_keys * 4 字节 (uint32)
    - 目标地址缓冲区:      num_targets * 20 字节 (HASH160_SIZE)
    - 执行临时开销:        上述缓冲区总和的 20%

    注意：PRNG 改造后私钥在 GPU 端由 seed+gid 生成，不再传输大型私钥缓冲区。
    """

    # ------------------------------------------------------------------
    # 常量定义
    # ------------------------------------------------------------------
    SEED_BUF_SIZE: int = 32      # PRNG 种子缓冲区（固定，不随 batch_size 变化）
    PRECOMP_TABLE_SIZE: int = 1984  # 预计算点表（31×2×8 uint32 = 496×4 字节，固定）
    PRIVATE_KEY_SIZE: int = 32   # 已弃用：PRNG 模式下私钥不再传输，保留仅供向后兼容
    HASH160_SIZE: int = 20       # Hash160（RIPEMD160(SHA256(pubkey))）字节数
    MATCH_FLAG_SIZE: int = 4     # 匹配标志（uint32）字节数
    KERNEL_OVERHEAD_RATIO: float = 0.20  # 内核执行临时显存开销比例（20%）

    BYTES_PER_MB: int = 1024 * 1024

    # ------------------------------------------------------------------
    # 公共静态方法
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_batch_memory(batch_size: int, num_targets: int) -> int:
        """计算给定 batch_size 和目标数的显存需求（字节）

        PRNG 模式：私钥在 GPU 端由 seed+gid 生成，host 仅传输 32 字节 seed_buf。

        Args:
            batch_size:   每批处理的私钥数量
            num_targets:  目标地址数量

        Returns:
            估算的显存需求（字节）
        """
        # 1. seed_buf（固定 32 字节，替代旧 batch_size * 32 私钥缓冲区）
        seed_buf_bytes = GPUMemoryCalculator.SEED_BUF_SIZE

        # 2. 预计算点表（固定 1984 字节）
        precomp_bytes = GPUMemoryCalculator.PRECOMP_TABLE_SIZE

        # 3. 匹配标志缓冲区
        match_flags_bytes = batch_size * GPUMemoryCalculator.MATCH_FLAG_SIZE

        # 4. 目标地址缓冲区
        targets_bytes = num_targets * GPUMemoryCalculator.HASH160_SIZE

        # 5. 内核执行临时开销（20%，仅对可变大小缓冲区计算）
        overhead_bytes = int(
            match_flags_bytes * GPUMemoryCalculator.KERNEL_OVERHEAD_RATIO
        )

        total_bytes = seed_buf_bytes + precomp_bytes + match_flags_bytes + targets_bytes + overhead_bytes
        return total_bytes

    @staticmethod
    def calculate_batch_memory_mb(batch_size: int, num_targets: int) -> float:
        """计算给定 batch_size 和目标数的显存需求（MB）

        Args:
            batch_size:   每批处理的私钥数量
            num_targets:  目标地址数量

        Returns:
            估算的显存需求（MB，浮点数）
        """
        total_bytes = GPUMemoryCalculator.calculate_batch_memory(batch_size, num_targets)
        return total_bytes / GPUMemoryCalculator.BYTES_PER_MB

    @staticmethod
    def estimate_max_batch_size(
        available_memory: int,
        num_targets: int,
        memory_ratio: float = 0.7
    ) -> int:
        """估算可用显存下的最大 batch_size

        Args:
            available_memory: 可用显存（字节）
            num_targets:      目标地址数量
            memory_ratio:     显存使用比例上限（默认 0.7，即使用 70%）

        Returns:
            估算的最大 batch_size（向下取整到 10000 的整数倍）
        """
        usable_memory = int(available_memory * memory_ratio)

        # 排除目标地址缓冲区固定占用
        targets_bytes = num_targets * GPUMemoryCalculator.HASH160_SIZE
        remaining = usable_memory - targets_bytes

        if remaining <= 0:
            logger.warning(
                f"可用显存 {available_memory / GPUMemoryCalculator.BYTES_PER_MB:.1f} MB "
                f"不足以容纳目标地址缓冲区 "
                f"{targets_bytes / GPUMemoryCalculator.BYTES_PER_MB:.1f} MB"
            )
            return 10_000  # 返回最小安全值

        # PRNG 模式：固定开销（seed_buf + precomp_table）先从可用显存中扣除
        fixed_bytes = GPUMemoryCalculator.SEED_BUF_SIZE + GPUMemoryCalculator.PRECOMP_TABLE_SIZE
        remaining -= fixed_bytes

        if remaining <= 0:
            logger.warning(
                f"可用显存扣除固定缓冲区后不足，使用最小 batch_size"
            )
            return 10_000

        # 每个 key 消耗的字节数（含 20% overhead，PRNG 模式下仅 match_flags）
        per_key_bytes = GPUMemoryCalculator.MATCH_FLAG_SIZE * (1 + GPUMemoryCalculator.KERNEL_OVERHEAD_RATIO)

        max_batch = int(remaining / per_key_bytes)

        # 向下取整到 10000 的整数倍，最小 10000
        max_batch = max(10_000, (max_batch // 10_000) * 10_000)

        logger.debug(
            f"显存估算: available={available_memory / GPUMemoryCalculator.BYTES_PER_MB:.1f}MB, "
            f"ratio={memory_ratio}, targets={num_targets}, "
            f"estimated_max_batch={max_batch}"
        )
        return max_batch

    @staticmethod
    def get_memory_breakdown(batch_size: int, num_targets: int) -> Dict[str, float]:
        """获取显存使用明细（MB）

        Args:
            batch_size:   每批处理的私钥数量
            num_targets:  目标地址数量

        Returns:
            显存使用明细字典，所有值单位为 MB：
            {
                'private_keys_mb':  私钥缓冲区占用,
                'match_flags_mb':   匹配标志缓冲区占用,
                'targets_mb':       目标地址缓冲区占用,
                'overhead_mb':      内核执行临时开销,
                'total_mb':         总计,
            }
        """
        bpMB = GPUMemoryCalculator.BYTES_PER_MB

        # PRNG 模式：固定缓冲区（seed_buf + precomp_table）
        seed_buf_bytes = GPUMemoryCalculator.SEED_BUF_SIZE
        precomp_bytes = GPUMemoryCalculator.PRECOMP_TABLE_SIZE
        match_flags_bytes = batch_size * GPUMemoryCalculator.MATCH_FLAG_SIZE
        targets_bytes = num_targets * GPUMemoryCalculator.HASH160_SIZE
        overhead_bytes = int(
            match_flags_bytes * GPUMemoryCalculator.KERNEL_OVERHEAD_RATIO
        )
        total_bytes = seed_buf_bytes + precomp_bytes + match_flags_bytes + targets_bytes + overhead_bytes

        breakdown = {
            'seed_buf_mb': seed_buf_bytes / bpMB,
            'precomp_table_mb': precomp_bytes / bpMB,
            'match_flags_mb': match_flags_bytes / bpMB,
            'targets_mb': targets_bytes / bpMB,
            'overhead_mb': overhead_bytes / bpMB,
            'total_mb': total_bytes / bpMB,
        }

        logger.debug(
            f"GPU显存估算(PRNG模式): seed_buf={breakdown['seed_buf_mb']:.4f}MB, "
            f"precomp={breakdown['precomp_table_mb']:.4f}MB, "
            f"match_flags={breakdown['match_flags_mb']:.2f}MB, "
            f"targets={breakdown['targets_mb']:.2f}MB, "
            f"overhead={breakdown['overhead_mb']:.2f}MB, "
            f"total={breakdown['total_mb']:.2f}MB"
        )

        return breakdown

    @staticmethod
    def calculate_from_hash160_bytes(
        num_keys: int,
        hash160_bytes: bytes
    ) -> float:
        """根据 hash160 字节串计算显存需求（MB）

        与 GPUCollisionEngine._calculate_gpu_memory_usage 保持一致的计算逻辑：
        目标缓冲区大小取 hash160_bytes 的实际字节长度（而非 num_targets * 20）。

        Args:
            num_keys:       私钥数量（即 batch_size）
            hash160_bytes:  已拼接好的目标 Hash160 字节串（可为 None）

        Returns:
            显存需求（MB，浮点数）
        """
        bpMB = GPUMemoryCalculator.BYTES_PER_MB

        # PRNG 模式：seed_buf（固定32字节）+ precomp_table（固定1984字节）+ match_flags（可变）
        seed_buf_mb = GPUMemoryCalculator.SEED_BUF_SIZE / bpMB
        precomp_mb = GPUMemoryCalculator.PRECOMP_TABLE_SIZE / bpMB
        match_flags_mb = (num_keys * GPUMemoryCalculator.MATCH_FLAG_SIZE) / bpMB
        targets_mb = len(hash160_bytes) / bpMB if hash160_bytes else 0.0
        overhead_mb = match_flags_mb * GPUMemoryCalculator.KERNEL_OVERHEAD_RATIO

        total_mb = seed_buf_mb + precomp_mb + match_flags_mb + targets_mb + overhead_mb

        logger.debug(
            f"GPU显存估算(PRNG模式): seed_buf={seed_buf_mb:.4f}MB, "
            f"precomp={precomp_mb:.4f}MB, "
            f"match_flags={match_flags_mb:.2f}MB, "
            f"targets={targets_mb:.2f}MB, "
            f"overhead={overhead_mb:.2f}MB, "
            f"total={total_mb:.2f}MB"
        )

        return total_mb
