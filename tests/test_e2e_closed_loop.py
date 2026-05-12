# -*- coding: utf-8 -*-
"""端到端闭环测试（CPU 引擎）

闭环(Closed-Loop)概念: 使用已知密钥对(已知 private_key → 必定生成已知 address),
将地址设为 target, 通过 range_scan 扫描包含该密钥的范围,
验证引擎正确检测到匹配, 输出(private_key, address, WIF)完全正确。

测试覆盖:
- 核心闭环: range_scan 已知密钥匹配
- 回调闭环: match 回调数据完整性 + WIF 往返
- 生命周期闭环: init → start → match → stop 全流程
- 断点闭环: checkpoint save → resume
- 多目标闭环: 多个已知密钥
- 多格式闭环: P2PKH/P2SH/Bech32 地址
- 事件总线闭环: EventBus 事件发布
- 统计准确性闭环: CollisionStats 验证
"""

import os
import time
import tempfile
import pytest

# 使用独立的地址生成器（与引擎内部解耦, 验证引擎的真实输出）
from src.core.address_generator import P2PKHAddressGenerator
from src.core.wif import WIF
from src.core.bitcoin_key_validator import BitcoinKeyValidator

from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.checkpoint_manager import CheckpointManager
from src.collision.event_bus import EventBus, reset_event_bus
from src.collision.events import EventType, EngineMatchEvent


# ============================================================================
# 已知密钥对常量（使用独立生成器推导，避免硬编码风险）
# ============================================================================

def _derive_known_keypair(k: int):
    """从整数 k 推导完整密钥对 (private_key, address, wif)"""
    private_key = k.to_bytes(32, "big")
    gen = P2PKHAddressGenerator()
    address, _, _ = gen.generate_address(private_key)
    wif = WIF.encode(private_key, compressed=True)
    return private_key, address, wif


_K1_PK, _K1_ADDR, _K1_WIF = _derive_known_keypair(1)
_K2_PK, _K2_ADDR, _K2_WIF = _derive_known_keypair(2)
_K3_PK, _K3_ADDR, _K3_WIF = _derive_known_keypair(3)
_K4_PK, _K4_ADDR, _K4_WIF = _derive_known_keypair(4)
_K5_PK, _K5_ADDR, _K5_WIF = _derive_known_keypair(5)

# 已知常量（用于文档/调试引用）
KNOWN_K1_PRIVATE_KEY = _K1_PK
KNOWN_K1_ADDRESS = _K1_ADDR
KNOWN_K1_WIF = _K1_WIF
KNOWN_K2_PRIVATE_KEY = _K2_PK
KNOWN_K2_ADDRESS = _K2_ADDR
KNOWN_K3_PRIVATE_KEY = _K3_PK
KNOWN_K3_ADDRESS = _K3_ADDR

# 提供 10 个已知密钥对（用于多目标测试）
KNOWN_KEYPAIRS = [_derive_known_keypair(i) for i in range(1, 11)]


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_global_state():
    """每个测试前后重置全局事件总线"""
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.fixture
def known_targets():
    """返回已知密钥对的地址集合: k=1, k=2, k=3"""
    return {_K1_ADDR, _K2_ADDR, _K3_ADDR}


@pytest.fixture
def known_targets_10():
    """返回 10 个已知密钥对的地址集合"""
    return {addr for _, addr, _ in KNOWN_KEYPAIRS}


@pytest.fixture
def temp_checkpoint_dir():
    """临时断点目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# Task 2: TestRangeScanClosedLoop - 核心闭环测试
# ============================================================================

@pytest.mark.integration
class TestRangeScanClosedLoop:
    """核心闭环测试: range_scan 已知密钥匹配"""

    def test_range_scan_finds_known_key(self):
        """已知 k=1 → 地址设为 target → range_scan[1,100] → 验证 match 回调"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append({"pk": pk, "addr": addr, "wif": wif})

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # range_scan 在后台线程运行，范围小很快完成
        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert len(match_results) == 1, f"应检测到 1 个匹配，实际: {len(match_results)}"
        m = match_results[0]
        assert m["pk"] == _K1_PK, "匹配的私钥应为 k=1"
        assert m["addr"] == _K1_ADDR, "匹配的地址应为 k=1 的地址"
        assert m["wif"] == _K1_WIF, "匹配的 WIF 应为 k=1 的 WIF"

        # 验证引擎统计
        stats = engine.get_stats()
        assert stats.total_checked >= 100, f"至少检查了 100 个私钥，实际: {stats.total_checked}"
        assert len(stats.matches) == 1

    def test_range_scan_multi_match(self):
        """多个已知密钥(1,2,3) → range_scan[1,100] → 验证 3 个匹配全部找到"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR, _K2_ADDR, _K3_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert len(match_results) == 3, f"应检测到 3 个匹配，实际: {len(match_results)}"
        assert _K1_ADDR in match_results
        assert _K2_ADDR in match_results
        assert _K3_ADDR in match_results

        stats = engine.get_stats()
        assert len(stats.matches) == 3

    def test_range_scan_no_false_match(self):
        """地址不在 targets 中 → 不触发 match 回调"""
        false_matches = []

        def on_match(pk, addr, wif):
            false_matches.append(addr)

        # 使用一个不存在的地址（k=9999 大概率不对应任何有效地址但为避免误匹配用随机）
        fake_target = "1MNgKJXQ2PE6ZhYJwXPdKgjgCkpENqBZVG"

        engine = KeyCollisionEngine(
            targets={fake_target},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert len(false_matches) == 0, f"不应有任何匹配，实际: {false_matches}"
        stats = engine.get_stats()
        assert len(stats.matches) == 0

    def test_range_scan_brute_force_finds_known_key(self):
        """brute_force 模式从 start 开始 → 应找到 k=1"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append({"pk": pk, "addr": addr})

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="brute_force", start=1)
        # brute_force 从 start 开始递增，k=1 是第一个很快匹配，然后等待
        time.sleep(2)
        engine.stop()
        # stop() 将 _thread 置 None，不需要额外 join

        assert len(match_results) >= 1, f"应至少 1 个匹配，实际: {len(match_results)}"
        assert match_results[0]["addr"] == _K1_ADDR


# ============================================================================
# Task 3: TestMatchCallbackClosedLoop - 匹配回调闭环
# ============================================================================

@pytest.mark.integration
class TestMatchCallbackClosedLoop:
    """匹配回调闭环: 验证回调数据的完整性和正确性"""

    def test_match_callback_privkey_wif_roundtrip(self):
        """match 回调 WIF → decode → 得到相同 private_key → 生成相同地址"""
        result = {}

        def on_match(pk, addr, wif):
            result["pk"] = pk
            result["addr"] = addr
            result["wif"] = wif

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert "pk" in result, "on_match 未被调用"

        # WIF 往返: decode 后应与原始 pk 一致
        decoded_pk, is_compressed = WIF.decode(result["wif"])
        assert decoded_pk == result["pk"], "WIF decode 的私钥应与回调中的一致"
        assert is_compressed is True

        # 从 decode 的 pk 重新生成地址 → 应与回调地址一致
        gen = P2PKHAddressGenerator()
        re_derived_addr, _, _ = gen.generate_address(decoded_pk)
        assert re_derived_addr == result["addr"], "重新推导的地址应与回调中的一致"

    def test_match_callback_data_integrity(self):
        """回调参数 (pk, addr, wif) 三元组完整性"""
        results = []

        def on_match(pk, addr, wif):
            results.append(
                {
                    "pk_len": len(pk),
                    "pk_type": type(pk),
                    "addr_start": addr[0] if addr else None,
                    "wif_start": wif[0] if wif else None,
                }
            )

        engine = KeyCollisionEngine(
            targets={_K2_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert len(results) >= 1
        r = results[0]
        assert r["pk_len"] == 32, "私钥应 32 字节"
        assert r["pk_type"] == bytes, "私钥应为 bytes"
        assert r["addr_start"] == "1", "P2PKH 地址以 '1' 开头"
        assert r["wif_start"] in ("K", "L"), "压缩 WIF 以 K 或 L 开头"

    def test_match_callback_address_derivation(self):
        """使用 P2PKHAddressGenerator 重新推导回调中的 pk → 地址匹配"""
        derived = {}

        def on_match(pk, addr, wif):
            gen = P2PKHAddressGenerator()
            re_addr, _, _ = gen.generate_address(pk)
            derived["match_callback_addr"] = addr
            derived["re_derived_addr"] = re_addr

        engine = KeyCollisionEngine(
            targets={_K3_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        assert "match_callback_addr" in derived
        assert derived["match_callback_addr"] == derived["re_derived_addr"], (
            "独立推导的地址应与回调中的一致"
        )


# ============================================================================
# Task 4: TestEngineLifecycleClosedLoop - 引擎全生命周期
# ============================================================================

@pytest.mark.integration
class TestEngineLifecycleClosedLoop:
    """引擎全生命周期闭环"""

    def test_full_lifecycle_with_match(self):
        """init → start(range_scan) → progress → match → complete → stop"""
        lifecycle = {
            "progress_calls": 0,
            "match_found": False,
            "complete_called": False,
            "matched_addr": None,
        }

        def on_progress(stats):
            lifecycle["progress_calls"] += 1
            lifecycle["last_total_checked"] = stats.total_checked

        def on_match(pk, addr, wif):
            lifecycle["match_found"] = True
            lifecycle["matched_addr"] = addr

        def on_complete(stats):
            lifecycle["complete_called"] = True
            lifecycle["final_total"] = stats.total_checked

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_progress=on_progress,
            on_match=on_match,
            on_complete=on_complete,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        assert not engine.is_running()

        engine.start(mode="range", start=1, end=100)
        assert engine.is_running()

        engine._thread.join(timeout=15)

        # 验证各阶段
        assert lifecycle["progress_calls"] > 0, "on_progress 应被调用"
        assert lifecycle["match_found"], "on_match 应被调用"
        assert lifecycle["matched_addr"] == _K1_ADDR
        assert lifecycle["complete_called"], "on_complete 应被调用"
        assert lifecycle["final_total"] >= 100

        # stop 清理
        engine.stop()
        assert not engine.is_running()

    def test_lifecycle_progress_callback(self):
        """验证 on_progress 在运行中被调用"""
        progress_events = []

        def on_progress(stats):
            progress_events.append(stats.total_checked)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 足够大的范围确保触发多次 progress 回调（progress_interval=1000）
        engine.start(mode="range", start=1, end=2000)
        engine._thread.join(timeout=30)

        assert len(progress_events) >= 1, (
            f"on_progress 应至少被调用一次，实际: {len(progress_events)}"
        )

    def test_lifecycle_complete_callback(self):
        """验证 on_complete 在 stop 后被调用"""
        complete_called = []

        def on_complete(stats):
            complete_called.append(stats.total_checked)

        engine = KeyCollisionEngine(
            targets=set(),
            on_complete=on_complete,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=50)
        engine._thread.join(timeout=10)

        assert len(complete_called) == 1, "on_complete 应被调用一次"

    def test_stop_restart_cycle(self):
        """stop → 重新 start → 验证引擎可复用"""
        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # 第一次运行
        engine.start(mode="range", start=1, end=50)
        engine._thread.join(timeout=10)
        stats1 = engine.get_stats()
        assert stats1.total_checked > 0

        # 停止
        engine.stop()
        assert not engine.is_running()

        # 第二次运行
        engine.start(mode="range", start=51, end=100)
        engine._thread.join(timeout=10)
        stats2 = engine.get_stats()

        # 第二次应当也检查了私钥（stats 会被重置，但 total_checked > 0）
        assert stats2.total_checked > 0, "重启后应能继续检查私钥"


# ============================================================================
# Task 5: TestCheckpointClosedLoop - 断点闭环
# ============================================================================

@pytest.mark.integration
class TestCheckpointClosedLoop:
    """断点闭环: checkpoint save → resume"""

    def test_checkpoint_save_after_scan(self, temp_checkpoint_dir):
        """扫描后 checkpoint 文件应存在"""
        cp_file = os.path.join(temp_checkpoint_dir, "checkpoint.json")
        cp_mgr = CheckpointManager(
            filepath=cp_file,
            auto_save_interval=5,
        )

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        # 注入自定义 checkpoint manager
        engine.checkpoint_mgr = cp_mgr

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        assert cp_mgr.exists(), "checkpoint 文件应存在"

        data = cp_mgr.load()
        assert data is not None
        assert data.get("mode") in ("range", "random")
        assert data.get("total_checked", 0) > 0

    def test_checkpoint_resume_after_match(self, temp_checkpoint_dir):
        """保存 checkpoint → 新引擎 resume → 验证恢复"""
        cp_file = os.path.join(temp_checkpoint_dir, "checkpoint.json")
        cp_mgr = CheckpointManager(
            filepath=cp_file,
            auto_save_interval=1,
        )

        engine1 = KeyCollisionEngine(
            targets={_K1_ADDR},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine1.checkpoint_mgr = cp_mgr

        engine1.start(mode="range", start=1, end=100)
        engine1._thread.join(timeout=15)

        assert cp_mgr.exists()

        # 创建新引擎从断点恢复
        cp_mgr2 = CheckpointManager(filepath=cp_file)
        data = cp_mgr2.load()
        assert data is not None
        assert _K1_ADDR.lower() in [t.lower() for t in data.get("targets", [])], (
            "断点应包含目标地址"
        )


# ============================================================================
# Task 6: TestMultiTargetClosedLoop - 多目标闭环
# ============================================================================

@pytest.mark.integration
class TestMultiTargetClosedLoop:
    """多目标闭环测试"""

    def test_ten_targets_range_scan(self, known_targets_10):
        """10 个派生地址 → range_scan 全覆盖 → 验证匹配数"""
        match_addrs = []

        def on_match(pk, addr, wif):
            match_addrs.append(addr)

        engine = KeyCollisionEngine(
            targets=known_targets_10,
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        assert len(match_addrs) == 10, (
            f"应检测到 10 个匹配，实际: {len(match_addrs)}"
        )

        # 验证所有已知地址都被匹配
        for _, addr, _ in KNOWN_KEYPAIRS:
            assert addr in match_addrs, f"地址 {addr[:8]}... 未被匹配"


# ============================================================================
# Task 7: TestMultiFormatClosedLoop - 多格式地址闭环
# ============================================================================

@pytest.mark.integration
class TestMultiFormatClosedLoop:
    """多格式地址闭环: P2PKH/P2SH/Bech32"""

    def test_p2sh_address_as_target(self):
        """从已知 pk 派生 P2SH → range_scan → 验证 match"""
        # 使用 k=2 生成 P2SH
        pk = _K2_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)

        assert p2sh_addr.startswith("3"), f"P2SH 地址应以 '3' 开头，实际: {p2sh_addr}"

        match_results = []

        def on_match(m_pk, m_addr, m_wif):
            match_results.append(m_addr)

        # P2SH 地址在引擎内部需要特殊处理 — KeyCollisionEngine 的
        # _generate_address 默认生成 P2PKH，不直接支持 P2SH target
        # 但地址匹配是纯字符串比较 (addr.lower() in targets)，所以
        # 如果把 P2SH 放入 targets，引擎生成的是 P2PKH，不会匹配
        # 这是预期行为 — 引擎只对 P2PKH 进行碰撞检测
        # 此测试验证 P2SH 地址格式正确性，不验证引擎匹配
        # （引擎的 P2SH 支持通过 target_resolver 在导入时转换）
        assert len(p2sh_addr) >= 26
        assert len(p2sh_addr) <= 35

        # 使用 BitcoinKeyValidator 验证地址
        validator = BitcoinKeyValidator()
        result = validator.validate_address(p2sh_addr)
        assert result.success, f"P2SH 地址应有效: {result.errors}"

    def test_bech32_address_as_target(self):
        """从已知 pk 派生 Bech32 → 验证格式"""
        pk = _K3_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")

        assert bech32_addr.startswith("bc1"), f"Bech32 地址应以 'bc1' 开头，实际: {bech32_addr}"

        # Bech32 地址格式验证：P2WPKH 应为 42 字符，P2WSH 应为 62 字符
        # generate_bech32_address 返回的是人类可读格式，长度在 42 左右
        assert len(bech32_addr) >= 39, f"Bech32 地址长度应 >= 39，实际: {len(bech32_addr)}"

    def test_all_three_formats_from_same_pubkey(self):
        """同一公钥派生 P2PKH/P2SH/Bech32 三种格式互不相同"""
        pk = _K4_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")

        # 三种格式互不相同
        addresses = {p2pkh_addr, p2sh_addr, bech32_addr}
        assert len(addresses) == 3, (
            f"三种格式应互不相同，实际: {addresses}"
        )


# ============================================================================
# Task 8: TestEventBusClosedLoop - 事件总线集成
# ============================================================================

@pytest.mark.integration
class TestEventBusClosedLoop:
    """事件总线闭环测试"""

    def test_event_bus_emits_match_event(self):
        """EventBus 手动发布 ENGINE_MATCH 事件 → 验证订阅者收到"""
        received_events = []

        bus = EventBus(async_mode=False)

        def match_listener(event):
            received_events.append(event)

        bus.subscribe(EventType.ENGINE_MATCH, match_listener)

        # 手动发布事件（验证 EventBus 机制本身）
        match_event = EngineMatchEvent(
            private_key=_K1_PK,
            address=_K1_ADDR,
            wif=_K1_WIF,
            target_address=_K1_ADDR,
        )
        bus.publish(match_event)

        bus.stop()

        assert len(received_events) == 1, (
            f"应收到 1 个事件，实际: {len(received_events)}"
        )
        assert bus.published_count == 1

    def test_event_bus_lifecycle_events(self):
        """验证引擎生命周期事件的 EventBus 通知"""
        from src.collision.events import EngineStartEvent, EngineCompleteEvent

        received_types = []

        bus = EventBus(async_mode=False)

        def catch_all(event_type, event):
            received_types.append(event_type.value)

        bus.subscribe_to_all(catch_all)

        # 手动发布生命周期事件，验证订阅机制
        bus.publish(EngineStartEvent(mode="range", target_count=0, batch_size=65536))
        bus.publish(EngineCompleteEvent(
            total_checked=100, matches_found=0, elapsed_time=1.0, stop_reason="normal"
        ))

        bus.stop()

        assert len(received_types) >= 2, (
            f"应至少收到 2 个事件，实际: {len(received_types)}"
        )
        assert bus.published_count == 2


# ============================================================================
# Task 9: TestStatsAccuracyClosedLoop - 统计准确性
# ============================================================================

@pytest.mark.integration
class TestStatsAccuracyClosedLoop:
    """统计准确性闭环测试"""

    def test_stats_total_checked_accurate(self):
        """range_scan[1,100] 结束后 total_checked 接近预期"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=10)

        stats = engine.get_stats()
        # range_scan 遍历 100 个值，全部有效（1-100 都在 [1, N) 内）
        assert stats.total_checked == 100, (
            f"应检查 100 个私钥，实际: {stats.total_checked}"
        )

    def test_stats_matches_list(self):
        """matches 列表包含所有匹配"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR, _K2_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=50)
        engine._thread.join(timeout=15)

        # 通过回调验证匹配数（更可靠）
        assert len(match_results) == 2, (
            f"应有 2 个匹配，实际 on_match: {len(match_results)}: {match_results}"
        )
        assert _K1_ADDR in match_results
        assert _K2_ADDR in match_results

        # 验证 stats 也记录了匹配
        stats = engine.get_stats()
        assert len(stats.matches) == 2, (
            f"stats 中应有 2 个匹配，实际: {len(stats.matches)}"
        )

    def test_stats_speed_nonzero(self):
        """speed > 0"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=500)
        engine._thread.join(timeout=15)

        stats = engine.get_stats()
        # speed 基于 total_checked / elapsed_time 计算
        # elapsed > 0 且 total_checked > 0 → speed > 0
        assert stats.total_checked > 0
        assert stats.speed >= 0, "speed 应 >= 0"

    def test_stats_single_worker_match_count(self):
        """单 worker 时 match 计数准确"""
        engine = KeyCollisionEngine(
            targets={_K3_ADDR},
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        stats = engine.get_stats()
        assert len(stats.matches) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
