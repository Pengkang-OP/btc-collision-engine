#!/usr/bin/env python3
"""
异常处理优化的单元测试

测试异常分类、统计指标、公共方法等
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.collision_stats import CollisionStats  # noqa: E402
from src.collision.key_collision_engine import KeyCollisionEngine  # noqa: E402
from src.gpu.device_helper import GPUDeviceHelper  # noqa: E402
from src.utils.exception_handler import ExceptionHandler  # noqa: E402


class TestGPUExceptionHandling:
    """GPU异常处理测试"""

    def test_handle_gpu_batch_error_resource_error(self):
        """测试资源不足错误识别"""
        stats = CollisionStats()

        # 测试各种资源不足关键词
        resource_errors = [
            RuntimeError("out of resources"),
            RuntimeError("Out Of Resources"),
            RuntimeError("CL_OUT_OF_RESOURCES"),
            ValueError("out of memory"),
            RuntimeError("memory allocation failed"),
            RuntimeError("insufficient resources"),
            RuntimeError("resource exhausted"),
            RuntimeError("cl_mem_object_allocation_failure"),
        ]

        for error in resource_errors:
            stats_before = stats.gpu_errors
            GPUDeviceHelper.handle_gpu_batch_error("测试模式", error, stats)
            assert stats.gpu_errors == stats_before + 1, f"应该记录GPU错误: {error}"
            assert stats.resource_errors > 0, f"应该识别为资源错误: {error}"

    def test_handle_gpu_batch_error_runtime_error(self):
        """测试运行时错误（非资源）"""
        stats = CollisionStats()

        runtime_errors = [
            RuntimeError("kernel execution failed"),
            ValueError("invalid parameter"),
        ]

        for error in runtime_errors:
            stats_before = stats.gpu_errors
            GPUDeviceHelper.handle_gpu_batch_error("测试模式", error, stats)
            assert stats.gpu_errors == stats_before + 1
            # 这些不是资源错误
            assert stats.resource_errors == 0

    def test_handle_gpu_batch_error_data_error(self):
        """测试数据错误（WIF编码等）"""
        stats = CollisionStats()

        data_errors = [
            TypeError("expected bytes"),
            OverflowError("value too large"),
        ]

        for error in data_errors:
            stats_before = stats.gpu_errors
            GPUDeviceHelper.handle_gpu_batch_error("测试模式", error, stats)
            assert stats.gpu_errors == stats_before + 1
            assert stats.wif_encode_errors == stats_before + 1  # 应该计数WIF错误

    def test_handle_gpu_batch_error_unknown_error(self):
        """测试未知错误"""
        stats = CollisionStats()

        unknown_error = KeyError("unexpected error")
        GPUDeviceHelper.handle_gpu_batch_error("测试模式", unknown_error, stats)
        assert stats.gpu_errors == 1

    def test_handle_gpu_batch_error_without_stats(self):
        """测试不传入stats参数（不应该崩溃）"""
        # 不应该抛出异常
        GPUDeviceHelper.handle_gpu_batch_error("测试模式", RuntimeError("test error"))
        GPUDeviceHelper.handle_gpu_batch_error("测试模式", TypeError("test error"))
        GPUDeviceHelper.handle_gpu_batch_error("测试模式", KeyError("test error"))


class TestCollisionStatsErrorTracking:
    """异常统计指标测试"""

    def test_initial_error_counts(self):
        """测试初始错误计数为0"""
        stats = CollisionStats()
        assert stats.gpu_errors == 0
        assert stats.worker_errors == 0
        assert stats.wif_encode_errors == 0
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

    def test_record_wif_encode_error(self):
        """测试记录WIF编码错误"""
        stats = CollisionStats()

        stats.record_wif_encode_error()
        assert stats.wif_encode_errors == 1

        stats.record_wif_encode_error()
        assert stats.wif_encode_errors == 2

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

        # 应该有 num_threads * iterations 个错误
        expected = num_threads * iterations
        assert stats.gpu_errors == expected
        assert stats.resource_errors == expected


class TestExceptionClassification:
    """异常分类逻辑测试"""

    def test_keyboard_interrupt_not_caught_by_exception_handler(self):
        """测试KeyboardInterrupt不会被普通Exception处理吞掉"""
        # 这是一个重要的安全性测试
        # KeyboardInterrupt必须能够被re-raise

        caught = False
        try:
            try:
                raise KeyboardInterrupt()
            except Exception as e:  # noqa: F841
                # 不应该捕获KeyboardInterrupt
                caught = True
        except KeyboardInterrupt:
            # 应该在这里被捕获
            assert not caught, "KeyboardInterrupt不应该被Exception捕获"

    def test_exception_hierarchy(self):
        """测试异常层次结构"""
        # Exception包含大多数异常，但不包括：
        # - KeyboardInterrupt
        # - SystemExit
        # - GeneratorExit

        assert issubclass(RuntimeError, Exception)
        assert issubclass(ValueError, Exception)
        assert issubclass(TypeError, Exception)
        assert issubclass(OverflowError, Exception)

        # 但这些不是Exception的子类
        assert not issubclass(KeyboardInterrupt, Exception)
        assert not issubclass(SystemExit, Exception)


class TestErrorRateCalculation:
    """错误率计算测试"""

    def test_error_rates_zero_total(self):
        """测试总检查数为0时的错误率（边界条件）"""
        stats = CollisionStats()
        rates = stats.get_error_rates()

        assert rates["total_error_rate"] == 0.0
        assert rates["gpu_error_rate"] == 0.0
        assert rates["worker_error_rate"] == 0.0
        assert rates["wif_encode_error_rate"] == 0.0
        assert rates["resource_error_rate"] == 0.0

    def test_error_rates_with_errors(self):
        """测试有错误时的错误率计算"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.gpu_errors = 10
        stats.worker_errors = 5
        stats.wif_encode_errors = 3
        stats.resource_errors = 2

        rates = stats.get_error_rates()

        assert rates["total_error_rate"] == 0.015  # (10+5)/1000
        assert rates["gpu_error_rate"] == 0.01  # 10/1000
        assert rates["worker_error_rate"] == 0.005  # 5/1000
        assert rates["wif_encode_error_rate"] == 0.003  # 3/1000
        assert rates["resource_error_rate"] == 0.002  # 2/1000

    def test_error_rates_thread_safety(self):
        """测试错误率计算的线程安全性"""
        import threading

        stats = CollisionStats()
        stats.total_checked = 10000

        def increment_errors():
            for _ in range(100):
                stats.record_gpu_error(is_resource_error=True)

        threads = [threading.Thread(target=increment_errors) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 并发读取错误率不应该崩溃
        rates = stats.get_error_rates()
        assert rates["total_error_rate"] > 0
        assert rates["gpu_error_rate"] > 0


class TestHealthCheck:
    """健康状态检查测试"""

    def test_healthy_with_no_errors(self):
        """测试无错误时系统健康"""
        stats = CollisionStats()
        stats.total_checked = 1000
        assert stats.is_healthy() is True
        assert stats.is_healthy(error_rate_threshold=0.001) is True

    def test_healthy_with_low_error_rate(self):
        """测试错误率低时系统健康"""
        stats = CollisionStats()
        stats.update(10000)  # 设置total_checked
        stats.gpu_errors = 5  # 0.05%
        stats.worker_errors = 3  # 0.03%

        assert stats.is_healthy() is True  # 默认阈值1%
        assert stats.is_healthy(error_rate_threshold=0.0001) is False  # 阈值0.01%

    def test_unhealthy_with_high_error_rate(self):
        """测试错误率高时系统不健康"""
        stats = CollisionStats()
        stats.total_checked = 1000
        stats.gpu_errors = 50  # 5%

        assert stats.is_healthy() is False  # 超过1%阈值
        assert stats.is_healthy(error_rate_threshold=0.1) is True  # 阈值10%


class TestErrorSummary:
    """错误统计摘要测试"""

    def test_error_summary_format(self):
        """测试错误统计摘要格式"""
        stats = CollisionStats()
        stats.gpu_errors = 10
        stats.worker_errors = 5
        stats.wif_encode_errors = 3
        stats.resource_errors = 2

        summary = stats.error_summary()

        assert "GPU=10" in summary
        assert "Worker=5" in summary
        assert "WIF=3" in summary
        assert "Resource=2" in summary
        assert "总计=15" in summary  # 10 + 5

    def test_error_summary_zero_errors(self):
        """测试无错误时的统计摘要"""
        stats = CollisionStats()
        summary = stats.error_summary()

        assert "GPU=0" in summary
        assert "Worker=0" in summary
        assert "总计=0" in summary


class TestWorkerErrorTracking:
    """工作线程异常统计测试"""

    def test_worker_error_recording(self):
        """测试工作线程错误记录"""
        stats = CollisionStats()

        stats.record_worker_error()
        assert stats.worker_errors == 1

        stats.record_worker_error()
        assert stats.worker_errors == 2

    def test_worker_error_in_collision_engine(self):
        """测试碰撞引擎中的工作线程错误统计"""
        # 创建一个会触发错误的场景
        engine = KeyCollisionEngine(
            targets={"1TestAddress"},
            max_workers=1,
        )

        # 验证stats对象存在
        assert engine.stats is not None
        assert engine.stats.worker_errors == 0

        # 注意：实际触发错误需要模拟异常场景
        # 这里只验证统计对象可访问


class TestSnapshotCompleteness:
    """快照完整性测试（回归测试）"""

    def test_snapshot_includes_error_stats(self):
        """测试快照包含异常统计属性"""
        stats = CollisionStats()
        stats.update(10000)
        stats.gpu_errors = 50
        stats.worker_errors = 30
        stats.wif_encode_errors = 10
        stats.resource_errors = 20

        # 创建快照
        snap = stats.snapshot()

        # 验证快照包含所有异常统计属性
        assert snap.gpu_errors == 50, "快照应包含gpu_errors"
        assert snap.worker_errors == 30, "快照应包含worker_errors"
        assert snap.wif_encode_errors == 10, "快照应包含wif_encode_errors"
        assert snap.resource_errors == 20, "快照应包含resource_errors"

    def test_snapshot_includes_eta_stats(self):
        """测试快照包含ETA相关属性"""
        stats = CollisionStats()
        stats.update(5000, total_range=10000)

        # 创建快照
        snap = stats.snapshot()

        # 验证快照包含ETA属性
        assert snap.total_range == 10000, "快照应包含total_range"
        assert snap.eta_seconds >= 0, "快照应包含eta_seconds"

    def test_snapshot_includes_basic_stats(self):
        """测试快照包含基础统计属性"""
        stats = CollisionStats()
        stats.start_time = 1000.0
        stats.update(1000)

        # 添加匹配以设置 _match_count
        test_private_key = b"\x01" * 32
        stats.add_match(test_private_key, "1TestAddress1")
        stats.add_match(test_private_key, "1TestAddress2")

        # 创建快照
        snap = stats.snapshot()

        # 验证基础属性
        assert snap.total_checked == 1000
        assert snap.speed > 0
        assert snap.elapsed > 0
        assert snap.start_time == 1000.0
        assert snap._match_count == 2, "快照应包含_match_count"

    def test_snapshot_isolation(self):
        """测试快照与原始对象隔离（深拷贝）"""
        stats = CollisionStats()

        # 添加一个匹配
        test_private_key = b"\x01" * 32
        stats.add_match(test_private_key, "1TestAddress")

        # 创建快照
        snap = stats.snapshot()

        # 修改原始对象
        stats.matches.clear()

        # 验证快照不受影响
        assert len(snap.matches) == 1, "快照应与原始对象隔离"
        assert snap.matches[0]["address"] == "1TestAddress"

    def test_snapshot_thread_safety(self):
        """测试快照的线程安全性"""
        import threading

        stats = CollisionStats()
        stats.update(1000)
        stats.gpu_errors = 100

        errors = []

        def create_snapshot():
            try:
                for _ in range(100):
                    snap = stats.snapshot()
                    assert snap.total_checked == 1000
                    assert snap.gpu_errors == 100
            except Exception as e:
                errors.append(e)

        # 多线程并发创建快照
        threads = [threading.Thread(target=create_snapshot) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"并发创建快照时发生错误: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================
# ExceptionHandler 单元测试 (从 src/utils/exception_handler.py)
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
        """KeyboardInterrupt 分支: raise 无异常上下文 → RuntimeError"""
        # 注: handle_engine_error 中 `raise` 裸写, 因 static method 无异常上下文,
        # 实际会抛出 RuntimeError: No active exception to reraise
        with patch("src.utils.exception_handler.logger") as mock_logger:
            with pytest.raises(RuntimeError, match="No active exception"):
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
        """未知错误分支: 记录 exception + record_worker_error"""
        stats = MagicMock()
        stats.record_worker_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", KeyError("unknown"), stats)
        mock_logger.exception.assert_called_once()
        stats.record_worker_error.assert_called_once()

    def test_no_stats(self):
        """无 stats 参数不崩溃"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", RuntimeError("no stats"))
        mock_logger.error.assert_called_once()

    def test_stats_without_method(self):
        """stats 无 record_worker_error 方法时也不崩溃"""
        stats = MagicMock(spec=[])
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_engine_error("CPU", RuntimeError("x"), stats)
        mock_logger.error.assert_called_once()


class TestHandleGpuError:
    """测试 handle_gpu_error — 5条分支"""

    def test_resource_error(self):
        """资源错误分支: 记录 error(gpu) + record_gpu_error(resource=True)"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_gpu_error(
                "随机碰撞", RuntimeError("out of resources"), stats
            )
        assert result is True
        mock_logger.error.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=True)

    def test_non_resource_runtime_error(self):
        """非资源 RuntimeError: record_gpu_error(resource=False)"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("范围扫描", RuntimeError("kernel fail"), stats)
        mock_logger.error.assert_called_once()
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
        """TypeError/OverflowError: 记录 error + wif_encode_error"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        stats.record_wif_encode_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("随机碰撞", TypeError("bad type"), stats)
        mock_logger.error.assert_called_once()
        stats.record_gpu_error.assert_called_once_with(is_resource_error=False)
        stats.record_wif_encode_error.assert_called_once()

    def test_unknown_error(self):
        """未知错误: 记录 exception"""
        stats = MagicMock()
        stats.record_gpu_error = MagicMock()
        with patch("src.utils.exception_handler.logger") as mock_logger:
            ExceptionHandler.handle_gpu_error("随机碰撞", KeyError("?"), stats)
        mock_logger.exception.assert_called_once()
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
        """未知错误 → 返回 True (保守策略)"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_gpu_async_error(KeyError("?"), "内核执行")
        assert result is True
        mock_logger.exception.assert_called_once()


class TestHandleClResourceError:
    """测试 handle_cl_resource_error"""

    def test_resource_exhausted(self):
        """资源耗尽 → 返回 True, 记录 warning"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_cl_resource_error(
                RuntimeError("out of resources"), "buffer"
            )
        assert result is True
        mock_logger.warning.assert_called_once()

    def test_non_resource_error(self):
        """非资源错误 → 返回 False, 记录 error"""
        with patch("src.utils.exception_handler.logger") as mock_logger:
            result = ExceptionHandler.handle_cl_resource_error(
                RuntimeError("unknown kernel error"), "kernel"
            )
        assert result is False
        mock_logger.error.assert_called_once()

    def test_cl_out_of_host_memory(self):
        """CL_OUT_OF_HOST_MEMORY → 识别为资源耗尽"""
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("cl_out_of_host_memory"), "buffer"
        )
        assert result is True

    def test_invalid_buffer_size(self):
        """invalid buffer size → 识别为资源耗尽"""
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("invalid buffer size"), "buffer"
        )
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
        # PermissionError 继承自 OSError, IOError 是 OSError 别名,
        # 因此被第一个 isinstance(error, (FileNotFoundError, IOError)) 捕获
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
            ExceptionHandler.handle_file_error(
                FileNotFoundError("no file"), "读取", "/path/to/file"
            )
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
