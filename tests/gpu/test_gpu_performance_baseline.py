"""GPU性能回归测试基线

建立GPU性能的基准线，用于：
1. 检测性能回归
2. 验证优化效果
3. 监控性能趋势
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# 模块级别 marker：本文件所有测试都属于 GPU 测试
pytestmark = pytest.mark.gpu


class PerformanceBaseline:
    """性能基线管理器"""

    def __init__(self, baseline_file: str = "test_results/gpu_performance_baseline.json"):
        self.baseline_file = Path(baseline_file)
        self.baseline_data = self._load_baseline()

    def _load_baseline(self) -> dict:
        """加载基线数据"""
        if self.baseline_file.exists():
            with Path(self.baseline_file).open() as f:
                return json.load(f)
        return {}

    def save_baseline(self):
        """保存基线数据"""
        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with Path(self.baseline_file).open("w") as f:
            json.dump(self.baseline_data, f, indent=2, ensure_ascii=False)
        logger.info(f"性能基线已保存: {self.baseline_file}")

    def record(self, test_name: str, metrics: dict):
        """记录性能数据"""
        if test_name not in self.baseline_data:
            self.baseline_data[test_name] = []

        record = {"timestamp": datetime.now().isoformat(), "metrics": metrics}

        self.baseline_data[test_name].append(record)

        # 只保留最近20次记录
        if len(self.baseline_data[test_name]) > 20:
            self.baseline_data[test_name] = self.baseline_data[test_name][-20:]

    def check_regression(
        self,
        test_name: str,
        current_value: float,
        metric_name: str,
        threshold: float = 0.1,
    ) -> bool:
        """检查性能回归

        Args:
            test_name: 测试名称
            current_value: 当前值
            metric_name: 指标名称
            threshold: 回归阈值（10%）

        Returns:
            True表示有回归

        """
        if test_name not in self.baseline_data:
            return False

        records = self.baseline_data[test_name]
        if not records:
            return False

        # 获取基线值（最近5次平均）
        recent = records[-5:]
        baseline_values = [r["metrics"].get(metric_name, 0) for r in recent]
        baseline_avg = sum(baseline_values) / len(baseline_values)

        if baseline_avg == 0:
            return False

        # 检查是否退化
        degradation = (current_value - baseline_avg) / baseline_avg

        return degradation > threshold


# 创建全局基线管理器
baseline = PerformanceBaseline()


class TestGPUPerformanceBaseline:
    """GPU性能基线测试"""

    def test_kernel_compilation_time_baseline(self):
        """测试内核编译时间基线"""
        # 跳过，需要真实GPU
        pytest.skip("需要真实GPU环境")

    def test_batch_execution_time_baseline(self):
        """测试批次执行时间基线"""
        # 跳过，需要真实GPU
        pytest.skip("需要真实GPU环境")

    def test_memory_allocation_time_baseline(self):
        """测试内存分配时间基线"""
        # 模拟测试
        allocations = []

        for _ in range(10):
            start = time.time()
            # 模拟内存分配
            buffer = bytearray(1024 * 1024)  # 1MB # noqa: F841
            elapsed = (time.time() - start) * 1000
            allocations.append(elapsed)

        avg_time = sum(allocations) / len(allocations)

        # 记录基线
        baseline.record(
            "memory_allocation",
            {
                "avg_time_ms": avg_time,
                "min_time_ms": min(allocations),
                "max_time_ms": max(allocations),
            },
        )

        # 应该在合理范围内
        assert avg_time < 10.0  # 10ms内

    def test_data_transfer_time_baseline(self):
        """测试数据传输时间基线"""
        # 模拟CPU到GPU数据传输
        data_size = 1024 * 1024  # 1MB
        transfers = []

        for _ in range(10):
            start = time.time()
            # 模拟数据传输
            data = bytearray(data_size)
            _ = bytes(data)
            elapsed = (time.time() - start) * 1000
            transfers.append(elapsed)

        avg_time = sum(transfers) / len(transfers)

        # 记录基线
        baseline.record(
            "data_transfer",
            {"avg_time_ms": avg_time, "data_size_mb": data_size / (1024 * 1024)},
        )

        # 应该在合理范围内
        assert avg_time < 5.0  # 5ms内


class TestPerformanceRegression:
    """性能回归检测测试"""

    def test_no_regression_in_baseline(self):
        """测试基线数据无回归"""
        # 创建测试数据
        baseline.record("test_metric", {"value": 100.0})

        # 检查回归
        has_regression = baseline.check_regression(
            "test_metric",
            105.0,
            "value",
            threshold=0.1,  # 5%增长，在阈值内 # 10%阈值
        )

        assert has_regression is False

    def test_detect_regression(self):
        """测试检测性能回归"""
        # 创建基线
        baseline.record("regression_test", {"value": 100.0})

        # 检查回归（15%增长，超过阈值）
        has_regression = baseline.check_regression(
            "regression_test",
            115.0,
            "value",
            threshold=0.1,  # 15%增长 # 10%阈值
        )

        assert has_regression is True


class TestPerformanceMetrics:
    """性能指标测试"""

    def test_throughput_calculation(self):
        """测试吞吐量计算"""
        items_processed = 1000000
        elapsed_seconds = 2.5

        throughput = items_processed / elapsed_seconds

        assert throughput == 400000.0  # 400K items/s

    def test_efficiency_calculation(self):
        """测试效率计算"""
        actual_throughput = 400000
        theoretical_max = 500000

        efficiency = actual_throughput / theoretical_max

        assert efficiency == 0.8  # 80%

    def test_speedup_calculation(self):
        """测试加速比计算"""
        cpu_time = 10.0
        gpu_time = 2.0

        speedup = cpu_time / gpu_time

        assert speedup == 5.0  # 5x加速


class TestPerformanceReporting:
    """性能报告测试"""

    def test_baseline_save_load(self, tmp_path):
        """测试基线保存和加载"""
        baseline_file = tmp_path / "test_baseline.json"
        test_baseline = PerformanceBaseline(str(baseline_file))

        # 记录数据
        test_baseline.record("test", {"value": 100.0})
        test_baseline.save_baseline()

        # 加载数据
        assert baseline_file.exists()

        with Path(baseline_file).open() as f:
            data = json.load(f)

        assert "test" in data
        assert len(data["test"]) == 1

    def test_baseline_retention(self, tmp_path):
        """测试基线数据保留策略"""
        baseline_file = tmp_path / "test_baseline.json"
        test_baseline = PerformanceBaseline(str(baseline_file))

        # 记录25次
        for i in range(25):
            test_baseline.record("test", {"value": i})

        test_baseline.save_baseline()

        # 加载检查
        with Path(baseline_file).open() as f:
            data = json.load(f)

        # 应该只保留最近20次
        assert len(data["test"]) == 20
        assert data["test"][0]["metrics"]["value"] == 5  # 从第5次开始


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
