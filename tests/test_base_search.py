#!/usr/bin/env python3
"""基础搜索模式 (BaseSearchMode) 单元测试

覆盖：
- BaseSearchMode 初始化（引擎引用）
- _generate_sequential_keys 连续私钥生成
- _execute_batch_loop 通用批处理循环
  - 正常流程：GPU batch 执行 + 匹配处理
  - 停止条件：_stop_event / stop_condition_fn
  - 异常处理：OOM、超时、设备丢失
  - 连续错误计数和最大重试
  - key_extractor_fn PRNG 模式
- 边界值：空数据、零批次大小、key_index 越界
"""

from unittest.mock import MagicMock

import pytest

from src.gpu.search_modes.base_search import BaseSearchMode

# ============================================================================
# 辅助函数
# ============================================================================


def _make_engine_stub(**kwargs):
    """创建 GPUCollisionEngine stub"""
    engine = MagicMock()
    engine._stop_event = MagicMock()
    engine._stop_event.is_set.return_value = kwargs.get("stop_event_set", False)
    engine._gpu_kernel = MagicMock()
    engine._gpu_kernel.run_batch.return_value = kwargs.get("run_batch_return", [])
    engine.stats = MagicMock()
    engine.stats.update = MagicMock()
    engine.stats.add_match = MagicMock()
    engine.stats.snapshot = MagicMock(return_value={})
    engine.on_match = kwargs.get("on_match", MagicMock())
    engine.on_progress = kwargs.get("on_progress")
    engine._target_list = kwargs.get("_target_list", ["target_addr"])
    engine._batch_size = kwargs.get("_batch_size", 1000)
    engine._batch_size_lock = MagicMock()
    # 支持上下文管理器 with engine._batch_size_lock:
    engine._batch_size_lock.__enter__ = MagicMock(return_value=None)
    engine._batch_size_lock.__exit__ = MagicMock(return_value=None)
    engine._consecutive_gpu_errors = kwargs.get("_consecutive_gpu_errors", 0)
    engine._max_gpu_error_retries = kwargs.get("_max_gpu_error_retries", 5)
    engine._last_progress_time = kwargs.get("_last_progress_time", 0)
    engine._progress_interval_sec = kwargs.get("_progress_interval_sec", 0.5)
    engine._save_checkpoint = MagicMock()
    engine._running = kwargs.get("_running", True)
    # CALL-1: 显式设置 _match_callback_timeout 避免 MagicMock hasattr 陷阱
    # (MagicMock 的 hasattr 永远返回 True 但属性值为 MagicMock 对象，
    #  导致 invoke_with_timeout 中 timeout <= 0 比较抛出 TypeError)
    engine._match_callback_timeout = kwargs.get("_match_callback_timeout", 5)
    return engine


# ============================================================================
# 初始化测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestBaseSearchModeInit:
    """BaseSearchMode 初始化测试"""

    def test_init_stores_engine_reference(self):
        """测试初始化存储引擎引用"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        assert mode.engine is engine

    def test_init_does_not_copy_state(self):
        """测试初始化不复制引擎状态（通过引用访问）"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        # 修改原始引擎，mode 应反映变化
        engine._running = False
        assert mode.engine._running is False


# ============================================================================
# _generate_sequential_keys 测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestGenerateSequentialKeys:
    """连续私钥生成测试"""

    def test_generate_single_key(self):
        """测试生成单个私钥"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        keys = mode._generate_sequential_keys(1, 1)
        assert len(keys) == 32
        # 验证值：私钥 1 的大端 32 字节
        expected = (1).to_bytes(32, "big")
        assert keys == expected

    def test_generate_zero_key(self):
        """测试生成私钥 0"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        keys = mode._generate_sequential_keys(0, 1)
        expected = (0).to_bytes(32, "big")
        assert keys == expected

    def test_generate_multiple_keys(self):
        """测试生成多个私钥"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        count = 5
        keys = mode._generate_sequential_keys(10, count)
        assert len(keys) == count * 32
        # 验证第一个和最后一个
        first = keys[0:32]
        last = keys[-32:]
        assert first == (10).to_bytes(32, "big")
        assert last == (10 + count - 1).to_bytes(32, "big")

    def test_generate_large_count(self):
        """测试生成大量私钥"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        count = 10000
        keys = mode._generate_sequential_keys(1000000, count)
        assert len(keys) == count * 32

    def test_generate_keys_sequential(self):
        """测试生成的私钥是连续序列"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        start = 42
        count = 10
        keys = mode._generate_sequential_keys(start, count)
        for i in range(count):
            chunk = keys[i * 32 : (i + 1) * 32]
            expected_int = start + i
            assert chunk == expected_int.to_bytes(32, "big"), f"Key {i} mismatch"

    def test_generate_large_start_value(self):
        """测试大起始值"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        start = 2**255  # 接近最大值
        keys = mode._generate_sequential_keys(start, 1)
        assert len(keys) == 32

    def test_generate_max_range(self):
        """测试接近 2**256-1 的起始值"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        start = 2**256 - 2
        keys = mode._generate_sequential_keys(start, 2)
        assert len(keys) == 64
        # 最后一个应该是 2**256 - 1
        last = int.from_bytes(keys[-32:], "big")
        assert last == 2**256 - 1

    def test_generate_zero_count_returns_empty(self):
        """测试生成 0 个私钥返回空字节串"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        keys = mode._generate_sequential_keys(0, 0)
        assert keys == b""

    # ── 确定性测试 ──

    def test_deterministic_output(self):
        """测试相同输入产生相同输出"""
        engine = _make_engine_stub()
        mode = BaseSearchMode(engine)
        keys1 = mode._generate_sequential_keys(100, 5)
        keys2 = mode._generate_sequential_keys(100, 5)
        assert keys1 == keys2


# ============================================================================
# _execute_batch_loop 正常流程
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestExecuteBatchLoopNormal:
    """批处理循环正常流程测试"""

    def test_normal_execution_single_batch(self):
        """测试单批次正常执行"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, True]  # 1 iter, then stop
        engine._gpu_kernel.run_batch.return_value = []  # no matches

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 验证一次批处理完成
        assert batch_count == 100
        engine._gpu_kernel.run_batch.assert_called_once_with(b"keys" * 8, 100)

    def test_normal_execution_with_matches(self):
        """测试匹配结果处理（无 key_extractor_fn）"""
        engine = _make_engine_stub(_target_list=["addr0", "addr1"])
        engine._stop_event.is_set.side_effect = [False, True]

        mode = BaseSearchMode(engine)
        # 返回一个匹配：key_index=0, target_index=1
        engine._gpu_kernel.run_batch.return_value = [{"key_index": 0, "target_index": 1}]

        def key_gen():
            # 生成两个私钥（每个 32 字节）
            key_data = (0).to_bytes(32, "big") + (1).to_bytes(32, "big")
            return (key_data, 2)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 验证匹配回调
        engine.stats.add_match.assert_called_once()
        engine.on_match.assert_called_once()
        assert batch_count == 2

    def test_normal_execution_multiple_batches(self):
        """测试多批次执行"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, False, False, True]

        mode = BaseSearchMode(engine)

        call_count = 0

        def key_gen():
            nonlocal call_count
            call_count += 1
            return (f"batch_{call_count}".encode() * 11, 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 300  # 3 batches * 100

    def test_empty_data_breaks_loop(self):
        """测试空 batch_data 停止循环"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, True]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"", 0)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 0
        engine._gpu_kernel.run_batch.assert_not_called()

    def test_none_generator_breaks_loop(self):
        """测试 key_gen 返回 None 停止循环"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.return_value = False

        mode = BaseSearchMode(engine)

        def key_gen():
            return None

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 0

    def test_zero_batch_size_breaks_loop(self):
        """测试 actual_batch_size=0 停止循环"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.return_value = False

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"data", 0)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 0


# ============================================================================
# _execute_batch_loop 停止条件
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestExecuteBatchLoopStopConditions:
    """停止条件测试"""

    def test_stop_event_checked(self):
        """测试 _stop_event 被检查"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.return_value = True

        mode = BaseSearchMode(engine)

        def key_gen():
            pytest.fail("Should not be called")
            return (b"", 0)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 0

    def test_stop_condition_fn(self):
        """测试自定义停止条件"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, True]

        mode = BaseSearchMode(engine)

        def stop_cond():
            return True  # 立即停止

        def key_gen():
            pytest.fail("Should not be called due to stop condition")
            return (b"", 0)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
            stop_condition_fn=stop_cond,
        )

        assert batch_count == 0

    def test_stop_condition_after_batch(self):
        """测试批处理后停止条件满足"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, False, True]

        mode = BaseSearchMode(engine)

        call_count = 0

        def stop_cond():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # 第一次迭代后停止

        def key_gen():
            return (b"keys" * 8, 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
            stop_condition_fn=stop_cond,
        )

        assert batch_count == 100


# ============================================================================
# _execute_batch_loop 异常处理
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestExecuteBatchLoopErrors:
    """异常处理测试"""

    def test_oom_reduces_batch_size(self):
        """测试 OOM 时缩减 batch_size"""
        engine = _make_engine_stub(_batch_size=4096)
        engine._stop_event.is_set.side_effect = [False, False, True]
        engine._gpu_kernel.run_batch.side_effect = [
            MemoryError("out of memory"),  # 第一次 OOM
            [],  # 第二次成功
        ]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, engine._batch_size)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # batch_size 应从 4096 减半到 2048
        assert engine._batch_size == 2048

    def test_oom_minimum_batch_size(self):
        """测试 OOM 时最小 batch_size 为 1024"""
        engine = _make_engine_stub(_batch_size=1024)
        engine._stop_event.is_set.side_effect = [False, True]
        engine._gpu_kernel.run_batch.side_effect = MemoryError("mem_object_allocation_failure")

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, engine._batch_size)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 最小为 1024，不再缩减
        assert engine._batch_size == 1024

    def test_timeout_continues(self):
        """测试超时继续执行"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, False, True]
        engine._gpu_kernel.run_batch.side_effect = [
            Exception("command_execution timeout"),  # 超时
            [],  # 恢复成功
        ]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 100

    def test_device_lost_triggers_recovery(self):
        """测试设备丢失触发恢复"""
        engine = _make_engine_stub()
        engine._recovery_manager = MagicMock()
        engine._recovery_manager.handle_gpu_failure.return_value = True
        engine.device_index = 0

        engine._stop_event.is_set.side_effect = [False, False, True]
        engine._gpu_kernel.run_batch.side_effect = [
            Exception("device lost"),  # 设备丢失
            [],  # 恢复后成功
        ]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        engine._recovery_manager.handle_gpu_failure.assert_called_once()
        assert batch_count == 100

    def test_device_lost_recovery_failure_stops(self):
        """测试设备恢复失败时停止引擎"""
        engine = _make_engine_stub()
        engine._recovery_manager = MagicMock()
        engine._recovery_manager.handle_gpu_failure.return_value = False
        engine.device_index = 0
        engine._stop_event.is_set.return_value = False
        engine._gpu_kernel.run_batch.side_effect = Exception("device lost and not found")

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert engine._running is False

    def test_max_consecutive_errors_stops_engine(self):
        """测试最大连续错误数达到上限时停止引擎"""
        engine = _make_engine_stub(_consecutive_gpu_errors=4, _max_gpu_error_retries=5)
        engine._stop_event.is_set.return_value = False
        engine._gpu_kernel.run_batch.side_effect = RuntimeError("random GPU error")

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 连续错误达到上限，引擎应停止
        assert engine._running is False


# ============================================================================
# _execute_batch_loop PRNG 模式 (key_extractor_fn)
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestExecuteBatchLoopPRNG:
    """PRNG 模式 key_extractor_fn 测试"""

    def test_prng_extracts_correct_key(self):
        """测试 PRNG 模式正确提取私钥"""
        engine = _make_engine_stub(_target_list=["addr0"])
        engine._stop_event.is_set.side_effect = [False, True]
        engine._gpu_kernel.run_batch.return_value = [{"key_index": 5, "target_index": 0}]

        mode = BaseSearchMode(engine)

        # key_extractor_fn: 从 key_index 计算私钥
        def extract_key(batch_data, key_index):
            return (key_index).to_bytes(32, "big")

        def key_gen():
            return (b"seed_data_32_bytes_long!!!!", 100)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
            key_extractor_fn=extract_key,
        )

        assert batch_count == 100
        engine.stats.add_match.assert_called_once()

    def test_prng_key_index_out_of_range(self):
        """测试 PRNG 模式 key_index 越界跳过"""
        engine = _make_engine_stub(_target_list=["addr0"])
        engine._stop_event.is_set.side_effect = [False, True]
        # key_index=10，但 batch_data 只有 32 字节 → 越界
        engine._gpu_kernel.run_batch.return_value = [{"key_index": 10, "target_index": 0}]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"X" * 32, 100)  # 仅 32 字节数据

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
            # 不提供 key_extractor_fn → 使用默认路径，会越界
        )

        # 应跳过越界匹配
        assert batch_count == 100


# ============================================================================
# 进度回调测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestProgressCallback:
    """进度回调测试"""

    def test_progress_callback_triggered(self):
        """测试进度回调被触发"""
        engine = _make_engine_stub(
            on_progress=MagicMock(),
            _last_progress_time=0,
            _progress_interval_sec=0.0,  # 始终触发
        )
        engine._stop_event.is_set.side_effect = [False, True]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        engine.on_progress.assert_called_once()
        engine._save_checkpoint.assert_called_once_with(100)

    def test_progress_not_triggered_before_interval(self):
        """测试进度间隔未到时不被触发"""
        import time

        engine = _make_engine_stub(
            on_progress=MagicMock(),
            _last_progress_time=time.time() + 100,  # 未来时间
            _progress_interval_sec=0.5,
        )
        engine._stop_event.is_set.side_effect = [False, True]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 100)

        mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 进度不应被触发
        engine.on_progress.assert_not_called()


# ============================================================================
# 边界值测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestBaseSearchBoundary:
    """BaseSearchMode 边界值测试"""

    def test_large_batch_count_accumulation(self):
        """测试大量批次计数累积"""
        engine = _make_engine_stub()
        engine._stop_event.is_set.side_effect = [False, False, False, True]

        mode = BaseSearchMode(engine)

        def key_gen():
            return (b"keys" * 8, 1000000)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        assert batch_count == 3000000

    def test_match_without_on_match_callback(self):
        """测试无 on_match 回调时仍然正常处理匹配"""
        engine = _make_engine_stub(
            _target_list=["addr0"],
            on_match=None,
        )
        engine._stop_event.is_set.side_effect = [False, True]
        engine._gpu_kernel.run_batch.return_value = [{"key_index": 0, "target_index": 0}]

        mode = BaseSearchMode(engine)

        def key_gen():
            key_data = (42).to_bytes(32, "big")
            return (key_data, 1)

        batch_count = mode._execute_batch_loop(
            key_generator_fn=key_gen,
            mode_name="test",
        )

        # 不应崩溃
        engine.stats.add_match.assert_called_once()
        assert batch_count == 1
