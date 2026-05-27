#!/usr/bin/env python3
"""测试 Windows 权限错误重试机制."""

import json
import os
import pathlib
import tempfile
from unittest.mock import patch

from src.monitoring.data_logger import DataLogger


class TestWindowsPermissionRetry:
    """测试 Windows 权限错误重试机制."""

    def setup_method(self, method):
        """设置测试环境."""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.data_logger = DataLogger(storage_dir=self.test_dir)

    def teardown_method(self, method):
        """清理测试环境."""
        import shutil

        if pathlib.Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_save_history_data_with_permission_error(self):
        """测试保存历史数据时遇到权限错误的重试机制."""
        # 添加一些历史数据
        self.data_logger.record_performance_data(
            speed=100.0,
            total_checked=1000,
            matches_found=0,
            cpu_usage=50.0,
            memory_usage=256.0,
            thread_count=4,
        )

        # 模拟第一次失败，第二次成功
        call_count = [0]
        original_remove = os.remove

        def mock_remove_first_fail(path):
            call_count[0] += 1
            if call_count[0] == 1:
                raise PermissionError("模拟权限错误")
            original_remove(path)

        # 使用 patch 模拟权限错误
        with patch("os.remove", side_effect=mock_remove_first_fail):
            # 这应该会失败一次，然后重试成功
            self.data_logger.save_history_data()

        # 验证文件已创建
        history_file = os.path.join(self.test_dir, "history_data.json")
        assert pathlib.Path(history_file).exists()

        # 验证数据已保存（P0 版本化格式）
        with pathlib.Path(history_file).open(encoding="utf-8") as f:
            raw = json.load(f)
        history = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
        assert len(history) == 1
        assert history[0]["speed"] == 100.0

    def test_save_current_data_with_permission_error(self):
        """测试保存当前数据时遇到权限错误的重试机制."""
        # 添加一些性能数据
        self.data_logger.record_performance_data(
            speed=200.0,
            total_checked=2000,
            matches_found=1,
            cpu_usage=60.0,
            memory_usage=512.0,
            thread_count=8,
        )

        # 模拟第一次失败，第二次成功
        call_count = [0]
        original_remove = os.remove

        def mock_remove_first_fail(path):
            call_count[0] += 1
            if call_count[0] == 1:
                raise PermissionError("模拟权限错误")
            original_remove(path)

        # 使用 patch 模拟权限错误
        with patch("os.remove", side_effect=mock_remove_first_fail):
            # 这应该会失败一次，然后重试成功
            self.data_logger.save_current_data()

        # 验证文件已创建
        current_file = os.path.join(self.test_dir, "current_data.json")
        assert pathlib.Path(current_file).exists()

        # 验证数据已保存
        with pathlib.Path(current_file).open(encoding="utf-8") as f:
            data = json.load(f)
        assert "performance" in data
        assert data["performance"]["speed"] == 200.0

    def test_retry_exhausted_returns_data_to_buffer(self):
        """测试重试耗尽后数据返回缓冲区."""
        # 添加一些历史数据
        self.data_logger.record_performance_data(
            speed=300.0,
            total_checked=3000,
            matches_found=2,
            cpu_usage=70.0,
            memory_usage=768.0,
            thread_count=12,
        )

        # 模拟持续失败
        def mock_remove_always_fail(path):
            raise PermissionError("持续权限错误")

        # 使用 patch 模拟持续权限错误
        with patch("os.remove", side_effect=mock_remove_always_fail):
            # 这应该会重试3次后失败
            self.data_logger.save_history_data()

        # 验证数据已返回缓冲区（通过再次保存成功来验证）
        # 移除 mock，恢复正常行为
        self.data_logger.save_history_data()

        history_file = os.path.join(self.test_dir, "history_data.json")
        assert pathlib.Path(history_file).exists()

        # 验证数据已保存（P0 版本化格式）
        with pathlib.Path(history_file).open(encoding="utf-8") as f:
            raw = json.load(f)
        history = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
        assert len(history) == 1
        assert history[0]["speed"] == 300.0
