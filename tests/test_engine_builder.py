"""CLI 引擎构建 (src/cli/engine_builder.py) 单元测试。

覆盖: on_match_callback, build_engine
目标: 67% → 95%+
"""

import importlib
import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.cli import engine_builder as eb


# ── on_match_callback ──────────────────────────────────────────

class TestOnMatchCallback(unittest.TestCase):
    """on_match_callback() 工厂函数测试。"""

    def test_full_mode_shows_complete_keys(self):
        """sensitive_mode='full' → 完整私钥 + 完整 WIF。"""
        callback = eb.on_match_callback(sensitive_mode="full")
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            callback(b"\x01" * 32, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBf")

        output = buf.getvalue()
        self.assertIn("0101010101010101010101010101010101010101010101010101010101010101", output)
        self.assertIn("KwDiBf", output)
        # 不应包含脱敏标记
        self.assertNotIn("*", output)
        self.assertNotIn("SHA256", output)

    def test_masked_mode_hides_middle(self):
        """sensitive_mode='masked' → 首尾保留，中间星号。"""
        callback = eb.on_match_callback(sensitive_mode="masked")
        pk = bytes(range(32))  # hex: 00010203...1c1d1e1f (非对称)
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            callback(pk, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBfQg4")

        output = buf.getvalue()
        self.assertIn("00010203", output)  # 前缀: bytes 0-3
        self.assertIn("1c1d1e1f", output)  # 后缀: bytes 28-31
        self.assertIn("*", output)
        self.assertNotIn("SHA256", output)

    def test_hash_only_mode_shows_sha256_prefix(self):
        """sensitive_mode='hash_only' → SHA256 哈希前缀 + [已隐藏]。"""
        callback = eb.on_match_callback(sensitive_mode="hash_only")
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            callback(b"\x01" * 32, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "KwDiBf")

        output = buf.getvalue()
        self.assertIn("SHA256:", output)
        self.assertNotIn("KwDiBf", output)


# ── build_engine ───────────────────────────────────────────────

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
                _make_args(), self.targets,
                on_progress=mock_progress, on_match=mock_match,
            )
            call_kwargs = mock_cls.call_args.kwargs
            self.assertIs(call_kwargs["on_progress"], mock_progress)
            self.assertIs(call_kwargs["on_match"], mock_match)


class TestBuildEngineGPU(unittest.TestCase):
    """build_engine() GPU 分支测试 (GPU_AVAILABLE=True)。"""

    def setUp(self):
        self.targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    def test_gpu_unavailable_use_gpu_exits(self):
        """GPU_AVAILABLE=False + use_gpu=True → SystemExit(1) + 错误提示。"""
        with patch.object(eb, "GPU_AVAILABLE", False):
            with patch("builtins.print") as mock_print:
                with self.assertRaises(SystemExit) as ctx:
                    eb.build_engine(_make_args(use_gpu=True), self.targets)
                self.assertEqual(ctx.exception.code, 1)
            mock_print.assert_called()
            printed = " ".join(str(c.args[0]) if c.args else ""
                              for c in mock_print.call_args_list)
            self.assertIn("GPU", printed)

    def test_gpu_unavailable_multi_gpu_exits(self):
        """GPU_AVAILABLE=False + multi_gpu=True → SystemExit(1) + 错误提示。"""
        with patch.object(eb, "GPU_AVAILABLE", False):
            with patch("builtins.print") as mock_print:
                with self.assertRaises(SystemExit) as ctx:
                    eb.build_engine(_make_args(multi_gpu=True), self.targets)
                self.assertEqual(ctx.exception.code, 1)
            mock_print.assert_called()
            printed = " ".join(str(c.args[0]) if c.args else ""
                              for c in mock_print.call_args_list)
            self.assertIn("GPU", printed)

    def test_gpu_runtime_error_during_init(self):
        """GPUCollisionEngine() 抛 RuntimeError → SystemExit(1) + 建议提示。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "GPUCollisionEngine") as mock_cls:
                mock_cls.side_effect = RuntimeError("CL_DEVICE_NOT_FOUND")
                with patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as ctx:
                        eb.build_engine(_make_args(use_gpu=True), self.targets)
                    self.assertEqual(ctx.exception.code, 1)
                # 多条 print 输出：错误 + 3条建议
                self.assertGreaterEqual(mock_print.call_count, 4)

    def test_gpu_generic_exception_during_init(self):
        """GPUCollisionEngine() 抛非 RuntimeError → SystemExit(1) + 错误提示。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "GPUCollisionEngine") as mock_cls:
                mock_cls.side_effect = MemoryError("out of memory")
                with patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as ctx:
                        eb.build_engine(_make_args(use_gpu=True), self.targets)
                    self.assertEqual(ctx.exception.code, 1)
                mock_print.assert_called()
                printed = " ".join(str(c.args[0]) if c.args else ""
                                  for c in mock_print.call_args_list)
                self.assertIn("GPU", printed)

    def test_gpu_success_returns_engine(self):
        """GPU_AVAILABLE=True + use_gpu=True → 返回 (engine, 'gpu')。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "GPUCollisionEngine") as mock_cls:
                mock_engine = MagicMock()
                mock_cls.return_value = mock_engine
                args = _make_args(use_gpu=True, gpu_device=0, gpu_batch_size=1000)
                engine, etype = eb.build_engine(args, self.targets)
                self.assertEqual(etype, "gpu")
                self.assertIs(engine, mock_engine)
                # 验证核心构造参数正确传递
                call_kwargs = mock_cls.call_args.kwargs
                self.assertEqual(call_kwargs["targets"], self.targets)
                self.assertEqual(call_kwargs["device_index"], 0)
                self.assertEqual(call_kwargs["batch_size"], 1000)


class TestBuildEngineMultiGPU(unittest.TestCase):
    """build_engine() 多GPU 分支测试 (GPU_AVAILABLE=True)。"""

    def setUp(self):
        self.targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    def test_multi_gpu_init_returns_false(self):
        """MultiGPUCollisionEngine.initialize() 返回 False → SystemExit(1) + 错误提示。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "MultiGPUCollisionEngine") as mock_cls:
                mock_engine = MagicMock()
                mock_engine.initialize.return_value = False
                mock_cls.return_value = mock_engine
                with patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as ctx:
                        eb.build_engine(_make_args(multi_gpu=True), self.targets)
                    self.assertEqual(ctx.exception.code, 1)
                mock_print.assert_called()
                printed = " ".join(str(c.args[0]) if c.args else ""
                                  for c in mock_print.call_args_list)
                self.assertIn("GPU", printed)

    def test_multi_gpu_init_raises_exception(self):
        """MultiGPUCollisionEngine() 初始化抛异常 → SystemExit(1) + 错误日志。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "MultiGPUCollisionEngine") as mock_cls:
                mock_engine = MagicMock()
                mock_engine.initialize.side_effect = OSError("device busy")
                mock_cls.return_value = mock_engine
                with patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as ctx:
                        eb.build_engine(_make_args(multi_gpu=True), self.targets)
                    self.assertEqual(ctx.exception.code, 1)
                # 多条 print 输出：错误 + 建议
                self.assertGreaterEqual(mock_print.call_count, 2)

    def test_multi_gpu_success(self):
        """MultiGPUCollisionEngine 初始化成功 → 返回 multi_gpu。"""
        with patch.object(eb, "GPU_AVAILABLE", True):
            with patch.object(eb, "MultiGPUCollisionEngine") as mock_cls:
                mock_engine = MagicMock()
                mock_engine.initialize.return_value = True
                mock_cls.return_value = mock_engine
                engine, etype = eb.build_engine(
                    _make_args(multi_gpu=True, gpu_indices=[0, 1], gpu_count=2),
                    self.targets,
                )
                self.assertEqual(etype, "multi_gpu")
                self.assertIs(engine, mock_engine)
                mock_engine.initialize.assert_called_once()


class TestGPUImportError(unittest.TestCase):
    """GPU_AVAILABLE=False 时的 ImportError 回退路径 (L32-35)。"""

    def test_gpu_import_failure_sets_flag_false(self):
        """导入 pyopencl 失败 → GPU_AVAILABLE=False + 类设为 None。"""
        import builtins

        _orig_import = builtins.__import__

        def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "src.collision.gpu_collision_engine":
                raise ImportError("No module named 'pyopencl'")
            return _orig_import(name, globals, locals, fromlist, level)

        # 移除 engine_builder 及其 GPU 依赖模块缓存，迫使重新导入
        pre_keys = set(sys.modules.keys())
        mod_keys = [k for k in list(sys.modules.keys())
                    if k == "src.cli.engine_builder"
                    or k.startswith("src.cli.engine_builder.")
                    or k in ("src.collision.gpu_collision_engine",
                             "src.gpu.multi_gpu_engine")]
        saved = {k: sys.modules.pop(k, None) for k in mod_keys}

        try:
            with patch("builtins.__import__", side_effect=_mock_import):
                fresh = importlib.import_module("src.cli.engine_builder")
                self.assertFalse(fresh.GPU_AVAILABLE)
                self.assertIsNone(fresh.GPUCollisionEngine)
                self.assertIsNone(fresh.MultiGPUCollisionEngine)
        finally:
            # 恢复保存的模块
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v
            # 清理重导入引入的多余 key (防止 sys.modules 污染)
            for k in set(sys.modules.keys()) - pre_keys:
                if k.startswith("src.cli.engine_builder"):
                    del sys.modules[k]


if __name__ == "__main__":
    unittest.main()
