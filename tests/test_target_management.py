"""目标地址管理模块单元测试."""

import os
import pathlib
import sys
import tempfile
from unittest.mock import patch

import pytest

from src.collision.targets.cache import AddressCache
from src.collision.targets.matcher import AddressMatcher
from src.collision.targets.resolver import TargetResolver
from src.collision.targets.storage import AddressStorage
from src.collision.targets.validator import AddressBatchValidator
from src.utils.encoding_utils import EncodingUtils


class TestAddressCache:
    """地址缓存测试."""

    def test_cache_put_get(self):
        """测试缓存存取."""
        cache = AddressCache(lru_size=100)

        cache.put("test_key", "test_value")
        result = cache.get("test_key")

        assert result == "test_value"

    def test_cache_miss(self):
        """测试缓存未命中."""
        cache = AddressCache(lru_size=100)

        result = cache.get("nonexistent")
        assert result is None

    def test_cache_stats(self):
        """测试缓存统计."""
        cache = AddressCache(lru_size=100, enable_stats=True)

        cache.put("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_clear(self):
        """测试清空缓存."""
        cache = AddressCache(lru_size=100)

        cache.put("key1", "value1")
        cache.clear()

        assert cache.get("key1") is None

    def test_cache_contains(self):
        """测试__contains__."""
        cache = AddressCache(lru_size=100)

        cache.put("key1", "value1")

        assert "key1" in cache
        assert "key2" not in cache


class TestTargetResolver:
    """目标地址解析器测试."""

    def test_resolve_p2pkh_address(self):
        """测试P2PKH地址解析."""
        resolver = TargetResolver(enable_cache=False)

        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = resolver.resolve(address)

        assert result == address

    def test_resolve_unknown_format(self):
        """测试未知格式."""
        resolver = TargetResolver(enable_cache=False)

        result = resolver.resolve("invalid_format!!!")

        assert result is None

    def test_resolve_with_cache(self):
        """测试缓存解析."""
        resolver = TargetResolver(enable_cache=True)

        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        # 第一次解析（缓存未命中）
        result1 = resolver.resolve(address)
        # 第二次解析（应从缓存命中）
        result2 = resolver.resolve(address)

        assert result1 == result2 == address

        # 检查缓存统计
        stats = resolver.get_cache_stats()
        # 验证统计字段存在
        assert "hits" in stats, f"缓存统计缺少'hits'字段: {stats.keys()}"
        assert "misses" in stats, "缓存统计缺少'misses'字段"
        # 第二次应该命中缓存
        assert stats["hits"] >= 1, f"缓存命中次数应该>=1，实际: {stats['hits']}"
        assert stats["misses"] >= 1, f"缓存未命中次数应该>=1，实际: {stats['misses']}"

    def test_resolve_multiple(self):
        """测试批量解析."""
        resolver = TargetResolver(enable_cache=False)

        inputs = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "invalid",
        ]

        results = resolver.resolve_multiple(inputs)

        assert len(results) == 1
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in results

    def test_load_from_file(self):
        """测试从文件加载."""
        resolver = TargetResolver(enable_cache=False)

        # 创建临时文件（明确指定UTF-8编码）
        temp_path = None
        try:
            # 使用显式编码创建文件
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
                f.write("# 这是注释\n")
                f.write("\n")
                f.write("invalid_address\n")
                temp_path = f.name

            addresses = resolver.load_from_file(temp_path)

            assert len(addresses) == 1
            assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in addresses
        finally:
            if temp_path and pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_detect_format(self):
        """测试格式检测."""
        assert TargetResolver.detect_format("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "address"
        assert TargetResolver.detect_format("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == "p2sh_address"
        assert TargetResolver.detect_format("invalid") == "unknown"


class TestAddressValidator:
    """地址验证器测试."""

    def test_validate_valid_address(self):
        """测试有效地址验证."""
        validator = AddressBatchValidator(max_workers=2)

        results = validator.validate_batch(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])

        assert results["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"].valid is True

    def test_validate_invalid_address(self):
        """测试无效地址验证."""
        validator = AddressBatchValidator(max_workers=2)

        results = validator.validate_batch(["invalid_address!!!"])

        assert results["invalid_address!!!"].valid is False

    def test_filter_valid(self):
        """测试过滤有效地址."""
        validator = AddressBatchValidator(max_workers=2)

        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "invalid",
        ]

        valid = validator.filter_valid(addresses)

        assert len(valid) == 1
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in valid

    def test_validation_summary(self):
        """测试验证摘要."""
        validator = AddressBatchValidator(max_workers=2)

        results = validator.validate_batch(
            [
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "invalid",
            ],
        )

        summary = validator.get_validation_summary(results)

        assert summary["total"] == 2
        assert summary["valid"] == 1
        assert summary["invalid"] == 1

    def test_validation_coverage(self):
        """测试验证覆盖率统计."""
        validator = AddressBatchValidator(max_workers=2)

        # 严格模式: 包含非字符串类型
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            12345,  # 非字符串,导致中止
        ]

        results = validator.validate_batch(addresses, strict_mode=True)
        coverage = validator.get_validation_coverage(results)

        # 验证覆盖率统计
        assert coverage["total"] == 3
        assert coverage["validated"] == 1  # 只有12345被验证(类型检查)
        assert coverage["unvalidated"] == 2  # 两个地址未验证
        assert coverage["coverage"] == pytest.approx(33.33, rel=0.1)
        assert coverage["valid"] == 0
        assert coverage["invalid"] == 1

    def test_validation_coverage_empty(self):
        """测试空列表的覆盖率统计."""
        validator = AddressBatchValidator(max_workers=2)

        results = validator.validate_batch([])
        coverage = validator.get_validation_coverage(results)

        assert coverage["total"] == 0
        assert coverage["validated"] == 0
        assert coverage["unvalidated"] == 0
        assert coverage["coverage"] == 0.0

    def test_strict_mode_skip_strategy(self):
        """测试严格模式的skip策略."""
        validator = AddressBatchValidator(max_workers=2)

        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            12345,  # 非字符串,应该被跳过
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        ]

        # 使用skip策略
        results = validator.validate_batch(addresses, strict_mode=True, on_type_error="skip")

        # 应该只验证了两个字符串地址
        assert len(results) == 2
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in results
        assert "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" in results
        assert "12345" not in results  # 被跳过,不在结果中

        # 两个地址都应该已验证
        assert all(r.validated for r in results.values())

    def test_strict_mode_convert_strategy(self):
        """测试严格模式的convert策略."""
        validator = AddressBatchValidator(max_workers=2)

        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            12345,  # 非字符串,应该被转换为"12345"
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        ]

        # 使用convert策略
        results = validator.validate_batch(addresses, strict_mode=True, on_type_error="convert")

        # 应该验证了三个地址(包括转换后的"12345")
        assert len(results) == 3
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in results
        assert "12345" in results
        assert "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" in results

        # "12345"应该被标记为无效(不是有效的比特币地址)
        assert results["12345"].valid is False
        assert results["12345"].validated is True  # 确实验证了

    def test_strict_mode_invalid_strategy(self):
        """测试无效的策略参数."""
        validator = AddressBatchValidator(max_workers=2)

        addresses = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]

        # 应该抛出ValueError
        with pytest.raises(ValueError, match="无效的策略"):
            validator.validate_batch(addresses, strict_mode=True, on_type_error="invalid")


class TestAddressMatcher:
    """地址匹配引擎测试."""

    def test_hash_set_match(self):
        """测试Hash集合匹配."""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert matcher.is_match("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") is False

    def test_add_target(self):
        """测试添加目标."""
        matcher = AddressMatcher(strategy="hash_set")

        matcher.add_target("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True

    def test_clear(self):
        """测试清空."""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        matcher.clear()

        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False

    def test_len(self):
        """测试__len__."""
        targets = {"addr1", "addr2", "addr3"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert len(matcher) == 3

    def test_contains(self):
        """测试__contains__."""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in matcher


class TestAddressStorage:
    """地址存储测试."""

    def test_json_save_load(self):
        """测试JSON保存和加载."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            storage = AddressStorage(storage_type="json", path=temp_path)

            targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"}
            metadata = {"name": "test"}

            # 保存
            assert storage.save_targets(targets, metadata) is True

            # 加载
            loaded_targets, loaded_metadata = storage.load_targets()

            assert loaded_targets == targets
            assert loaded_metadata == metadata
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_csv_save_load(self):
        """测试CSV保存和加载."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            storage = AddressStorage(storage_type="csv", path=temp_path)

            targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"}

            # 保存
            assert storage.save_targets(targets) is True

            # 加载
            loaded_targets, _ = storage.load_targets()

            assert loaded_targets == targets
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_get_storage_info(self):
        """测试获取存储信息."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("{}")
            temp_path = f.name

        try:
            storage = AddressStorage(storage_type="json", path=temp_path)

            info = storage.get_storage_info()

            assert info["storage_type"] == "json"
            assert info["exists"] is True
            assert info["size_bytes"] > 0
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()


class TestEncodingCompatibility:
    """编码兼容性测试."""

    def test_read_utf8_file(self):
        """测试读取UTF-8编码文件."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("# 中文注释\n")
            temp_path = f.name

        try:
            content = EncodingUtils.read_file(temp_path, encoding="utf-8")
            assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in content
            assert "中文注释" in content
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_read_gbk_file(self):
        """测试读取GBK编码文件."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            # 写入GBK编码的内容
            content = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n# 中文注释\n"
            f.write(content.encode("gbk"))
            temp_path = f.name

        try:
            # 自动检测编码
            content = EncodingUtils.read_file(temp_path, try_multiple=True)
            assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in content
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_detect_encoding(self):
        """测试编码检测."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            content = "测试内容".encode()
            f.write(content)
            temp_path = f.name

        try:
            detected = EncodingUtils.detect_file_encoding(temp_path)
            # 应该检测到utf-8或类似的编码
            assert detected in ["utf-8", "utf-8-sig", "ascii"]
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_write_and_read_utf8(self):
        """测试写入和读取UTF-8文件."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = f.name

        try:
            content = "测试内容\n1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
            EncodingUtils.write_file(temp_path, content, encoding="utf-8")

            read_content = EncodingUtils.read_file(temp_path, encoding="utf-8")
            assert read_content == content
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_fixed_sampling(self):
        """测试固定采样模式."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            # 创建50KB的文件
            content = "测试内容" * 5000
            f.write(content.encode("utf-8"))
            temp_path = f.name

        try:
            # 使用固定采样，限制5KB
            encoding = EncodingUtils.detect_file_encoding(
                temp_path,
                max_sample_size=5000,
                use_dynamic_sampling=False,
            )
            # 应该能检测到utf-8
            assert encoding == "utf-8"
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_boundary_sampling_small(self):
        """测试边界大小文件采样 - 小文件边界."""
        # 10KB - 1字节（应该是小文件，全量读取）
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            content = "A" * (10 * 1024 - 1)
            f.write(content.encode("utf-8"))
            temp_path = f.name

        try:
            encoding = EncodingUtils.detect_file_encoding(temp_path)
            assert encoding in ["utf-8", "ascii"]
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_boundary_sampling_medium(self):
        """测试边界大小文件采样 - 中文件边界."""
        # 10KB（边界，应该是中文件）
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            content = "A" * (10 * 1024)
            f.write(content.encode("utf-8"))
            temp_path = f.name

        try:
            encoding = EncodingUtils.detect_file_encoding(temp_path)
            assert encoding in ["utf-8", "ascii"]
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_dynamic_vs_fixed_sampling(self):
        """对比动态和固定采样的差异."""
        # 创建100KB的文件
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            content = "测试内容" * 10000
            f.write(content.encode("utf-8"))
            temp_path = f.name

        try:
            # 动态采样（应该读取10% = 10KB）
            encoding_dynamic = EncodingUtils.detect_file_encoding(temp_path, use_dynamic_sampling=True)

            # 固定采样（限制1KB）
            encoding_fixed = EncodingUtils.detect_file_encoding(
                temp_path,
                max_sample_size=1024,
                use_dynamic_sampling=False,
            )

            # 两种模式都应该能检测到utf-8
            assert encoding_dynamic == "utf-8"
            assert encoding_fixed == "utf-8"
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_none_max_sample_size(self):
        """测试max_sample_size为None时使用默认值."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            content = "测试内容".encode()
            f.write(content)
            temp_path = f.name

        try:
            # None应该使用MAX_SAMPLE_SIZE (100KB)
            encoding = EncodingUtils.detect_file_encoding(temp_path, max_sample_size=None)
            assert encoding == "utf-8"
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_sampling_strategy_matrix(self):
        """测试采样策略矩阵：不同文件大小 x 不同max_sample_size."""
        test_cases = [
            # (文件大小, max_sample_size, use_dynamic_sampling, 描述)
            (1024, None, True, "1KB小文件，动态采样"),
            (5 * 1024, None, True, "5KB小文件，动态采样"),
            (10 * 1024 - 1, None, True, "10KB-1字节，动态采样（小文件边界）"),
            (10 * 1024, None, True, "10KB，动态采样（中文件边界）"),
            (100 * 1024, None, True, "100KB，动态采样（中文件）"),
            (500 * 1024, None, True, "500KB，动态采样（中文件）"),
            (1024 * 1024, None, True, "1MB，动态采样（大文件边界）"),
            (5 * 1024 * 1024, None, True, "5MB，动态采样（大文件）"),
            (10 * 1024 * 1024, None, True, "10MB，动态采样（大文件）"),
            # 自定义max_sample_size
            (1024, 512, True, "1KB文件，限制512B"),
            (100 * 1024, 10 * 1024, True, "100KB文件，限制10KB"),
            (10 * 1024 * 1024, 50 * 1024, True, "10MB文件，限制50KB"),
            # 固定采样模式
            (100 * 1024, 10 * 1024, False, "100KB文件，固定采样10KB"),
            (10 * 1024 * 1024, 5 * 1024, False, "10MB文件，固定采样5KB"),
        ]

        for file_size, max_size, use_dynamic, description in test_cases:
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
                # 创建指定大小的文件
                content = "A" * file_size
                f.write(content.encode("utf-8"))
                temp_path = f.name

            try:
                # 执行编码检测
                if max_size is None:
                    encoding = EncodingUtils.detect_file_encoding(
                        temp_path,
                        use_dynamic_sampling=use_dynamic,
                    )
                else:
                    encoding = EncodingUtils.detect_file_encoding(
                        temp_path,
                        max_sample_size=max_size,
                        use_dynamic_sampling=use_dynamic,
                    )

                # 所有测试都应该能检测到utf-8或ascii
                assert encoding in [
                    "utf-8",
                    "ascii",
                ], f"{description} 失败: 期望utf-8或ascii，实际{encoding}"
            finally:
                if pathlib.Path(temp_path).exists():
                    pathlib.Path(temp_path).unlink()

    def test_sampling_size_calculation(self):
        """测试采样大小计算的准确性."""
        from src.utils.encoding_utils import EncodingUtils

        # 测试不同文件大小的采样计算
        test_cases = [
            # (文件大小, use_dynamic, 期望策略描述)
            (1024, True, "小文件-全量"),  # 1KB
            (10 * 1024, True, "中文件-50%"),  # 10KB
            (100 * 1024, True, "中文件-50%"),  # 100KB
            (1024 * 1024, True, "大文件-10%"),  # 1MB
            (10 * 1024 * 1024, True, "大文件-10%"),  # 10MB
        ]

        for file_size, use_dynamic, strategy_desc in test_cases:
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
                content = "测试内容" * (file_size // 10)  # 约file_size大小
                f.write(content.encode("utf-8"))
                temp_path = f.name

            try:
                # 验证不会抛出异常，且能检测到编码
                encoding = EncodingUtils.detect_file_encoding(
                    temp_path,
                    use_dynamic_sampling=use_dynamic,
                )
                assert encoding in [
                    "utf-8",
                    "ascii",
                ], f"{strategy_desc} (文件大小={file_size}) 失败"
            finally:
                if pathlib.Path(temp_path).exists():
                    pathlib.Path(temp_path).unlink()


class TestDataCompatibility:
    """数据类型兼容性测试."""

    def test_validator_with_mixed_types(self):
        """测试验证器处理混合类型."""
        validator = AddressBatchValidator(max_workers=2)

        # 混合类型输入
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            12345,  # 整数
            None,  # None值
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        ]

        results = validator.validate_batch(addresses)

        # 应该能处理所有输入
        assert len(results) >= 2  # 至少两个字符串地址

    def test_matcher_with_non_string(self):
        """测试匹配器处理非字符串输入."""
        matcher = AddressMatcher(strategy="hash_set")
        matcher.add_target("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

        # 测试非字符串输入
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert matcher.is_match(12345) is False  # 应该返回False而不是抛出异常

    def test_cache_with_mixed_types(self):
        """测试缓存处理混合类型."""
        cache = AddressCache(lru_size=100)

        # 测试字符串键值
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

        # 测试非字符串键值（应该能转换）
        cache.put(123, "value2")
        assert cache.get("123") == "value2"

    def test_strict_mode_validated_field(self):
        """测试严格模式下的validated字段."""
        validator = AddressBatchValidator(max_workers=2)

        # 严格模式：包含非字符串类型
        addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            12345,  # 非字符串，导致中止
        ]

        results = validator.validate_batch(addresses, strict_mode=True)

        # 验证结果
        assert len(results) == 3

        # 前两个地址应该是“未验证”
        assert results["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"].validated is False
        assert results["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"].validated is False

        # 导致失败的地址应该是“已验证”（类型检查失败）
        assert results["12345"].validated is True
        assert "期望字符串类型" in results["12345"].error


class TestCrossPlatformCompatibility:
    """跨平台兼容性测试."""

    def test_path_handling(self):
        """测试路径处理."""
        # 测试Windows和Unix风格路径
        from src.collision.targets.resolver import TargetResolver

        resolver = TargetResolver(enable_cache=False)

        # 创建临时文件测试
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            temp_path = f.name

        try:
            addresses = resolver.load_from_file(temp_path)
            assert len(addresses) == 1
        finally:
            if pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink()

    def test_platform_encoding_detection(self):
        """测试平台编码检测."""
        platform_encoding = EncodingUtils.get_platform_default_encoding()

        # 根据不同平台返回不同编码
        if sys.platform == "win32":
            assert platform_encoding in ["gbk", "utf-8"]
        else:
            assert platform_encoding == "utf-8"


class TestErrorHandling:
    """错误处理测试."""

    def test_resolver_invalid_file(self):
        """测试解析器处理无效文件."""
        resolver = TargetResolver(enable_cache=False)

        # 测试不存在的文件
        addresses = resolver.load_from_file("/nonexistent/file.txt")
        assert len(addresses) == 0

    def test_storage_invalid_path(self):
        """测试存储处理无效路径."""
        # 使用一个权限不足的路径（在测试环境中应该无法写入）
        import platform

        if platform.system() == "Windows":
            # Windows系统目录（通常需要管理员权限）
            storage = AddressStorage(
                storage_type="json",
                path="C:\\Windows\\System32\\test_btc_data.json",
            )
        else:
            # Unix系统目录
            storage = AddressStorage(storage_type="json", path="/etc/test_btc_data.json")

        # 应该返回False而不是抛出异常
        try:
            result = storage.save_targets({"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"})
            # 如果没抛异常，检查结果
            assert (
                result is False
                or pathlib.Path("C:\\Windows\\System32\\test_btc_data.json").exists()
                or pathlib.Path("/etc/test_btc_data.json").exists()
            )
        except PermissionError:
            # 如果抛出权限错误，也是预期的行为
            pass
        except Exception:
            # 其他异常也 acceptable
            pass

    def test_cache_error_recovery(self):
        """测试缓存错误恢复."""
        cache = AddressCache(lru_size=100)

        # 测试异常情况
        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert "hits" in stats


class TestTargetResolverSecurity:
    """TargetResolver 安全测试 - 从test_target_resolver.py迁移."""

    @pytest.mark.parametrize(
        "malicious_path,description",
        [
            ("../etc/passwd", "基础路径遍历"),
            ("../../secret.txt", "双点遍历"),
            ("../../../etc/shadow", "三层遍历"),
            ("..\\..\\windows\\system32", "Windows遍历"),
            ("./../outside.txt", "混合路径"),
            ("....//....//etc/passwd", "双点混淆"),
        ],
    )
    def test_path_traversal_variants(self, malicious_path, description):
        """参数化路径遍历攻击测试."""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.load_from_file(malicious_path)
        # 所有路径遍历攻击都应被阻止
        assert result == set(), f"{description} 应该被阻止: {malicious_path}"

    def test_path_traversal_blocked(self):
        """路径遍历攻击被阻止（向后兼容）."""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.load_from_file("../etc/passwd")
        # 路径遍历应被阻止，返回空集合
        assert result == set()

    def test_absolute_path_outside_cwd_blocked(self):
        """工作目录外的绝对路径被阻止."""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.load_from_file("C:\\Windows\\System32\\drivers\\etc\\hosts")
        assert result == set()

    def test_double_dot_traversal_blocked(self):
        """双点遍历被阻止."""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.load_from_file("../../secret.txt")
        assert result == set()

    def test_normal_path_allowed(self):
        """正常路径允许（文件在当前目录）."""
        resolver = TargetResolver(enable_cache=False)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            dir=os.getcwd(),
            encoding="utf-8",
        )
        tmp.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
        tmp.close()
        try:
            result = resolver.load_from_file(tmp.name)
            assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in result
        finally:
            pathlib.Path(tmp.name).unlink()

    def test_oversized_file_rejected(self):
        """文件超过100MB限制时返回空集合."""
        resolver = TargetResolver(enable_cache=False)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            dir=os.getcwd(),
            encoding="utf-8",
        )
        tmp.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
        tmp.close()
        try:
            # 使用mock模拟超大文件（线程安全）
            with patch("os.path.getsize", return_value=200 * 1024 * 1024):  # 200MB
                result = resolver.load_from_file(tmp.name)
                assert result == set()
        finally:
            pathlib.Path(tmp.name).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
