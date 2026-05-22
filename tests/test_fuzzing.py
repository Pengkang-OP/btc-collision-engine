"""
模糊测试 (Fuzzing) - 基于 Hypothesis 框架 - 中优先级

覆盖范围：
- 地址格式属性测试
- 私钥随机生成
- 统计数字运算不变量

如果 hypothesis 未安装，测试自动跳过。

运行：
    pip install hypothesis
    pytest tests/test_fuzzing.py -v --tb=short
"""

import sys

import pytest

sys.path.insert(0, ".")

HYPOTHESIS_AVAILABLE = False
try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE,
    reason="需要安装 hypothesis: pip install hypothesis",
)


# ============================================================================
# 测试：Stats 属性测试
# ============================================================================

if HYPOTHESIS_AVAILABLE:

    @pytest.mark.unit
    class TestFuzzingStats:
        """Stats 属性测试"""

        @given(st.integers(min_value=0, max_value=10**12))
        @settings(max_examples=50)
        def test_fuzz_update_total_checked(self, value):
            """测试：update 后 total_checked 等于输入值"""
            from src.collision.collision_stats import CollisionStats

            stats = CollisionStats()
            stats.start_time = 1.0
            stats.update(value)
            assert stats.total_checked == value

        @given(st.integers(min_value=0, max_value=10**6))
        @settings(max_examples=50)
        def test_fuzz_increment_accumulates(self, delta):
            """测试：increment 累加后 total_checked >= delta"""
            from src.collision.collision_stats import CollisionStats

            stats = CollisionStats()
            stats.increment(delta)
            assert stats.total_checked == delta

        @given(
            st.binary(min_size=32, max_size=32),
            st.text(min_size=1, max_size=50),
        )
        @settings(max_examples=50)
        def test_fuzz_add_match_safety(self, private_key, address):
            """测试：add_match 不存储私钥原文"""
            from src.collision.collision_stats import CollisionStats

            stats = CollisionStats()
            stats.add_match(private_key, address)

            match = stats.matches[0]
            assert "private_key" not in match
            assert match["address"] == address

        @given(st.integers(min_value=1, max_value=10000))
        @settings(max_examples=20)
        def test_fuzz_snapshot_never_raises(self, count):
            """测试：大量快照不抛出异常"""
            from src.collision.collision_stats import CollisionStats

            stats = CollisionStats()
            stats.start_time = 1.0
            for i in range(min(count, 100)):
                stats.update(i)
                snap = stats.snapshot()
                assert snap.total_checked == i

    @pytest.mark.unit
    class TestFuzzingEvents:
        """事件属性测试"""

        @given(
            st.integers(min_value=0, max_value=10**9),
            st.floats(min_value=0.0, max_value=10**6, allow_nan=False),
            st.integers(min_value=0, max_value=1000),
        )
        @settings(max_examples=50)
        def test_fuzz_progress_event_fields(self, total, speed, matches):
            """测试：进度事件字段任意组合不崩溃"""
            from src.collision.events import EngineProgressEvent

            event = EngineProgressEvent(
                total_checked=total,
                speed=speed,
                matches_found=matches,
            )
            assert event.total_checked == total
            assert event.speed == speed
            assert event.matches_found == matches

    @pytest.mark.unit
    class TestFuzzingEventBus:
        """事件总线属性测试"""

        @given(st.integers(min_value=1, max_value=100))
        @settings(max_examples=20)
        def test_fuzz_event_publish_no_raise(self, count):
            """测试：大量事件发布不抛出异常"""
            from src.collision.event_bus import EventBus
            from src.collision.events import (
                EngineProgressEvent,
                EventType,
            )

            bus = EventBus(async_mode=False)
            received = []

            def collector(event):
                received.append(1)

            bus.subscribe(EventType.ENGINE_PROGRESS, collector)
            for i in range(min(count, 50)):
                bus.publish(EngineProgressEvent(total_checked=i))

            assert len(received) == min(count, 50)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
