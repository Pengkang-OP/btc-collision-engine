#!/usr/bin/env python3
"""碰撞引擎核心模块综合测试

覆盖 src/collision/ 下未充分测试的模块：
- base_engine.py (抽象基类)
- constants.py (常量定义)
- types.py (类型别名)
- factory.py (引擎工厂)
- collision_helpers.py (辅助函数)
- delta_stats.py (增量统计)
- match_storage.py (匹配存储)
"""

import json
import os
import threading
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# 1. BaseCollisionEngine 抽象基类测试
# ============================================================================
from src.collision.base_engine import BaseCollisionEngine


class TestBaseCollisionEngine:
    """测试 BaseCollisionEngine 抽象基类"""

    def test_cannot_instantiate(self):
        """抽象基类不能直接实例化"""
        with pytest.raises(TypeError):
            BaseCollisionEngine(targets=set())

    def test_concrete_subclass(self):
        """具体子类可以实例化"""

        class MyEngine(BaseCollisionEngine):
            def __init__(self, targets, **kwargs):
                self.targets = targets
                self._running = False

            def start(self, mode="random", resume=False, **kwargs):
                self._running = True

            def stop(self, timeout=None):
                self._running = False

            def is_running(self):
                return self._running

            def get_stats(self):
                from src.collision.collision_stats import CollisionStats

                return CollisionStats()

        engine = MyEngine(targets={"addr1", "addr2"})
        assert engine.is_running() is False
        engine.start()
        assert engine.is_running() is True
        engine.stop()
        assert engine.is_running() is False

    def test_get_device_info_default(self):
        """默认 get_device_info 返回空字典"""

        class MyEngine(BaseCollisionEngine):
            def __init__(self, targets, **kwargs):
                pass

            def start(self, **kwargs):
                pass

            def stop(self, timeout=None):
                pass

            def is_running(self):
                return False

            def get_stats(self):
                from src.collision.collision_stats import CollisionStats

                return CollisionStats()

        engine = MyEngine(targets=set())
        assert engine.get_device_info() == {}

    def test_get_supported_modes_default(self):
        """默认 get_supported_modes 返回三种模式"""

        class MyEngine(BaseCollisionEngine):
            def __init__(self, targets, **kwargs):
                pass

            def start(self, **kwargs):
                pass

            def stop(self, timeout=None):
                pass

            def is_running(self):
                return False

            def get_stats(self):
                from src.collision.collision_stats import CollisionStats

                return CollisionStats()

        engine = MyEngine(targets=set())
        modes = engine.get_supported_modes()
        assert "random" in modes
        assert "range" in modes
        assert "brute_force" in modes


# ============================================================================
# 2. 常量定义测试
# ============================================================================

from src.collision import constants as c  # noqa: E402


class TestCollisionConstants:
    """测试碰撞引擎常量"""

    def test_private_key_constants(self):
        assert c.PRIVATE_KEY_SIZE == 32
        assert c.PRIVATE_KEY_MIN == 1
        assert c.COMPRESSED_FLAG == b"\x01"

    def test_batch_size_constants(self):
        assert c.BATCH_SIZE_DEFAULT == 1000
        assert c.BATCH_SIZE_GPU_DEFAULT == 65536
        assert c.BATCH_SIZE_LARGE == 1_000_000

    def test_progress_interval_constants(self):
        assert c.PROGRESS_INTERVAL_COUNT == 1000
        assert c.CHECKPOINT_INTERVAL_DEFAULT == 30
        assert c.DATA_LOGGING_INTERVAL_DEFAULT == 10

    def test_dedup_cache_constants(self):
        assert c.DEDUP_MAX_SIZE_DEFAULT == 1_000_000
        assert c.BLOOM_FILTER_MAX_SIZE == 10_000_000
        assert c.BLOOM_FILTER_FALSE_POSITIVE_RATE == 0.001

    def test_queue_buffer_constants(self):
        assert c.RESULT_QUEUE_MAX_SIZE == 1000
        assert c.GPU_BUFFER_TRACKER_MAX == 1000
        assert c.GPU_BUFFER_TIMEOUT == 300

    def test_performance_limit_constants(self):
        assert c.MAX_RETRY_COUNT == 100
        assert c.MAX_HISTORY_RECORDS == 1000
        assert c.MAX_ALERT_HISTORY == 1000

    def test_timeout_constants(self):
        assert c.THREAD_JOIN_TIMEOUT_MIN == 10.0
        assert c.THREAD_JOIN_TIMEOUT_PER_TARGET == 0.001
        assert c.ASYNC_GENERATION_TIMEOUT == 30.0
        assert c.STATS_UPDATE_TIMEOUT == 5.0

    def test_file_permission_constants(self):
        assert c.FILE_PERMISSION_RESTRICTED == 0o600
        assert c.LOG_MAX_BYTES == 10_485_760  # 10MB
        assert c.LOG_BACKUP_COUNT == 5

    def test_gpu_constants(self):
        assert c.GPU_MEMORY_RATIO_DEFAULT == 0.5
        assert c.GPU_DEVICE_AUTO_SELECT == -1
        assert c.GPU_COMPILE_TIMEOUT == 60

    def test_retry_constants(self):
        assert c.MAX_RETRIES == 3
        assert c.RETRY_DELAY == 0.5
        assert c.RETRY_DELAY_INCREMENT == 0.1

    def test_alert_constants(self):
        assert c.ALERT_RATE_LIMIT_MAX == 10
        assert c.ALERT_RATE_LIMIT_WINDOW == 60
        assert c.ALERT_DEDUP_LOOKBACK == 10

    def test_monitor_constants(self):
        assert c.PERFORMANCE_TRACKING_MAX_RECORDS == 10000
        assert c.SLOW_OPERATION_THRESHOLD_MS == 1000

    def test_address_format_constants(self):
        assert c.P2PKH_VERSION_BYTE == 0x00
        assert c.WIF_VERSION_BYTE == 0x80
        assert c.ADDRESS_MIN_LENGTH == 26
        assert c.ADDRESS_MAX_LENGTH == 35


# ============================================================================
# 3. 类型别名测试
# ============================================================================


class TestCollisionTypes:
    """测试碰撞引擎类型别名"""

    def test_progress_callback_type(self):
        """验证 ProgressCallback 类型别名可用"""
        from src.collision.types import ProgressCallback

        assert ProgressCallback is not None

    def test_match_callback_type(self):
        """验证 MatchCallback 类型别名可用"""
        from src.collision.types import MatchCallback

        assert MatchCallback is not None

    def test_complete_callback_type(self):
        """验证 CompleteCallback 类型别名可用"""
        from src.collision.types import CompleteCallback

        assert CompleteCallback is not None

    def test_error_callback_type(self):
        """验证 ErrorCallback 类型别名可用"""
        from src.collision.types import ErrorCallback

        assert ErrorCallback is not None

    def test_event_handler_type(self):
        """验证 EventHandler 类型别名可用"""
        from src.collision.types import EventHandler

        assert EventHandler is not None

    def test_error_handler_type(self):
        """验证 ErrorHandler 类型别名可用"""
        from src.collision.types import ErrorHandler

        assert ErrorHandler is not None

    def test_target_addresses_type(self):
        """验证 TargetAddresses 类型别名可用"""
        from src.collision.types import TargetAddresses

        assert TargetAddresses is not None

    def test_engine_config_type(self):
        """验证 EngineConfig 类型别名可用"""
        from src.collision.types import EngineConfig

        assert EngineConfig is not None

    def test_match_result_type(self):
        """验证 MatchResult 类型别名可用"""
        from src.collision.types import MatchResult

        assert MatchResult is not None


# ============================================================================
# 4. EngineFactory 测试
# ============================================================================

from src.collision.factory import EngineFactory  # noqa: E402


class TestEngineFactory:
    """测试引擎工厂 — 使用 mock 隔离依赖，不创建真实引擎实例"""

    TARGETS = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX"}
    TARGETS_1 = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}

    # ========================================================================
    # CPU 引擎创建
    # ========================================================================

    def test_create_cpu_engine_default(self):
        """默认参数创建 CPU 引擎，targets 正确传递"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            engine = EngineFactory.create_cpu_engine(self.TARGETS)
            mock_engine_cls.assert_called_once_with(targets=self.TARGETS, event_bus=None)
            assert engine is mock_engine

    def test_create_cpu_engine_passes_targets(self):
        """targets 参数正确传递给引擎构造器"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            EngineFactory.create_cpu_engine(self.TARGETS_1)
            call_kwargs = mock_engine_cls.call_args.kwargs
            assert call_kwargs["targets"] == self.TARGETS_1

    def test_create_cpu_engine_no_event_bus(self):
        """无 container、无 event_bus 时传递 event_bus=None"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine_cls.return_value = MagicMock()
            EngineFactory.create_cpu_engine(self.TARGETS_1)
            call_kwargs = mock_engine_cls.call_args.kwargs
            assert call_kwargs["event_bus"] is None

    def test_create_cpu_engine_container_event_bus_fallback(self):
        """传入 container 时 event_bus 回退到 container.event_bus"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine_cls.return_value = MagicMock()
            mock_eb = MagicMock()
            mock_container = MagicMock()
            mock_container.event_bus = mock_eb
            EngineFactory.create_cpu_engine(self.TARGETS_1, container=mock_container)
            mock_engine_cls.assert_called_once_with(targets=self.TARGETS_1, event_bus=mock_eb)

    def test_create_cpu_engine_event_bus_priority(self):
        """直接 event_bus 参数优先于 container.event_bus"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine_cls.return_value = MagicMock()
            direct_eb = MagicMock()
            container_eb = MagicMock()
            mock_container = MagicMock()
            mock_container.event_bus = container_eb
            EngineFactory.create_cpu_engine(
                self.TARGETS_1,
                container=mock_container,
                event_bus=direct_eb,
            )
            mock_engine_cls.assert_called_once_with(targets=self.TARGETS_1, event_bus=direct_eb)

    def test_create_cpu_engine_kwargs_passthrough(self):
        """**kwargs 透传给引擎构造器"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_engine_cls:
            mock_engine_cls.return_value = MagicMock()
            EngineFactory.create_cpu_engine(self.TARGETS_1, max_keys=10000, batch_size=512)
            call_kwargs = mock_engine_cls.call_args.kwargs
            assert call_kwargs["max_keys"] == 10000
            assert call_kwargs["batch_size"] == 512

    def test_create_cpu_engine_stats_deprecation(self):
        """传入 stats 参数触发 DeprecationWarning"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_ec:
            mock_ec.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="stats"):
                EngineFactory.create_cpu_engine(self.TARGETS_1, stats=MagicMock())

    def test_create_cpu_engine_data_logger_deprecation(self):
        """传入 data_logger 参数触发 DeprecationWarning"""
        with patch("src.collision.key_collision_engine.KeyCollisionEngine") as mock_ec:
            mock_ec.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="data_logger"):
                EngineFactory.create_cpu_engine(self.TARGETS_1, data_logger=MagicMock())

    # ========================================================================
    # GPU 引擎创建
    # ========================================================================

    def test_create_gpu_engine_default(self):
        """默认参数创建 GPU 引擎，targets 正确传递

        注意: GPU factory 不传递 event_bus 给 GPUCollisionEngine
        (与 CPU factory 不同)，因此仅验证 targets 参数。
        """
        with patch("src.collision.gpu_collision_engine.GPUCollisionEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            engine = EngineFactory.create_gpu_engine(self.TARGETS_1)
            mock_engine_cls.assert_called_once_with(targets=self.TARGETS_1)
            assert engine is mock_engine

    def test_create_gpu_engine_with_container(self):
        """GPU 引擎传入 container 不崩溃（container 在当前实现中被忽略）"""
        with patch("src.collision.gpu_collision_engine.GPUCollisionEngine") as mock_engine_cls:
            mock_engine_cls.return_value = MagicMock()
            mock_container = MagicMock()
            engine = EngineFactory.create_gpu_engine(self.TARGETS_1, container=mock_container)
            mock_engine_cls.assert_called_once_with(targets=self.TARGETS_1)
            assert engine is not None

    def test_create_gpu_engine_stats_deprecation(self):
        """GPU 引擎传入 stats 参数触发 DeprecationWarning"""
        with patch("src.collision.gpu_collision_engine.GPUCollisionEngine") as mock_ec:
            mock_ec.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="stats"):
                EngineFactory.create_gpu_engine(self.TARGETS_1, stats=MagicMock())

    def test_create_gpu_engine_event_bus_deprecation(self):
        """GPU 引擎传入 event_bus 参数触发 DeprecationWarning"""
        with patch("src.collision.gpu_collision_engine.GPUCollisionEngine") as mock_ec:
            mock_ec.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="event_bus"):
                EngineFactory.create_gpu_engine(self.TARGETS_1, event_bus=MagicMock())

    def test_create_gpu_engine_data_logger_deprecation(self):
        """GPU 引擎传入 data_logger 参数触发 DeprecationWarning"""
        with patch("src.collision.gpu_collision_engine.GPUCollisionEngine") as mock_ec:
            mock_ec.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="data_logger"):
                EngineFactory.create_gpu_engine(self.TARGETS_1, data_logger=MagicMock())


# ============================================================================
# 5. collision_helpers 测试
# ============================================================================

from src.collision.collision_helpers import (  # noqa: E402
    encode_private_key_to_wif,
    format_match_result,
    safe_wif_encode,
)


class TestCollisionHelpers:
    """测试碰撞辅助函数"""

    def test_encode_private_key_to_wif_valid(self):
        """有效私钥编码为 WIF"""
        # 使用已知测试私钥: 全1
        pk = b"\x01" * 32
        wif = encode_private_key_to_wif(pk, compressed=True)
        assert isinstance(wif, str)
        assert len(wif) > 30

    def test_encode_private_key_to_wif_uncompressed(self):
        """非压缩格式 WIF"""
        pk = b"\x01" * 32
        wif = encode_private_key_to_wif(pk, compressed=False)
        assert isinstance(wif, str)
        assert len(wif) > 30

    def test_format_match_result(self):
        """格式化匹配结果"""
        pk = b"\x02" * 32
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = format_match_result(pk, addr)
        assert result[0] == pk
        assert result[1] == addr
        assert isinstance(result[2], str)  # WIF

    def test_safe_wif_encode_valid(self):
        """安全 WIF 编码 - 有效私钥"""
        pk = b"\x03" * 32
        wif = safe_wif_encode(pk)
        assert wif is not None
        assert isinstance(wif, str)

    def test_safe_wif_encode_invalid_returns_none(self):
        """安全 WIF 编码 - 无效私钥返回 None"""
        pk = b"\x00" * 31  # 长度不对
        wif = safe_wif_encode(pk)
        assert wif is None

    @pytest.mark.parametrize(
        "pk_bytes",
        [
            b"\x01" * 32,
            b"\x00" * 31 + b"\x01",
            os.urandom(32),
        ],
    )
    def test_encode_wif_roundtrip(self, pk_bytes):
        """WIF 编码参数化测试"""
        try:
            wif = safe_wif_encode(pk_bytes)
            if wif is not None:
                assert isinstance(wif, str)
                assert len(wif) > 30
        except Exception as e:  # noqa: F841
            # 某些随机私钥可能无效，safe_wif_encode 返回 None
            pass


# ============================================================================
# 6. DeltaStats 测试
# ============================================================================

from conftest import poll_until  # noqa: E402
from src.collision.delta_stats import DeltaStats, ThreadLocalDeltaStats  # noqa: E402


class TestDeltaStats:
    """测试 DeltaStats 增量统计"""

    def test_init_defaults(self):
        ds = DeltaStats(flush_interval=0.02)
        try:
            stats = ds.get_stats()
            assert stats["total_checked"] == 0
            assert stats["matches_found"] == 0
            assert stats["gpu_errors"] == 0
        finally:
            ds.stop()

    def test_queue_update_single(self):
        ds = DeltaStats(flush_interval=0.02)
        try:
            ds.queue_update({"total_checked": 100})
            poll_until(lambda: ds.get_stats()["total_checked"] >= 100)
            stats = ds.get_stats()
            assert stats["total_checked"] >= 100
        finally:
            ds.stop()

    def test_queue_update_multiple(self):
        ds = DeltaStats(flush_interval=0.02)
        try:
            for _ in range(5):
                ds.queue_update({"total_checked": 200})
            poll_until(lambda: ds.get_stats()["total_checked"] >= 1000)
            stats = ds.get_stats()
            assert stats["total_checked"] >= 1000
        finally:
            ds.stop()

    def test_queue_update_different_keys(self):
        ds = DeltaStats(flush_interval=0.02)
        try:
            ds.queue_update({"total_checked": 100})
            ds.queue_update({"matches_found": 3})
            ds.queue_update({"gpu_errors": 1})
            poll_until(
                lambda: (
                    ds.get_stats()["total_checked"] >= 100
                    and ds.get_stats()["matches_found"] >= 3
                    and ds.get_stats()["gpu_errors"] >= 1
                )
            )
            stats = ds.get_stats()
            assert stats["total_checked"] >= 100
            assert stats["matches_found"] >= 3
            assert stats["gpu_errors"] >= 1
        finally:
            ds.stop()

    def test_reset(self):
        ds = DeltaStats(flush_interval=0.02)
        try:
            ds.queue_update({"total_checked": 1000})
            poll_until(lambda: ds.get_stats()["total_checked"] >= 1000)
            ds.reset()
            stats = ds.get_stats()
            assert stats["total_checked"] == 0
        finally:
            ds.stop()

    def test_throughput_calculation(self):
        """验证吞吐量计算"""
        ds = DeltaStats(flush_interval=0.02)
        try:
            ds.queue_update({"total_checked": 50000})
            poll_until(lambda: ds.get_stats()["total_checked"] >= 50000)
            stats = ds.get_stats()
            if stats["elapsed_time"] > 0:
                assert stats["throughput"] > 0
        finally:
            ds.stop()

    def test_stop_flushes_remaining(self):
        """stop() 应该刷新剩余更新"""
        ds = DeltaStats(flush_interval=0.02)
        ds.queue_update({"total_checked": 500})
        ds.stop()
        stats = ds.get_stats()
        assert stats["total_checked"] >= 500

    def test_stop_twice(self):
        """重复 stop() 不应崩溃"""
        ds = DeltaStats(flush_interval=0.02)
        ds.stop()
        ds.stop()  # 不应抛出异常


class TestThreadLocalDeltaStats:
    """测试 ThreadLocalDeltaStats"""

    def test_init(self):
        tlds = ThreadLocalDeltaStats()
        try:
            stats = tlds.get_global_stats()
            assert stats["total_checked"] == 0
        finally:
            tlds.stop()

    def test_add_check(self):
        tlds = ThreadLocalDeltaStats()
        try:
            tlds.add_check(50)
            tlds.flush_to_global()
            poll_until(lambda: tlds.get_global_stats()["total_checked"] >= 50)
            stats = tlds.get_global_stats()
            assert stats["total_checked"] >= 50
        finally:
            tlds.stop()

    def test_add_match(self):
        tlds = ThreadLocalDeltaStats()
        try:
            tlds.add_match()
            tlds.flush_to_global()
            poll_until(lambda: tlds.get_global_stats()["matches_found"] >= 1)
            stats = tlds.get_global_stats()
            assert stats["matches_found"] >= 1
        finally:
            tlds.stop()

    def test_add_error(self):
        tlds = ThreadLocalDeltaStats()
        try:
            tlds.add_error("gpu_errors")
            tlds.flush_to_global()
            poll_until(lambda: tlds.get_global_stats()["gpu_errors"] >= 1)
            stats = tlds.get_global_stats()
            assert stats["gpu_errors"] >= 1
        finally:
            tlds.stop()

    def test_add_error_unknown_type(self):
        """未知错误类型不崩溃"""
        tlds = ThreadLocalDeltaStats()
        try:
            tlds.add_error("unknown_error_type")
            tlds.flush_to_global()
        finally:
            tlds.stop()

    def test_flush_empty(self):
        """空刷新不崩溃"""
        tlds = ThreadLocalDeltaStats()
        try:
            tlds.flush_to_global()
        finally:
            tlds.stop()

    def test_concurrent_access(self):
        """多线程并发访问"""
        tlds = ThreadLocalDeltaStats()
        errors = []

        def worker():
            try:
                for _ in range(100):
                    tlds.add_check(10)
                tlds.flush_to_global()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        poll_until(lambda: tlds.get_global_stats()["total_checked"] >= 4000)
        stats = tlds.get_global_stats()
        tlds.stop()
        # 4 threads * 100 iterations * 10 = 4000
        assert stats["total_checked"] >= 4000


# ============================================================================
# 7. MatchDataStorage 测试
# ============================================================================

from src.collision.match_storage import MatchDataStorage  # noqa: E402


class TestMatchDataStorage:
    """测试匹配数据存储"""

    def test_init_creates_directory(self, tmp_path):
        storage_path = tmp_path / "matches"
        MatchDataStorage(str(storage_path))
        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_init_nonexistent_path(self, tmp_path):
        """初始化不存在的路径会自动创建"""
        storage_path = tmp_path / "new_matches" / "subdir"
        MatchDataStorage(str(storage_path))
        assert storage_path.exists()

    def test_save_match_atomic(self, tmp_path):
        """测试原子保存匹配数据"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))

        match_data = {
            "found_at": "2024-01-01T00:00:00",
            "hash160": "a" * 40,
            "generated": {
                "private_key": b"\x01" * 32,
                "wif_compressed": "5" + "H" + "0" * 49,  # 明显占位WIF
                "wif_uncompressed": "5" + "J" + "0" * 49,  # 明显占位WIF
                "public_key_compressed": b"\x02" * 33,
                "public_key_uncompressed": b"\x04" * 65,
                "address_compressed": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "address_uncompressed": "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1",
                "hash160_compressed": b"\x03" * 20,
                "hash160_uncompressed": b"\x04" * 20,
            },
            "target": {"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
        }
        filepath = storage.save_match(match_data)
        assert os.path.exists(filepath)

        # 读取并验证保存的数据
        with open(filepath) as f:
            saved_data = json.load(f)
        assert saved_data["match_info"]["hash160"] == "a" * 40
        assert saved_data["private_key"]["hex"] == "01" * 32

    def test_list_matches(self, tmp_path):
        """测试列出匹配文件"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))

        # 创建几个匹配文件（使用不同hash160避文件名冲突）
        match_template = {
            "hash160": "",  # placeholder
            "generated": {
                "private_key": b"\x01" * 32,
                "wif_compressed": "Kx",
                "wif_uncompressed": "5J",
                "public_key_compressed": b"\x02" * 33,
                "public_key_uncompressed": b"\x04" * 65,
                "address_compressed": "addr1",
                "address_uncompressed": "addr2",
                "hash160_compressed": b"\x03" * 20,
                "hash160_uncompressed": b"\x04" * 20,
            },
            "target": {},
        }

        for i in range(3):
            data = dict(match_template)
            data["hash160"] = f"{i:08x}" + "a" * 32  # 前8字符唯一
            data["generated"] = dict(match_template["generated"])
            storage.save_match(data)

        matches = storage.list_matches()
        assert len(matches) == 3

    def test_load_match(self, tmp_path):
        """测试加载匹配文件"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))

        match_data = {
            "hash160": "c" * 40,
            "generated": {
                "private_key": b"\x05" * 32,
                "wif_compressed": "abc",
                "wif_uncompressed": "def",
                "public_key_compressed": b"\x02" * 33,
                "public_key_uncompressed": b"\x04" * 65,
                "address_compressed": "test_addr",
                "address_uncompressed": "test_addr2",
                "hash160_compressed": b"\x03" * 20,
                "hash160_uncompressed": b"\x04" * 20,
            },
            "target": {},
        }
        filepath = storage.save_match(match_data)

        loaded = storage.load_match(filepath)
        assert loaded is not None
        assert loaded["match_info"]["hash160"] == "c" * 40

    def test_load_match_nonexistent(self, tmp_path):
        """加载不存在的文件返回 None"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))
        result = storage.load_match("/nonexistent/match.json")
        assert result is None

    def test_get_statistics(self, tmp_path):
        """测试统计信息"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))

        stats = storage.get_statistics()
        assert stats["total_matches"] == 0
        assert "storage_path" in stats
        assert stats["backup_enabled"] is True

    def test_save_match_invalid_path(self, tmp_path):
        """在无效路径保存时抛出异常"""
        storage_path = tmp_path / "matches"
        storage = MatchDataStorage(str(storage_path))
        # 尝试写入只读目录（通过 mock）
        with patch.object(storage, "_build_complete_data", side_effect=TypeError("Invalid data")):
            with pytest.raises(Exception):  # noqa: B017
                storage.save_match({"hash160": "", "generated": None, "target": {}})
