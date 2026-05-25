"""ALG-2: 范围扫描边界优化测试

测试覆盖:
1. GPU _generate_sequential_keys 边界：零元素、单元素、大批次
2. GPU RangeScanSearchMode 第一批发包 off-by-one 修复验证
3. CPU _range_scan_worker 边界：单元素范围、无效key跳过
4. CPU range_scan 多worker分配边界：chunk_size=0、小范围
5. 范围切分不重叠验证
"""

from unittest.mock import Mock

import pytest

from src.collision.key_collision_engine import KeyCollisionEngine


class TestGenerateSequentialKeysBoundary:
    """_generate_sequential_keys 边界测试"""

    def test_count_zero(self):
        """count=0 返回空字节串"""
        from src.gpu.search_modes.base_search import BaseSearchMode

        mock_engine = Mock()
        mock_engine._target_list = []
        mode = BaseSearchMode.__new__(BaseSearchMode)
        mode.engine = mock_engine

        result = mode._generate_sequential_keys(1, 0)
        assert result == b""

    def test_count_one(self):
        """count=1 生成单个私钥（32字节大端整数）"""
        from src.gpu.search_modes.base_search import BaseSearchMode

        mock_engine = Mock()
        mock_engine._target_list = []
        mode = BaseSearchMode.__new__(BaseSearchMode)
        mode.engine = mock_engine

        result = mode._generate_sequential_keys(5, 1)
        assert len(result) == 32
        assert int.from_bytes(result, "big") == 5

    def test_count_sequence_correctness(self):
        """验证生成的私钥序列连续性"""
        from src.gpu.search_modes.base_search import BaseSearchMode

        mock_engine = Mock()
        mock_engine._target_list = []
        mode = BaseSearchMode.__new__(BaseSearchMode)
        mode.engine = mock_engine

        start = 100
        count = 5
        result = mode._generate_sequential_keys(start, count)
        assert len(result) == count * 32

        for i in range(count):
            key = int.from_bytes(result[i * 32 : (i + 1) * 32], "big")
            assert key == start + i, f"key[{i}] expected {start + i}, got {key}"

    def test_count_large_value(self):
        """大批次生成不报错且长度正确"""
        from src.gpu.search_modes.base_search import BaseSearchMode

        mock_engine = Mock()
        mock_engine._target_list = []
        mode = BaseSearchMode.__new__(BaseSearchMode)
        mode.engine = mock_engine

        count = 10000
        result = mode._generate_sequential_keys(0, count)
        assert len(result) == count * 32

    def test_start_large_value(self):
        """大起始值生成（接近2^256-1）"""
        from src.gpu.search_modes.base_search import BaseSearchMode

        mock_engine = Mock()
        mock_engine._target_list = []
        mode = BaseSearchMode.__new__(BaseSearchMode)
        mode.engine = mock_engine

        large_start = (1 << 255) - 100
        result = mode._generate_sequential_keys(large_start, 3)
        assert len(result) == 96

        first_key = int.from_bytes(result[:32], "big")
        assert first_key == large_start


class TestRangescanWorkerBoundary:
    """_range_scan_worker 边界测试（CPU路径）"""

    def test_single_element_range(self):
        """单元素范围 [n, n] 只扫描一个私钥"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(5, 5, 0)
        assert count == 1, f"单元素范围应返回1，实际{count}"
        engine.stop()

    def test_range_with_invalid_start_zero(self):
        """范围含 k=0 时跳过无效私钥"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(0, 5, 0)
        assert count == 5, f"k=0应跳过，仅5个有效，实际{count}"
        engine.stop()

    def test_range_exactly_one_valid(self):
        """范围 [0, 0] 全部无效返回0"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(0, 0, 0)
        assert count == 0, f"[0,0]无有效私钥，应返回0，实际{count}"
        engine.stop()

    def test_large_single_element_range(self):
        """大值单元素范围正常工作"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        large_val = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140
        count = engine._range_scan_worker(large_val, large_val, 0)
        assert count == 1, f"大值单元素范围应返回1，实际{count}"
        engine.stop()


class TestRangescanMultiWorkerBoundary:
    """range_scan 多worker分配边界测试（CPU路径）"""

    def test_range_smaller_than_workers(self):
        """总范围小于 worker 数时回退到单线程"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=4,
            data_logging_enabled=False,
        )
        engine.range_scan(1, 3)
        stats = engine.get_stats()
        assert stats.total_checked == 3, f"小范围应完整扫描3个私钥，实际{stats.total_checked}"

    def test_range_exactly_equals_workers(self):
        """总范围恰好等于 worker 数"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=4,
            data_logging_enabled=False,
        )
        engine.range_scan(1, 4)
        stats = engine.get_stats()
        assert stats.total_checked == 4, f"应完整扫描4个私钥，实际{stats.total_checked}"

    def test_range_chunk_size_one(self):
        """chunk_size=1 场景（范围仅比worker数多1）"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=4,
            data_logging_enabled=False,
        )
        engine.range_scan(1, 5)
        stats = engine.get_stats()
        assert stats.total_checked == 5, f"应完整扫描5个私钥，实际{stats.total_checked}"

    def test_range_no_overlap_verification(self):
        """多worker分配不重叠（范围[1,1000] max_workers=4）"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=4,
            data_logging_enabled=False,
        )
        engine.range_scan(1, 1000)
        stats = engine.get_stats()
        assert stats.total_checked == 1000, f"无重叠应扫描1000个私钥，实际{stats.total_checked}"

    def test_range_uneven_split(self):
        """范围不能被worker数整除时的剩余分配"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=3,
            data_logging_enabled=False,
        )
        engine.range_scan(1, 10)
        stats = engine.get_stats()
        assert stats.total_checked == 10, f"不均匀分割应扫描全部10个私钥，实际{stats.total_checked}"


@pytest.mark.gpu_kernel
class TestRangescanGPUFirstBatchBoundary:
    """GPU range_scan 第一批发包 off-by-one 修复验证

    通过直接实例化 RangeScanSearchMode 并使用 Mock 引擎来避免
    GPUCollisionEngine 完整初始化（需要真实 pyopencl 环境）。
    标记为 gpu_kernel 测试，无 GPU 环境时自动 skip。
    """

    @staticmethod
    def _make_mock_engine(batch_size):
        """创建 Mock 引擎用于测试 RangeScanSearchMode"""
        mock_engine = Mock()
        mock_engine.batch_size = batch_size
        mock_engine._current_position = 0
        mock_engine._stop_event = Mock()
        mock_engine._stop_event.is_set.return_value = False
        mock_engine._gpu_kernel = Mock()
        mock_engine._gpu_kernel.run_batch.return_value = []
        mock_engine._target_list = []
        mock_engine.stats = Mock()
        mock_engine._last_progress_time = 9999999
        mock_engine._progress_interval_sec = 9999
        mock_engine._batch_size_lock = Mock()
        mock_engine._batch_size_lock.__enter__ = Mock(return_value=None)
        mock_engine._batch_size_lock.__exit__ = Mock(return_value=None)
        mock_engine._consecutive_gpu_errors = 0
        mock_engine._max_gpu_error_retries = 3
        mock_engine._save_checkpoint = Mock()
        mock_engine.on_progress = None
        mock_engine.on_match = None
        mock_engine.on_complete = None
        mock_engine._running = True
        return mock_engine

    def test_first_batch_small_range_smaller_than_batch_size(self):
        """范围小于 batch_size 时不应遗漏最后一个key"""
        from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

        mock_engine = self._make_mock_engine(batch_size=1000)
        batch_sizes = []

        def capture_run_batch(batch_data, actual_size):
            batch_sizes.append(actual_size)
            return []

        mock_engine._gpu_kernel.run_batch.side_effect = capture_run_batch

        mode = RangeScanSearchMode(mock_engine)
        mode.execute(5, 10)

        total_generated = sum(batch_sizes)
        assert total_generated == 6, f"范围[5,10]应生成6个私钥，实际{total_generated}"

    def test_first_batch_range_exactly_equals_batch_size(self):
        """范围恰好等于 batch_size 时全部在首批完成"""
        from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

        mock_engine = self._make_mock_engine(batch_size=10)
        batch_sizes = []

        def capture_run_batch(batch_data, actual_size):
            batch_sizes.append(actual_size)
            return []

        mock_engine._gpu_kernel.run_batch.side_effect = capture_run_batch

        mode = RangeScanSearchMode(mock_engine)
        mode.execute(1, 10)

        total_generated = sum(batch_sizes)
        assert total_generated == 10, f"范围[1,10] batch_size=10 应生成10个，实际{total_generated}"
        assert len(batch_sizes) == 1, f"应在一个批次完成，实际{len(batch_sizes)}批"

    def test_first_batch_range_slightly_larger_than_batch_size(self):
        """范围略大于 batch_size 时分两批完成"""
        from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

        mock_engine = self._make_mock_engine(batch_size=10)
        batch_sizes = []

        def capture_run_batch(batch_data, actual_size):
            batch_sizes.append(actual_size)
            return []

        mock_engine._gpu_kernel.run_batch.side_effect = capture_run_batch

        mode = RangeScanSearchMode(mock_engine)
        mode.execute(1, 15)

        total_generated = sum(batch_sizes)
        assert total_generated == 15, f"范围[1,15] batch_size=10 应生成15个，实际{total_generated}"
        assert len(batch_sizes) == 2, f"应分两批完成，实际{len(batch_sizes)}批"

    def test_first_batch_single_element_range(self):
        """单元素范围（start==end）首批只生成一个私钥"""
        from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

        mock_engine = self._make_mock_engine(batch_size=1000)
        batch_sizes = []

        def capture_run_batch(batch_data, actual_size):
            batch_sizes.append(actual_size)
            return []

        mock_engine._gpu_kernel.run_batch.side_effect = capture_run_batch

        mode = RangeScanSearchMode(mock_engine)
        mode.execute(100, 100)

        total_generated = sum(batch_sizes)
        assert total_generated == 1, f"单元素范围[100,100]应生成1个，实际{total_generated}"

    def test_first_batch_range_multi_batch_exact_fit(self):
        """范围恰好是 batch_size 整数倍时边界正确"""
        from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

        mock_engine = self._make_mock_engine(batch_size=5)
        batch_sizes = []

        def capture_run_batch(batch_data, actual_size):
            batch_sizes.append(actual_size)
            return []

        mock_engine._gpu_kernel.run_batch.side_effect = capture_run_batch

        mode = RangeScanSearchMode(mock_engine)
        mode.execute(1, 10)

        total_generated = sum(batch_sizes)
        assert total_generated == 10, f"范围[1,10] batch_size=5 应生成10个，实际{total_generated}"
        assert len(batch_sizes) == 2, f"应分2批完成（每批5），实际{len(batch_sizes)}批"


class TestCLIValidationBoundary:
    """CLI 参数验证边界测试"""

    def test_range_start_greater_equal_end_rejected(self):
        """Start >= end 被拒绝"""
        from unittest.mock import Mock

        from src.cli.validation import validate_args

        mock_args = Mock()
        mock_args.mode = "range"
        mock_args.start = "0A"
        mock_args.end = "05"
        mock_args.file = None
        mock_args.targets = ["1TestAddr"]
        mock_args.health_check = False
        mock_args.platform_check = False
        mock_args.cleanup = False
        mock_args.validate_addresses = None
        mock_args.examples = False
        mock_args.config_check = False
        mock_args.quick_start = False
        mock_args.duration = 0
        mock_args.checkpoint_interval = 30
        mock_args.use_gpu = False
        mock_args.multi_gpu = False
        mock_args.no_optimize = False
        mock_args.window_size = 8
        mock_args.no_simd = False
        mock_args.no_memory_pool = False
        mock_args.workers = None
        mock_args.dedup = False
        mock_args.dedup_max_size = 1000000
        mock_args.checkpoint = False
        mock_args.batch_size = None
        mock_args.progress_interval = None

        result = validate_args(mock_args)
        assert result is False, "start>=end 应被拒绝"

    def test_range_start_less_than_one_rejected(self):
        """Start < 1 被拒绝"""
        from unittest.mock import Mock

        from src.cli.validation import validate_args

        mock_args = Mock()
        mock_args.mode = "range"
        mock_args.start = "0"
        mock_args.end = "05"
        mock_args.file = None
        mock_args.targets = ["1TestAddr"]
        mock_args.health_check = False
        mock_args.platform_check = False
        mock_args.cleanup = False
        mock_args.validate_addresses = None
        mock_args.examples = False
        mock_args.config_check = False
        mock_args.quick_start = False
        mock_args.duration = 0
        mock_args.checkpoint_interval = 30
        mock_args.use_gpu = False
        mock_args.multi_gpu = False
        mock_args.no_optimize = False
        mock_args.window_size = 8
        mock_args.no_simd = False
        mock_args.no_memory_pool = False
        mock_args.workers = None
        mock_args.dedup = False
        mock_args.dedup_max_size = 1000000
        mock_args.checkpoint = False
        mock_args.batch_size = None
        mock_args.progress_interval = None

        result = validate_args(mock_args)
        assert result is False, "start<1 应被拒绝"

    def test_range_valid_boundary_accepted(self):
        """start=1 end=2 合法范围被接受"""
        from unittest.mock import Mock

        from src.cli.validation import validate_args

        mock_args = Mock()
        mock_args.mode = "range"
        mock_args.start = "1"
        mock_args.end = "2"
        mock_args.file = None
        mock_args.targets = ["1TestAddr"]
        mock_args.health_check = False
        mock_args.platform_check = False
        mock_args.cleanup = False
        mock_args.validate_addresses = None
        mock_args.examples = False
        mock_args.config_check = False
        mock_args.quick_start = False
        mock_args.duration = 0
        mock_args.checkpoint_interval = 30
        mock_args.use_gpu = False
        mock_args.multi_gpu = False
        mock_args.no_optimize = False
        mock_args.window_size = 8
        mock_args.no_simd = False
        mock_args.no_memory_pool = False
        mock_args.workers = None
        mock_args.dedup = False
        mock_args.dedup_max_size = 1000000
        mock_args.checkpoint = False
        mock_args.batch_size = None
        mock_args.progress_interval = None

        result = validate_args(mock_args)
        assert result is True, "start=1 end=2 应被接受"
