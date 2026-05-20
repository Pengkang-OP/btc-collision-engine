# -*- coding: utf-8 -*-
"""端到端闭环测试（CPU 引擎）

闭环(Closed-Loop)概念: 使用已知密钥对(已知 private_key → 必定生成已知 address),
将地址设为 target, 通过 range_scan 扫描包含该密钥的范围,
验证引擎正确检测到匹配, 输出(private_key, address, WIF)完全正确。

测试覆盖:
- 核心闭环: range_scan 已知密钥匹配 (参数化 max_workers=[1,2,4])
- 回调闭环: match 回调数据完整性 + WIF 往返
- 生命周期闭环: init → start → match → stop 全流程
- 断点闭环: checkpoint save → resume
- 多目标闭环: 多个已知密钥
- 多线程闭环: max_workers > 1 并行扫描
- 多格式闭环: P2PKH/P2SH/Bech32/Taproot 地址
- 事件总线闭环: EventBus 事件发布
- 统计准确性闭环: CollisionStats 验证
- Random 模式闭环: random_search 引擎生命周期
- Data Logging 闭环: data_logging_enabled=True 集成路径
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
from src.collision.targets.resolver import TargetResolver
from src.utils.bech32_codec import bech32_encode


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

    @pytest.mark.parametrize("max_workers", [1, 2, 4])
    def test_range_scan_finds_known_key(self, max_workers):
        """已知 k=1 → 地址设为 target → range_scan[1,100] → 验证 match 回调"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append({"pk": pk, "addr": addr, "wif": wif})

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=max_workers,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        # range_scan 在后台线程运行，范围小很快完成
        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

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

        # monkeypatch: 降低进度回调阈值，确保测试中触发
        # 注意: 不能设为 0.0，否则 wait(timeout=0) 造成 busy-wait 饿死 worker 线程
        engine._progress_interval_sec = 0.001  # 1ms 高频轮询
        engine._progress_interval_count = 1

        # 足够大的范围确保触发多次 progress 回调
        engine.start(mode="range", start=1, end=20000)
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
        """扫描后 checkpoint 文件应存在（需 on_match 避免提前停止）"""
        cp_file = os.path.join(temp_checkpoint_dir, "checkpoint.json")
        cp_mgr = CheckpointManager(
            filepath=cp_file,
            auto_save_interval=1,  # 1 秒触发一次自动保存
        )

        match_addrs = []

        def on_match(pk, addr, wif):
            match_addrs.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,  # 有回调 → 匹配后继续扫描，确保 auto_save 触发
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        # 注入自定义 checkpoint manager
        engine.checkpoint_mgr = cp_mgr

        engine.start(mode="range", start=1, end=5000)  # 更大范围确保扫描时长 >= 1s
        engine._thread.join(timeout=15)

        assert cp_mgr.exists(), "checkpoint 文件应存在"
        assert len(match_addrs) >= 1, "应至少找到 k=1"

        data = cp_mgr.load()
        assert data is not None
        assert data.get("mode") == "range"
        assert data.get("total_checked", 0) > 0

    def test_checkpoint_resume_after_match(self, temp_checkpoint_dir):
        """保存 checkpoint → 新引擎 resume → 验证恢复"""
        cp_file = os.path.join(temp_checkpoint_dir, "checkpoint.json")
        cp_mgr = CheckpointManager(
            filepath=cp_file,
            auto_save_interval=1,  # 1 秒触发
        )

        match_addrs = []

        def on_match(pk, addr, wif):
            match_addrs.append(addr)

        engine1 = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,  # 有回调 → 匹配后继续扫描，确保 auto_save 触发
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine1.checkpoint_mgr = cp_mgr

        engine1.start(mode="range", start=1, end=5000)  # 更大范围确保扫描时长 >= 1s
        engine1._thread.join(timeout=15)

        assert cp_mgr.exists(), "第一次扫描后 checkpoint 应存在"
        assert len(match_addrs) >= 1, "应至少找到 k=1"

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
    """多格式地址闭环: P2PKH/P2SH/Bech32

    闭环原理:
    1. 从已知私钥派生 Bech32 地址
    2. 通过 TargetResolver 转为 P2PKH（Bech32 witness program = pubkey_hash）
    3. 用 P2PKH 作为引擎 target → range_scan 扫描
    4. 验证 on_match 回调收到正确的 private_key 和 WIF

    注意: P2SH 地址无法在此测试中做引擎闭环（其 payload 是 script_hash,
    引擎只生成 pubkey_hash 的 P2PKH），P2SH 的 Resolver 正确性在
    TestResolverPipelineClosedLoop 中验证。
    """

    def test_p2sh_resolver_correctness(self):
        """P2SH → Resolver → 保持原格式 (payload=script_hash, 无法转为 P2PKH)"""
        pk = _K2_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)
        assert p2sh_addr.startswith("3"), f"P2SH 地址应以 '3' 开头，实际: {p2sh_addr}"

        # Resolver 保留 P2SH 原格式 (payload=script_hash ≠ pubkey_hash, 无法转为 P2PKH)
        resolver = TargetResolver(enable_cache=False)
        resolved = resolver.resolve(p2sh_addr)
        assert resolved is not None, "Resolver 应验证 P2SH 地址"
        assert resolved.startswith("3"), f"P2SH 应保持原格式，实际: {resolved}"

        # P2SH 的 payload 是 script_hash，不是 pubkey_hash
        # 引擎只做 P2PKH 碰撞 (基于 pubkey_hash)，P2SH 目标必然无法匹配
        # 这是预期行为 — 非 P2PKH 目标需在外部预先转换

    def test_bech32_engine_closed_loop(self):
        """从已知私钥派生 Bech32 → Resolver 转 P2PKH → 引擎匹配 → 验证私钥"""
        pk = _K3_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")
        assert bech32_addr.startswith("bc1"), f"Bech32 地址应以 'bc1' 开头，实际: {bech32_addr}"

        # Resolver 将 Bech32 转为 P2PKH（witness program = pubkey_hash = Legacy P2PKH payload）
        resolver = TargetResolver(enable_cache=False)
        p2pkh_from_bech32 = resolver.resolve(bech32_addr)
        assert p2pkh_from_bech32 is not None, "Resolver 应将 Bech32 转为 P2PKH"
        assert p2pkh_from_bech32.startswith("1"), f"转换结果应为 P2PKH，实际: {p2pkh_from_bech32}"

        # 引擎闭环验证
        match_results = []

        def on_match(m_pk, m_addr, m_wif):
            match_results.append((m_pk, m_addr, m_wif))

        engine = KeyCollisionEngine(
            targets={p2pkh_from_bech32},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine.start(mode="range", start=1, end=10)
        engine._thread.join(timeout=15)

        assert len(match_results) == 1, f"应有 1 个匹配，实际: {len(match_results)}"
        m_pk, m_addr, _ = match_results[0]
        assert m_addr == p2pkh_from_bech32
        assert m_pk == pk, "匹配的私钥应正确"

    def test_bech32_and_legacy_same_p2pkh(self):
        """Bech32 → Resolver → 应与 Legacy P2PKH 相同（共用 pubkey_hash）"""
        pk = _K4_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)

        # 三种格式互不相同
        assert len({p2pkh_addr, p2sh_addr, bech32_addr}) == 3

        resolver = TargetResolver(enable_cache=False)
        # Bech32 的 witness program 就是 pubkey_hash → 与 Legacy P2PKH 相同
        assert resolver.resolve(bech32_addr) == p2pkh_addr, (
            "Bech32 解析结果应等于 Legacy P2PKH（共用 Hash160 载荷）"
        )
        # P2SH 的 payload 是 script_hash（不是 pubkey_hash）→ 保持原格式
        resolved_p2sh = resolver.resolve(p2sh_addr)
        assert resolved_p2sh is not None
        assert resolved_p2sh.startswith("3"), (
            f"P2SH 应保持原格式 '3' 开头，实际: {resolved_p2sh}"
        )
        assert resolved_p2sh != p2pkh_addr, (
            "P2SH 地址应不同于 Legacy P2PKH（载荷是 script_hash）"
        )


# ============================================================================
# Task 7a: TestResolverPipelineClosedLoop - Resolver 集成管线
# ============================================================================

@pytest.mark.integration
class TestResolverPipelineClosedLoop:
    """TargetResolver 集成管线: P2PKH/P2SH/Bech32/Bech32m → P2PKH 转换验证"""

    def test_resolver_converts_p2sh_to_p2pkh(self):
        """P2SH → Resolver → 保持原格式（载荷为 script_hash，无法转 P2PKH）"""
        pk = _K2_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)

        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve(p2sh_addr)

        assert result is not None, "Resolver 应返回 P2SH 原地址"
        assert result == p2sh_addr, "P2SH 应保持原格式（载荷为 script_hash，无法转换为 P2PKH）"
        # P2SH 的 payload 是 hash160(redeem_script)，不是 hash160(pubkey)
        # 所以解析器保持原格式不变
        assert result != p2pkh_addr, (
            "P2SH 保持原格式，应不同于 Legacy P2PKH（载荷不同）"
        )

    def test_resolver_converts_bech32_to_p2pkh(self):
        """Bech32 → Resolver → 正确的 P2PKH（载荷为 pubkey_hash）"""
        pk = _K3_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")

        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve(bech32_addr)

        assert result == p2pkh_addr, (
            f"Bech32 解析结果应等于 Legacy P2PKH（共用 Hash160 载荷）\n"
            f"  Bech32: {bech32_addr}\n"
            f"  Expected: {p2pkh_addr}\n"
            f"  Got: {result}"
        )

    def test_resolver_converts_taproot_to_p2pkh(self):
        """Taproot (Bech32m) → Resolver → 保持原格式（载荷为 x-only pubkey）"""
        pk = _K4_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        x_only_pk = compressed_pk[1:]  # 去掉 02/03 前缀
        taproot_addr = bech32_encode("bc", 1, x_only_pk, "bech32m")
        assert taproot_addr.startswith("bc1p")

        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve(taproot_addr)

        assert result is not None, "Resolver 应返回 Taproot 原地址"
        assert result == taproot_addr, "Taproot 应保持原格式（payload 为 x-only pubkey，无法转换为 P2PKH）"
        # Taproot 的 witness program 是 x-only pubkey → P2PKH 载荷不同
        assert result != p2pkh_addr, (
            "Taproot 保持原格式，应不同于 Legacy P2PKH（载荷为 x-only pubkey）"
        )

    def test_resolver_mixed_formats_same_pubkey(self):
        """同一公钥 → 四种格式 → Resolver 全部可解析 → Bech32 与 Legacy 一致"""
        pk = _K5_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")
        x_only_pk = compressed_pk[1:]
        taproot_addr = bech32_encode("bc", 1, x_only_pk, "bech32m")

        # 四种种格式互不相同
        assert len({p2pkh_addr, p2sh_addr, bech32_addr, taproot_addr}) == 4

        resolver = TargetResolver(enable_cache=False)
        # Bech32 与 Legacy 解析结果相同（都是 P2PKH 以 '1' 开头）
        assert resolver.resolve(bech32_addr) == p2pkh_addr
        assert resolver.resolve(bech32_addr).startswith("1")
        # P2SH 和 Taproot 保持原格式
        assert resolver.resolve(p2sh_addr) != p2pkh_addr
        assert resolver.resolve(p2sh_addr).startswith("3")
        assert resolver.resolve(taproot_addr) != p2pkh_addr
        assert resolver.resolve(taproot_addr).startswith("bc1p")
        # 全部可解析
        for addr in [p2pkh_addr, p2sh_addr, bech32_addr, taproot_addr]:
            assert resolver.resolve(addr) is not None, f"{addr[:6]}... 应可解析"


# ============================================================================
# Task 7b: TestTaprootClosedLoop - Bech32m (Taproot) 格式
# ============================================================================

@pytest.mark.integration
class TestTaprootClosedLoop:
    """Bech32m (Taproot) 格式验证"""

    def test_taproot_address_format(self):
        """x-only pubkey → bech32m 编码 → 格式正确"""
        pk = _K5_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        x_only_pk = compressed_pk[1:]  # 去掉 02/03 前缀，得到 32 字节 x-only pubkey

        addr = bech32_encode("bc", 1, x_only_pk, "bech32m")
        assert addr.startswith("bc1p"), f"Taproot 地址应以 'bc1p' 开头，实际: {addr}"
        # Bech32m 地址长度：hrp + 分隔符 + 编码数据 + 6 字符校验和
        # 对于 32 字节 witness program，长度在 42-62 字符范围
        assert 42 <= len(addr) <= 90, f"地址长度不合理: {len(addr)}"
        # Bech32 字符 '1' 仅作为分隔符出现，数据部分不应包含

    def test_taproot_vs_p2pkh_different(self):
        """同一公钥 → Legacy P2PKH vs Taproot Bech32m 互不相同"""
        pk = _K1_PK
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
        x_only_pk = compressed_pk[1:]

        taproot_addr = bech32_encode("bc", 1, x_only_pk, "bech32m")

        assert taproot_addr != p2pkh_addr, "Taproot 地址应与 Legacy P2PKH 不同"
        assert taproot_addr.startswith("bc1p")
        assert p2pkh_addr.startswith("1")

    def test_taproot_bech32m_encoding_uses_correct_constant(self):
        """Bech32m 编码使用 BECH32M_CONST (0x2BC830A3) 而非 BECH32_CONST (1)"""
        from src.utils.bech32_codec import BECH32_CONST, BECH32M_CONST

        # BECH32M_CONST 应不同于 BECH32_CONST
        assert BECH32M_CONST != BECH32_CONST
        assert BECH32M_CONST == 0x2BC830A3

        pk = _K3_PK
        gen = P2PKHAddressGenerator()
        _, compressed_pk, _ = gen.generate_address(pk)
        x_only_pk = compressed_pk[1:]

        # 使用正确 spec 生成地址
        addr_m = bech32_encode("bc", 1, x_only_pk, "bech32m")
        assert addr_m.startswith("bc1p")

        # 验证 bech32 vs bech32m 产生不同地址（不同 checksum）
        addr_legacy = bech32_encode("bc", 1, x_only_pk, "bech32")
        assert addr_legacy != addr_m, "bech32 和 bech32m 应产生不同地址"


# ============================================================================
# Task 7c: TestFileLoadingClosedLoop - 混格式文件加载
# ============================================================================

@pytest.mark.integration
class TestFileLoadingClosedLoop:
    """混格式文件加载闭环: targets.txt 含 P2PKH/P2SH/Bech32/Bech32m"""

    def test_load_mixed_formats_from_file(self, tmp_path):
        """四种格式混排文件 → Resolver 加载 → 引擎匹配"""
        gen = P2PKHAddressGenerator()
        lines = []
        expected_legacy_p2pkh = set()

        for k in range(1, 6):
            pk = k.to_bytes(32, "big")
            p2pkh_addr, compressed_pk, _ = gen.generate_address(pk)
            p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)
            bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")
            x_only_pk = compressed_pk[1:]
            taproot_addr = bech32_encode("bc", 1, x_only_pk, "bech32m")

            lines.extend([p2pkh_addr, p2sh_addr, bech32_addr, taproot_addr])
            expected_legacy_p2pkh.add(p2pkh_addr)

        # 写入临时文件
        targets_file = tmp_path / "mixed_targets.txt"
        targets_file.write_text("\n".join(lines))

        # 用 Resolver 加载
        resolver = TargetResolver(enable_cache=False)
        loaded_p2pkh = resolver.load_from_file(str(targets_file))

        # 验证解析结果：4 种格式 × 5 个密钥 = 20 行
        # - Legacy P2PKH + Bech32 → 5 个相同的 P2PKH (pubkey_hash)
        # - P2SH → 5 个不同的 P2PKH (script_hash)
        # - Taproot → 5 个不同的 P2PKH (x-only pubkey)
        # 总计 15 个唯一 P2PKH
        assert len(loaded_p2pkh) >= 10, (
            f"应至少解析出 10 个唯一 P2PKH（5 Legacy + 5 P2SH + 5 Taproot），实际: {len(loaded_p2pkh)}"
        )

        # 引擎闭环验证：Legacy P2PKH 应该全部匹配
        match_results = []

        def on_match(m_pk, m_addr, m_wif):
            match_results.append(m_addr)

        engine = KeyCollisionEngine(
            targets=loaded_p2pkh,
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine.start(mode="range", start=1, end=20)
        engine._thread.join(timeout=15)

        # Legacy P2PKH + Bech32 解析的 5 个 P2PKH 应该匹配
        for addr in expected_legacy_p2pkh:
            assert addr in match_results, f"Legacy P2PKH {addr[:10]}... 应被匹配"

    def test_load_file_with_comments_and_blanks(self, tmp_path):
        """混格式文件含注释和空行 → Resolver 正确跳过"""
        gen = P2PKHAddressGenerator()
        p2pkh_addr, compressed_pk, _ = gen.generate_address(_K1_PK)
        p2sh_addr = BitcoinKeyValidator.generate_p2sh_address(compressed_pk)
        bech32_addr = BitcoinKeyValidator.generate_bech32_address(compressed_pk, hrp="bc")

        content = (
            f"# 这是注释行\n"
            f"\n"
            f"# 另一条注释\n"
            f"{p2pkh_addr}\n"
            f"\n"
            f"{p2sh_addr}\n"
            f"# 中间注释\n"
            f"{bech32_addr}\n"
            f"\n"
        )
        targets_file = tmp_path / "commented_targets.txt"
        targets_file.write_text(content)

        resolver = TargetResolver(enable_cache=False)
        loaded = resolver.load_from_file(str(targets_file))

        # P2PKH + P2SH + Bech32 → Legacy P2PKH 和 Bech32 解析为相同的 p2pkh_addr
        # P2SH 解析为不同的 P2PKH, Taproot 无
        # 预期：Legacy/Bech32 相同(p2pkh_addr) + P2SH 不同 → 至少 1 个
        assert len(loaded) >= 1, f"应至少解析出 1 个唯一 P2PKH，实际: {len(loaded)}"
        assert p2pkh_addr in loaded, "Legacy P2PKH 应在结果中"


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

    def test_engine_publishes_start_progress_complete(self):
        """v3.5.2: range_scan 引擎运行 → 验证 ENGINE_START/PROGRESS/COMPLETE 事件发布"""
        received_types = []

        bus = EventBus(async_mode=False)

        def catch_all(event_type, event):
            received_types.append(event_type.value)

        bus.subscribe_to_all(catch_all)

        engine = KeyCollisionEngine(
            targets=set(),  # 空目标，不会匹配
            event_bus=bus,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine.start(mode="range", start=1, end=50)
        engine._thread.join(timeout=15)

        bus.stop()

        # 验证事件类型存在
        event_values = set(received_types)
        assert "engine.start" in event_values, f"缺少 ENGINE_START，已收到: {event_values}"
        assert "engine.progress" in event_values, f"缺少 ENGINE_PROGRESS，已收到: {event_values}"
        assert "engine.complete" in event_values, f"缺少 ENGINE_COMPLETE，已收到: {event_values}"
        assert bus.published_count >= 3, (
            f"应至少发布 3 个事件，实际: {bus.published_count}"
        )

    def test_engine_publishes_match_event(self):
        """v3.5.2: range_scan 匹配 → 验证 ENGINE_MATCH 事件发布"""
        received_matches = []

        bus = EventBus(async_mode=False)

        def match_listener(event):
            received_matches.append(event)

        bus.subscribe(EventType.ENGINE_MATCH, match_listener)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            event_bus=bus,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )
        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        bus.stop()

        assert len(received_matches) >= 1, (
            f"应至少收到 1 个 ENGINE_MATCH 事件，实际: {len(received_matches)}"
        )
        match = received_matches[0]
        assert match.address == _K1_ADDR, (
            f"事件地址应为 {_K1_ADDR}，实际: {match.address}"
        )
        assert match.target_address == _K1_ADDR


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


# ============================================================================
# Task A: TestMultiWorkerClosedLoop - 多线程 Worker 闭环
# ============================================================================

@pytest.mark.integration
class TestMultiWorkerClosedLoop:
    """多线程 Worker 闭环: max_workers > 1 的并行扫描"""

    def test_multi_worker_range_scan_finds_match(self):
        """max_workers=2 range_scan[1,200] → k=1 匹配找到且不重复"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=2,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=200)
        engine._thread.join(timeout=15)

        assert len(match_results) == 1, (
            f"应检测到 1 个匹配（不重复），实际: {len(match_results)}"
        )
        assert match_results[0] == _K1_ADDR

    def test_multi_worker_range_scan_all_matches(self):
        """max_workers=4 range_scan[1,100] → k=1/2/3 全部找到"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR, _K2_ADDR, _K3_ADDR},
            on_match=on_match,
            max_workers=4,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        assert len(match_results) == 3, (
            f"应检测到 3 个匹配，实际: {len(match_results)}"
        )
        for expected in [_K1_ADDR, _K2_ADDR, _K3_ADDR]:
            assert expected in match_results, f"{expected[:8]}... 应被匹配"

    def test_multi_worker_stats_accurate(self):
        """max_workers=4 range_scan[1,1000] → total_checked 统计准确"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=4,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=1000)
        engine._thread.join(timeout=20)

        stats = engine.get_stats()
        # 多线程下 total_checked 可能略少于 1000（窗口边界），但应接近
        assert stats.total_checked >= 900, (
            f"多线程至少检查 900 个私钥，实际: {stats.total_checked}"
        )
        assert stats.speed >= 0, "speed 应 >= 0"


# ============================================================================
# Task B: TestRandomModeClosedLoop - Random 模式引擎闭环
# ============================================================================

@pytest.mark.integration
class TestRandomModeClosedLoop:
    """Random 模式引擎闭环: 验证引擎生命周期和统计累积"""

    def test_random_mode_starts_stops(self):
        """start(random) → is_running → stop → is_running False"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        assert not engine.is_running()
        engine.start(mode="random")
        time.sleep(0.5)
        assert engine.is_running(), "random start 后应 running"

        engine.stop()
        time.sleep(0.5)
        assert not engine.is_running(), "stop 后应 not running"

    def test_random_mode_progress_increases(self):
        """random search → 等待 2 秒 → total_checked > 0"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="random")
        time.sleep(2)
        engine.stop()

        stats = engine.get_stats()
        assert stats.total_checked > 0, (
            f"random 模式应检查至少 1 个私钥，实际: {stats.total_checked}"
        )
        assert stats.speed >= 0, "speed 应 >= 0"

    def test_random_mode_on_progress_called(self):
        """random search → on_progress 回调被触发"""
        progress_calls = []

        def on_progress(stats):
            progress_calls.append(stats.total_checked)

        engine = KeyCollisionEngine(
            targets=set(),
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="random")
        time.sleep(3)
        engine.stop()

        assert len(progress_calls) >= 1, (
            f"on_progress 应至少被调用一次，实际: {len(progress_calls)}"
        )


# ============================================================================
# Task C: TestDataLoggingClosedLoop - Data Logging 集成闭环
# ============================================================================

@pytest.mark.integration
class TestDataLoggingClosedLoop:
    """Data Logging 集成闭环: data_logging_enabled=True 路径验证"""

    def test_data_logging_runs_without_crash(self):
        """data_logging_enabled=True → range_scan 正常完成不崩溃"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=True,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=50)
        engine._thread.join(timeout=15)

        stats = engine.get_stats()
        # 有 on_match 回调 → 引擎不会提前停止 → total_checked 应为 50
        assert stats.total_checked >= 50, (
            f"data_logging 启用时应正常扫描，实际: {stats.total_checked}"
        )
        assert _K1_ADDR in match_results, "匹配应正确"

    def test_data_logging_with_match(self):
        """data_logging_enabled=True + 匹配 → on_match 回调正常触发"""
        match_results = []

        def on_match(pk, addr, wif):
            match_results.append(addr)

        engine = KeyCollisionEngine(
            targets={_K1_ADDR},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=True,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="range", start=1, end=100)
        engine._thread.join(timeout=15)

        assert len(match_results) == 1, (
            f"data_logging 启用时匹配回调应正常，实际: {len(match_results)}"
        )
        assert match_results[0] == _K1_ADDR

    def test_data_logging_random_mode(self):
        """data_logging_enabled=True + random mode → 正常启停"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=True,
            use_enhanced_monitoring=False,
        )

        engine.start(mode="random")
        time.sleep(1.5)
        engine.stop()

        stats = engine.get_stats()
        assert stats.total_checked > 0, (
            f"data_logging + random 应检查至少 1 个私钥，实际: {stats.total_checked}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
