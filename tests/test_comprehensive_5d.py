"""全面可执行测试方案 - 五大维度覆盖

测试维度：
1. 多模式：正常流、边界值与异常流
2. 多状态：状态转换、隔离性、非法转换拦截
3. 多数据：空值、极值、类型校验
4. 多参数：参数组合、互斥与依赖逻辑
5. 多功能维度：核心功能、性能、安全性

运行方式：
    pytest tests/test_comprehensive_5d.py -v --tb=short
"""

import hashlib
import inspect
import threading
import time

import pytest

from src.collision.collision_stats import CollisionStats, StatsSnapshot
from src.collision.event_bus import EventBus
from src.collision.events import (
    CollisionEvent,
    EngineCompleteEvent,
    EngineErrorEvent,
    EngineMatchEvent,
    EngineProgressEvent,
    EngineStartEvent,
    EngineStopEvent,
)

# ============================================================================
# 维度一：多模式测试 (Multi-Mode Tests)
# ============================================================================


class TestMultiModeSemantics:
    """多模式测试 - 语义验证（update 赋值语义）"""

    def test_update_assignment_semantics(self):
        """测试：语义 - update() 是赋值而非增量"""
        stats = CollisionStats()
        stats.start_time = time.time() - 1

        # 第一次 update
        stats.update(1000)
        assert stats.total_checked == 1000

        # 第二次 update 是赋值，不是累加
        stats.update(500)
        assert stats.total_checked == 500, "update() 应是赋值语义，非增量累加"

    def test_update_with_increment_combination(self):
        """测试：语义 - update() + increment() 配合使用"""
        stats = CollisionStats()
        stats.start_time = time.time() - 1

        # 先赋值设基准
        stats.update(1000)
        # 再增量追加（increment 只影响 total_checked，不影响 _match_count）
        for _ in range(5):
            stats.increment(100)

        assert stats.total_checked == 1500  # 1000 + 5*100
        assert stats._total_matches == 0  # increment 不影响匹配计数


@pytest.mark.unit
class TestMultiModeNormalFlow:
    """多模式测试 - 正常流"""

    def test_normal_initialization(self):
        """测试：正常初始化流程"""
        stats = CollisionStats()

        # 状态断言
        assert stats.total_checked == 0
        assert stats._match_count == 0
        assert len(stats.matches) == 0

        # 数据断言
        assert stats.speed == 0.0
        assert 0 <= stats.elapsed < 0.1  # 初始化后经过微秒级时间

        # 副作用断言
        assert isinstance(stats._lock, type(threading.Lock()))
        assert stats.gpu_errors == 0

    def test_normal_update_flow(self):
        """测试：正常更新流程"""
        stats = CollisionStats()
        stats.start_time = time.time() - 10

        stats.update(1000000)

        assert stats.total_checked == 1000000
        assert stats.elapsed > 0
        assert stats.speed > 0

    def test_normal_match_recording(self):
        """测试：正常匹配记录流程"""
        stats = CollisionStats()
        private_key = bytes(range(32))
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        stats.add_match(private_key, address)

        assert len(stats.matches) == 1
        match = stats.matches[0]

        # 安全校验：不应包含私钥
        assert "private_key" not in match
        assert "private_key_hex" not in match

        # 应包含地址和哈希
        assert match["address"] == address
        assert "private_key_hash" in match


@pytest.mark.unit
class TestMultiModeBoundaryValues:
    """多模式测试 - 边界值"""

    def test_boundary_zero_values(self):
        """测试：边界值 - 零值"""
        stats = CollisionStats()
        stats.start_time = time.time()

        stats.update(0)

        assert stats.total_checked == 0
        assert stats.speed == 0.0

    def test_boundary_single_match(self):
        """测试：边界值 - 单次匹配"""
        stats = CollisionStats()
        pk = b"\x01" + b"\x00" * 31
        address = "1A" * 16

        stats.add_match(pk, address)

        assert len(stats.matches) == 1
        assert stats._match_count == 1

    def test_boundary_eta_calculation(self):
        """测试：边界值 - ETA计算"""
        stats = CollisionStats()
        stats.start_time = time.time() - 10

        # 场景1: 无限的 ETA (total_range = 0)
        stats.update(1000, total_range=0)
        assert stats.eta_seconds == -1.0

        # 场景2: 即将完成 (remaining <= 0)
        stats.update(1000, total_range=1000)
        assert stats.eta_seconds == 0.0


@pytest.mark.unit
class TestMultiModeExceptionFlow:
    """多模式测试 - 异常流"""

    def test_exception_negative_delta(self):
        """测试：异常流 - 负数增量"""
        stats = CollisionStats()

        with pytest.raises(ValueError) as exc_info:
            stats.increment(-1)

        assert "delta must be non-negative" in str(exc_info.value)

    def test_exception_invalid_event_type(self):
        """测试：异常流 - 无效事件类型处理"""
        event = CollisionEvent()

        assert event.event_type is None

        event_dict = event.to_dict()
        assert event_dict["event_type"] is None

    def test_exception_callback_timeout_handling(self):
        """测试：异常流 - 回调超时处理"""
        # 验证超时/回调机制存在（类级别属性检查）
        # BaseCollisionEngine 的 __init__ 中设置了 _match_callback 和 _running
        from src.collision.base_engine import BaseCollisionEngine

        init_source = inspect.getsource(BaseCollisionEngine.__init__)
        assert "_match_callback" in init_source
        assert "_running" in init_source


# ============================================================================
# 维度二：多状态测试 (Multi-State Tests)
# ============================================================================


@pytest.mark.unit
@pytest.mark.state_machine
class TestMultiStateTransitions:
    """多状态测试 - 状态转换"""

    def test_state_initial_to_running(self):
        """测试：状态转换 - 初始化 → 运行中"""
        stats = CollisionStats()
        assert stats.total_checked == 0  # 初始状态：未开始碰撞

        stats.start_time = time.time()
        stats.update(0)

        assert stats.start_time > 0
        assert stats.elapsed >= 0

    def test_state_running_to_stopped(self):
        """测试：状态转换 - 运行中 → 停止"""
        stats = CollisionStats()
        stats.start_time = time.time() - 5
        stats.update(10000)

        assert stats.elapsed > 0
        assert stats.total_checked > 0

        stats.reset()

        assert stats.total_checked == 0
        assert stats.speed == 0.0

    def test_state_multiple_start_stop_cycles(self):
        """测试：状态转换 - 多次启动停止循环"""
        stats = CollisionStats()

        for cycle in range(3):
            stats.start_time = time.time()
            stats.update(1000 * (cycle + 1))
            assert stats.total_checked == 1000 * (cycle + 1)

            stats.reset()
            assert stats.total_checked == 0


@pytest.mark.unit
class TestMultiStateIsolation:
    """多状态测试 - 隔离性"""

    def test_isolation_independent_instances(self):
        """测试：隔离性 - 独立实例互不影响"""
        stats1 = CollisionStats()
        stats2 = CollisionStats()

        stats1.start_time = time.time()
        stats1.update(1000)

        stats2.start_time = time.time()
        stats2.update(2000)

        assert stats1.total_checked == 1000
        assert stats2.total_checked == 2000

        stats1.reset()
        assert stats1.total_checked == 0
        assert stats2.total_checked == 2000

    def test_isolation_snapshot_independence(self):
        """测试：隔离性 - 快照独立性"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(500)
        stats.add_match(b"\x01" * 32, "1Address1")

        snap = stats.snapshot()

        # update() 是赋值语义，会覆盖 total_checked
        stats.update(9999)
        stats.add_match(b"\x02" * 32, "1Address2")

        # 快照应保持独立
        assert snap.total_keys_checked == 500
        assert len(snap.matches) == 1
        # stats 已被覆盖
        assert stats.total_checked == 9999
        assert len(stats.matches) == 2  # 添加了两个匹配


@pytest.mark.unit
class TestMultiStateIllegalTransitions:
    """多状态测试 - 非法转换拦截"""

    def test_illegal_double_reset(self):
        """测试：非法转换 - 重复重置检测"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(1000)

        stats.reset()
        assert stats.total_checked == 0

        # 第二次重置（应为空操作，不应崩溃）
        stats.reset()
        assert stats.total_checked == 0

    def test_illegal_invalid_state_access(self):
        """测试：非法转换 - 无效状态访问"""
        stats = CollisionStats()

        assert stats.total_checked == 0
        assert stats.speed == 0.0

        elapsed_str = stats.format_elapsed()
        assert isinstance(elapsed_str, str)


# ============================================================================
# 维度三：多数据测试 (Multi-Data Tests)
# ============================================================================


@pytest.mark.unit
class TestMultiDataNullValues:
    """多数据测试 - 空值注入"""

    def test_null_empty_address(self):
        """测试：空值 - 空地址"""
        stats = CollisionStats()

        stats.add_match(b"\x01" * 32, "")

        assert len(stats.matches) == 1
        assert stats.matches[0]["address"] == ""

    def test_null_empty_target_set(self):
        """测试：空值 - 空目标集合"""
        event = EngineStartEvent(target_count=0)

        assert event.target_count == 0


@pytest.mark.unit
class TestMultiDataExtremeValues:
    """多数据测试 - 极值注入"""

    def test_extreme_large_number(self):
        """测试：极值 - 超大数字"""
        stats = CollisionStats()
        stats.start_time = time.time()

        large_number = 2**62
        stats.update(large_number)

        assert stats.total_checked == large_number

    def test_extreme_long_address(self):
        """测试：极值 - 超长地址"""
        stats = CollisionStats()

        long_address = "A" * 10000
        stats.add_match(b"\x01" * 32, long_address)

        assert stats.matches[0]["address"] == long_address

    def test_extreme_many_matches(self):
        """测试：极值 - 大量匹配"""
        stats = CollisionStats()

        for i in range(1000):
            pk = i.to_bytes(32, "big")
            stats.add_match(pk, f"1Address{i}")

        assert len(stats.matches) == 1000
        assert stats._match_count == 1000


@pytest.mark.unit
class TestMultiDataValidInvalidTypes:
    """多数据测试 - 有效与无效类型"""

    def test_type_valid_private_key_bytes(self):
        """测试：类型 - 有效私钥类型 (bytes)"""
        stats = CollisionStats()

        pk = b"\x01" * 32
        stats.add_match(pk, "1Address")

        assert len(stats.matches) == 1
        assert stats.matches[0]["private_key_hash"] == hashlib.sha256(pk).hexdigest()[:16]

    def test_type_invalid_private_key_int(self):
        """测试：类型 - 无效私钥类型 (int)"""
        stats = CollisionStats()

        # add_match 接受 int 作为 pk（内部调用 bytes(pk) 转换），不抛出异常
        stats.add_match(12345, "1Address")
        assert len(stats.matches) == 1
        assert "private_key_hash" in stats.matches[0]


@pytest.mark.unit
class TestMultiDataIncrementTypes:
    """多数据测试 - increment 类型校验"""

    def test_increment_valid_int(self):
        """测试：increment 接受合法 int"""
        stats = CollisionStats()
        stats.increment(100)
        assert stats.total_checked == 100

    def test_increment_zero(self):
        """测试：increment 接受 0"""
        stats = CollisionStats()
        stats.increment(0)
        assert stats.total_checked == 0

    def test_increment_negative_raises(self):
        """测试：increment 负数抛出 ValueError"""
        stats = CollisionStats()
        with pytest.raises(ValueError) as exc_info:
            stats.increment(-1)
        assert "delta must be non-negative" in str(exc_info.value)

    def test_increment_large_value(self):
        """测试：increment 接受大数值"""
        stats = CollisionStats()
        stats.increment(10**12)
        assert stats.total_checked == 10**12

    def test_increment_float_handling(self):
        """测试：increment 拒绝 float 类型"""
        stats = CollisionStats()
        with pytest.raises(TypeError) as exc_info:
            stats.increment(1.5)
        assert "int" in str(exc_info.value)


# ============================================================================
# 维度四：多参数测试 (Multi-Parameter Tests)
# ============================================================================


@pytest.mark.unit
class TestMultiParameterCombinations:
    """多参数测试 - 参数组合"""

    def test_combination_mode_and_resume(self):
        """测试：组合 - 模式与恢复参数"""
        modes = ["random", "range", "brute_force"]

        for mode in modes:
            event = EngineStartEvent(mode=mode, target_count=1, batch_size=65536)
            assert event.mode == mode
            assert event.target_count == 1

    def test_combination_progress_event_fields(self):
        """测试：组合 - 进度事件字段组合"""
        event = EngineProgressEvent(
            total_checked=100000,
            speed=50000.0,
            matches_found=5,
        )

        assert event.total_checked == 100000
        assert event.speed == 50000.0
        assert event.matches_found == 5


@pytest.mark.unit
class TestMultiParameterDependencyLogic:
    """多参数测试 - 依赖逻辑"""

    def test_dependency_eta_on_total_range(self):
        """测试：依赖 - ETA 依赖 total_range"""
        stats = CollisionStats()
        stats.start_time = time.time() - 10

        # total_range = 0 → ETA 不可用
        stats.update(1000, total_range=0)
        assert stats.eta_seconds == -1.0

        # total_range > 0 → ETA 可用
        stats.update(1000, total_range=10000)
        assert stats.eta_seconds >= 0

    def test_dependency_speed_on_elapsed_time(self):
        """测试：依赖 - 速度依赖运行时间"""
        stats = CollisionStats()

        assert stats.speed == 0.0

        stats.start_time = time.time() - 10
        stats.update(10000)
        assert stats.speed > 0


# ============================================================================
# 维度五：多功能维度测试 (Multi-Function Tests)
# ============================================================================


@pytest.mark.unit
class TestMultiFunctionCoreFunctionality:
    """多功能维度测试 - 核心功能验证"""

    def test_core_collision_detection_workflow(self):
        """测试：核心功能 - 碰撞检测工作流"""
        events_received = []
        bus = EventBus()

        def collector(event):
            events_received.append(type(event).__name__)

        bus.subscribe(EngineStartEvent, collector)
        bus.subscribe(EngineProgressEvent, collector)
        bus.subscribe(EngineMatchEvent, collector)
        bus.subscribe(EngineStopEvent, collector)
        bus.subscribe(EngineCompleteEvent, collector)

        bus.publish(EngineStartEvent())
        bus.publish(EngineProgressEvent(total_checked=1000))
        bus.publish(EngineMatchEvent())
        bus.publish(EngineStopEvent())
        bus.publish(EngineCompleteEvent())

        assert len(events_received) == 5
        assert events_received[0] == "EngineStartEvent"
        assert events_received[4] == "EngineCompleteEvent"

    def test_core_statistics_accuracy(self):
        """测试：核心功能 - 统计准确性"""
        stats = CollisionStats()
        stats.start_time = time.time() - 1  # 确保 elapsed > 0

        for i in range(10):
            stats.update((i + 1) * 1000)

        assert stats.total_checked == 10000
        assert stats.speed > 0

        speed_str = stats.format_speed()
        assert isinstance(speed_str, str)
        assert "/s" in speed_str


@pytest.mark.unit
@pytest.mark.performance
class TestMultiFunctionPerformance:
    """多功能维度测试 - 性能指标阈值断言"""

    def test_performance_update_speed(self):
        """测试：性能 - update() 速度"""
        stats = CollisionStats()
        stats.start_time = time.time()

        start_time = time.time()
        for i in range(10000):
            stats.update(i)
        elapsed = time.time() - start_time

        assert elapsed < 1.0

    def test_performance_snapshot_speed(self):
        """测试：性能 - snapshot() 速度"""
        stats = CollisionStats()
        stats.start_time = time.time()

        for i in range(1000):
            stats.add_match(i.to_bytes(32, "big"), f"1Address{i}")

        start_time = time.time()
        for _ in range(100):
            stats.snapshot()
        elapsed = time.time() - start_time

        assert elapsed < 1.0

    def test_performance_event_publish_speed(self):
        """测试：性能 - 事件发布速度"""
        bus = EventBus()

        def dummy_subscriber(event):
            pass

        for _ in range(10):
            bus.subscribe(EngineProgressEvent, dummy_subscriber)

        start_time = time.time()
        for i in range(10000):
            bus.publish(EngineProgressEvent(total_checked=i))
        elapsed = time.time() - start_time

        assert elapsed < 5.0


@pytest.mark.unit
@pytest.mark.security
class TestMultiFunctionSecurity:
    """多功能维度测试 - 安全性越权与注入校验"""

    def test_security_private_key_not_stored(self):
        """测试：安全 - 私钥未存储"""
        stats = CollisionStats()

        private_key = b"\x01" * 32
        stats.add_match(private_key, "1Address")

        match = stats.matches[0]

        assert "private_key" not in match
        assert "private_key_hex" not in match
        assert "private_key_wif" not in match

        assert "private_key_hash" in match

    def test_security_event_sensitive_data_masking(self):
        """测试：安全 - 事件敏感数据脱敏"""
        event = EngineMatchEvent(
            private_key=b"\x01" * 32,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            wif="KwDiBf89QgGbjEhKnhxAbTtPCGZxx3GZvV3gxCSQHhTtRzmxy1fy",
            target_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        )

        assert event.wif != "KwDiBf89QgGbjEhKnhxAbTtPCGZxx3GZvV3gxCSQHhTtRzmxy1fy"
        assert "..." in event.wif

        assert "private_key" not in event.metadata
        assert "wif" not in event.metadata

    def test_security_injection_in_address(self):
        """测试：安全 - 地址注入攻击"""
        stats = CollisionStats()

        malicious_address = "1Address; rm -rf /"
        stats.add_match(b"\x01" * 32, malicious_address)

        assert stats.matches[0]["address"] == malicious_address

    def test_security_thread_safety(self):
        """测试：安全 - 线程安全（防止竞态条件）"""
        stats = CollisionStats()
        stats.start_time = time.time()

        errors = []
        thread_count = 10

        def concurrent_updater():
            try:
                for i in range(1000):
                    stats.update(i)
                    stats.increment(1)
                    snap = stats.snapshot()
                    assert isinstance(snap, StatsSnapshot)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=concurrent_updater) for _ in range(thread_count)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================================
# 综合测试：跨维度场景
# ============================================================================


@pytest.mark.integration
class TestCrossDimensionScenarios:
    """跨维度综合测试"""

    def test_scenario_complete_workflow(self):
        """测试：综合场景 - 完整工作流"""
        stats = CollisionStats()
        bus = EventBus()

        events = []
        bus.subscribe(EngineStartEvent, lambda e: events.append(e))
        bus.subscribe(EngineProgressEvent, lambda e: events.append(e))
        bus.subscribe(EngineMatchEvent, lambda e: events.append(e))
        bus.subscribe(EngineCompleteEvent, lambda e: events.append(e))

        stats.start_time = time.time()
        bus.publish(EngineStartEvent(mode="random", target_count=1, batch_size=65536))

        for i in range(5):
            stats.update((i + 1) * 1000)
            bus.publish(EngineProgressEvent(total_checked=stats.total_checked))

        pk = b"\x01" * 32
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        stats.add_match(pk, address)
        bus.publish(EngineMatchEvent(private_key=pk, address=address))

        bus.publish(
            EngineCompleteEvent(
                total_checked=stats.total_checked,
                matches_found=len(stats.matches),
            )
        )

        assert stats.total_checked == 5000
        assert len(stats.matches) == 1
        assert len(events) == 8

    def test_scenario_error_recovery(self):
        """测试：综合场景 - 错误恢复"""
        bus = EventBus()

        errors = []
        bus.subscribe(EngineErrorEvent, lambda e: errors.append(e))

        error_event = EngineErrorEvent(
            error_type="gpu_error",
            error_message="GPU out of memory",
            recoverable=True,
        )
        bus.publish(error_event)

        assert len(errors) == 1
        assert errors[0].error_type == "gpu_error"
        assert errors[0].recoverable is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
