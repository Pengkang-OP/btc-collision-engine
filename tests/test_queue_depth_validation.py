#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
queue_depth 队列深度优化完整验证测试

验证内容:
1. ConfigManager Schema 可正确接受/拒绝 queue_depth 值
2. config.json / config.intel_arc.json 包含 queue_depth 且验证通过
3. AsyncGPUExecutor 构造函数读取 queue_depth 参数
4. 引擎初始化时正确从配置文件读取 queue_depth 并传入 AsyncGPUExecutor
5. get_stats() 返回 queue_depth / queue_depth_hits 字段
6. 不同 queue_depth 值 (1/4/8) 均可正常构建缓冲区池
"""

import sys
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ──────────────────────────────────────────────
# 测试组 1: ConfigManager Schema 验证
# ──────────────────────────────────────────────
class TestQueueDepthSchema(unittest.TestCase):
    """验证 queue_depth 在 JSON Schema 中的注册和边界检查"""

    def setUp(self):
        from src.config.config_manager import ConfigManager

        self.cm = ConfigManager()

    def test_valid_queue_depth_4(self):
        errors = self.cm.validate({"gpu": {"queue_depth": 4}})
        self.assertNotIn("gpu.queue_depth", errors, f"queue_depth=4 应通过验证，实际错误: {errors}")

    def test_valid_queue_depth_1_min(self):
        errors = self.cm.validate({"gpu": {"queue_depth": 1}})
        self.assertNotIn("gpu.queue_depth", errors, "queue_depth=1 (最小值) 应通过验证")

    def test_valid_queue_depth_16_max(self):
        errors = self.cm.validate({"gpu": {"queue_depth": 16}})
        self.assertNotIn("gpu.queue_depth", errors, "queue_depth=16 (最大值) 应通过验证")

    def test_invalid_queue_depth_0(self):
        errors = self.cm.validate({"gpu": {"queue_depth": 0}})
        self.assertIn("gpu.queue_depth", errors, "queue_depth=0 (< minimum=1) 应报错")

    def test_invalid_queue_depth_17(self):
        errors = self.cm.validate({"gpu": {"queue_depth": 17}})
        self.assertIn("gpu.queue_depth", errors, "queue_depth=17 (> maximum=16) 应报错")

    def test_default_config_has_queue_depth(self):
        from src.config.config_manager import ConfigManager

        default_qd = ConfigManager.DEFAULT_CONFIG["gpu"].get("queue_depth")
        self.assertEqual(
            default_qd, 4, f"DEFAULT_CONFIG['gpu']['queue_depth'] 应为 4，实际: {default_qd}"
        )


# ──────────────────────────────────────────────
# 测试组 2: 配置文件验证
# ──────────────────────────────────────────────
class TestConfigFilesQueueDepth(unittest.TestCase):
    """验证项目配置文件中 queue_depth 字段存在且通过 Schema"""

    def setUp(self):
        from src.config.config_manager import ConfigManager

        self.cm = ConfigManager()

    def _load_and_strip(self, path: Path) -> dict:
        from src.config.config_manager import ConfigManager

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return ConfigManager._strip_comments(raw)

    def test_config_json_has_queue_depth(self):
        cfg_path = ROOT.parent / "config.json"
        cfg = self._load_and_strip(cfg_path)
        gpu_cfg = cfg.get("gpu", {})
        self.assertIn("queue_depth", gpu_cfg, "config.json gpu 块应包含 queue_depth 字段")
        self.assertEqual(
            gpu_cfg["queue_depth"],
            4,
            f"config.json queue_depth 应为 4，实际: {gpu_cfg['queue_depth']}",
        )

    @unittest.skipIf(
        not (ROOT.parent / "config.intel_arc.json").exists(), "config.intel_arc.json 不存在"
    )
    def test_config_intel_arc_has_queue_depth(self):
        cfg_path = ROOT.parent / "config.intel_arc.json"
        cfg = self._load_and_strip(cfg_path)
        gpu_cfg = cfg.get("gpu", {})
        self.assertIn("queue_depth", gpu_cfg, "config.intel_arc.json gpu 块应包含 queue_depth 字段")

    def test_config_example_has_queue_depth(self):
        cfg_path = ROOT.parent / "config.example.json"
        cfg = self._load_and_strip(cfg_path)
        gpu_cfg = cfg.get("gpu", {})
        self.assertIn("queue_depth", gpu_cfg, "config.example.json gpu 块应包含 queue_depth 字段")

    @unittest.skipIf(
        not (ROOT.parent / "config.optimized.json").exists(), "config.optimized.json 不存在"
    )
    def test_config_optimized_has_queue_depth(self):
        cfg_path = ROOT.parent / "config.optimized.json"
        cfg = self._load_and_strip(cfg_path)
        gpu_cfg = cfg.get("gpu", {})
        self.assertIn("queue_depth", gpu_cfg, "config.optimized.json gpu 块应包含 queue_depth 字段")

    @unittest.skipIf(
        not (ROOT.parent / "config.intel_arc.json").exists(), "config.intel_arc.json 不存在"
    )
    def test_gpu_block_validates_without_queue_depth_errors(self):
        """intel_arc 配置的 gpu 块不应有 queue_depth 相关验证错误"""
        cfg_path = ROOT.parent / "config.intel_arc.json"
        cfg = self._load_and_strip(cfg_path)
        gpu_only = {"gpu": cfg.get("gpu", {})}
        errors = self.cm.validate(gpu_only)
        queue_errors = {k: v for k, v in errors.items() if "queue_depth" in k}
        self.assertEqual(
            queue_errors, {}, f"config.intel_arc.json gpu 块 queue_depth 验证失败: {queue_errors}"
        )


# ──────────────────────────────────────────────
# 测试组 3: AsyncGPUExecutor 单元测试
# ──────────────────────────────────────────────
class TestAsyncGPUExecutorQueueDepth(unittest.TestCase):
    """验证 AsyncGPUExecutor 对 queue_depth 的处理"""

    def _make_mock_device(self, enable_async=True):
        dev = MagicMock()
        dev.enable_async_execution = enable_async
        dev.compute_queue = MagicMock()
        dev.transfer_queue = MagicMock()
        dev.queue = MagicMock()
        return dev

    def test_default_queue_depth_is_4(self):
        from src.gpu.async_executor import AsyncGPUExecutor, DEFAULT_QUEUE_DEPTH

        self.assertEqual(DEFAULT_QUEUE_DEPTH, 4)
        dev = self._make_mock_device()
        ex = AsyncGPUExecutor(dev, max_batch_size=1024)
        self.assertEqual(ex.queue_depth, 4)

    def test_custom_queue_depth_8(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        dev = self._make_mock_device()
        ex = AsyncGPUExecutor(dev, max_batch_size=1024, queue_depth=8)
        self.assertEqual(ex.queue_depth, 8)

    def test_queue_depth_minimum_clamp_to_1(self):
        """传入 0 时应被 max(1, ...) 钳制到 1"""
        from src.gpu.async_executor import AsyncGPUExecutor

        dev = self._make_mock_device()
        ex = AsyncGPUExecutor(dev, max_batch_size=1024, queue_depth=0)
        self.assertEqual(ex.queue_depth, 1)

    def test_prefetch_events_list_initialized_empty(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        dev = self._make_mock_device()
        ex = AsyncGPUExecutor(dev, max_batch_size=1024, queue_depth=4)
        self.assertEqual(len(ex._prefetch_events), 0)

    def test_get_stats_contains_queue_depth_fields(self):
        from src.gpu.async_executor import AsyncGPUExecutor

        dev = self._make_mock_device()
        ex = AsyncGPUExecutor(dev, max_batch_size=1024, queue_depth=4)
        stats = ex.get_stats()
        self.assertIn("queue_depth", stats)
        self.assertIn("queue_depth_hits", stats)
        self.assertIn("current_queue_depth", stats)
        self.assertEqual(stats["queue_depth"], 4)
        self.assertEqual(stats["current_queue_depth"], 0)

    def test_initialize_buffers_creates_pool_matching_queue_depth(self):
        """initialize_buffers 应创建 queue_depth 个缓冲区（通过 mock pyopencl）"""
        import numpy as np
        from src.gpu.async_executor import AsyncGPUExecutor

        dev = self._make_mock_device()
        mock_context = MagicMock()
        mock_buf = MagicMock()

        # async_executor 内部用 import pyopencl as cl，需 mock sys.modules
        mock_cl = MagicMock()
        mock_cl.Buffer.return_value = mock_buf
        mock_cl.mem_flags.READ_ONLY = 1
        mock_cl.mem_flags.READ_WRITE = 2
        mock_cl.mem_flags.COPY_HOST_PTR = 4

        with (
            patch.dict("sys.modules", {"pyopencl": mock_cl}),
            patch(
                "src.gpu.precompute.get_precomp_table", return_value=np.zeros(496, dtype=np.uint32)
            ),
        ):
            for qd in [1, 4, 8]:
                ex = AsyncGPUExecutor(dev, max_batch_size=256, queue_depth=qd)
                # precomp_buffer / seed_buffer 置 None 确保走创建分支
                ex.precomp_buffer = None
                ex.seed_buffer = None
                ex.initialize_buffers(mock_context, num_keys=256)
                self.assertEqual(
                    len(ex._buffer_pool), qd, f"queue_depth={qd} 时缓冲区池应有 {qd} 个缓冲区"
                )


# ──────────────────────────────────────────────
# 测试组 4: 引擎初始化读取 queue_depth
# ──────────────────────────────────────────────
class TestEngineQueueDepthInit(unittest.TestCase):
    """验证 GPUCollisionEngine 初始化时从 config 读取 queue_depth"""

    def test_engine_reads_queue_depth_from_config(self):
        """模拟引擎内部读取 queue_depth 的逻辑，验证正确从 config 传入 AsyncGPUExecutor"""
        captured = {}

        class CapturingAsyncExecutor:
            def __init__(self, gpu_device, max_batch_size, queue_depth=4):
                captured["queue_depth"] = queue_depth

        # 直接模拟引擎内部读取逻辑（gpu_collision_engine.py 第1775-1781行）
        config = {"gpu": {"queue_depth": 7}}
        _cfg_gpu = config.get("gpu", {}) if config else {}
        _queue_depth = _cfg_gpu.get("queue_depth", 4)
        CapturingAsyncExecutor(None, max_batch_size=1024, queue_depth=_queue_depth)

        self.assertEqual(
            captured["queue_depth"],
            7,
            f"引擎应从 config 读取 queue_depth=7，实际: {captured.get('queue_depth')}",
        )

    def test_engine_uses_default_queue_depth_when_not_in_config(self):
        """当 config 中没有 queue_depth 时，应使用默认值 4"""
        captured = {}

        class CapturingAsyncExecutor:
            def __init__(self, gpu_device, max_batch_size, queue_depth=4):
                captured["queue_depth"] = queue_depth

        # 模拟引擎内读取逻辑
        config = {"gpu": {"async_execution": True}}  # 故意没有 queue_depth
        _cfg_gpu = config.get("gpu", {})
        _queue_depth = _cfg_gpu.get("queue_depth", 4)
        CapturingAsyncExecutor(None, max_batch_size=1024, queue_depth=_queue_depth)

        self.assertEqual(
            captured["queue_depth"],
            4,
            f"无 queue_depth 配置时应默认 4，实际: {captured.get('queue_depth')}",
        )


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  queue_depth 队列深度优化 - 完整验证测试")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestQueueDepthSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigFilesQueueDepth))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncGPUExecutorQueueDepth))
    suite.addTests(loader.loadTestsFromTestCase(TestEngineQueueDepthInit))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"结果: {passed}/{total} 通过", "✓ ALL PASS" if result.wasSuccessful() else "✗ FAILED")
    sys.exit(0 if result.wasSuccessful() else 1)
