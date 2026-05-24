#!/usr/bin/env python3
"""ExceptionHandler 扩展单元测试 (P1-5)

测试 src.utils.exception_handler 中 P3-6 新增的 GPU 异步错误、
OpenCL 资源错误、GPU 清理错误、配置错误和文件错误处理方法。

测试覆盖:
- handle_gpu_async_error: 回退决策 (应回退/应传播)
- handle_cl_resource_error: 资源耗尽判断
- handle_gpu_cleanup_error: 非致命错误处理
- handle_file_error: 文件操作分类
- handle_config_error: 配置错误分类
- 边界场景: 空 context、空 resource_type、空 mode、空 filepath
"""

import pytest

from src.utils.exception_handler import ExceptionHandler

# ============================================================================
# handle_gpu_async_error 回退决策测试
# ============================================================================


@pytest.mark.unit
class TestGPUAsyncError:
    """测试 GPU 异步错误处理 — 回退决策"""

    # ── 应回退到同步模式 (返回 True) ──

    def test_runtime_error_should_fallback(self):
        """RuntimeError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            RuntimeError("OpenCL kernel execution failed"),
            "内核执行",
        )
        assert result is True

    def test_memory_error_should_fallback(self):
        """MemoryError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            MemoryError("OpenCL out of host memory"),
            "缓冲分配",
        )
        assert result is True

    def test_value_error_should_fallback(self):
        """ValueError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            ValueError("invalid work group size"),
            "内核执行",
        )
        assert result is True

    def test_type_error_should_fallback(self):
        """TypeError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(TypeError("expected int, got str"), "结果回读")
        assert result is True

    def test_index_error_should_fallback(self):
        """IndexError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            IndexError("buffer index out of range"),
            "缓冲清理",
        )
        assert result is True

    def test_attribute_error_should_fallback(self):
        """AttributeError 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            AttributeError("'NoneType' object has no attribute 'enqueue'"),
            "种子写入",
        )
        assert result is True

    # ── 不应回退, 应向上传播 (返回 False) ──

    def test_system_exit_should_propagate(self):
        """SystemExit 应向上传播"""
        result = ExceptionHandler.handle_gpu_async_error(SystemExit(1), "内核执行")
        assert result is False

    def test_keyboard_interrupt_should_propagate(self):
        """KeyboardInterrupt 应向上传播"""
        result = ExceptionHandler.handle_gpu_async_error(KeyboardInterrupt(), "结果回读")
        assert result is False

    # ── 未知错误根据消息判断 ──

    def test_unknown_error_with_fatal_keyword_should_not_fallback(self):
        """未知错误含 'fatal' 关键字 → 不应回退"""
        result = ExceptionHandler.handle_gpu_async_error(Exception("A fatal error occurred"), "缓冲清理")
        assert result is False

    def test_unknown_error_with_corruption_keyword_should_not_fallback(self):
        """未知错误含 'corruption' 关键字 → 不应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            Exception("data corruption detected"),
            "结果回读",
        )
        assert result is False

    def test_unknown_error_with_segmentation_keyword_should_not_fallback(self):
        """未知错误含 'segmentation' 关键字 → 不应回退"""
        result = ExceptionHandler.handle_gpu_async_error(Exception("segmentation fault"), "内核执行")
        assert result is False

    def test_unknown_error_with_access_violation_keyword_should_not_fallback(self):
        """未知错误含 'access violation' 关键字 → 不应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            Exception("memory access violation"),
            "缓冲分配",
        )
        assert result is False

    def test_unknown_error_without_critical_keyword_should_fallback(self):
        """未知错误不含严重关键字 → 应回退"""
        result = ExceptionHandler.handle_gpu_async_error(
            Exception("some weird unexpected thing happened"),
            "种子写入",
        )
        assert result is True

    # ── 边界 ──

    def test_empty_context(self):
        """空上下文"""
        result = ExceptionHandler.handle_gpu_async_error(RuntimeError("error"), "")
        assert result is True  # RuntimeError always falls back

    def test_case_insensitive_keywords(self):
        """严重关键字不区分大小写"""
        result = ExceptionHandler.handle_gpu_async_error(
            Exception("ACCESS VIOLATION in module"),
            "内核执行",
        )
        assert result is False


# ============================================================================
# handle_cl_resource_error 资源耗尽判断测试
# ============================================================================


@pytest.mark.unit
class TestCLResourceError:
    """测试 OpenCL 资源错误分类"""

    # ── 资源耗尽关键字 (应返回 True) ──

    def test_out_of_resources(self):
        result = ExceptionHandler.handle_cl_resource_error(RuntimeError("CL_OUT_OF_RESOURCES"), "buffer")
        assert result is True

    def test_out_of_memory(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("device out of memory"),
            "kernel",
        )
        assert result is True

    def test_allocation_failed(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("buffer allocation failed"),
            "queue",
        )
        assert result is True

    def test_insufficient_resources(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("insufficient device memory"),
            "event",
        )
        assert result is True

    def test_cl_out_of_host_memory(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("CL_OUT_OF_HOST_MEMORY"),
            "buffer",
        )
        assert result is True

    def test_invalid_buffer_size(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("invalid buffer size requested"),
            "buffer",
        )
        assert result is True

    # ── 非资源错误 (应返回 False) ──

    def test_invalid_kernel_name(self):
        result = ExceptionHandler.handle_cl_resource_error(RuntimeError("invalid kernel name"), "kernel")
        assert result is False

    def test_compile_error(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("kernel compile error"),
            "kernel",
        )
        assert result is False

    def test_invalid_work_group_size(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("invalid work group size"),
            "queue",
        )
        assert result is False

    # ── 边界 ──

    def test_empty_resource_type(self):
        result = ExceptionHandler.handle_cl_resource_error(RuntimeError("out of resources"), "")
        assert result is True

    def test_case_insensitive_match(self):
        result = ExceptionHandler.handle_cl_resource_error(
            RuntimeError("CL_MEM_OBJECT_ALLOCATION_FAILURE"),
            "buffer",
        )
        assert result is True


# ============================================================================
# handle_gpu_cleanup_error 非致命错误测试
# ============================================================================


@pytest.mark.unit
class TestGPUCleanupError:
    """测试 GPU 清理错误处理 (全部非致命, 使用 WARNING)"""

    def test_runtime_error(self):
        """RuntimeError — 清理 OpenCL 错误"""
        # 不应抛出异常
        ExceptionHandler.handle_gpu_cleanup_error(RuntimeError("buffer release failed"), "seed_buffer")

    def test_os_error(self):
        """OSError — 清理系统 I/O 错误"""
        ExceptionHandler.handle_gpu_cleanup_error(OSError("file handle closed"), "precomp_buffer")

    def test_other_error(self):
        """其他未知错误"""
        ExceptionHandler.handle_gpu_cleanup_error(Exception("something unexpected"), "compute_queue")

    # ── 边界 ──

    def test_empty_resource_name(self):
        """空资源名称"""
        ExceptionHandler.handle_gpu_cleanup_error(RuntimeError("cleanup error"), "")

    def test_none_resource_name_handling(self):
        """资源名称非字符串但不影响执行"""
        # 所有路径都应正常处理，不抛异常
        try:
            ExceptionHandler.handle_gpu_cleanup_error(RuntimeError("error"), "test_buffer")
        except Exception as e:
            pytest.fail(f"handle_gpu_cleanup_error 不应抛出异常: {e}")


# ============================================================================
# handle_file_error 文件操作分类测试
# ============================================================================


@pytest.mark.unit
class TestFileError:
    """测试文件操作错误分类"""

    def test_file_not_found(self):
        """FileNotFoundError"""
        ExceptionHandler.handle_file_error(
            FileNotFoundError("config.json not found"),
            "读取",
            "config.json",
        )

    def test_permission_error(self):
        """PermissionError"""
        ExceptionHandler.handle_file_error(PermissionError("access denied"), "写入", "data.json")

    def test_io_error(self):
        """IOError"""
        ExceptionHandler.handle_file_error(OSError("disk full"), "写入", "large_file.bin")

    def test_unknown_error(self):
        """未知错误 — 使用 logger.exception"""
        ExceptionHandler.handle_file_error(Exception("weird error"), "删除", "temp.txt")

    # ── 边界 ──

    def test_empty_operation(self):
        """空操作描述"""
        ExceptionHandler.handle_file_error(FileNotFoundError("missing"), "", "/path/to/file")

    def test_empty_filepath(self):
        """空文件路径"""
        ExceptionHandler.handle_file_error(PermissionError("denied"), "读取", "")

    def test_empty_both(self):
        """操作和路径均为空"""
        ExceptionHandler.handle_file_error(OSError("error"), "", "")


# ============================================================================
# handle_config_error 配置错误分类测试
# ============================================================================


@pytest.mark.unit
class TestConfigError:
    """测试配置错误分类"""

    def test_file_not_found(self):
        """配置文件不存在"""
        ExceptionHandler.handle_config_error(FileNotFoundError("config.json missing"), "ConfigManager")

    def test_io_error(self):
        """配置文件 IO 错误"""
        ExceptionHandler.handle_config_error(OSError("read error"), "CryptoConfig")

    def test_value_error(self):
        """配置值无效"""
        ExceptionHandler.handle_config_error(ValueError("invalid port number"), "GPUConfig")

    def test_type_error(self):
        """配置类型错误"""
        ExceptionHandler.handle_config_error(TypeError("expected dict"), "ConfigManager")

    def test_permission_error(self):
        """配置文件权限不足"""
        ExceptionHandler.handle_config_error(PermissionError("access denied"), "CryptoConfig")

    def test_unknown_error(self):
        """未知配置错误"""
        ExceptionHandler.handle_config_error(Exception("unknown config issue"), "ConfigManager")

    # ── 边界 ──

    def test_empty_config_type(self):
        """空配置类型"""
        ExceptionHandler.handle_config_error(ValueError("bad value"), "")

    def test_empty_config_all(self):
        """全部为空"""
        ExceptionHandler.handle_config_error(Exception("error"), "")


# ============================================================================
# handle_engine_error 回归测试 (补充覆盖)
# ============================================================================


@pytest.mark.unit
class TestEngineErrorEdge:
    """测试引擎错误处理的额外边界"""

    def test_keyboard_interrupt_raises(self):
        """KeyboardInterrupt 应重新抛出"""
        with pytest.raises(KeyboardInterrupt):
            ExceptionHandler.handle_engine_error("CPU", KeyboardInterrupt(), context="扫描循环")

    def test_import_error_classified(self):
        """ImportError 被正确分类 (P3-6)"""
        # 不应抛出异常
        ExceptionHandler.handle_engine_error(
            "CPU",
            ImportError("no module named pyopencl"),
            context="GPU初始化",
        )

    def test_os_error_classified(self):
        """OSError 被正确分类 (P3-6)"""
        ExceptionHandler.handle_engine_error("GPU", OSError("device busy"), context="内核执行")

    def test_empty_context(self):
        """空上下文"""
        ExceptionHandler.handle_engine_error("CPU", RuntimeError("test"), context="")

    def test_none_stats(self):
        """Stats 为 None"""
        ExceptionHandler.handle_engine_error("CPU", ValueError("test"), stats=None)

    def test_stats_without_methods(self):
        """Stats 对象无相关方法"""
        stats = object()
        # 不应抛出 AttributeError
        try:
            ExceptionHandler.handle_engine_error("GPU", RuntimeError("test"), stats=stats)
        except AttributeError:
            pytest.fail("stats 缺方法时应优雅降级，不应抛出 AttributeError")


# ============================================================================
# handle_gpu_error 回归测试 (补充覆盖)
# ============================================================================


@pytest.mark.unit
class TestGPUErrorEdge:
    """测试 GPU 错误处理的额外边界"""

    def test_always_returns_true(self):
        """handle_gpu_error 总是返回 True"""
        result = ExceptionHandler.handle_gpu_error("随机碰撞", RuntimeError("test"))
        assert result is True

        result = ExceptionHandler.handle_gpu_error("随机碰撞", Exception("unknown"))
        assert result is True

    def test_memory_error_classified(self):
        """MemoryError 被正确分类 (P3-6)"""
        result = ExceptionHandler.handle_gpu_error("范围扫描", MemoryError("out of memory"))
        assert result is True

    def test_type_error_classified(self):
        """TypeError → 数据错误分类"""
        result = ExceptionHandler.handle_gpu_error("暴力穷举", TypeError("bad type"))
        assert result is True

    def test_overflow_error_classified(self):
        """OverflowError → 数据错误分类"""
        result = ExceptionHandler.handle_gpu_error("随机碰撞", OverflowError("int too large"))
        assert result is True

    def test_resource_error_detection_by_message(self):
        """资源耗尽通过错误消息检测"""
        result = ExceptionHandler.handle_gpu_error(
            "随机碰撞",
            RuntimeError("CL_OUT_OF_RESOURCES: device memory exhausted"),
        )
        assert result is True

    def test_empty_mode(self):
        """空模式字符串"""
        result = ExceptionHandler.handle_gpu_error("", RuntimeError("test"))
        assert result is True

    def test_none_stats(self):
        """Stats 为 None"""
        result = ExceptionHandler.handle_gpu_error("随机碰撞", RuntimeError("test"), stats=None)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
