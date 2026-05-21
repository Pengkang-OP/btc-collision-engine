"""碰撞插件系统 (src/collision/plugins/) 单元测试.

覆盖: CollisionPlugin ABC, PluginManager, ExamplePlugin, __init__ 重导出
目标: 0% -> 90%+
"""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# ── 被测模块 ─────────────────────────────────────────────────
from src.collision.plugins import CollisionPlugin, PluginManager
from src.collision.plugins.base_plugin import CollisionPlugin as _BasePlugin
from src.collision.plugins.example_plugin import ExamplePlugin

# ═══════════════════════════════════════════════════════════════
# 1. CollisionPlugin ABC 测试
# ═══════════════════════════════════════════════════════════════


class ConcretePlugin(CollisionPlugin):
    """用于测试的具体插件实现."""

    def __init__(self, plugin_name="test_plugin"):
        self._name = plugin_name
        self._running = False
        self._stats = MagicMock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A test plugin"

    def initialize(self, targets, **kwargs):
        self._targets = targets

    def start(self, on_progress=None, on_match=None, on_complete=None):
        self._running = True

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def get_stats(self):
        return self._stats


class TestCollisionPlugin(unittest.TestCase):
    """CollisionPlugin 抽象基类测试."""

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化抽象类."""
        with self.assertRaises(TypeError):
            CollisionPlugin()  # type: ignore[abstract]

    def test_concrete_subclass_works(self):
        """具体子类可正常实例化和使用."""
        plugin = ConcretePlugin()
        self.assertEqual(plugin.name, "test_plugin")
        self.assertEqual(plugin.description, "A test plugin")

    def test_abstract_name_required(self):
        """未实现 name 的子类无法实例化."""

        class NoNamePlugin(CollisionPlugin):
            description = "missing name"

            def initialize(self, targets, **kwargs):
                pass

            def start(self, **kwargs):
                pass

            def stop(self):
                pass

            def is_running(self):
                return False

            def get_stats(self):
                return MagicMock()

        with self.assertRaises(TypeError):
            NoNamePlugin()  # type: ignore[abstract]

    # ── 接口契约 ──────────────────────────────────────────

    def test_initialize_sets_targets(self):
        """initialize 传递 targets."""
        plugin = ConcretePlugin()
        targets = {"addr1", "addr2"}
        plugin.initialize(targets)
        self.assertEqual(plugin._targets, targets)

    def test_start_sets_running(self):
        """start 设置 _running=True."""
        plugin = ConcretePlugin()
        plugin.start()
        self.assertTrue(plugin.is_running())

    def test_stop_sets_not_running(self):
        """stop 设置 _running=False."""
        plugin = ConcretePlugin()
        plugin.start()
        plugin.stop()
        self.assertFalse(plugin.is_running())

    def test_get_stats_returns_stats(self):
        """get_stats 返回统计对象."""
        plugin = ConcretePlugin()
        stats = plugin.get_stats()
        self.assertIs(stats, plugin._stats)


# ═══════════════════════════════════════════════════════════════
# 2. PluginManager 测试
# ═══════════════════════════════════════════════════════════════


class TestPluginManager(unittest.TestCase):
    """PluginManager 测试."""

    def setUp(self):
        self.manager = PluginManager()

    # ── __init__ / add_plugin_directory ────────────────────

    def test_init_empty(self):
        """初始化时 plugins 为空."""
        self.assertEqual(self.manager.plugins, {})
        self.assertEqual(self.manager.plugin_dirs, [])

    def test_add_plugin_directory(self):
        """添加插件目录."""
        self.manager.add_plugin_directory("/tmp/plugins")
        self.assertIn("/tmp/plugins", self.manager.plugin_dirs)

    def test_add_plugin_directory_no_duplicate(self):
        """重复添加同一目录不重复."""
        self.manager.add_plugin_directory("/tmp/plugins")
        self.manager.add_plugin_directory("/tmp/plugins")
        self.assertEqual(len(self.manager.plugin_dirs), 1)

    # ── load_plugins ───────────────────────────────────────

    def test_load_plugins_nonexistent_dir(self):
        """不存在的目录 → 跳过，返回空列表."""
        self.manager.add_plugin_directory("/nonexistent/plugins")
        loaded = self.manager.load_plugins()
        self.assertEqual(loaded, [])

    def test_load_plugins_no_py_files(self):
        """目录无 .py 文件 → 空列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.manager.add_plugin_directory(tmpdir)
            loaded = self.manager.load_plugins()
            self.assertEqual(loaded, [])

    def test_load_plugins_skips_dunder_files(self):
        """跳过 __init__.py 等文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "__init__.py"), "w") as f:
                f.write("")
            self.manager.add_plugin_directory(tmpdir)
            loaded = self.manager.load_plugins()
            self.assertEqual(loaded, [])

    def test_load_plugins_loads_valid_plugin(self):
        """加载有效的插件文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_code = """
from src.collision.plugins.base_plugin import CollisionPlugin

class TestPlugin(CollisionPlugin):
    @property
    def name(self):
        return "test_plugin"
    @property
    def description(self):
        return "test"
    def initialize(self, targets, **kwargs):
        pass
    def start(self, **kwargs):
        pass
    def stop(self):
        pass
    def is_running(self):
        return False
    def get_stats(self):
        return None
"""
            with open(os.path.join(tmpdir, "test_plugin.py"), "w") as f:
                f.write(plugin_code)
            self.manager.add_plugin_directory(tmpdir)
            loaded = self.manager.load_plugins()
            self.assertEqual(loaded, ["test_plugin"])
            self.assertIn("test_plugin", self.manager.plugins)

    @patch("os.path.islink", return_value=True)
    @patch("os.listdir")
    @patch("os.path.exists", return_value=True)
    def test_load_plugins_skips_symlink(self, mock_exists, mock_listdir, mock_islink):
        """符号链接插件被跳过并记录警告."""
        mock_listdir.return_value = ["symlink_plugin.py"]
        self.manager.add_plugin_directory("/fake/plugins")
        with patch("logging.warning") as mock_warn:
            loaded = self.manager.load_plugins()
        self.assertEqual(loaded, [])
        mock_warn.assert_called_with("拒绝加载符号链接插件: symlink_plugin.py")

    @patch("os.path.islink", return_value=False)
    @patch("os.path.abspath", side_effect=lambda x: x)
    @patch("os.listdir")
    @patch("os.path.exists", return_value=True)
    def test_load_plugins_path_traversal_rejected(
        self, mock_exists, mock_listdir, mock_abspath, mock_islink
    ):
        """路径遍历攻击被安全检查拒绝 (L52-57)."""
        mock_listdir.return_value = ["evil.py"]
        plugin_dir = "/fake/plugins"
        self.manager.add_plugin_directory(plugin_dir)

        def fake_join(d, f):
            return "/etc/evil.py"  # 目录外路径

        with patch("os.path.join", side_effect=fake_join), patch("logging.warning") as mock_warn:
            loaded = self.manager.load_plugins()
        self.assertEqual(loaded, [])
        mock_warn.assert_called_with("插件路径安全检查失败，跳过: evil.py")

    @patch("importlib.util.spec_from_file_location", side_effect=Exception("load error"))
    def test_load_plugins_handles_exception(self, mock_spec):
        """加载异常被捕获并记录 (L84-85)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "bad.py"), "w") as f:
                f.write("pass")
            self.manager.add_plugin_directory(tmpdir)
            with patch("logging.error") as mock_err:
                loaded = self.manager.load_plugins()
        self.assertEqual(loaded, [])
        mock_err.assert_called()

    def test_load_plugins_module_import_error(self):
        """模块加载异常时记录错误并跳过 (L84-85)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "bad_plugin.py"), "w") as f:
                f.write("raise SyntaxError('invalid syntax')")
            self.manager.add_plugin_directory(tmpdir)
            with patch("logging.error") as mock_err:
                loaded = self.manager.load_plugins()
            self.assertEqual(loaded, [])
            mock_err.assert_called()

    # ── get_plugin / get_all_plugins / get_plugin_names ─────

    def test_get_plugin_exists(self):
        """获取存在的插件."""
        plugin = ConcretePlugin("p1")
        self.manager.plugins["p1"] = plugin
        self.assertIs(self.manager.get_plugin("p1"), plugin)

    def test_get_plugin_not_exists(self):
        """获取不存在的插件返回 None."""
        self.assertIsNone(self.manager.get_plugin("nonexistent"))

    def test_get_all_plugins(self):
        """获取所有插件字典."""
        p1 = ConcretePlugin("p1")
        p2 = ConcretePlugin("p2")
        self.manager.plugins = {"p1": p1, "p2": p2}
        all_plugins = self.manager.get_all_plugins()
        self.assertEqual(all_plugins, {"p1": p1, "p2": p2})

    def test_get_plugin_names(self):
        """获取所有插件名称列表."""
        self.manager.plugins = {"a": MagicMock(), "b": MagicMock()}
        names = self.manager.get_plugin_names()
        self.assertEqual(set(names), {"a", "b"})

    # ── unload_plugins ─────────────────────────────────────

    def test_unload_plugins_stops_running(self):
        """unload_plugins 停止运行中的插件."""
        plugin = ConcretePlugin("running_plugin")
        plugin.start()
        self.manager.plugins = {"running_plugin": plugin}
        self.manager.unload_plugins()
        self.assertFalse(plugin.is_running())
        self.assertEqual(self.manager.plugins, {})

    def test_unload_plugins_handles_stop_exception(self):
        """插件 stop 异常 → 记录错误，继续卸载."""
        plugin = ConcretePlugin("bad_plugin")
        plugin._running = True  # 确保 is_running() 返回 True，触发 stop()
        plugin.stop = MagicMock(side_effect=RuntimeError("stop failed"))
        self.manager.plugins = {"bad_plugin": plugin}
        with patch("logging.error") as mock_err:
            self.manager.unload_plugins()
        mock_err.assert_called()
        self.assertEqual(self.manager.plugins, {})

    def test_unload_plugins_empty(self):
        """空插件表卸载不抛异常."""
        self.manager.unload_plugins()
        self.assertEqual(self.manager.plugins, {})

    def test_unload_plugins_not_running_skips_stop(self):
        """未运行的插件不调用 stop."""
        plugin = ConcretePlugin("idle")
        plugin.stop = MagicMock()
        self.manager.plugins = {"idle": plugin}
        self.manager.unload_plugins()
        plugin.stop.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# 3. ExamplePlugin 测试
# ═══════════════════════════════════════════════════════════════


class TestExamplePlugin(unittest.TestCase):
    """ExamplePlugin 测试."""

    def setUp(self):
        self.plugin = ExamplePlugin()

    # ── 属性 ───────────────────────────────────────────────

    def test_name(self):
        """name 返回 'example'."""
        self.assertEqual(self.plugin.name, "example")

    def test_description(self):
        """description 包含关键信息."""
        self.assertIn("示例", self.plugin.description)
        self.assertIn("随机", self.plugin.description)

    # ── initialize ─────────────────────────────────────────

    def test_initialize(self):
        """initialize 设置 targets 和 generator."""
        targets = {"addr1", "addr2"}
        self.plugin.initialize(targets)
        self.assertEqual(self.plugin.targets, targets)
        self.assertIsNotNone(self.plugin.generator)
        self.assertIsNotNone(self.plugin.stats)
        self.assertIsNotNone(self.plugin._stop_event)

    def test_initialize_with_progress_interval(self):
        """initialize 可传入 progress_interval."""
        self.plugin.initialize({"addr"}, progress_interval=500)
        self.assertEqual(self.plugin.progress_interval, 500)

    def test_initialize_default_progress_interval(self):
        """默认 progress_interval=1000."""
        self.plugin.initialize({"addr"})
        self.assertEqual(self.plugin.progress_interval, 1000)

    # ── start ──────────────────────────────────────────────

    def test_start_sets_running(self):
        """start 设置 _running=True 并启动线程."""
        self.plugin.initialize({"addr"})
        self.plugin.start()
        try:
            self.assertTrue(self.plugin._running)
        finally:
            self.plugin.stop()

    def test_start_already_running_does_nothing(self):
        """已运行时重复 start 无操作."""
        self.plugin.initialize({"addr"})
        self.plugin._running = True
        prev_thread = self.plugin._thread
        self.plugin.start()
        self.assertIs(self.plugin._thread, prev_thread)

    def test_start_sets_callbacks(self):
        """start 设置回调函数."""
        cb = MagicMock()
        self.plugin.initialize({"addr"})
        self.plugin.start(on_progress=cb)
        try:
            self.assertIs(self.plugin.on_progress, cb)
        finally:
            self.plugin.stop()

    # ── stop ───────────────────────────────────────────────

    def test_stop_sets_event_and_not_running(self):
        """stop 设置停止事件并标记 _running=False."""
        self.plugin.initialize({"addr"})
        self.plugin.stop()
        self.assertTrue(self.plugin._stop_event.is_set())
        self.assertFalse(self.plugin._running)

    def test_stop_without_thread(self):
        """无线程时 stop 不抛异常."""
        self.plugin.initialize({"addr"})
        self.plugin._thread = None
        self.plugin.stop()  # 不应抛异常

    # ── is_running ─────────────────────────────────────────

    def test_is_running_false_initially(self):
        """initialize 后未 start 则 is_running=False."""
        self.plugin.initialize({"addr"})
        self.assertFalse(self.plugin.is_running())

    def test_is_running_true_after_start(self):
        """start 后短时间内 is_running=True."""
        self.plugin.initialize({"addr"})
        self.plugin.start()
        try:
            # 轮询等待线程启动，最多等 2 秒
            for _ in range(200):
                if self.plugin.is_running():
                    break
                time.sleep(0.01)
            else:
                self.fail("插件未在 2 秒内启动")
            self.assertTrue(self.plugin.is_running())
        finally:
            self.plugin.stop()

    # ── get_stats ──────────────────────────────────────────

    def test_get_stats_returns_stats(self):
        """get_stats 返回 CollisionStats."""
        self.plugin.initialize({"addr"})
        stats = self.plugin.get_stats()
        self.assertIs(stats, self.plugin.stats)

    # ── _run 内部逻辑 ─────────────────────────────────────

    def test_run_invalid_private_key_skipped(self):
        """无效私钥 (k<1 或 k>=N) → continue，count 保持 0 (L86)."""
        self.plugin.initialize({"addr"})
        self.plugin.on_progress = None
        self.plugin.on_match = None
        self.plugin.on_complete = None
        mock_stats_update = MagicMock()
        self.plugin.stats.update = mock_stats_update
        with patch.object(self.plugin, "_stop_event") as mock_event:
            mock_event.is_set.side_effect = [False, True]  # 运行一次循环
            with patch("secrets.token_bytes") as mock_bytes:
                # k >= N (SECP256K1_N) → 无效，触发 continue
                mock_bytes.return_value = b"\xff" * 32
                with patch.object(
                    self.plugin.generator, "generate_address", return_value=("fake", "key", None)
                ):
                    self.plugin._run()
        # k 无效 → count 保持 0 → stats.update(0) 被调用
        mock_stats_update.assert_called_once_with(0)

    def test_run_match_triggers_callback(self):
        """匹配时触发 on_match 回调并停止 (L93-101)."""
        target = "1TestAddress123"
        self.plugin.initialize({target})
        on_match = MagicMock()
        self.plugin.on_progress = None
        self.plugin.on_match = on_match
        self.plugin.on_complete = None
        self.plugin._stop_event = threading.Event()

        with patch.object(self.plugin._stop_event, "is_set", side_effect=[False, True]):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                with patch.object(
                    self.plugin.generator, "generate_address", return_value=(target, "key", None)
                ):
                    with patch("src.core.wif.WIF.encode", return_value="fake_wif"):
                        self.plugin._run()

        on_match.assert_called_once()
        # 验证传入了 private_key, address, wif
        args = on_match.call_args[0]
        self.assertEqual(args[1], target)
        self.assertEqual(args[2], "fake_wif")

    def test_run_completion_calls_on_complete(self):
        """正常完成时触发 on_complete 回调 (L111)."""
        self.plugin.initialize({"addr"})
        on_complete = MagicMock()
        self.plugin.on_complete = on_complete
        # 设置立即停止 → 循环体不执行，直接走 L109-112 完成路径
        self.plugin._stop_event.set()
        self.plugin._run()
        on_complete.assert_called_once()
        self.assertFalse(self.plugin.is_running())

    def test_run_progress_callback(self):
        """进度达到间隔时触发 on_progress (L104-107)."""
        # 使用不匹配的地址，避免意外触发 on_match 和真实 WIF.encode
        self.plugin.initialize({"non_matching_addr"}, progress_interval=1)
        on_progress = MagicMock()
        self.plugin.on_progress = on_progress
        self.plugin.on_match = None
        self.plugin.on_complete = None

        call_count = [0]

        def controlled_is_set():
            call_count[0] += 1
            return call_count[0] > 3  # 运行 3 次循环

        with patch.object(self.plugin._stop_event, "is_set", side_effect=controlled_is_set):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                with patch.object(
                    self.plugin.generator,
                    "generate_address",
                    return_value=("non_matching_addr", "key", None),
                ):
                    self.plugin._run()

        # 每 1 次循环触发 on_progress → 3 次循环触发恰好 3 次
        self.assertEqual(on_progress.call_count, 3)


# ═══════════════════════════════════════════════════════════════
# 4. __init__ 重导出测试
# ═══════════════════════════════════════════════════════════════


class TestPluginsInit(unittest.TestCase):
    """__init__.py 重导出验证."""

    def test_all_exports(self):
        """__all__ 包含 PluginManager 和 CollisionPlugin."""
        from src.collision.plugins import __all__

        self.assertIn("PluginManager", __all__)
        self.assertIn("CollisionPlugin", __all__)

    def test_plugin_manager_importable(self):
        """PluginManager 可从包级别导入."""
        from src.collision.plugins import PluginManager as PM

        self.assertTrue(callable(PM))

    def test_collision_plugin_importable(self):
        """CollisionPlugin 可从包级别导入."""
        from src.collision.plugins import CollisionPlugin as CP

        self.assertTrue(issubclass(CP, _BasePlugin))


if __name__ == "__main__":
    unittest.main()
