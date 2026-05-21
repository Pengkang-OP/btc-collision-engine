"""CLI 引擎构建 (src/cli/engine_builder.py) 单元测试。

覆盖: on_match_callback, build_engine, 异常类
目标: 67% → 95%+
"""

import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.cli import engine_builder as eb


class TestExceptionClasses(unittest.TestCase):
    """异常类层次结构测试。"""

    def test_engine_build_error_basic(self):
        """EngineBuildError 基本功能测试。"""
        err = eb.EngineBuildError(message="test error", user_message="用户错误")
        self.assertEqual(err.message, "test error")
        self.assertEqual(err.user_message, "用户错误")
        self.assertIsNone(err.engine_type)

    def test_engine_build_error_default_user_message(self):
        """EngineBuildError 默认 user_message 等于 message。"""
        err = eb.EngineBuildError(message="test error")
        self.assertEqual(err.user_message, "test error")

    def test_gpu_not_available_error_defaults(self):
        """GPUNotAvailableError 默认值测试。"""
        err = eb.GPUNotAvailableError()
        self.assertEqual(err.message, "GPU not available")
        self.assertEqual(err.engine_type, "gpu")

    def test_gpu_not_available_error_custom(self):
        """GPUNotAvailableError 自定义消息测试。"""
        err = eb.GPUNotAvailableError(
            message="custom error",
            user_message="自定义错误",
        )
        self.assertEqual(err.message, "custom error")
        self.assertEqual(err.user_message, "自定义错误")
        self.assertEqual(err.engine_type, "gpu")

    def test_gpu_initialization_error_defaults(self):
        """GPUInitializationError 默认值测试。"""
        err = eb.GPUInitializationError()
        self.assertEqual(err.message, "GPU initialization failed")
        self.assertEqual(err.engine_type, "gpu")

    def test_gpu_initialization_error_custom_engine_type(self):
        """GPUInitializationError 自定义 engine_type 测试。"""
        err = eb.GPUInitializationError(
            message="multi-gpu failed",
            engine_type="multi_gpu",
        )
        self.assertEqual(err.engine_type, "multi_gpu")

    def test_exception_inheritance(self):
        """异常继承关系测试。"""
        self.assertTrue(issubclass(eb.GPUNotAvailableError, eb.EngineBuildError))
        self.assertTrue(issubclass(eb.GPUInitializationError, eb.EngineBuildError))
        self.assertTrue(issubclass(eb.EngineBuildError, Exception))


class TestOnMatchCallback:
    """on_match_callback() 工厂函数测试。"""

    def test_full_mode_shows_complete_keys_in_tty(self, capsys):
        """sensitive_mode='full' 在TTY环境 → 完整私钥 + 完整 WIF。"""
        callback = eb.on_match_callback(sensitive_mode="full")
        with patch("sys.stdout.isatty", return_value=True):
            callback(b"\x01" * 32, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBf")

        captured = capsys.readouterr()
        assert "0101010101010101010101010101010101010101010101010101010101010101" in captured.out
        assert "KwDiBf" in captured.out
        assert "*" not in captured.out
        assert "SHA256" not in captured.out

    def test_masked_mode_hides_middle_in_tty(self, capsys):
        """sensitive_mode='masked' 在TTY环境 → 首尾保留，中间星号。"""
        callback = eb.on_match_callback(sensitive_mode="masked")
        pk = bytes(range(32))
        with patch("sys.stdout.isatty", return_value=True):
            callback(pk, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBfQg4")

        captured = capsys.readouterr()
        assert "00010203" in captured.out
        assert "1c1d1e1f" in captured.out
        assert "*" in captured.out
        assert "SHA256" not in captured.out

    def test_hash_only_mode_shows_sha256_prefix(self, capsys):
        """sensitive_mode='hash_only' → SHA256 哈希前缀 + [已隐藏]。"""
        callback = eb.on_match_callback(sensitive_mode="hash_only")
        callback(b"\x01" * 32, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBf")

        captured = capsys.readouterr()
        assert "SHA256:" in captured.out
        assert "KwDiBf" not in captured.out

    def test_non_tty_forces_hash_only_mode(self, capsys):
        """非TTY环境强制降级为hash_only模式。"""
        callback = eb.on_match_callback(sensitive_mode="full")
        with patch("sys.stdout.isatty", return_value=False):
            callback(b"\x01" * 32, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBf")

        captured = capsys.readouterr()
        assert "SHA256:" in captured.out
        assert "[已隐藏]" in captured.out


def _make_args(**kwargs):
    """创建模拟 CLI args 对象。"""
    defaults = {
        "use_gpu": False,
        "multi_gpu": False,
        "no_optimize": False,
        "window_size": 8,
        "no_simd": False,
        "no_memory_pool": False,
        "workers": 2,
        "checkpoint": False,
        "checkpoint_interval": 30,
        "dedup": False,
        "dedup_max_size": 1000000,
        "gpu_device": -1,
        "gpu_batch_size": None,
        "gpu_indices": None,
        "gpu_count": -1,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


class TestBuildEngineCPU(unittest.TestCase):
    """build_engine() CPU 分支测试。"""

    def setUp(self):
        self.targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    def test_cpu_default_engine(self):
        """默认参数 → 构建 CPU 引擎。"""
        with patch.object(eb, "KeyCollisionEngine") as mock_cls:
            mock_cls.return_value = MagicMock()
            engine, etype = eb.build_engine(_make_args(), self.targets)
            self.assertEqual(etype, "cpu")
            mock_cls.assert_called_once()

    def test_cpu_with_no_optimize_flags(self):
        """no_optimize/no_simd/no_memory_pool → 传递给构造器。"""
        with patch.object(eb, "KeyCollisionEngine") as mock_cls:
            mock_cls.return_value = MagicMock()
            args = _make_args(no_optimize=True, no_simd=True, no_memory_pool=True)
            _, etype = eb.build_engine(args, self.targets)
            self.assertEqual(etype, "cpu")
            call_kwargs = mock_cls.call_args.kwargs
            self.assertTrue(call_kwargs["use_performance_optimization"] is False)
            self.assertTrue(call_kwargs["use_simd_hash"] is False)
            self.assertTrue(call_kwargs["use_memory_pool"] is False)

    def test_cpu_with_custom_callbacks(self):
        """自定义 on_progress / on_match → 直接传递。"""
        mock_progress = MagicMock()
        mock_match = MagicMock()
        with patch.object(eb, "KeyCollisionEngine") as mock_cls:
            mock_cls.return_value = MagicMock()
            eb.build_engine(
                _make_args(),
                self.targets,
                on_progress=mock_progress,
                on_match=mock_match,
            )
            call_kwargs = mock_cls.call_args.kwargs
            self.assertIs(call_kwargs["on_progress"], mock_progress)
            self.assertIs(call_kwargs["on_match"], mock_match)


class TestBuildEngineGPU(unittest.TestCase):
    """build_engine() GPU 分支测试 (GPU_AVAILABLE=True)。"""

    def setUp(self):
        self.targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    def test_gpu_unavailable_use_gpu_raises_exception(self):
        """GPU_AVAILABLE=False + use_gpu=True → GPUNotAvailableError。"""
        with patch.object(eb, "GPU_AVAILABLE", False):
            with self.assertRaises(eb.GPUNotAvailableError) as ctx:
                eb.build_engine(_make_args(use_gpu=True), self.targets)
            self.assertIn("OpenCL", ctx.exception.message)

    def test_gpu_unavailable_multi_gpu_raises_exception(self):
        """GPU_AVAILABLE=False + multi_gpu=True → GPUNotAvailableError。"""
        with patch.object(eb, "GPU_AVAILABLE", False):
            with self.assertRaises(eb.GPUNotAvailableError) as ctx:
                eb.build_engine(_make_args(multi_gpu=True), self.targets)
            self.assertIn("OpenCL", ctx.exception.message)

    def test_gpu_runtime_error_fallback_to_cpu(self):
        """GPUCollisionEngine() 抛 RuntimeError → 自动降级到 CPU。"""
        mock_gpu_engine = MagicMock()
        mock_gpu_engine.side_effect = RuntimeError("CL_DEVICE_NOT_FOUND")

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            patch.dict(
                "sys.modules",
                {"src.collision.gpu.engine": MagicMock(GPUCollisionEngine=mock_gpu_engine)},
            ),
            patch.object(eb, "KeyCollisionEngine") as mock_cpu_cls,
        ):
            mock_cpu_cls.return_value = MagicMock()
            with patch("builtins.print"):
                engine, etype = eb.build_engine(_make_args(use_gpu=True), self.targets)
            self.assertEqual(etype, "cpu")
            mock_cpu_cls.assert_called_once()

    def test_gpu_generic_exception_raises_gpu_initialization_error(self):
        """GPUCollisionEngine() 抛非 RuntimeError → GPUInitializationError。"""
        mock_gpu_engine = MagicMock()
        mock_gpu_engine.side_effect = MemoryError("out of memory")

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            patch.dict(
                "sys.modules",
                {"src.collision.gpu.engine": MagicMock(GPUCollisionEngine=mock_gpu_engine)},
            ),
        ):
            with self.assertRaises(eb.GPUInitializationError) as ctx:
                eb.build_engine(_make_args(use_gpu=True), self.targets)
            self.assertIn("GPU initialization error", ctx.exception.message)

    def test_gpu_success_returns_engine(self):
        """GPU_AVAILABLE=True + use_gpu=True → 返回 (engine, 'gpu')。"""
        mock_engine_instance = MagicMock()
        mock_gpu_engine = MagicMock(return_value=mock_engine_instance)

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            patch.dict(
                "sys.modules",
                {"src.collision.gpu.engine": MagicMock(GPUCollisionEngine=mock_gpu_engine)},
            ),
        ):
            args = _make_args(use_gpu=True, gpu_device=0, gpu_batch_size=1000)
            engine, etype = eb.build_engine(args, self.targets)
            self.assertEqual(etype, "gpu")
            self.assertIs(engine, mock_engine_instance)


class TestBuildEngineMultiGPU(unittest.TestCase):
    """build_engine() 多GPU 分支测试 (GPU_AVAILABLE=True)。

    注意: engine_builder 导入的是 MultiFormatMultiGPUEngine，
    测试 mock 路径必须对齐: src.gpu.multi_format_multi_gpu_engine。
    """

    def setUp(self):
        self.targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        # 清理缓存确保 mock 生效
        for key in list(sys.modules.keys()):
            if "multi_format_multi_gpu_engine" in key:
                sys.modules.pop(key, None)

    def _patch_multi_engine(self, mock_engine_instance):
        """创建多GPU引擎 mock 上下文管理器。

        engine_builder 通过 'from src.gpu.multi_format_multi_gpu_engine
        import MultiFormatMultiGPUEngine as _MEngine' 导入。
        """
        mock_multi_engine = MagicMock(return_value=mock_engine_instance)
        return patch.dict(
            "sys.modules",
            {
                "src.gpu.multi_format_multi_gpu_engine": MagicMock(
                    MultiFormatMultiGPUEngine=mock_multi_engine
                )
            },
        )

    def test_multi_gpu_init_returns_false_raises_exception(self):
        """MultiFormatMultiGPUEngine.initialize() 返回 False → GPUInitializationError。"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.initialize.return_value = False

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            self._patch_multi_engine(mock_engine_instance),
        ):
            with self.assertRaises(eb.GPUInitializationError) as ctx:
                eb.build_engine(_make_args(multi_gpu=True), self.targets)
            self.assertEqual(ctx.exception.engine_type, "multi_gpu")

    def test_multi_gpu_init_raises_exception(self):
        """MultiFormatMultiGPUEngine() 初始化抛异常 → GPUInitializationError。"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.initialize.side_effect = OSError("device busy")

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            self._patch_multi_engine(mock_engine_instance),
        ):
            with self.assertRaises(eb.GPUInitializationError) as ctx:
                eb.build_engine(_make_args(multi_gpu=True), self.targets)
            self.assertIn("Multi-GPU initialization failed", ctx.exception.message)

    def test_multi_gpu_success(self):
        """MultiFormatMultiGPUEngine 初始化成功 → 返回 multi_gpu。"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.initialize.return_value = True

        with (
            patch.object(eb, "GPU_AVAILABLE", True),
            self._patch_multi_engine(mock_engine_instance),
        ):
            engine, etype = eb.build_engine(
                _make_args(multi_gpu=True, gpu_indices=[0, 1], gpu_count=2),
                self.targets,
            )
            self.assertEqual(etype, "multi_gpu")
            self.assertIs(engine, mock_engine_instance)
            mock_engine_instance.initialize.assert_called_once()


class TestGPUImportError(unittest.TestCase):
    """GPU_AVAILABLE=False 时的 ImportError 回退路径 (L88-93)。"""

    def test_gpu_import_failure_sets_flag_false(self):
        """导入 pyopencl 失败 → GPU_AVAILABLE=False。"""
        import builtins

        _orig_import = builtins.__import__

        def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pyopencl":
                raise ImportError("No module named 'pyopencl'")
            return _orig_import(name, globals, locals, fromlist, level)

        pre_keys = set(sys.modules.keys())
        mod_keys = [
            k
            for k in list(sys.modules.keys())
            if k == "src.cli.engine_builder" or k.startswith("src.cli.engine_builder.")
        ]
        saved = {k: sys.modules.pop(k, None) for k in mod_keys}

        try:
            with patch("builtins.__import__", side_effect=_mock_import):
                fresh = importlib.import_module("src.cli.engine_builder")
                self.assertFalse(fresh.GPU_AVAILABLE)
        finally:
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v
            for k in set(sys.modules.keys()) - pre_keys:
                if k.startswith("src.cli.engine_builder"):
                    del sys.modules[k]


if __name__ == "__main__":
    unittest.main()
