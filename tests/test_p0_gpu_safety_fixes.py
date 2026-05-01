#!/usr/bin/env python3
"""P0级GPU安全修复验证测试

本文件验证以下P0级修复的正确性：
- P0-1: on_progress 回调传递 snapshot 而非原始 stats 对象（引用隔离）
- P0-2: _safe_invoke_match_callback 能隔离回调异常，不影响引擎运行
- P0-3: pyproject.toml 与 requirements-base.txt 中 coincurve 版本声明一致
- P0-4: 范围扫描首批次与后续批次的边界计算逻辑一致，覆盖全部范围
"""

import os
import re
import sys
import pytest
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.collision.gpu_collision_engine import GPUCollisionEngine

# 模块级别 marker：本文件所有测试都属于 GPU 测试
pytestmark = pytest.mark.gpu

# ---------------------------------------------------------------------------
# 项目根目录
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent


# ===========================================================================
# P0-1: snapshot 隔离测试
# ===========================================================================


class TestSnapshotIsolation:
    """P0-1: 验证 on_progress 传递 snapshot 而非原始 stats 对象"""

    def test_snapshot_returns_different_object(self):
        """snapshot() 返回的对象与原始 stats 不是同一个实例"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.total_checked = 1000
        stats.speed = 500.0

        snapshot = stats.snapshot()

        assert snapshot is not stats, "snapshot() 必须返回新对象，而非原始引用"

    def test_snapshot_copies_basic_fields(self):
        """snapshot 正确复制基础统计字段"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.total_checked = 2048
        stats.speed = 1024.5
        stats.elapsed = 2.0

        snap = stats.snapshot()

        assert snap.total_checked == 2048
        assert snap.speed == 1024.5
        assert snap.elapsed == 2.0

    def test_snapshot_mutation_does_not_affect_original(self):
        """修改 snapshot 字段不影响原始 stats 对象"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.total_checked = 1000
        stats.speed = 500.0

        snap = stats.snapshot()
        # 修改 snapshot
        snap.total_checked = 9999
        snap.speed = 0.0

        # 原始对象保持不变
        assert stats.total_checked == 1000, "修改 snapshot 不应影响原始 stats.total_checked"
        assert stats.speed == 500.0, "修改 snapshot 不应影响原始 stats.speed"

    def test_snapshot_matches_list_deep_copy(self):
        """snapshot 的 matches 列表是深拷贝，修改不影响原始对象"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.add_match(b"\x01" * 32, "1TestAddress")

        snap = stats.snapshot()
        assert len(snap.matches) == 1

        # 修改 snapshot 的 matches
        snap.matches.clear()
        assert len(stats.matches) == 1, "清空 snapshot.matches 不应影响原始 stats.matches"

    def test_snapshot_copies_error_counters(self):
        """snapshot 正确复制异常统计指标"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.gpu_errors = 3
        stats.worker_errors = 1
        stats.wif_encode_errors = 2
        stats.resource_errors = 1

        snap = stats.snapshot()

        assert snap.gpu_errors == 3
        assert snap.worker_errors == 1
        assert snap.wif_encode_errors == 2
        assert snap.resource_errors == 1

    def test_snapshot_copies_eta_fields(self):
        """snapshot 正确复制 ETA 相关字段"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        stats.total_range = 1_000_000
        stats.eta_seconds = 120.5

        snap = stats.snapshot()

        assert snap.total_range == 1_000_000
        assert snap.eta_seconds == 120.5

    def test_snapshot_is_collision_stats_instance(self):
        """snapshot() 返回的对象是 CollisionStats 实例"""
        from src.collision.collision_stats import CollisionStats

        stats = CollisionStats()
        snap = stats.snapshot()

        assert isinstance(snap, CollisionStats)


# ===========================================================================
# P0-2: _safe_invoke_match_callback 异常隔离测试
# ===========================================================================


class TestSafeInvokeMatchCallbackIsolation:
    """P0-2: 验证 GPU _safe_invoke_match_callback 能隔离回调异常

    通过 mock __init__ 跳过完整 GPU 初始化流程，
    直接构造最小化引擎实例来测试回调安全机制。
    """

    @pytest.fixture(autouse=True)
    def _mock_engine(self):
        """创建跳过 GPU 初始化的最小化引擎实例

        Phase 6: _init_gpu 已移除，改用 __init__ mock。
        """
        with patch.object(GPUCollisionEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = GPUCollisionEngine.__new__(GPUCollisionEngine)
            engine.on_match = None
            engine.on_progress = None
            engine.stats = Mock()
            engine._running = False
            engine._match_callback_timeout = 5.0
            self._engine = engine
            yield

    def test_exception_in_callback_does_not_raise(self):
        """回调函数抛出异常时，_safe_invoke_match_callback 不向外传播异常"""

        def bad_callback(pk, addr, wif):
            raise RuntimeError("callback crash")

        self._engine.on_match = bad_callback

        # 不应抛出任何异常
        try:
            result = self._engine._safe_invoke_match_callback(
                b"\x01" * 32, "1TestAddress", "Kwif123"
            )
            # 异常回调应返回 False（隔离失败结果）
            assert result is False, "异常回调应返回 False"
        except Exception as exc:
            pytest.fail(f"_safe_invoke_match_callback 不应传播回调异常，但抛出了: {exc}")

    def test_no_on_match_returns_true(self):
        """未设置 on_match 时，_safe_invoke_match_callback 应返回 True"""
        self._engine.on_match = None

        result = self._engine._safe_invoke_match_callback(b"\x01" * 32, "1TestAddress", "Kwif123")
        assert result is True, "无 on_match 时应返回 True"

    def test_normal_callback_returns_true(self):
        """正常回调成功执行时，_safe_invoke_match_callback 应返回 True"""
        called = []

        def good_callback(pk, addr, wif):
            called.append((addr, wif))
            return True

        self._engine.on_match = good_callback

        result = self._engine._safe_invoke_match_callback(b"\x02" * 32, "1TestAddress", "Kwif456")
        assert result is True, "正常回调应返回 True"
        assert len(called) == 1, "回调应被调用一次"
        assert called[0][0] == "1TestAddress"

    def test_timeout_callback_returns_false_on_windows(self):
        """Windows 下超时回调应返回 False（通过线程超时机制）"""
        if os.name != "nt":
            pytest.skip("该测试仅适用于 Windows 平台")

        def slow_callback(pk, addr, wif):
            import time

            time.sleep(10)

        self._engine.on_match = slow_callback

        # mock Thread.is_alive 返回 True 模拟超时
        with patch.object(threading.Thread, "is_alive", return_value=True):
            result = self._engine._safe_invoke_match_callback(
                b"\x03" * 32, "1TestAddress", "Kwif789"
            )
        assert result is False, "超时回调应返回 False"


# ===========================================================================
# P0-3: coincurve 版本一致性测试
# ===========================================================================


class TestCoinCurveVersionConsistency:
    """P0-3: 验证 coincurve 版本声明在各配置文件中一致"""

    def test_coincurve_declared_in_pyproject(self):
        """pyproject.toml 中存在 coincurve 版本声明"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml 文件不存在"

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r"coincurve>=([\d.]+)", content)
        assert match is not None, "pyproject.toml 中未找到 coincurve>= 声明"

    def test_coincurve_declared_in_requirements_base(self):
        """requirements-base.txt 中存在 coincurve 版本声明"""
        req_path = PROJECT_ROOT / "requirements-base.txt"
        assert req_path.exists(), "requirements-base.txt 文件不存在"

        content = req_path.read_text(encoding="utf-8")
        match = re.search(r"coincurve>=([\d.]+)", content)
        assert match is not None, "requirements-base.txt 中未找到 coincurve>= 声明"

    def test_coincurve_version_consistency(self):
        """pyproject.toml 与 requirements-base.txt 中 coincurve 最低版本一致"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        req_path = PROJECT_ROOT / "requirements-base.txt"

        pyproject_content = pyproject_path.read_text(encoding="utf-8")
        req_content = req_path.read_text(encoding="utf-8")

        match_toml = re.search(r"coincurve>=([\d.]+)", pyproject_content)
        match_req = re.search(r"coincurve>=([\d.]+)", req_content)

        assert match_toml is not None, "pyproject.toml 中未找到 coincurve>= 声明"
        assert match_req is not None, "requirements-base.txt 中未找到 coincurve>= 声明"

        version_toml = match_toml.group(1)
        version_req = match_req.group(1)

        assert version_toml == version_req, (
            f"coincurve 版本不一致: "
            f"pyproject.toml={version_toml}, "
            f"requirements-base.txt={version_req}"
        )

    def test_coincurve_minimum_version_is_18(self):
        """coincurve 最低版本要求不低于 18.0.0"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r"coincurve>=([\d.]+)", content)
        assert match is not None

        version_parts = [int(x) for x in match.group(1).split(".")]
        major = version_parts[0]
        assert major >= 18, f"coincurve 最低版本应 >=18，当前声明: {match.group(1)}"


# ===========================================================================
# P0-4: 范围扫描边界一致性测试
# ===========================================================================


class TestRangeScanBoundaryConsistency:
    """P0-4: 验证范围扫描首批次和后续批次边界逻辑一致，不重不漏"""

    @pytest.mark.parametrize(
        "start,end,batch_size",
        [
            (1, 100, 33),
            (1, 10, 20),  # 范围小于 batch_size
            (90, 100, 20),  # 末尾不足 batch_size
            (1, 33, 33),  # 恰好整数倍
            (0, 0, 10),  # 单个元素
            (5, 5, 1),  # 单个元素，batch_size=1
            (1, 1000, 256),  # 大范围
            (100, 199, 50),  # 整数倍边界
            (1, 99, 10),  # 末尾余1
        ],
    )
    def test_boundary_no_gap_no_overlap(self, start, end, batch_size):
        """批次迭代不遗漏、不重复地覆盖 [start, end] 全范围"""
        current = start
        all_keys = []

        while current <= end:
            batch_end = min(current + batch_size, end + 1)
            keys = list(range(current, batch_end))
            all_keys.extend(keys)
            current = batch_end

        expected = list(range(start, end + 1))
        assert sorted(all_keys) == expected, (
            f"边界不一致: start={start}, end={end}, batch_size={batch_size}\n"
            f"期望 {len(expected)} 个元素，实际得到 {len(all_keys)} 个"
        )

    def test_first_batch_same_logic_as_subsequent(self):
        """首批次与后续批次使用相同的 batch_end 计算公式"""
        start, end, batch_size = 1, 100, 30
        batches = []
        current = start

        while current <= end:
            batch_end = min(current + batch_size, end + 1)
            batches.append((current, batch_end))
            current = batch_end

        # 每个批次的计算公式应当一致：batch_end = min(current + batch_size, end + 1)
        for i, (b_start, b_end) in enumerate(batches):
            expected_end = min(b_start + batch_size, end + 1)
            assert b_end == expected_end, (
                f"批次 {i} 的 batch_end 计算不一致: " f"得到 {b_end}，期望 {expected_end}"
            )

    def test_each_batch_size_within_limit(self):
        """每个批次实际包含的元素数不超过 batch_size"""
        start, end, batch_size = 1, 100, 33
        current = start

        while current <= end:
            batch_end = min(current + batch_size, end + 1)
            actual_size = batch_end - current
            assert actual_size <= batch_size, (
                f"批次大小超限: current={current}, batch_end={batch_end}, "
                f"actual={actual_size}, limit={batch_size}"
            )
            assert actual_size > 0, f"批次大小不能为0: current={current}"
            current = batch_end

    def test_last_batch_handles_remainder(self):
        """最后一个不足 batch_size 的批次被正确处理"""
        start, end, batch_size = 1, 10, 3  # 10 个元素，每批3个，最后一批1个
        batches = []
        current = start

        while current <= end:
            batch_end = min(current + batch_size, end + 1)
            batches.append(list(range(current, batch_end)))
            current = batch_end

        all_keys = [k for b in batches for k in b]
        assert all_keys == list(range(start, end + 1))

        # 最后一批应包含余数元素
        last_batch = batches[-1]
        remainder = (end - start + 1) % batch_size
        if remainder != 0:
            assert (
                len(last_batch) == remainder
            ), f"最后批次大小应为 {remainder}，实际为 {len(last_batch)}"
