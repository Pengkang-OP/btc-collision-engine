"""数据清理模块测试

测试当前简化版 DataCleaner API:
- 初始化
- clean_all() 清理过期文件
- 边界情况
"""

import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase

from src.utils.data_cleanup import DataCleaner


class TestDataCleanerBasic(TestCase):
    """DataCleaner 基础功能测试"""

    def setUp(self):
        """创建临时目录结构"""
        self.test_dir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # 创建目标子目录
        for d in ["data_logs", "logs", "temp"]:
            Path(d).mkdir(exist_ok=True, parents=True)

    def tearDown(self):
        """清理并恢复工作目录"""
        os.chdir(self._orig_cwd)
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_initialization_default(self):
        """默认初始化 — retention_days=7, 默认 target_dirs 解析为项目根路径"""
        cleaner = DataCleaner()
        self.assertEqual(cleaner._retention_seconds, 7 * 86400)
        self.assertEqual(len(cleaner._target_dirs), 3)
        # 默认路径解析为 PROJECT_ROOT 下的绝对路径
        self.assertTrue(all(isinstance(p, Path) for p in cleaner._target_dirs))
        self.assertTrue(all(p.is_absolute() for p in cleaner._target_dirs))
        names = [p.name for p in cleaner._target_dirs]
        self.assertEqual(names, ["data_logs", "logs", "temp"])

    def test_initialization_custom(self):
        """自定义参数初始化"""
        cleaner = DataCleaner(retention_days=3, target_dirs=["custom_dir"])
        self.assertEqual(cleaner._retention_seconds, 3 * 86400)
        self.assertEqual(cleaner._target_dirs, [Path("custom_dir")])


class TestDataCleanerCleanAll(TestCase):
    """clean_all() 测试"""

    def setUp(self):
        """创建临时目录和文件"""
        self.test_dir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.test_dir)

        for d in ["data_logs", "logs", "temp"]:
            Path(d).mkdir(exist_ok=True, parents=True)

    def tearDown(self):
        """清理"""
        os.chdir(self._orig_cwd)
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_clean_all_empty_dirs(self):
        """空目录 — 返回 0"""
        cleaner = DataCleaner(
            retention_days=7,
            target_dirs=[str(Path(d)) for d in ["data_logs", "logs", "temp"]],
        )
        result = cleaner.clean_all()
        self.assertEqual(result, 0)

    def test_clean_all_old_files(self):
        """清理过期文件"""
        dirs = [str(Path(d)) for d in ["data_logs", "logs", "temp"]]
        cleaner = DataCleaner(retention_days=1, target_dirs=dirs)

        # 创建过期文件（2天前）
        old_file = Path("data_logs") / "old_file.tmp"
        old_file.write_text("old data")
        old_time = time.time() - (2 * 86400)
        os.utime(str(old_file), (old_time, old_time))

        result = cleaner.clean_all()
        self.assertEqual(result, 1)
        self.assertFalse(old_file.exists())

    def test_clean_all_new_files_preserved(self):
        """新文件不被清理"""
        dirs = [str(Path(d)) for d in ["data_logs", "logs", "temp"]]
        cleaner = DataCleaner(retention_days=7, target_dirs=dirs)

        # 创建新文件
        new_file = Path("data_logs") / "new_file.tmp"
        new_file.write_text("new data")

        result = cleaner.clean_all()
        self.assertEqual(result, 0)
        self.assertTrue(new_file.exists())

    def test_clean_all_multiple_dirs(self):
        """清理多个目录中的过期文件"""
        dirs = [str(Path(d)) for d in ["data_logs", "logs", "temp"]]
        cleaner = DataCleaner(retention_days=1, target_dirs=dirs)

        old_time = time.time() - (2 * 86400)
        for d in ["data_logs", "logs", "temp"]:
            old_file = Path(d) / "old.tmp"
            old_file.write_text("old")
            os.utime(str(old_file), (old_time, old_time))

        result = cleaner.clean_all()
        self.assertEqual(result, 3)

    def test_clean_all_mixed_old_new(self):
        """混合新旧文件 — 只清理过期的"""
        dirs = [str(Path(d)) for d in ["data_logs", "logs", "temp"]]
        cleaner = DataCleaner(retention_days=1, target_dirs=dirs)

        old_time = time.time() - (2 * 86400)

        # 旧文件
        old_file = Path("data_logs") / "old.tmp"
        old_file.write_text("old")
        os.utime(str(old_file), (old_time, old_time))

        # 新文件
        new_file = Path("data_logs") / "new.tmp"
        new_file.write_text("new")

        result = cleaner.clean_all()
        self.assertEqual(result, 1)
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())


class TestDataCleanerEdgeCases(TestCase):
    """边界情况测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self._orig_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_nonexistent_target_dirs(self):
        """目标目录不存在时不报错"""
        cleaner = DataCleaner(target_dirs=["nonexistent_dir"])
        result = cleaner.clean_all()
        self.assertEqual(result, 0)

    def test_zero_retention_days(self):
        """retention_days=0 — 所有文件都被清理"""
        Path("data_logs").mkdir(exist_ok=True)
        f = Path("data_logs") / "file.tmp"
        f.write_text("data")
        # 确保 mtime < now (Windows 时间粒度问题)
        time.sleep(0.01)

        cleaner = DataCleaner(
            retention_days=0,
            target_dirs=["data_logs"],
        )
        result = cleaner.clean_all()
        self.assertEqual(result, 1)

    def test_custom_target_dirs(self):
        """自定义 target_dirs"""
        Path("custom").mkdir(exist_ok=True)
        old_file = Path("custom") / "old.tmp"
        old_file.write_text("old")
        old_time = time.time() - (8 * 86400)
        os.utime(str(old_file), (old_time, old_time))

        cleaner = DataCleaner(retention_days=7, target_dirs=["custom"])
        result = cleaner.clean_all()
        self.assertEqual(result, 1)
