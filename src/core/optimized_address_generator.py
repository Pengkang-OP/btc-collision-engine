"""优化版P2PKH地址生成器 - 集成性能优化模块

继承自 BaseAddressGenerator，添加预计算表/SIMD/内存池优化。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base58 import Base58
from .hash_utils import HashUtils
from .memory_pool import get_pool_manager
from .precomputed_table import get_precomputed_table
from .secp256k1 import ECPoint, Secp256k1
from .simd_hash import get_simd_hash_optimizer

if TYPE_CHECKING:
    from .memory_pool import ECPointPool
    from .precomputed_table import PrecomputedPointTable
    from .simd_hash import SIMDHashOptimizer

# 导入日志配置
from ..utils import get_configured_logger
from .address_generator import BaseAddressGenerator

<<<<<<< Updated upstream
# 日志系统由CLI/main.py入口统一初始化
=======
# 获取模块日志记录器
>>>>>>> Stashed changes
logger = get_configured_logger("OptimizedAddressGenerator")


class OptimizedP2PKHAddressGenerator(BaseAddressGenerator):
    """优化版P2PKH地址生成器

    集成以下优化:
    1. 预计算点表 - 标量乘法加速50-70%
    2. SIMD哈希优化 - SHA256/RIPEMD160加速
    3. ECPoint内存池 - 减少对象分配开销
    4. 批量处理支持 - 提升吞吐量

    使用示例:
        generator = OptimizedP2PKHAddressGenerator()
        address = generator.generate_from_private_key(private_key_bytes)

        # 批量生成
        addresses = generator.batch_generate(private_keys_list)
    """

    def __init__(
        self,
        use_precomputed_table: bool = True,
        use_simd_hash: bool = True,
        use_memory_pool: bool = True,
        window_size: int = 8,
    ) -> None:
        """
        初始化优化版地址生成器

        Args:
            use_precomputed_table: 使用预计算点表
            use_simd_hash: 使用SIMD哈希优化
            use_memory_pool: 使用内存池
            window_size: 预计算表窗口大小(4-8)
        """
        super().__init__()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

        # 优化模块
        self.use_precomputed_table = use_precomputed_table
        self.use_simd_hash = use_simd_hash
        self.use_memory_pool = use_memory_pool

        # 初始化预计算表
        self.precomputed_table: PrecomputedPointTable | None = None
        if use_precomputed_table:
            self.precomputed_table = get_precomputed_table(window_size=window_size)
            logger.info(f"预计算点表已启用: window_size={window_size}")
        else:
            logger.info("预计算点表未启用,使用标准标量乘法")

        # 初始化SIMD哈希优化器
        self.simd_optimizer: SIMDHashOptimizer | None = None
        if use_simd_hash:
            self.simd_optimizer = get_simd_hash_optimizer()
            logger.info(f"SIMD哈希优化已启用: {self.simd_optimizer.get_backend_name()}")
        else:
            pass

        # 初始化内存池
        self.ecpoint_pool: ECPointPool | None = None
        if use_memory_pool:
            self.pool_manager = get_pool_manager()
            self.pool_manager.initialize()
            self.ecpoint_pool = self.pool_manager.get_ecpoint_pool()
            logger.info("ECPoint内存池已启用")
        else:
            logger.info("ECPoint内存池未启用")

        logger.info("OptimizedP2PKHAddressGenerator初始化完成")

    def private_key_to_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """
        私钥推导公钥(优化版)

        Args:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        Returns:
            公钥字节(33字节压缩或65字节未压缩)
        """
        k = int.from_bytes(private_key, "big")

        # 使用预计算表或标准方法
        if self.use_precomputed_table and self.precomputed_table:
            point = self.precomputed_table.scalar_multiply_with_table(k, self.ec)
        else:
<<<<<<< Updated upstream
=======
            # v4.2.2 C1-regression修复: 使用恒定时间实现
>>>>>>> Stashed changes
            point = self.ec.scalar_multiply_const_time(k, self.G)

        # 压缩或未压缩格式
        if compressed:
            # 压缩公钥: 0x02/0x03 + X坐标
            prefix = b"\x02" if point.y % 2 == 0 else b"\x03"
            return prefix + point.x.to_bytes(32, "big")
        else:
            # 未压缩公钥: 0x04 + X坐标 + Y坐标
            return b"\x04" + point.x.to_bytes(32, "big") + point.y.to_bytes(32, "big")

    def public_key_to_hash160(self, public_key: bytes) -> bytes:
        """
        公钥计算 Hash160 (SIMD优化路径，跳过 Base58Check 编码)

        用于碰撞引擎热路径上的快速匹配检测，仅返回 20 字节 Hash160。

        Args:
            public_key: 公钥字节

        Returns:
            20字节 Hash160 值
        """
        if self.use_simd_hash and self.simd_optimizer:
            sha256_result = self.simd_optimizer.batch_sha256([public_key])[0]
            ripemd160_result = self.simd_optimizer.batch_ripemd160([sha256_result])[0]
            return ripemd160_result
        else:
            return super().public_key_to_hash160(public_key)

    def public_key_to_address(self, public_key: bytes) -> str:
        """
        公钥生成地址(SIMD优化路径)

        Args:
            public_key: 公钥字节

        Returns:
            Base58编码的P2PKH地址
        """
        # SHA256(RIPEMD160(SHA256(public_key)))
        if self.use_simd_hash and self.simd_optimizer:
            sha256_result = self.simd_optimizer.batch_sha256([public_key])[0]
            ripemd160_result = self.simd_optimizer.batch_ripemd160([sha256_result])[0]
            # 添加版本字节 + 校验和 + Base58编码
            extended = b"\x00" + ripemd160_result
            checksum = HashUtils.double_sha256(extended)[:4]
            return Base58.encode(extended + checksum)
        else:
            # 回退到基类标准实现
            return super().public_key_to_address(public_key)

    def generate_from_private_key(self, private_key: bytes, compressed: bool = True) -> str:
        """
        从私钥生成地址(完整流程，仅返回地址字符串)

        Args:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        Returns:
            P2PKH地址
        """
        return super().generate_address(private_key, compressed)[0]

    def batch_generate(self, private_keys: list[bytes], compressed: bool = True) -> list[str]:
        """
        批量生成地址(高性能)

        Args:
            private_keys: 私钥列表
            compressed: 是否使用压缩格式

        Returns:
            地址列表
        """
        if not private_keys:
            return []

        # 批量推导公钥
        public_keys = []
        for pk in private_keys:
            pk_int = int.from_bytes(pk, "big")

            # 使用预计算表
            if self.use_precomputed_table and self.precomputed_table:
                point = self.precomputed_table.scalar_multiply_with_table(pk_int, self.ec)
            else:
<<<<<<< Updated upstream
=======
                # v4.2.2 C1-regression修复: 使用恒定时间实现
>>>>>>> Stashed changes
                point = self.ec.scalar_multiply_const_time(pk_int, self.G)

            # 压缩格式
            prefix = b"\x02" if point.y % 2 == 0 else b"\x03"
            public_key = prefix + point.x.to_bytes(32, "big")
            public_keys.append(public_key)

        # 批量哈希(SIMD优化)
        if self.use_simd_hash and self.simd_optimizer:
            # 批量SHA256
            sha256_results = self.simd_optimizer.batch_sha256(public_keys)
            # 批量RIPEMD160
            ripemd160_results = self.simd_optimizer.batch_ripemd160(sha256_results)
        else:
            # 标准方法
            sha256_results = [HashUtils.sha256(pk) for pk in public_keys]
            ripemd160_results = [HashUtils.ripemd160(sha) for sha in sha256_results]

        # 批量生成地址
        addresses = []
        for ripemd160 in ripemd160_results:
            extended = b"\x00" + ripemd160
            checksum = HashUtils.double_sha256(extended)[:4]
            address = Base58.encode(extended + checksum)
            addresses.append(address)

        return addresses

    def get_optimization_info(self) -> dict:
        """获取优化配置信息"""
        info = {
            "precomputed_table": {
                "enabled": self.use_precomputed_table,
                "window_size": (self.precomputed_table.window_size if self.precomputed_table else None),
                "memory_usage_kb": (
                    self.precomputed_table.get_memory_usage() / 1024 if self.precomputed_table else 0
                ),
            },
            "simd_hash": {
                "enabled": self.use_simd_hash,
                "backend": (
                    self.simd_optimizer.get_backend_name() if self.simd_optimizer else "disabled"
                ),
            },
            "memory_pool": {
                "enabled": self.use_memory_pool,
                "pool_stats": self.ecpoint_pool.get_stats() if self.ecpoint_pool else {},
            },
        }
        return info
