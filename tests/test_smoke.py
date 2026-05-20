#!/usr/bin/env python3
"""冒烟测试 (Smoke Tests) - 核心功能快速验证

目的：在短时间内 (通常 < 30 秒) 验证项目核心功能是否正常工作。
可用作 CI/CD 的第一道关口和开发中的快速自检。

覆盖：
- 核心加密模块 (Base58, WIF, SHA256)
- 碰撞统计 (CollisionStats)
- 事件系统 (EventBus)
- 日志存储 (LogStorage)
- 配置加载 (ConfigManager)
- 关键类型导入
"""

import json
import os
import tempfile
import time

import pytest

# ============================================================================
# 1. 核心加密模块冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestCryptoSmoke:
    """加密模块冒烟测试"""

    def test_base58_encode_decode(self):
        """Base58 编解码基本功能"""
        from src.core.base58 import Base58

        data = b"\x00" + bytes(range(20))
        encoded = Base58.encode(data)
        decoded = Base58.decode(encoded)
        assert data == decoded

    def test_sha256(self):
        """SHA256 已知向量验证"""
        from src.core.hash_utils import HashUtils

        result = HashUtils.sha256(b"hello")
        expected = bytes.fromhex("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        assert result == expected

    def test_wif_encode_decode(self):
        """WIF 编解码往返"""
        from src.core.wif import WIF

        pk = bytes(range(1, 33))
        wif = WIF.encode(pk, compressed=True)
        result = WIF.decode(wif)
        if isinstance(result, tuple):
            decoded, _ = result
        else:
            decoded = result
        assert decoded == pk

    def test_secp256k1_constants(self):
        """secp256k1 常量检查"""
        from src.core.secp256k1 import Secp256k1

        assert Secp256k1.N > 0
        assert Secp256k1.P > 0
        assert Secp256k1.Gx > 0
        assert Secp256k1.Gy > 0


# ============================================================================
# 2. 碰撞统计冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestCollisionStatsSmoke:
    """碰撞统计冒烟测试"""

    def test_stats_update(self):
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.start_time = time.time() - 1.0
        stats.update(1000)
        assert stats.total_checked == 1000
        assert stats.speed > 0

    def test_stats_snapshot(self):
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.start_time = time.time()
        stats.add_match(b"\x01" * 32, "1TestAddr")
        snap = stats.snapshot()
        assert snap.total_checked == stats.total_checked

    def test_stats_format(self):
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(1000000)
        formatted = stats.format_speed()
        assert "/s" in formatted

    def test_stats_health(self):
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        assert stats.is_healthy() is True


# ============================================================================
# 3. 事件系统冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestEventSystemSmoke:
    """事件系统冒烟测试"""

    def test_event_bus_publish_subscribe(self):
        from src.collision.event_bus import EventBus, reset_event_bus
        from src.collision.events import EngineStartEvent, EventType

        reset_event_bus()

        bus = EventBus(async_mode=False)
        handler_called = []

        def handler(event):
            handler_called.append(event.mode)

        bus.subscribe(EventType.ENGINE_START, handler)
        bus.publish(EngineStartEvent(mode="smoke_test", target_count=1, batch_size=1024))

        assert len(handler_called) == 1
        assert handler_called[0] == "smoke_test"
        bus.stop()

    def test_global_event_bus_singleton(self):
        from src.collision.event_bus import get_event_bus, reset_event_bus

        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
        bus1.stop()


# ============================================================================
# 4. 日志系统冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestLoggingSmoke:
    """日志系统冒烟测试"""

    def test_log_storage_save_query(self):
        from src.log_engine.log_storage import LogStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            s = LogStorage(storage_dir=tmpdir)
            s.save({"type": "test", "message": "smoke_test_message", "timestamp": 1000})
            recent = s.get_recent(10)
            assert len(recent) == 1
            assert recent[0]["message"] == "smoke_test_message"

    def test_log_processor_format(self):
        from src.log_engine.events import LogEvent, LogEventType
        from src.log_engine.log_processor import LogProcessor

        processor = LogProcessor()
        event = LogEvent(LogEventType.STATUS_UPDATE, {"message": "smoke test"})
        result = processor.process(event)
        assert result is not None
        assert "smoke test" in result["message"]


# ============================================================================
# 5. 配置系统冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestConfigSmoke:
    """配置系统冒烟测试"""

    def test_config_manager_load(self):
        from src.config.config_manager import ConfigManager

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"collision": {"max_workers": 2}}, f)
            config_path = f.name

        try:
            cm = ConfigManager(config_path)
            assert cm is not None
        finally:
            os.unlink(config_path)


# ============================================================================
# 6. 类型与事件定义冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestTypeDefinitionsSmoke:
    """类型定义冒烟测试"""

    def test_collision_event_types_import(self):
        from src.collision.events import (
            EventType,
        )

        assert EventType.ENGINE_START.value == "engine.start"
        assert EventType.ENGINE_STOP.value == "engine.stop"
        assert EventType.ENGINE_PROGRESS.value == "engine.progress"

    def test_collision_types_import(self):
        from src.collision.types import (
            MatchCallback,
            ProgressCallback,
        )

        assert ProgressCallback is not None
        assert MatchCallback is not None


# ============================================================================
# 7. 导入冒烟检查
# ============================================================================


@pytest.mark.smoke
class TestImportSmoke:
    """关键模块导入冒烟测试"""

    def test_core_imports(self):
        from src.core.base58 import Base58
        from src.core.hash_utils import HashUtils
        from src.core.secp256k1 import Secp256k1
        from src.core.wif import WIF

        assert Base58 is not None
        assert WIF is not None
        assert HashUtils is not None
        assert Secp256k1 is not None

    def test_utils_imports(self):
        from src.utils.exceptions import (
            CollisionError,
            CryptoBackendError,
        )

        assert CollisionError is not None
        assert CryptoBackendError is not None

    def test_cli_imports(self):
        from src.cli.arg_parser import parse_args

        assert callable(parse_args)

    def test_i18n_imports(self):
        from src.i18n.translator import Translator

        assert Translator is not None


# ============================================================================
# 主入口验证
# ============================================================================


class TestArgParserModuleCoverage:
    """arg_parser.py 模块级代码覆盖测试 (L15, L22-23)。"""

    def test_sys_path_insert_when_root_not_in_path(self):
        """模块首次加载时 _project_root 不在 sys.path → sys.path.insert (L15)。"""
        import importlib
        import sys

        # 获取当前已加载模块的 _project_root
        mod = sys.modules.get("src.cli.arg_parser")
        if mod is None:
            mod = importlib.import_module("src.cli.arg_parser")
        project_root = mod._project_root

        # 卸载模块，移除 project_root，重新导入
        sys.modules.pop("src.cli.arg_parser", None)
        original_path = list(sys.path)
        sys.path = [p for p in sys.path if p != project_root]
        try:
            new_mod = importlib.import_module("src.cli.arg_parser")
            assert new_mod is not None
            assert hasattr(new_mod, "_project_root")
            assert project_root in sys.path  # 验证 L15 insert 已执行
        finally:
            sys.path[:] = original_path
            sys.modules.pop("src.cli.arg_parser", None)
            importlib.import_module("src.cli.arg_parser")

    def test_version_import_fallback(self):
        """from src import __version__ 失败时回退到 '4.4.0' (L22-23)。"""
        import builtins
        import importlib
        import sys
        from unittest.mock import patch

        # 卸载模块
        sys.modules.pop("src.cli.arg_parser", None)

        real_import = builtins.__import__

        # 拦截 __import__('src', fromlist=['__version__']) → 抛出 ImportError
        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "src" and "__version__" in (fromlist or ()):
                raise ImportError("No module named 'src.__version__'")
            return real_import(name, globals, locals, fromlist, level)

        try:
            with patch("builtins.__import__", side_effect=mock_import):
                mod = importlib.import_module("src.cli.arg_parser")
                assert mod._VERSION == "4.4.0"
        finally:
            sys.modules.pop("src.cli.arg_parser", None)
            importlib.import_module("src.cli.arg_parser")


@pytest.mark.smoke
def test_smoke_all_modules_importable():
    """验证所有主要模块可被导入"""
    modules_to_check = [
        "src.core",
        "src.collision",
        "src.config",
        "src.cli",
        "src.log_engine",
        "src.monitoring",
        "src.utils",
        "src.i18n",
        "src.wizard",
    ]
    for mod_name in modules_to_check:
        try:
            __import__(mod_name)
        except ImportError as e:
            pytest.fail(f"模块导入失败 {mod_name}: {e}")
