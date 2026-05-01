#!/usr/bin/env python3
"""Intel GPU 显存监控器 (IntelMemoryMonitor) 单元测试

覆盖：
- IntelMemoryMonitor 初始化与阈值计算
- track_allocation / track_deallocation 分配/释放跟踪
- get_status 状态查询
- check_warnings 警告检测
- should_reduce_batch_size / get_recommended_batch_reduction
- _detect_memory_leak 泄漏检测
- get_history / reset / get_report
- MemorySnapshot 数据类
- MemoryStatus 枚举
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock


# ============================================================================
# MemoryStatus / MemorySnapshot 测试
# ============================================================================

@pytest.mark.unit
class TestMemoryStatus:
    """MemoryStatus 枚举测试"""

    def test_all_status_values(self):
        from src.gpu.intel_memory_monitor import MemoryStatus
        assert MemoryStatus.NORMAL.value == "normal"
        assert MemoryStatus.WARNING.value == "warning"
        assert MemoryStatus.CRITICAL.value == "critical"
        assert MemoryStatus.EMERGENCY.value == "emergency"

    def test_status_is_enum(self):
        from src.gpu.intel_memory_monitor import MemoryStatus
        assert isinstance(MemoryStatus.NORMAL, MemoryStatus)


@pytest.mark.unit
class TestMemorySnapshot:
    """MemorySnapshot 数据类测试"""

    def test_creates_snapshot(self):
        from src.gpu.intel_memory_monitor import MemorySnapshot, MemoryStatus
        snap = MemorySnapshot(
            timestamp=12345.0,
            allocated_bytes=1024,
            total_bytes=8192,
            usage_percent=12.5,
            status=MemoryStatus.NORMAL,
            batch_count=5,
        )
        assert snap.timestamp == 12345.0
        assert snap.allocated_bytes == 1024
        assert snap.total_bytes == 8192
        assert snap.usage_percent == 12.5
        assert snap.status == MemoryStatus.NORMAL
        assert snap.batch_count == 5

    def test_default_batch_count(self):
        from src.gpu.intel_memory_monitor import MemorySnapshot, MemoryStatus
        snap = MemorySnapshot(0, 0, 0, 0, MemoryStatus.NORMAL)
        assert snap.batch_count == 0


# ============================================================================
# IntelMemoryMonitor 初始化测试
# ============================================================================

@pytest.mark.unit
class TestIntelMemoryMonitorInit:
    """初始化测试"""

    def test_init_defaults(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3  # 8GB
        monitor = IntelMemoryMonitor(total)
        assert monitor.total_memory == total
        assert monitor.safe_limit == int(total * 0.45)
        assert monitor.current_usage == 0
        assert monitor.peak_usage == 0
        assert monitor.total_allocations == 0
        assert monitor.total_deallocations == 0

    def test_init_custom_thresholds(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 4 * 1024**3  # 4GB
        monitor = IntelMemoryMonitor(
            total,
            safe_usage_ratio=0.5,
            warning_threshold=0.6,
            critical_threshold=0.8,
            emergency_threshold=0.9,
        )
        assert monitor.safe_limit == int(total * 0.5)
        assert monitor.warning_limit == int(monitor.safe_limit * 0.6)
        assert monitor.critical_limit == int(monitor.safe_limit * 0.8)
        assert monitor.emergency_limit == int(monitor.safe_limit * 0.9)


# ============================================================================
# track_allocation 测试
# ============================================================================

@pytest.mark.unit
class TestTrackAllocation:
    """显存分配跟踪测试"""

    def test_track_valid_allocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        result = monitor.track_allocation(1024 * 1024 * 100)  # 100MB
        assert result is True
        assert monitor.current_usage == 1024 * 1024 * 100
        assert monitor.total_allocations == 1

    def test_track_zero_allocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        result = monitor.track_allocation(0)
        assert result is False
        assert monitor.total_allocations == 0

    def test_track_negative_allocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        result = monitor.track_allocation(-100)
        assert result is False
        assert monitor.total_allocations == 0

    def test_track_exceeds_safe_limit(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)  # 10% safe limit
        # safe_limit = 0.8GB
        result = monitor.track_allocation(int(total * 0.5))  # 50% > 10%
        assert result is False
        # 不应更新 current_usage
        assert monitor.current_usage == 0

    def test_peak_usage_tracking(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 200)  # 200MB
        monitor.track_allocation(1024 * 1024 * 100)  # 100MB, total 300MB
        monitor.track_deallocation(1024 * 1024 * 150)  # release 150MB, total 150MB
        assert monitor.peak_usage == 1024 * 1024 * 300  # peak at 300MB

    def test_history_recorded_on_allocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        history = monitor.get_history(1)
        assert len(history) == 1
        assert history[0].allocated_bytes == 1024 * 1024 * 100


# ============================================================================
# track_deallocation 测试
# ============================================================================

@pytest.mark.unit
class TestTrackDeallocation:
    """显存释放跟踪测试"""

    def test_track_valid_deallocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 200)
        monitor.track_deallocation(1024 * 1024 * 50)
        assert monitor.current_usage == 1024 * 1024 * 150
        assert monitor.total_deallocations == 1

    def test_track_zero_deallocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        monitor.track_deallocation(0)
        assert monitor.current_usage == 1024 * 1024 * 100
        assert monitor.total_deallocations == 0

    def test_track_negative_deallocation(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        monitor.track_deallocation(-50)
        assert monitor.current_usage == 1024 * 1024 * 100

    def test_deallocation_cannot_go_negative(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        monitor.track_deallocation(1024 * 1024 * 999)  # more than allocated
        assert monitor.current_usage == 0


# ============================================================================
# get_status 测试
# ============================================================================

@pytest.mark.unit
class TestGetStatus:
    """状态查询测试"""

    def test_normal_status(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor, MemoryStatus
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 50)  # 50MB, well below safe limit
        status = monitor.get_status()
        assert status["status"] == MemoryStatus.NORMAL

    def test_emergency_status(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor, MemoryStatus
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        # safe_limit = 0.8GB, allocate close to safe_limit to get high usage ratio
        monitor.track_allocation(monitor.safe_limit)
        status = monitor.get_status()
        # 100% usage of safe_limit should be >= emergency
        assert status["status"] in [MemoryStatus.EMERGENCY, MemoryStatus.CRITICAL]

    def test_status_returns_all_keys(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        status = monitor.get_status()
        expected_keys = [
            "status", "current_bytes", "current_mb", "peak_bytes", "peak_mb",
            "safe_limit_bytes", "safe_limit_mb", "usage_percent",
            "total_memory_gb", "total_allocations", "total_deallocations",
        ]
        for key in expected_keys:
            assert key in status

    def test_total_memory_gb_conversion(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        status = monitor.get_status()
        assert status["total_memory_gb"] == 8.0


# ============================================================================
# check_warnings 测试
# ============================================================================

@pytest.mark.unit
class TestCheckWarnings:
    """警告检测测试"""

    def test_no_warnings_normal(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        warnings = monitor.check_warnings()
        assert warnings == []

    def test_warning_on_high_usage(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.5)
        # Fill to just above warning threshold
        monitor.track_allocation(int(monitor.warning_limit * 1.01))
        warnings = monitor.check_warnings()
        assert len(warnings) >= 1

    def test_emergency_warning(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        monitor.track_allocation(monitor.emergency_limit + 1)
        warnings = monitor.check_warnings()
        assert any("紧急" in w or "EMERGENCY" in w.upper() for w in warnings)


# ============================================================================
# should_reduce_batch_size / get_recommended_batch_reduction 测试
# ============================================================================

@pytest.mark.unit
class TestBatchReduction:
    """批次缩减建议测试"""

    def test_normal_no_reduction(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        assert monitor.should_reduce_batch_size() is False
        assert monitor.get_recommended_batch_reduction() == 0.0

    def test_critical_reduction(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        # Fill to critical level
        monitor.track_allocation(int(monitor.critical_limit * 1.01))
        assert monitor.should_reduce_batch_size() is True
        assert monitor.get_recommended_batch_reduction() == 0.3

    def test_emergency_reduction(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        monitor.track_allocation(monitor.emergency_limit + 1)
        assert monitor.should_reduce_batch_size() is True
        assert monitor.get_recommended_batch_reduction() == 0.5

    def test_warning_reduction(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        monitor.track_allocation(int(monitor.warning_limit * 1.01))
        assert monitor.should_reduce_batch_size() is False
        assert monitor.get_recommended_batch_reduction() == 0.1


# ============================================================================
# _detect_memory_leak 测试
# ============================================================================

@pytest.mark.unit
class TestDetectMemoryLeak:
    """泄漏检测测试"""

    def test_no_leak_with_few_allocations(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        # < 10 allocations, should not detect leak
        for i in range(5):
            monitor.track_allocation(1024)
        warnings = monitor.check_warnings()
        leak_warnings = [w for w in warnings if "泄漏" in w or "leak" in w.lower()]
        assert len(leak_warnings) == 0

    def test_leak_detected_high_ratio(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3, safe_usage_ratio=0.9)
        # Many allocations, no deallocations
        for i in range(30):
            monitor.track_allocation(1024 * 1024)
        warnings = monitor.check_warnings()
        leak_warnings = [w for w in warnings if "泄漏" in w or "leak" in w.lower()]
        assert len(leak_warnings) >= 1

    def test_no_leak_with_balanced_ops(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3, safe_usage_ratio=0.9)
        for i in range(30):
            monitor.track_allocation(1024 * 1024)
            monitor.track_deallocation(1024 * 1024)  # balanced
        warnings = monitor.check_warnings()
        leak_warnings = [w for w in warnings if "泄漏" in w or "leak" in w.lower()]
        assert len(leak_warnings) == 0


# ============================================================================
# get_history / reset / get_report 测试
# ============================================================================

@pytest.mark.unit
class TestHistoryAndReset:
    """历史记录与重置测试"""

    def test_history_limited_to_max(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        # Add more than max_history (100) records
        for i in range(150):
            monitor.track_allocation(1024 * 1024)
        history = monitor.get_history(200)
        assert len(history) <= monitor._max_history

    def test_reset_clears_all(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        monitor.track_deallocation(1024 * 1024 * 50)
        monitor.reset()
        assert monitor.current_usage == 0
        assert monitor.peak_usage == 0
        assert monitor.total_allocations == 0
        assert monitor.total_deallocations == 0
        assert len(monitor._history) == 0

    def test_get_report_contains_info(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        monitor.track_allocation(1024 * 1024 * 100)
        report = monitor.get_report()
        assert "Intel GPU" in report
        assert "8.0 GB" in report
        assert "NORMAL" in report.upper()

    def test_get_report_with_warnings(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        total = 8 * 1024**3
        monitor = IntelMemoryMonitor(total, safe_usage_ratio=0.1)
        monitor.track_allocation(monitor.warning_limit + 1)
        report = monitor.get_report()
        assert "警告" in report or "WARNING" in report.upper()

    def test_get_history_default_last_10(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        for i in range(20):
            monitor.track_allocation(1024 * 1024)
        history = monitor.get_history()  # default last_n=10
        assert len(history) <= 10

    def test_allocation_sizes_window(self):
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        monitor = IntelMemoryMonitor(8 * 1024**3)
        # Add more records than the leak detection window
        for i in range(60):
            monitor.track_allocation(1024 * 1024)
        # Should be capped at _leak_detection_window (50)
        assert len(monitor._allocation_sizes) <= 50
