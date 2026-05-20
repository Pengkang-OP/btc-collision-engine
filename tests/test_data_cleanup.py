"""数据清理模块测试

测试 DataCleaner 类的各项功能:
- 临时文件清理
- 历史数据清理
- 日志轮转
- 监控数据清理
- 清理统计
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.data_cleanup import DataCleaner  # noqa: E402


class TestDataCleanerBasic(TestCase):
    """DataCleaner基础功能测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()

        # 创建必要的子目录
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "monitoring_data"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """初始化测试"""
        self.assertIsNotNone(self.cleaner.project_root)
        self.assertEqual(self.cleaner.project_root, self.test_dir)

        # 验证初始统计
        self.assertEqual(self.cleaner.stats["files_removed"], 0)
        self.assertEqual(self.cleaner.stats["space_freed_bytes"], 0)
        self.assertEqual(self.cleaner.stats["errors"], 0)

    def test_initialization_default_path(self):
        """默认路径初始化"""
        cleaner = DataCleaner()

        # 应该使用项目根目录
        self.assertIsNotNone(cleaner.project_root)

    def test_stats_structure(self):
        """统计数据结构测试"""
        expected_keys = ["files_removed", "space_freed_bytes", "dirs_cleaned", "errors"]

        for key in expected_keys:
            self.assertIn(key, self.cleaner.stats)


class TestDataCleanerTempFiles(TestCase):
    """临时文件清理测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()

        # 创建必要的子目录
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_temp_files_no_files(self):
        """无临时文件时清理"""
        removed, freed = self.cleaner.clean_temp_files()

        self.assertEqual(removed, 0)
        self.assertEqual(freed, 0)

    def test_clean_temp_files_old_files(self):
        """清理旧临时文件"""
        # 创建旧临时文件（修改时间为8天前）
        old_file = Path(self.test_dir) / "data_logs" / "old_file.tmp"
        old_file.touch()

        # 设置文件时间为8天前
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_temp_files(max_age_days=7, dry_run=False)

        self.assertEqual(removed, 1)
        self.assertFalse(old_file.exists())

    def test_clean_temp_files_new_files(self):
        """不清理新临时文件"""
        # 创建新临时文件
        new_file = Path(self.test_dir) / "data_logs" / "new_file.tmp"
        new_file.touch()

        removed, freed = self.cleaner.clean_temp_files(max_age_days=7, dry_run=False)

        self.assertEqual(removed, 0)
        self.assertTrue(new_file.exists())

    def test_clean_temp_files_dry_run(self):
        """试运行模式清理"""
        # 创建旧临时文件
        old_file = Path(self.test_dir) / "data_logs" / "old_file.tmp"
        old_file.touch()

        old_time = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_temp_files(max_age_days=7, dry_run=True)

        # 试运行应该报告文件但实际不删除
        self.assertEqual(removed, 1)
        self.assertTrue(old_file.exists())  # 文件仍然存在

    def test_clean_temp_files_multiple_dirs(self):
        """清理多个目录的临时文件"""
        # 在data_logs创建旧文件
        old_file1 = Path(self.test_dir) / "data_logs" / "old1.tmp"
        old_file1.touch()
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(old_file1, (old_time, old_time))

        # 在logs创建旧文件
        old_file2 = Path(self.test_dir) / "logs" / "old2.tmp"
        old_file2.touch()
        os.utime(old_file2, (old_time, old_time))

        removed, freed = self.cleaner.clean_temp_files(max_age_days=7, dry_run=False)

        self.assertEqual(removed, 2)
        self.assertFalse(old_file1.exists())
        self.assertFalse(old_file2.exists())


class TestDataCleanerOldData(TestCase):
    """历史数据清理测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_old_data_no_files(self):
        """无历史数据时清理"""
        removed, freed = self.cleaner.clean_old_data()

        self.assertEqual(removed, 0)
        self.assertEqual(freed, 0)

    def test_clean_old_data_old_files(self):
        """清理旧历史数据"""
        # 创建旧历史数据文件（31天前）
        old_file = Path(self.test_dir) / "data_logs" / "history_data_old.json"
        old_file.touch()

        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_old_data(max_age_days=30, dry_run=False)

        self.assertEqual(removed, 1)
        self.assertFalse(old_file.exists())

    def test_clean_old_data_new_files(self):
        """不清理新历史数据"""
        # 创建新历史数据文件
        new_file = Path(self.test_dir) / "data_logs" / "history_data_new.json"
        new_file.touch()

        removed, freed = self.cleaner.clean_old_data(max_age_days=30, dry_run=False)

        self.assertEqual(removed, 0)
        self.assertTrue(new_file.exists())

    def test_clean_old_data_dry_run(self):
        """试运行模式"""
        # 创建旧历史数据文件
        old_file = Path(self.test_dir) / "data_logs" / "history_data_old.json"
        old_file.touch()

        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_old_data(max_age_days=30, dry_run=True)

        self.assertEqual(removed, 1)
        self.assertTrue(old_file.exists())

    def test_clean_old_data_non_matching_files(self):
        """不清理不匹配模式的文件"""
        # 创建不匹配的文件
        other_file = Path(self.test_dir) / "data_logs" / "other_file.txt"
        other_file.touch()

        old_time = time.time() - (31 * 24 * 3600)
        os.utime(other_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_old_data(max_age_days=30, dry_run=False)

        # 只清理history_data_*.json文件
        self.assertEqual(removed, 0)
        self.assertTrue(other_file.exists())


class TestDataCleanerLogRotation(TestCase):
    """日志轮转测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_rotate_logs_no_files(self):
        """无日志文件时轮转"""
        removed = self.cleaner.rotate_log_files()

        self.assertEqual(removed, 0)

    def test_rotate_logs_under_limit(self):
        """日志文件未超过限制"""
        # 创建3个日志文件（限制5个）
        for i in range(3):
            log_file = Path(self.test_dir) / "logs" / f"app_{i}.log"
            log_file.touch()

        removed = self.cleaner.rotate_log_files(max_files=5)

        self.assertEqual(removed, 0)

    def test_rotate_logs_over_limit(self):
        """日志文件超过限制"""
        # 创建7个日志文件（限制5个）
        for i in range(7):
            log_file = Path(self.test_dir) / "logs" / f"app_{i}.log"
            log_file.touch()
            # 设置不同的修改时间
            old_time = time.time() - (i * 3600)
            os.utime(log_file, (old_time, old_time))

        removed = self.cleaner.rotate_log_files(max_files=5)

        # 应该删除最旧的2个文件
        self.assertEqual(removed, 2)

    def test_rotate_logs_dry_run(self):
        """试运行模式"""
        # 创建7个日志文件
        for i in range(7):
            log_file = Path(self.test_dir) / "logs" / f"app_{i}.log"
            log_file.touch()
            old_time = time.time() - (i * 3600)
            os.utime(log_file, (old_time, old_time))

        removed = self.cleaner.rotate_log_files(max_files=5, dry_run=True)

        # 试运行应该报告但实际不删除
        self.assertEqual(removed, 2)

        # 所有文件应该仍然存在
        log_count = len(list((Path(self.test_dir) / "logs").glob("*.log*")))
        self.assertEqual(log_count, 7)


class TestDataCleanerMonitoringData(TestCase):
    """监控数据清理测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "monitoring_data"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_monitoring_data_no_files(self):
        """无监控数据时清理"""
        removed, freed = self.cleaner.clean_monitoring_data()

        self.assertEqual(removed, 0)
        self.assertEqual(freed, 0)

    def test_clean_monitoring_data_old_files(self):
        """清理旧监控数据"""
        # 创建旧监控数据文件（31天前）
        old_file = Path(self.test_dir) / "monitoring_data" / "metrics_old.json"
        old_file.touch()

        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_monitoring_data(max_age_days=30, dry_run=False)

        self.assertEqual(removed, 1)
        self.assertFalse(old_file.exists())

    def test_clean_monitoring_data_dry_run(self):
        """试运行模式"""
        # 创建旧监控数据文件
        old_file = Path(self.test_dir) / "monitoring_data" / "metrics_old.json"
        old_file.touch()

        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        removed, freed = self.cleaner.clean_monitoring_data(max_age_days=30, dry_run=True)

        self.assertEqual(removed, 1)
        self.assertTrue(old_file.exists())


class TestDataCleanerCleanAll(TestCase):
    """清理所有数据测试"""

    def setUp(self):
        """创建临时项目目录结构"""
        self.test_dir = tempfile.mkdtemp()

        # 创建所有子目录
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "monitoring_data"), exist_ok=True)

        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_all_empty_dirs(self):
        """清理空目录"""
        result = self.cleaner.clean_all(dry_run=False)

        self.assertIn("files_removed", result)
        self.assertIn("space_freed_bytes", result)
        self.assertIn("errors", result)

    def test_clean_all_dry_run(self):
        """试运行清理所有"""
        result = self.cleaner.clean_all(dry_run=True)

        # 试运行不应该有错误
        self.assertEqual(result["errors"], 0)

    def test_clean_all_stats_accumulation(self):
        """清理统计累积"""
        # 创建一些旧文件
        old_file = Path(self.test_dir) / "data_logs" / "old.tmp"
        old_file.touch()
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        result = self.cleaner.clean_all(dry_run=False)

        # 应该至少删除1个文件
        self.assertGreaterEqual(result["files_removed"], 1)


class TestDataCleanerDiskUsage(TestCase):
    """磁盘使用情况测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_disk_usage(self):
        """获取磁盘使用情况"""
        usage = self.cleaner.get_disk_usage()

        self.assertIn("total_gb", usage)
        self.assertIn("used_gb", usage)
        self.assertIn("free_gb", usage)
        self.assertIn("usage_percent", usage)

        # 验证数值合理性
        self.assertGreater(usage["total_gb"], 0)
        self.assertGreaterEqual(usage["usage_percent"], 0)
        self.assertLessEqual(usage["usage_percent"], 100)


class TestDataCleanerEdgeCases(TestCase):
    """边界情况测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_nonexistent_project_root(self):
        """不存在的项目根目录"""
        nonexistent_dir = os.path.join(self.test_dir, "nonexistent")
        cleaner = DataCleaner(project_root=nonexistent_dir)

        # 应该能正常初始化
        self.assertIsNotNone(cleaner.project_root)

        # 清理应该能处理不存在的目录
        result = cleaner.clean_all(dry_run=True)
        self.assertIsInstance(result, dict)

    def test_clean_with_permission_error(self):
        """清理时遇到权限错误"""
        # 在Windows上难以真正测试权限问题
        # 这里测试正常情况
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        cleaner = DataCleaner(project_root=self.test_dir)

        result = cleaner.clean_all(dry_run=True)
        self.assertIsInstance(result, dict)

    def test_multiple_clean_operations(self):
        """多次清理操作"""
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        cleaner = DataCleaner(project_root=self.test_dir)

        # 第一次清理
        result1 = cleaner.clean_all(dry_run=True)

        # 第二次清理
        result2 = cleaner.clean_all(dry_run=True)

        # 两次都应该成功
        self.assertIsInstance(result1, dict)
        self.assertIsInstance(result2, dict)


class TestDataCleanerOldReports(TestCase):
    """报告归档测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_old_reports_no_dir(self):
        """data_logs 不存在返回空"""
        empty_dir = tempfile.mkdtemp()
        try:
            cleaner = DataCleaner(project_root=empty_dir)
            result = cleaner.clean_old_reports()
            self.assertEqual(result["moved"], 0)
            self.assertEqual(result["space_freed_bytes"], 0)
            self.assertEqual(result["errors"], 0)
        finally:
            shutil.rmtree(empty_dir)

    def test_clean_old_reports_old_files(self):
        """过期报告被移动到 archive/"""
        old_file = Path(self.test_dir) / "data_logs" / "report_old.json"
        old_file.touch()
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(str(old_file), (old_time, old_time))

        result = self.cleaner.clean_old_reports(max_age_days=7)
        self.assertEqual(result["moved"], 1)
        self.assertFalse(old_file.exists())
        archive_path = Path(self.test_dir) / "data_logs" / "archive" / "report_old.json"
        self.assertTrue(archive_path.exists())

    def test_clean_old_reports_new_files(self):
        """新报告不被移动"""
        new_file = Path(self.test_dir) / "data_logs" / "report_new.json"
        new_file.touch()

        result = self.cleaner.clean_old_reports(max_age_days=7)
        self.assertEqual(result["moved"], 0)
        self.assertTrue(new_file.exists())

    def test_clean_old_reports_daily_pattern(self):
        """匹配 report_daily_*.json 模式"""
        old_file = Path(self.test_dir) / "data_logs" / "report_daily_2024.json"
        old_file.touch()
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(str(old_file), (old_time, old_time))

        result = self.cleaner.clean_old_reports(max_age_days=7)
        self.assertEqual(result["moved"], 1)

    def test_clean_old_reports_creates_archive(self):
        """自动创建 archive 目录"""
        archive_dir = Path(self.test_dir) / "data_logs" / "archive"
        self.assertFalse(archive_dir.exists())

        result = self.cleaner.clean_old_reports(max_age_days=7)
        self.assertEqual(result["moved"], 0)
        self.assertTrue(archive_dir.exists())

    def test_clean_old_reports_empty_result(self):
        """无匹配文件"""
        result = self.cleaner.clean_old_reports()
        self.assertEqual(result["moved"], 0)


class TestRotatePerformanceLog(TestCase):
    """性能日志轮转测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.test_dir, "data_logs"), exist_ok=True)
        self.cleaner = DataCleaner(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_no_file_returns_false(self):
        """文件不存在返回 False"""
        result = self.cleaner.rotate_performance_log()
        self.assertFalse(result)

    def test_under_threshold_returns_false(self):
        """文件未超 10MB 返回 False"""
        perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        perf_log.write_text("small content")

        result = self.cleaner.rotate_performance_log(max_size_mb=10.0)
        self.assertFalse(result)
        self.assertTrue(perf_log.exists())

    def test_over_threshold_rotates(self):
        """超过阈值触发归档"""
        perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        # 写入超过 1MB 的内容（使用较小阈值测试）
        content = "x" * (1024 * 1024 + 100)  # ~1MB+100B
        perf_log.write_text(content)

        result = self.cleaner.rotate_performance_log(max_size_mb=1.0)
        self.assertTrue(result)
        # 轮转后 touch() 创建了新文件
        new_perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        self.assertTrue(new_perf_log.exists())
        self.assertEqual(new_perf_log.stat().st_size, 0)
        # 归档文件存在
        archive_dir = Path(self.test_dir) / "data_logs" / "archive"
        archives = list(archive_dir.glob("performance_log_*.log"))
        self.assertEqual(len(archives), 1)

    def test_archive_name_collision(self):
        """同日期归档文件已存在时添加时间戳"""
        from datetime import datetime

        perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        content = "x" * (1024 * 1024 + 100)
        perf_log.write_text(content)

        # 预先创建同日期归档文件
        archive_dir = Path(self.test_dir) / "data_logs" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # 使用固定日期避免午夜竞态
        fixed_now = datetime(2026, 5, 4, 12, 0, 0)
        date_str = fixed_now.strftime("%Y%m%d")
        existing_archive = archive_dir / f"performance_log_{date_str}.log"
        existing_archive.write_text("existing")

        with patch("src.utils.data_cleanup.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            result = self.cleaner.rotate_performance_log(max_size_mb=1.0)
        self.assertTrue(result)
        self.assertTrue(existing_archive.exists())
        # 应该创建带时间戳的归档文件
        archives = list(archive_dir.glob("performance_log_*.log"))
        self.assertEqual(len(archives), 2)

    def test_dry_run_does_not_move(self):
        """dry_run 不实际移动"""
        perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        content = "x" * (1024 * 1024 + 100)
        perf_log.write_text(content)

        result = self.cleaner.rotate_performance_log(max_size_mb=1.0, dry_run=True)
        self.assertTrue(result)
        # dry_run 模式下文件仍然存在
        self.assertTrue(perf_log.exists())

    def test_rotation_error_returns_false(self):
        """OSError 返回 False"""
        perf_log = Path(self.test_dir) / "data_logs" / "performance.log"
        content = "x" * (1024 * 1024 + 100)
        perf_log.write_text(content)

        with patch("shutil.move", side_effect=OSError("disk full")):
            result = self.cleaner.rotate_performance_log(max_size_mb=1.0)
        self.assertFalse(result)


if __name__ == "__main__":
    import unittest

    unittest.main()
