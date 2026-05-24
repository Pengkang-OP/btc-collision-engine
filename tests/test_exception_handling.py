#!/usr/bin/env python3
"""异常处理优化的单元测试

测试异常分类、统计指标、公共方法等
"""

from unittest.mock import MagicMock, patch

import pytest

from src.collision.collision_stats import CollisionStats
from src.utils.exception_handler import ExceptionHandler


class TestCollisionStatsErrorTracking:
    """异常统计指标测试"""

    def test_initial_error_counts(self):
        """测试初始错误计数为0"""
        stats = CollisionStats()
        assert stats.gpu_errors == 0
        assert stats.worker_errors == 0
        assert stats.resource_errors == 0

    def test_record_gpu_error(self):
        """测试记录GPU错误"""
        stats = CollisionStats()

        stats.record_gpu_error(is_resource_error=True)
        assert stats.gpu_errors == 1
        assert stats.resource_errors == 1

        stats.record_gpu_error(is_resource_error=False)
        assert stats.gpu_errors == 2
        assert stats.resource_errors == 1  # 不增加

    def test_record_worker_error(self):
        """测试记录工作线程错误"""
        stats = CollisionStats()

        stats.record_worker_error()
        assert stats.worker_errors == 1

        stats.record_worker_error()
        assert stats.worker_errors == 2

    def test_error_stats_thread_safety(self):
        """测试异常统计的线程安全性"""
        import threading

        stats = CollisionStats()
        num_threads = 10
        iterations = 100

        def increment_gpu_errors():
            for _ in range(iterations):
                stats.record_gpu_error(is_resource_error=True)

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=increment_gpu_errors)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        expected = num_threads * iterations
        assert stats.gpu_errors == expected
        assert stats.resource_errors == expected


class TestExceptionClassification:
    """异常分类逻辑测试"""

    def test_keyboard_interrupt_not_caught_by_exception_handler(self):
        """测试KeyboardInterrupt不会被普通Exception处理吞掉"""
        caught = False
        try:
            try:
                raise KeyboardInterrupt
            except Exception as e:  # noqa: F841
                caught = True
        except KeyboardInterrupt:
            assert not caught, "KeyboardInterrupt不应该被Exception捕获"

    def test_exception_hierarchy(self):
        """测试异常层次结构"""
        assert issubclass(RuntimeError, Exception)
        assert issubclass(ValueError, Exception)
        assert issubclass(TypeError, Exception)
        assert issubclass(OverflowError, Exception)

        assert not issubclass(KeyboardInterrupt, Exception)
        assert not issubclass(SystemExit, Exception)


class TestWorkerErrorTracking:
    """工作线程异常统计测试"""

    def test_worker_error_recording(self):
        """测试工作线程错误记录"""
        stats = CollisionStats()

        stats.record_worker_error()
        assert stats.worker_errors == 1

        stats.record_worker_error()
        assert stats.worker_errors == 2

    def test_stats_object_accessible(self):
        """测试统计对象可正常创建和访问"""
        stats = CollisionStats()
        assert stats is not None
        assert stats.worker_errors == 0
        assert stats.gpu_errors == 0


class TestSnapshotCompleteness:
    """快照完整性测试（回归测试）"""

    def test_snapshot_includes_basic_stats(self):
        """测试快照包含基础统计属性"""
        stats = CollisionStats()
        stats._start_time = 1000.0
        stats._total_keys = 1000

        # 添加匹配
        test_private_key = b"\x01" * 32
        stats.add_match(test_private_key, "1TestAddress1")
        stats.add_match(test_private_key, "1TestAddress2")

        snap = stats.snapshot()

        assert snap.total_keys_checked == 1000
        assert snap.total_matches == 2
        assert snap.elapsed_seconds >= 0
        assert snap.throughput > 0

    def test_snapshot_isolation(self):
        """测试快照与原始对象隔离（深拷贝）"""
        stats = CollisionStats()

        test_private_key = b"\x01" * 32
        stats.add_match(test_private_key, "1TestAddress")

        snap = stats.snapshot()

        # 修改原始对象
        stats.matches.clear()

        # 验证快照不受影响
        assert len(snap.matches) == 1
        assert snap.matches[0]["address"] == "1TestAddress"

    def test_snapshot_thread_safety(self):
        """测试快照的线程安全性"""
        import threading

        stats = CollisionStats()
        stats._total_keys = 1000

        errors = []

        def create_snapshot():
            try:
                for _ in range(100):
                    snap = stats.snapshot()
                    assert snap.total_keys_checked == 1000
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_snapshot) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发创建快照时发生错误: {errors}"


# ============================================================
# ExceptionHandler 单元测试
# ============================================================


class TestHandleEngineError:
    """测试 handle_engine_error — 7条分支"""

    def test_runtime_error(self):
        """RuntimeError 分支: 记录 warning + record_worker_error"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", RuntimeError("test"), stats, "处理")
        mock_logger.warning.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_value_error(self):
        """ValueError 分支: 同 RuntimeError 处理"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("GPU", ValueError("bad"), stats)
        mock_logger.warning.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_keyboard_interrupt(self):
        """KeyboardInterrupt 分支: 正确重新抛出 (raise error from None)"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            with pytest.raises(KeyboardInterrupt):
                ExceptionHandler.handle_engine_error("CPU", KeyboardInterrupt())
        mock_logger.info.assert_called_once()

    def test_memory_error(self):
        """MemoryError 分支: 记录 critical + record_error"""
        stats = MagicMock()
        stats.record_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("GPU", MemoryError("oom"), stats)
        mock_logger.critical.assert_called_once()
        stats.record_error.assert_called_once()

    def test_import_error(self):
        """ImportError 分支: 记录 error + record_worker_error"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("GPU", ImportError("no module"), stats)
        mock_logger.error.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_os_error(self):
        """OSError 分支: 记录 error + record_worker_error"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", OSError("io"), stats)
        mock_logger.error.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_unknown_error(self):
        """未知错误分支: 记录 error + record_worker_error"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", KeyError("unknown"), stats)
        mock_logger.error.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_no_stats(self):
        """无 stats 参数不崩溃"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", RuntimeError("no stats"))
        mock_logger.warning.assert_called_once()

    def test_stats_without_method(self):
        """Stats 无 record_worker_error 方法时也不崩溃"""
        stats = MagicMock(spec=[])
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", RuntimeError("x"), stats)
        mock_logger.warning.assert_called_once()


class TestHandleGpuError:
    """测试 handle_gpu_error — 5条分支"""

    def test_resource_error(self):
        """资源错误分支: 记录 warning + record_gpu_error(resource=True)"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_gpu_error(
                "随机碰撞", RuntimeError("out of resources"), stats,
            )
        assert result is True
        mock_logger.warning.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)

    def test_non_resource_runtime_error(self):
        """非资源 RuntimeError: record_gpu_error(resource=False)"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("范围扫描", RuntimeError("kernel fail"), stats)
        mock_logger.warning.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)

    def test_memory_error(self):
        """MemoryError: 记录 critical + resource=True"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("暴力穷举", MemoryError("oom"), stats)
        mock_logger.critical.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)

    def test_type_error_and_overflow(self):
        """TypeError/OverflowError: 记录 warning + wif_encode_error"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        stats.record_wif_encode_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("随机碰撞", TypeError("bad type"), stats)
        mock_logger.warning.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        stats.record_wif_encode_error.assert_called_once()

    def test_unknown_error(self):
        """未知错误: 记录 error"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("随机碰撞", KeyError("?"), stats)
        mock_logger.error.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)

    def test_no_stats(self):
        """无 stats 也不崩溃"""
        result = ExceptionHandler.handle_gpu_error("测试", RuntimeError("no stats"))
        assert result is True


class TestHandleGpuAsyncError:
    """测试 handle_gpu_async_error — 4条分支"""

    def test_runtime_error_returns_true(self):
        """RuntimeError → 返回 True (可回退)"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_gpu_async_error(RuntimeError("cl error"), "内核执行")
        assert result is True
        mock_logger.warning.assert_called_once()

    def test_memory_error_returns_true(self):
        """MemoryError → 返回 True"""
        result = ExceptionHandler.handle_gpu_async_error(MemoryError("oom"), "缓冲清理")
        assert result is True

    def test_value_type_index_error_returns_true(self):
        """ValueError/TypeError/IndexError → 返回 True"""
        for err_cls in [ValueError, TypeError, IndexError]:
            result = ExceptionHandler.handle_gpu_async_error(err_cls("data"), "结果回读")
            assert result is True

    def test_attribute_error_returns_true(self):
        """AttributeError → 返回 True"""
        result = ExceptionHandler.handle_gpu_async_error(AttributeError("no attr"), "种子写入")
        assert result is True

    def test_unknown_error_returns_true(self):
        """未知错误 → 返回 True (保守策略), 记录 warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_gpu_async_error(KeyError("?"), "内核执行")
        assert result is True
        mock_logger.warning.assert_called_once()


class TestHandleClResourceError:
    """测试 handle_cl_resource_error"""

    def test_resource_exhausted(self):
        """资源耗尽 → 返回 True, 记录 warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_cl_resource_error(
                RuntimeError("out of resources"), "buffer",
            )
        assert result is True
        mock_logger.warning.assert_called_once()

    def test_non_resource_error(self):
        """非资源错误 → 返回 False, 记录 error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_cl_resource_error(
                RuntimeError("unknown kernel error"), "kernel",
            )
        assert result is False
        mock_logger.error.assert_called_once()

    def test_cl_out_of_host_memory(self):
        """CL_OUT_OF_HOST_MEMORY → 识别为资源耗尽"""
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("cl_out_of_host_memory"), "buffer",
        )
        assert result is True

    def test_invalid_buffer_size(self):
        """Invalid buffer size → 识别为资源耗尽"""
        result = ExceptionHandler.handle_cl_resource_error(RuntimeError("invalid buffer size"), "buffer")
        assert result is True


class TestHandleGpuCleanupError:
    """测试 handle_gpu_cleanup_error"""

    def test_runtime_error(self):
        """RuntimeError → warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_cleanup_error(RuntimeError("cl cleanup"), "compute_queue")
        mock_logger.warning.assert_called_once()

    def test_os_error(self):
        """OSError → warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_cleanup_error(OSError("io cleanup"), "seed_buffer")
        mock_logger.warning.assert_called_once()

    def test_unknown_error(self):
        """未知错误 → warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_cleanup_error(KeyError("?"), "precomp_buffer")
        mock_logger.warning.assert_called_once()


class TestHandleConfigError:
    """测试 handle_config_error"""

    def test_file_not_found(self):
        """FileNotFoundError → warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_config_error(FileNotFoundError("no file"), "ConfigManager")
        mock_logger.warning.assert_called_once()

    def test_value_error(self):
        """ValueError → error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_config_error(ValueError("bad config"), "CryptoConfig")
        mock_logger.error.assert_called_once()

    def test_permission_error(self):
        """PermissionError 是 OSError 子类 → 被 FileNotFoundError/IOError 先捕获"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_config_error(PermissionError("denied"), "GPUConfig")
        mock_logger.warning.assert_called_once()

    def test_unknown_error(self):
        """未知错误 → exception"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_config_error(KeyError("?"), "ConfigManager")
        mock_logger.exception.assert_called_once()


class TestHandleFileError:
    """测试 handle_file_error"""

    def test_file_not_found(self):
        """FileNotFoundError → error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_file_error(FileNotFoundError("no file"), "读取", "/path/to/file")
        mock_logger.error.assert_called_once()

    def test_permission_error(self):
        """PermissionError → error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_file_error(PermissionError("denied"), "写入", "/path/to/file")
        mock_logger.error.assert_called_once()

    def test_io_error(self):
        """IOError → error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_file_error(OSError("io fail"), "删除", "/path/to/file")
        mock_logger.error.assert_called_once()

    def test_unknown_error(self):
        """未知错误 → exception"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_file_error(KeyError("?"), "读取", "/path/to/file")
        mock_logger.exception.assert_called_once()
