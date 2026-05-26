"""BaseAddressGenerator 基类与继承体系测试

覆盖 P3-1 架构去重后新增的抽象基类体系:
- BaseAddressGenerator 抽象性验证
- P2PKHAddressGenerator / OptimizedP2PKHAddressGenerator 继承关系
- LSP 签名兼容性 (P3-1 审查 W1 修复验证)
- 向后兼容别名 AddressGenerator
- generate_address 双公钥返回行为
"""

from abc import ABC

import pytest

from src.core.address_generator import (
    AddressGenerator,
    BaseAddressGenerator,
    P2PKHAddressGenerator,
)
from src.core.optimized_address_generator import OptimizedP2PKHAddressGenerator
from src.core.secp256k1 import Secp256k1


class TestBaseAddressGeneratorInheritance:
    """基类抽象性与继承层次测试"""

    def test_01_base_is_abstract(self):
        """BaseAddressGenerator 是抽象类，不可直接实例化"""
        assert issubclass(BaseAddressGenerator, ABC)
        with pytest.raises(TypeError):
            BaseAddressGenerator()  # type: ignore[abstract]

    def test_02_p2pkh_inherits_base(self):
        """P2PKHAddressGenerator 继承自 BaseAddressGenerator"""
        assert issubclass(P2PKHAddressGenerator, BaseAddressGenerator)

    def test_03_optimized_inherits_base(self):
        """OptimizedP2PKHAddressGenerator 继承自 BaseAddressGenerator"""
        assert issubclass(OptimizedP2PKHAddressGenerator, BaseAddressGenerator)

    def test_04_backward_compat_alias(self):
        """AddressGenerator 是 P2PKHAddressGenerator 的向后兼容别名"""
        assert AddressGenerator  is  P2PKHAddressGenerator

    def test_05_both_are_instances_of_base(self):
        """两个子类实例都是 BaseAddressGenerator 的实例"""
        p2pkh = P2PKHAddressGenerator()
        opt = OptimizedP2PKHAddressGenerator()
        assert isinstance(p2pkh, BaseAddressGenerator)
        assert isinstance(opt, BaseAddressGenerator)


class TestP2PKHAddressGeneratorLSP:
    """LSP 兼容性验证 (审查 W1 修复后)"""

    def setUp(self):
        self.gen = P2PKHAddressGenerator()
        self.private_key = b"\x01" * 32  # 有效私钥 (在 [1,N) 范围内)

    def test_01_generate_address_no_args(self):
        """无参数调用生成随机地址"""
        addr, compressed_pk, uncompressed_pk = self.gen.generate_address()
        assert addr.startswith("1")
        assert len(compressed_pk)  ==  33
        assert len(uncompressed_pk)  ==  65

    def test_02_generate_address_with_private_key(self):
        """传入私钥生成地址"""
        addr, cpk, upk = self.gen.generate_address(self.private_key)
        assert addr.startswith("1")
        assert len(cpk)  ==  33
        assert len(upk)  ==  65

    def test_03_compressed_param_accepted(self):
        """compressed=True 参数被接受 (LSP 兼容)"""
        addr, cpk, _ = self.gen.generate_address(self.private_key, compressed=True)
        assert addr.startswith("1")

    def test_04_compressed_false_param_accepted(self):
        """compressed=False 参数被接受 (P2PKH 始终返回双格式)"""
        addr, cpk, upk = self.gen.generate_address(self.private_key, compressed=False)
        # compressed=False 仍返回两种格式
        assert len(cpk)  ==  33
        assert len(upk)  ==  65

    def test_05_invalid_key_len_raises(self):
        """无效私钥长度抛出 ValueError"""
        with pytest.raises(ValueError):
            self.gen.generate_address(b"\x00" * 31)

    def test_06_zero_key_raises(self):
        """零私钥抛出 ValueError"""
        with pytest.raises(ValueError):
            self.gen.generate_address(b"\x00" * 32)

    def test_07_key_exceeds_order_raises(self):
        """超出曲线阶 N 的私钥抛出 ValueError"""
        big_key = Secp256k1.N.to_bytes(32, "big")
        with pytest.raises(ValueError):
            self.gen.generate_address(big_key)


class TestBaseViaSuperDelegation:
    """子类通过 super() 委托基类方法的正确性"""

    def setUp(self):
        self.p2pkh = P2PKHAddressGenerator()
        self.opt = OptimizedP2PKHAddressGenerator()
        self.private_key = b"\x01" * 32

    def test_01_p2pkh_public_key_to_address_via_super(self):
        """P2PKH: public_key_to_address 通过 super() 委托基类"""
        pk = self.p2pkh.private_key_to_public_key(self.private_key)
        addr = self.p2pkh.public_key_to_address(pk)
        assert addr.startswith("1")
        assert len(addr)  ==  34

    def test_02_opt_public_key_to_address_via_super_fallback(self):
        """Optimized: public_key_to_address SIMD 失败回退到 base"""
        pk = self.opt.private_key_to_public_key(self.private_key)
        addr = self.opt.public_key_to_address(pk)
        assert addr.startswith("1")

    def test_03_p2pkh_generate_private_key_in_range(self):
        """P2PKH: generate_private_key 返回有效范围私钥"""
        for _ in range(5):
            pk = self.p2pkh.generate_private_key()
            assert len(pk)  ==  32
            key_int = int.from_bytes(pk, "big")
            assert key_int  >=  1
            assert key_int  <  Secp256k1.N

    def test_04_opt_generate_private_key_in_range(self):
        """Optimized: generate_private_key 返回有效范围私钥"""
        for _ in range(5):
            pk = self.opt.generate_private_key()
            assert len(pk)  ==  32
            key_int = int.from_bytes(pk, "big")
            assert key_int  >=  1
            assert key_int  <  Secp256k1.N

    def test_05_both_generators_produce_same_address_from_same_key(self):
        """同一私钥在两个生成器中产生相同地址"""
        pk = self.p2pkh.generate_private_key()
        addr1, _, _ = self.p2pkh.generate_address(pk)
        addr2, _, _ = self.opt.generate_address(pk, compressed=True)
        assert addr1  ==  addr2


class TestOptimizedAddressGeneratorEdge:
    """OptimizedP2PKHAddressGenerator 边界路径测试"""

    def test_batch_generate_empty_list(self):
        """batch_generate 空列表返回空 (cover line 178)"""
        gen = OptimizedP2PKHAddressGenerator()
        result = gen.batch_generate([])
        assert result  ==  []

    def test_batch_generate_all_optimizations_off(self):
        """batch_generate 关闭所有优化 (cover lines 189, 204-205)"""
        gen = OptimizedP2PKHAddressGenerator(
            use_precomputed_table=False,
            use_simd_hash=False,
            use_memory_pool=False,
        )
        result = gen.batch_generate([b"\x01" * 32, b"\x02" * 32])
        assert len(result)  ==  2
        for addr in result:
            assert addr.startswith("1")

    def test_get_optimization_info_enabled(self):
        """get_optimization_info 返回优化配置信息 (cover lines 219-242)"""
        gen = OptimizedP2PKHAddressGenerator()
        info = gen.get_optimization_info()
        assert info  in  "precomputed_table"
        assert info  in  "simd_hash"
        assert info  in  "memory_pool"
        assert info["precomputed_table"]["enabled"]

    def test_get_optimization_info_all_disabled(self):
        """get_optimization_info 全部优化禁用时"""
        gen = OptimizedP2PKHAddressGenerator(
            use_precomputed_table=False,
            use_simd_hash=False,
            use_memory_pool=False,
        )
        info = gen.get_optimization_info()
        assert not info["precomputed_table"]["enabled"]
        assert not info["simd_hash"]["enabled"]
        assert not info["memory_pool"]["enabled"]

    def test_private_key_to_public_key_uncompressed(self):
        """private_key_to_public_key compressed=False (cover line 129)"""
        gen = OptimizedP2PKHAddressGenerator()
        pk = gen.private_key_to_public_key(b"\x01" * 32, compressed=False)
        assert len(pk)  ==  65  # 未压缩公钥 65 字节
        assert pk.startswith(b"\x04")

    def test_private_key_to_public_key_no_precomputed(self):
        """private_key_to_public_key 无预计算表 → line 120"""
        gen = OptimizedP2PKHAddressGenerator(use_precomputed_table=False)
        pk = gen.private_key_to_public_key(b"\x01" * 32, compressed=True)
        assert len(pk)  ==  33

    def test_public_key_to_address_no_simd(self):
        """public_key_to_address SIMD 关闭回退到基类 → line 151"""
        gen = OptimizedP2PKHAddressGenerator(use_simd_hash=False)
        pubkey = gen.private_key_to_public_key(b"\x01" * 32)
        addr = gen.public_key_to_address(pubkey)
        assert addr.startswith("1")

    def test_generate_from_private_key(self):
        """generate_from_private_key → line 164"""
        gen = OptimizedP2PKHAddressGenerator()
        addr = gen.generate_from_private_key(b"\x01" * 32)
        assert addr.startswith("1")

    def test_batch_generate_with_optimizations_enabled(self):
        """batch_generate 全优化开启路径 → lines 187, 199-201"""
        gen = OptimizedP2PKHAddressGenerator(
            use_precomputed_table=True,
            use_simd_hash=True,
            use_memory_pool=False,
        )
        result = gen.batch_generate([b"\x01" * 32, b"\x02" * 32])
        assert len(result)  ==  2
        for addr in result:
            assert addr.startswith("1")

