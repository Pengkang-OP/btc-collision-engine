"""simd_optimizer 全面测试 — 覆盖 BatchOptimizer, BatchCollisionProcessor,
NumpyOptimizedAddressGenerator 及工厂函数
"""

import hashlib
from unittest.mock import MagicMock, patch

from src.core.simd_optimizer import (
    BatchCollisionProcessor,
    BatchOptimizer,
    NumpyOptimizedAddressGenerator,
    SIMDVectorizedOperations,
    create_batch_optimizer,
    create_batch_processor,
    create_simd_optimizer,
)

# ──────────────────────────── BatchOptimizer 初始化 ────────────────────────────


class TestBatchOptimizerInit:
    """BatchOptimizer 初始化测试"""

    def test_init_default_batch_size(self):
        """默认 batch_size=100000"""
        bo = BatchOptimizer()
        assert bo.batch_size  ==  100000
        assert bo.p  ==  bo.curve.P
        assert bo.n  ==  bo.curve.N

    def test_init_custom_batch_size(self):
        """自定义 batch_size"""
        bo = BatchOptimizer(batch_size=5000)
        assert bo.batch_size  ==  5000

    def test_precompute_constants(self):
        """_precompute_constants 设置 p 和 n"""
        bo = BatchOptimizer(batch_size=10)
        assert bo.p is not None
        assert bo.n is not None

    def test_init_zero_batch_size(self):
        """batch_size=0 边界"""
        bo = BatchOptimizer(batch_size=0)
        assert bo.batch_size  ==  0


# ──────────────────────── BatchOptimizer 转换方法 ──────────────────────────────


class TestBatchOptimizerConvert:
    """batch_private_key_to_int 测试"""

    def setUp(self):
        self.bo = BatchOptimizer(batch_size=100)

    def test_batch_private_key_to_int_normal(self):
        """正常转换"""
        pks = [b"\x01" * 32, b"\xff" * 32, b"\x00" * 31 + b"\x01"]
        result = self.bo.batch_private_key_to_int(pks)
        assert len(result)  ==  3
        assert isinstance(result[0], int)

    def test_batch_private_key_to_int_empty(self):
        """空列表"""
        result = self.bo.batch_private_key_to_int([])
        assert result  ==  []

    def test_batch_private_key_to_int_single(self):
        """单个私钥"""
        pk = bytes(range(32))
        result = self.bo.batch_private_key_to_int([pk])
        assert result[0]  ==  int.from_bytes(pk, "big")


# ──────────────────────── BatchOptimizer 哈希方法 ──────────────────────────────


class TestBatchOptimizerHash:
    """batch_ripemd160, batch_sha256, batch_hash160 测试"""

    def setUp(self):
        self.bo = BatchOptimizer(batch_size=100)

    def test_batch_ripemd160_normal(self):
        """批量 RIPEMD160"""
        data_list = [b"hello", b"world", b"test"]
        result = self.bo.batch_ripemd160(data_list)
        assert len(result)  ==  3
        for i, d in enumerate(data_list):
            expected = hashlib.new("ripemd160", d).digest()
            assert result[i]  ==  expected

    def test_batch_ripemd160_empty(self):
        """空列表"""
        assert self.bo.batch_ripemd160([])  ==  []

    def test_batch_ripemd160_single(self):
        """单个元素"""
        result = self.bo.batch_ripemd160([b"data"])
        assert len(result)  ==  1

    def test_batch_sha256_normal(self):
        """批量 SHA256"""
        data_list = [b"alpha", b"beta", b"gamma"]
        result = self.bo.batch_sha256(data_list)
        assert len(result)  ==  3
        for i, d in enumerate(data_list):
            expected = hashlib.sha256(d).digest()
            assert result[i]  ==  expected

    def test_batch_sha256_empty(self):
        """空列表"""
        assert self.bo.batch_sha256([])  ==  []

    def test_batch_sha256_single(self):
        """单个元素"""
        result = self.bo.batch_sha256([b"x"])
        assert len(result)  ==  1

    def test_batch_hash160_normal(self):
        """批量 Hash160 = SHA256 + RIPEMD160"""
        pks = [b"\x04" + bytes(i) * 64 for i in range(3)]
        result = self.bo.batch_hash160(pks)
        assert len(result)  ==  3
        for i, pk in enumerate(pks):
            expected = hashlib.new("ripemd160", hashlib.sha256(pk).digest()).digest()
            assert result[i]  ==  expected

    def test_batch_hash160_empty(self):
        """空列表"""
        assert self.bo.batch_hash160([])  ==  []


# ────────────────────── BatchOptimizer Base58 编码 ────────────────────────────


class TestBatchOptimizerBase58:
    """batch_base58_encode 测试"""

    def setUp(self):
        self.bo = BatchOptimizer(batch_size=100)

    def test_batch_base58_encode_zero(self):
        """编码 0 → '1'"""
        result = self.bo.batch_base58_encode([0])
        assert result  ==  ["1"]

    def test_batch_base58_encode_positive(self):
        """正常编码"""
        result = self.bo.batch_base58_encode([1, 58])
        # 1 → "2", 58 → "21"
        assert result  ==  ["2", "21"]

    def test_batch_base58_encode_mixed(self):
        """混合编码（含零）"""
        result = self.bo.batch_base58_encode([0, 1, 0, 58])
        assert result  ==  ["1", "2", "1", "21"]

    def test_batch_base58_encode_empty(self):
        """空列表"""
        assert self.bo.batch_base58_encode([])  ==  []

    def test_batch_base58_encode_large_number(self):
        """大数编码"""
        result = self.bo.batch_base58_encode([123456789])
        assert isinstance(result[0], str)
        assert len(result[0])  >  0


# ────────────────────── BatchOptimizer 地址生成 ───────────────────────────────


class TestBatchOptimizerAddress:
    """batch_address_from_hash160 测试"""

    def setUp(self):
        self.bo = BatchOptimizer(batch_size=100)

    def test_batch_address_from_hash160_default_version(self):
        """默认版本字节 b'\x00'"""
        h160_list = [b"\xaa" * 20, b"\xbb" * 20]
        result = self.bo.batch_address_from_hash160(h160_list)
        assert len(result)  ==  2
        for addr in result:
            assert isinstance(addr, str)
            assert addr.startswith("1")

    def test_batch_address_from_hash160_custom_version(self):
        """自定义版本字节"""
        h160_list = [b"\xcc" * 20]
        result = self.bo.batch_address_from_hash160(h160_list, version_byte=b"\x05")
        assert len(result)  ==  1
        assert result[0].startswith("3")

    def test_batch_address_from_hash160_empty(self):
        """空列表"""
        assert self.bo.batch_address_from_hash160([])  ==  []

    def test_batch_address_from_hash160_single(self):
        """单个 hash160"""
        result = self.bo.batch_address_from_hash160([b"\x01" * 20])
        assert len(result)  ==  1
        assert isinstance(result[0], str)


# ─────────────────────── BatchCollisionProcessor ──────────────────────────────


class TestBatchCollisionProcessorInit:
    """BatchCollisionProcessor 初始化测试"""

    def test_init_default(self):
        """默认 batch_size"""
        bcp = BatchCollisionProcessor()
        assert bcp.batch_size  ==  100000
        assert isinstance(bcp.target_addresses, set)
        assert len(bcp.target_addresses)  ==  0

    def test_init_custom_batch_size(self):
        """自定义 batch_size"""
        bcp = BatchCollisionProcessor(batch_size=500)
        assert bcp.batch_size  ==  500

    def test_set_targets(self):
        """设置目标地址"""
        bcp = BatchCollisionProcessor()
        bcp.set_targets(["1Addr1", "1Addr2", "1Addr3"])
        assert len(bcp.target_addresses)  ==  3
        assert bcp.target_addresses  in  "1Addr1"


class TestBatchCollisionProcessorProcessBatch:
    """process_batch 和 _batch_generate_addresses 测试"""

    def setUp(self):
        self.processor = BatchCollisionProcessor(batch_size=2)

    def _make_fallback_mock(self, addresses):
        """创建走 fallback 路径的 mock generator（无 batch_generate）"""
        mock_gen = MagicMock(spec=["generate_from_private_key"])
        mock_gen.generate_from_private_key.side_effect = addresses
        return mock_gen

    def test_process_batch_no_match(self):
        """无匹配时返回空列表"""
        self.processor.set_targets(["1Target1"])
        mock_gen = self._make_fallback_mock(["1Other"] * 2)
        result = self.processor.process_batch([b"\x01" * 32, b"\x02" * 32], mock_gen)
        assert result  ==  []

    def test_process_batch_with_match(self):
        """有匹配时返回匹配项"""
        self.processor.set_targets(["1Match"])
        mock_gen = self._make_fallback_mock(["1Match", "1Other"])
        result = self.processor.process_batch([b"\x01" * 32, b"\x02" * 32], mock_gen)
        assert len(result)  ==  1
        assert result[0][0]  ==  b"\x01" * 32
        assert result[0][1]  ==  "1Match"

    def test_process_batch_empty_keys(self):
        """空私钥列表"""
        self.processor.set_targets(["1Target"])
        mock_gen = MagicMock()
        result = self.processor.process_batch([], mock_gen)
        assert result  ==  []

    def test_process_batch_multiple_batches(self):
        """跨越多个批次的处理"""
        self.processor.set_targets(["1Target"])
        mock_gen = self._make_fallback_mock(["1Other", "1Target", "1Other", "1Other"])
        result = self.processor.process_batch([b"\x01" * 32] * 4, mock_gen)
        assert len(result)  ==  1

    def test_batch_generate_addresses_with_batch_generate(self):
        """address_generator 有 batch_generate 方法时使用它"""
        mock_gen = MagicMock()
        mock_gen.batch_generate.return_value = ["addr1", "addr2"]
        result = self.processor._batch_generate_addresses([b"\x01" * 32, b"\x02" * 32], mock_gen)
        assert result  ==  ["addr1", "addr2"]
        mock_gen.batch_generate.assert_called_once()

    def test_batch_generate_addresses_fallback(self):
        """address_generator 没有 batch_generate 方法时逐個生成"""
        mock_gen = self._make_fallback_mock(["a1", "a2"])
        result = self.processor._batch_generate_addresses([b"\x01" * 32, b"\x02" * 32], mock_gen)
        assert result  ==  ["a1", "a2"]
        assert mock_gen.generate_from_private_key.call_count  ==  2

    def test_batch_generate_addresses_fallback_no_attr(self):
        """address_generator 没有 batch_generate 属性(通过 mock spec)"""
        mock_gen = MagicMock(spec=["generate_from_private_key"])
        mock_gen.generate_from_private_key.return_value = "addr"
        result = self.processor._batch_generate_addresses([b"\x01" * 32], mock_gen)
        assert result  ==  ["addr"]

    def test_process_batch_matches_across_batches(self):
        """跨批次匹配"""
        self.processor = BatchCollisionProcessor(batch_size=2)
        self.processor.set_targets(["1T1", "1T2"])
        mock_gen = self._make_fallback_mock(["1T1", "x", "y", "1T2"])
        result = self.processor.process_batch([b"\x01" * 32] * 4, mock_gen)
        assert len(result)  ==  2


# ──────────────────── NumpyOptimizedAddressGenerator ──────────────────────────


class TestNumpyOptimizedAddressGenerator:
    """NumpyOptimizedAddressGenerator 测试"""

    @patch("src.core.address_generator.AddressGenerator")
    def test_init(self, mock_ag_cls):
        """初始化创建 base_generator"""
        mock_ag_cls.return_value = MagicMock()
        nog = NumpyOptimizedAddressGenerator()
        assert nog.base_generator is not None
        mock_ag_cls.assert_called_once()

    @patch("src.core.address_generator.AddressGenerator")
    def test_batch_generate_compressed(self, mock_ag_cls):
        """批量生成压缩地址"""
        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.side_effect = ["addr1", "addr2"]
        mock_ag_cls.return_value = mock_gen
        nog = NumpyOptimizedAddressGenerator()
        pks = [b"\x01" * 32, b"\x02" * 32]
        result = nog.batch_generate(pks, compressed=True)
        assert result  ==  ["addr1", "addr2"]

    @patch("src.core.address_generator.AddressGenerator")
    def test_batch_generate_uncompressed(self, mock_ag_cls):
        """批量生成非压缩地址"""
        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.return_value = "addr"
        mock_ag_cls.return_value = mock_gen
        nog = NumpyOptimizedAddressGenerator()
        pks = [b"\x03" * 32]
        result = nog.batch_generate(pks, compressed=False)
        assert result  ==  ["addr"]

    def test_batch_generate_empty(self):
        """空列表"""
        nog = NumpyOptimizedAddressGenerator()
        result = nog.batch_generate([])
        assert result  ==  []

    @patch("src.core.address_generator.AddressGenerator")
    def test_batch_generate_default_compressed(self, mock_ag_cls):
        """默认 compressed=True"""
        mock_gen = MagicMock()
        mock_gen.generate_from_private_key.return_value = "addr"
        mock_ag_cls.return_value = mock_gen
        nog = NumpyOptimizedAddressGenerator()
        pks = [b"\x04" * 32]
        result = nog.batch_generate(pks)
        assert result  ==  ["addr"]


# ─────────────────────────── 工厂函数 ─────────────────────────────────────────


class TestFactoryFunctions:
    """工厂函数测试"""

    def test_create_batch_optimizer(self):
        """create_batch_optimizer 返回 BatchOptimizer"""
        bo = create_batch_optimizer(batch_size=500)
        assert isinstance(bo, BatchOptimizer)
        assert bo.batch_size  ==  500

    def test_create_batch_optimizer_default(self):
        """create_batch_optimizer 默认参数"""
        bo = create_batch_optimizer()
        assert isinstance(bo, BatchOptimizer)
        assert bo.batch_size  ==  100000

    def test_create_simd_optimizer_alias(self):
        """create_simd_optimizer 是 create_batch_optimizer 的别名"""
        assert create_simd_optimizer  is  create_batch_optimizer

    def test_create_batch_processor(self):
        """create_batch_processor 返回 BatchCollisionProcessor"""
        bcp = create_batch_processor(batch_size=1000)
        assert isinstance(bcp, BatchCollisionProcessor)
        assert bcp.batch_size  ==  1000

    def test_create_batch_processor_default(self):
        """create_batch_processor 默认参数"""
        bcp = create_batch_processor()
        assert isinstance(bcp, BatchCollisionProcessor)
        assert bcp.batch_size  ==  100000

    def test_simd_vectorized_operations_alias(self):
        """SIMDVectorizedOperations 是 BatchOptimizer 的别名"""
        assert SIMDVectorizedOperations  is  BatchOptimizer

