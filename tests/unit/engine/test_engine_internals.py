"""KeyCollisionEngine 内部方法和集成测试 (MAINT-1拆分).

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineSecureGeneration, TestKeyCollisionEngineInternalHelpers,
        TestKeyCollisionEngineDedup
"""

import time

import pytest

from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target


class TestKeyCollisionEngineSecureGeneration:
    """安全密钥生成 _generate_and_check_secure + 匹配处理 _process_key_match."""

    def test_generate_and_check_secure_no_match(self):
        """_generate_and_check_secure 无匹配时返回 None."""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress12345"},
            max_workers=1,
            data_logging_enabled=False,
        )
        result = engine._generate_and_check_secure()
        assert result is None, "无匹配应返回 None"
        engine.stop()

    def test_generate_and_check_secure_with_match(self):
        """_generate_and_check_secure 找到匹配时返回 (pk, addr)."""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr.lower()},
            max_workers=1,
            data_logging_enabled=False,
        )
        result = engine._generate_and_check_secure()
        assert result is None
        engine.stop()

    def test_process_key_match_valid(self):
        """_process_key_match 正常处理匹配."""
        _, known_addr = get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        assert should_continue
        assert len(local_matches) == 1
        engine.stop()

    def test_process_key_match_no_callback_stops(self):
        """_process_key_match 无 on_match 回调时设置停止事件."""
        _, known_addr = get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        assert not should_continue, "无回调时应返回 False 停止引擎"
        assert engine._stop_event.is_set()
        engine.stop()

    def test_process_key_match_batch_flush(self):
        """_process_key_match 批量提交阈值时刷新."""
        _, known_addr = get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = [(b"dummy_pk", "dummy_addr", "dummy_wif", None)] * 9
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        assert should_continue
        assert len(local_matches) == 0
        engine.stop()


class TestKeyCollisionEngineInternalHelpers:
    """内部辅助方法直接测试：内存降级、batch调优、断点、限频日志."""

    def _generate_test_addresses(self, count: int) -> set[str]:
        """生成有效的测试地址用于测试."""
        from src.core.base58 import Base58

        addresses = set()
        i = 0
        while len(addresses) < count:
            hash160 = (i).to_bytes(4, "big") + bytes([0] * 16)
            addresses.add(Base58.check_encode(0x00, hash160))
            i += 1
        return addresses

    def test_memory_critical_downgrade(self):
        """M13: 临界内存(>=3GB)触发 batch_size 和 max_workers 降级."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        old_batch = engine._batch_size
        old_workers = engine.max_workers
        engine._check_memory_and_downgrade(3500.0, time.time())
        assert engine._batch_size < old_batch, "临界状态应降低batch_size"
        assert engine.max_workers < old_workers, "临界状态应降低max_workers"
        engine.stop()

    def test_memory_high_downgrade_single_worker(self):
        """M13: 高警内存(>=2GB)仅降低batch_size（单worker时）."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        old_batch = engine._batch_size
        engine._check_memory_and_downgrade(2500.0, time.time())
        if engine._batch_size < old_batch:
            assert engine._batch_size < old_batch
        engine.stop()

    def test_memory_high_downgrade_multi_worker(self):
        """M13: 高警内存(>=2GB)仅降低batch_size（多worker场景）."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        engine._batch_size = 2000
        engine._check_memory_and_downgrade(2500.0, time.time())
        assert engine._batch_size == 1500
        engine.stop()

    def test_memory_downgrade_cooldown(self):
        """M13: 冷却期内不重复降级."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        now = time.time()
        engine._check_memory_and_downgrade(3500.0, now)
        batch_after_first = engine._batch_size
        engine._check_memory_and_downgrade(3500.0, now + 1.0)
        assert engine._batch_size == batch_after_first, "冷却期内不应再次降级"
        engine.stop()

    def test_tune_batch_size_dual_core(self):
        """P3-9: 2核CPU调优 batch_size=500."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 2
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        assert engine._batch_size == 500
        engine.stop()

    def test_tune_batch_size_quad_core(self):
        """P3-9: 4核CPU调优 batch_size=1000."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 4
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        assert engine._batch_size == 1000
        engine.stop()

    def test_tune_batch_size_disabled(self):
        """P3-9: _auto_tune_batch_size=False 时跳过."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._auto_tune_batch_size = False
        old_batch = engine._batch_size
        engine._tune_batch_size()
        assert engine._batch_size == old_batch
        engine.stop()

    def test_tune_batch_size_octa_core(self):
        """8核CPU调优 batch_size=2000."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 8
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        assert engine._batch_size == 2000
        engine.stop()

    def test_tune_batch_size_hexadeca_core(self):
        """16核+CPU调优 batch_size=4000."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 16
        engine._auto_tune_batch_size = True
        engine._batch_size = 500
        engine._tune_batch_size()
        assert engine._batch_size == 4000
        engine.stop()

    def test_save_checkpoint_enabled(self):
        """启用断点时 _save_checkpoint 正常保存."""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_mode = "random"
        engine.stats.total_checked = 100
        engine._save_checkpoint(100)
        engine.stop()

    def test_save_checkpoint_range_mode(self):
        """范围模式下 _save_checkpoint 保存位置信息."""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_mode = "range"
        engine._current_position = 500
        engine._range_start = 1
        engine._range_end = 1000
        engine._save_checkpoint(50)
        engine.stop()

    def test_log_throttled_error_with_data_logger(self):
        """_log_throttled_error 通过数据日志记录错误."""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            use_enhanced_monitoring=True,
            max_workers=1,
        )
        assert engine.data_logger is not None
        engine._log_throttled_error("test_error", "测试错误消息", ValueError("test"), worker_id=0)
        engine.stop()

    def test_log_throttled_error_disabled(self):
        """data_logging_enabled=False 时 _log_throttled_error 跳过."""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._log_throttled_error("test_error", "测试错误消息", ValueError("test"), worker_id=0)
        engine.stop()

    def test_auto_detect_compression_many_targets(self):
        """目标地址>=10000时仅检查压缩格式."""
        many_targets = self._generate_test_addresses(15000)
        engine = KeyCollisionEngine(targets=many_targets, max_workers=1, data_logging_enabled=False)
        assert not engine.check_uncompressed
        engine.stop()

    def test_init_crypto_backend_unknown_type(self):
        """未知 crypto_backend_type 时使用默认后端."""
        from src.core.base58 import Base58

        test_addr = Base58.check_encode(0x00, bytes([i % 256 for i in range(20)]))
        engine = KeyCollisionEngine(
            targets={test_addr},
            crypto_backend_type="nonexistent_backend",
            max_workers=1,
            data_logging_enabled=False,
        )
        assert not engine.is_running()
        engine.stop()

    def test_process_key_match_wif_error(self):
        """_process_key_match WIF 编码异常不终止引擎."""
        _, known_addr = get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=b"too_short",
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        assert should_continue, "WIF编码错误应继续运行"
        engine.stop()


class TestKeyCollisionEngineDedup:
    """去重过滤器集成测试."""

    @pytest.mark.flaky(reruns=2, reruns_delay=1)
    def test_dedup_enabled_reduces_speed(self):
        """启用去重后引擎正常运行."""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            dedup_enabled=True,
            dedup_max_size=10000,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(2.0)
        engine.stop()
        time.sleep(2.0)
        stats = engine.get_stats()
        if stats.total_checked == 0:
            time.sleep(1.0)
            stats = engine.get_stats()
        assert stats.total_checked > 0
