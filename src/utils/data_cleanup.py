# -*- coding: utf-8 -*-
"""数据清理模块

自动清理过期的临时文件、日志和监控数据，防止磁盘空间耗尽。
"""

import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class DataCleaner:
    """数据清理器
    
    清理策略:
    - 删除7天前的临时文件（.tmp）
    - 保留最近30天的历史数据
    - 日志文件轮转（保留最近5个）
    - 监控数据自动归档
    """
    
    def __init__(self, project_root: str = None) -> None:
        """初始化数据清理器
        
        参数:
            project_root: 项目根目录路径
        """
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.stats = {
            'files_removed': 0,
            'space_freed_bytes': 0,
            'dirs_cleaned': 0,
            'errors': 0
        }
    
    def clean_temp_files(self, max_age_days: int = 7, dry_run: bool = False) -> Tuple[int, int]:
        """清理临时文件
        
        参数:
            max_age_days: 最大保留天数
            dry_run: 是否为试运行（不实际删除）
            
        返回:
            (删除的文件数, 释放的空间字节数)
        """
        logger.info(f"开始清理临时文件（>{max_age_days}天）...")
        
        temp_dirs = ['data_logs', 'logs']
        files_removed = 0
        space_freed = 0
        
        for dir_name in temp_dirs:
            dir_path = os.path.join(self.project_root, dir_name)
            if not os.path.exists(dir_path):
                continue
            
            for file_path in Path(dir_path).rglob('*.tmp'):
                try:
                    file_age = time.time() - file_path.stat().st_mtime
                    file_age_days = file_age / (24 * 3600)
                    
                    if file_age_days > max_age_days:
                        file_size = file_path.stat().st_size
                        
                        if not dry_run:
                            file_path.unlink()
                            logger.debug(f"删除临时文件: {file_path}")
                        
                        files_removed += 1
                        space_freed += file_size
                except Exception as e:
                    logger.error(f"清理临时文件失败 {file_path}: {e}")
                    self.stats['errors'] += 1
        
        self.stats['files_removed'] += files_removed
        self.stats['space_freed_bytes'] += space_freed
        
        logger.info(f"临时文件清理完成: 删除{files_removed}个文件, 释放{space_freed / 1024 / 1024:.2f}MB")
        return files_removed, space_freed
    
    def clean_old_data(self, max_age_days: int = 30, dry_run: bool = False) -> Tuple[int, int]:
        """清理过期历史数据
        
        参数:
            max_age_days: 最大保留天数
            dry_run: 是否为试运行
            
        返回:
            (删除的文件数, 释放的空间字节数)
        """
        logger.info(f"开始清理过期数据（>{max_age_days}天）...")
        
        data_dir = os.path.join(self.project_root, 'data_logs')
        if not os.path.exists(data_dir):
            return 0, 0
        
        files_removed = 0
        space_freed = 0
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        for file_path in Path(data_dir).glob('history_data_*.json'):
            try:
                file_mtime = file_path.stat().st_mtime
                
                if file_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        file_path.unlink()
                        logger.debug(f"删除过期数据: {file_path}")
                    
                    files_removed += 1
                    space_freed += file_size
            except Exception as e:
                logger.error(f"清理过期数据失败 {file_path}: {e}")
                self.stats['errors'] += 1
        
        self.stats['files_removed'] += files_removed
        self.stats['space_freed_bytes'] += space_freed
        
        logger.info(f"过期数据清理完成: 删除{files_removed}个文件, 释放{space_freed / 1024 / 1024:.2f}MB")
        return files_removed, space_freed
    
    def rotate_log_files(self, max_files: int = 5, dry_run: bool = False) -> int:
        """轮转日志文件
        
        参数:
            max_files: 保留的最大文件数
            dry_run: 是否为试运行
            
        返回:
            删除的文件数
        """
        logger.info(f"开始轮转日志文件（保留{max_files}个）...")
        
        log_dir = os.path.join(self.project_root, 'logs')
        if not os.path.exists(log_dir):
            return 0
        
        # 按修改时间排序
        log_files = []
        for file_path in Path(log_dir).glob('*.log*'):
            log_files.append((file_path, file_path.stat().st_mtime))
        
        log_files.sort(key=lambda x: x[1], reverse=True)
        
        # 删除超出数量的旧日志
        files_removed = 0
        for file_path, _ in log_files[max_files:]:
            try:
                file_size = file_path.stat().st_size
                
                if not dry_run:
                    file_path.unlink()
                    logger.debug(f"删除旧日志: {file_path}")
                
                files_removed += 1
                self.stats['space_freed_bytes'] += file_size
            except Exception as e:
                logger.error(f"删除旧日志失败 {file_path}: {e}")
                self.stats['errors'] += 1
        
        self.stats['files_removed'] += files_removed
        logger.info(f"日志轮转完成: 删除{files_removed}个文件")
        return files_removed
    
    def clean_monitoring_data(self, max_age_days: int = 30, dry_run: bool = False) -> Tuple[int, int]:
        """清理监控数据
        
        参数:
            max_age_days: 最大保留天数
            dry_run: 是否为试运行
            
        返回:
            (删除的文件数, 释放的空间字节数)
        """
        logger.info(f"开始清理监控数据（>{max_age_days}天）...")
        
        monitor_dir = os.path.join(self.project_root, 'monitoring_data')
        if not os.path.exists(monitor_dir):
            return 0, 0
        
        files_removed = 0
        space_freed = 0
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        for file_path in Path(monitor_dir).glob('*.json'):
            try:
                file_mtime = file_path.stat().st_mtime
                
                if file_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        file_path.unlink()
                        logger.debug(f"删除监控数据: {file_path}")
                    
                    files_removed += 1
                    space_freed += file_size
            except Exception as e:
                logger.error(f"清理监控数据失败 {file_path}: {e}")
                self.stats['errors'] += 1
        
        self.stats['files_removed'] += files_removed
        self.stats['space_freed_bytes'] += space_freed
        
        logger.info(f"监控数据清理完成: 删除{files_removed}个文件, 释放{space_freed / 1024 / 1024:.2f}MB")
        return files_removed, space_freed
    
    def clean_old_reports(self, max_age_days: int = 7, archive_dir: str = "archive") -> Dict[str, Any]:
        """清理过期的报告文件，将超过指定天数的报告归档
        
        Args:
            max_age_days: 报告保留天数，默认7天
            archive_dir: 归档子目录名称，默认为 "archive"
        
        Returns:
            清理统计信息
        """
        logger.info(f"开始归档过期报告文件（>{max_age_days}天）...")
        
        data_dir = os.path.join(self.project_root, 'data_logs')
        if not os.path.exists(data_dir):
            return {'moved': 0, 'space_freed_bytes': 0, 'errors': 0}
        
        archive_path = os.path.join(data_dir, archive_dir)
        os.makedirs(archive_path, exist_ok=True)
        
        moved_count = 0
        space_freed = 0
        errors = 0
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        patterns = ['report_daily_*.json', 'report_*.json']
        matched_files = set()
        for pattern in patterns:
            for file_path in Path(data_dir).glob(pattern):
                matched_files.add(file_path)
        
        for file_path in matched_files:
            try:
                file_mtime = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    dest = os.path.join(archive_path, file_path.name)
                    shutil.move(str(file_path), dest)
                    logger.debug(f"归档报告文件: {file_path.name}")
                    moved_count += 1
                    space_freed += file_size
                    self.stats['files_removed'] += 1
                    self.stats['space_freed_bytes'] += file_size
            except OSError as e:
                logger.error(f"归档报告文件失败 {file_path}: {e}")
                self.stats['errors'] += 1
                errors += 1
        
        logger.info(f"报告归档完成: 移动{moved_count}个文件, 释放{space_freed / 1024 / 1024:.2f}MB")
        return {'moved': moved_count, 'space_freed_bytes': space_freed, 'errors': errors}

    def rotate_performance_log(self, max_size_mb: float = 10.0, dry_run: bool = False) -> bool:
        """轮转 performance.log 日志文件

        当 data_logs/performance.log 超过指定大小时，将其归档到
        data_logs/archive/ 目录，并创建新的空文件。

        参数:
            max_size_mb: 触发轮转的文件大小阈值（MB），默认 10MB
            dry_run: 是否为试运行（不实际操作文件）

        返回:
            True 表示执行了轮转操作，False 表示无需轮转
        """
        # 构建 performance.log 的完整路径
        perf_log_path = Path(self.project_root) / 'data_logs' / 'performance.log'

        # 文件不存在则直接返回
        if not perf_log_path.exists():
            logger.debug("performance.log 不存在，跳过轮转")
            return False

        # 获取文件大小（字节转 MB）
        file_size_bytes = perf_log_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # 文件未超过阈值则不需要轮转
        if file_size_mb <= max_size_mb:
            logger.debug(f"performance.log 大小为 {file_size_mb:.2f}MB，未超过阈值 {max_size_mb}MB，无需轮转")
            return False

        logger.info(f"performance.log 大小为 {file_size_mb:.2f}MB，超过 {max_size_mb}MB 阈值，开始轮转...")

        # 确保归档目录存在
        archive_dir = Path(self.project_root) / 'data_logs' / 'archive'
        archive_dir.mkdir(parents=True, exist_ok=True)

        # 归档文件命名格式：performance_log_YYYYMMDD.log
        date_str = datetime.now().strftime('%Y%m%d')
        archive_name = f'performance_log_{date_str}.log'
        archive_path = archive_dir / archive_name

        # 如果同日期归档文件已存在，追加时间戳以避免覆盖
        if archive_path.exists():
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'performance_log_{timestamp_str}.log'
            archive_path = archive_dir / archive_name

        try:
            if not dry_run:
                # 将当前文件移动到归档目录
                shutil.move(str(perf_log_path), str(archive_path))
                logger.info(f"performance.log 已归档至: {archive_path}")

                # 创建新的空 performance.log
                perf_log_path.touch()
                logger.info("已创建新的空 performance.log")

                # 更新统计信息
                self.stats['space_freed_bytes'] += file_size_bytes
                self.stats['files_removed'] += 1
            else:
                logger.info(f"[试运行] 将归档 performance.log ({file_size_mb:.2f}MB) -> {archive_path}")

            return True
        except OSError as e:
            logger.error(f"轮转 performance.log 失败: {e}")
            self.stats['errors'] += 1
            return False

    def clean_all(self, dry_run: bool = False) -> dict:
        """执行所有清理任务
        
        参数:
            dry_run: 是否为试运行
            
        返回:
            清理统计信息
        """
        print("=" * 70)
        print("BTC碰撞引擎 - 数据清理")
        print("=" * 70)
        print()
        
        if dry_run:
            print("[试运行模式] 不会实际删除文件")
            print()
        
        # 执行清理任务
        tasks = [
            ("临时文件", lambda: self.clean_temp_files(dry_run=dry_run)),
            ("过期数据", lambda: self.clean_old_data(dry_run=dry_run)),
            ("日志轮转", lambda: (self.rotate_log_files(dry_run=dry_run), 0)),
            ("监控数据", lambda: self.clean_monitoring_data(dry_run=dry_run)),
            ("报告归档", lambda: (lambda r: (r['moved'], r['space_freed_bytes']))(self.clean_old_reports()) if not dry_run else (0, 0)),
        ]

        # 单独处理 performance.log 轮转（返回值为 bool，不适合统一的 (files, space) 格式）
        try:
            rotated = self.rotate_performance_log(dry_run=dry_run)
            if rotated:
                print("[成功] performance.log轮转: 已归档超大日志文件")
            else:
                print("[跳过] performance.log轮转: 文件未超过10MB阈值")
        except Exception as e:
            print(f"[错误] performance.log轮转: {e}")
            logger.error(f"performance.log 轮转任务失败: {e}")
            self.stats['errors'] += 1
        
        for task_name, task_func in tasks:
            try:
                files, space = task_func()
                print(f"[成功] {task_name}: 删除{files}个文件, 释放{space / 1024 / 1024:.2f}MB")
            except Exception as e:
                print(f"[错误] {task_name}: {e}")
                logger.error(f"清理任务失败 {task_name}: {e}")
                self.stats['errors'] += 1
        
        print()
        print("=" * 70)
        print("清理统计:")
        print(f"  删除文件数: {self.stats['files_removed']}")
        print(f"  释放空间: {self.stats['space_freed_bytes'] / 1024 / 1024:.2f}MB")
        print(f"  错误数: {self.stats['errors']}")
        print("=" * 70)
        
        return self.stats
    
    def get_disk_usage(self) -> dict:
        """获取磁盘使用情况"""
        try:
            total, used, free = shutil.disk_usage(self.project_root)
            return {
                'total_gb': total / (1024**3),
                'used_gb': used / (1024**3),
                'free_gb': free / (1024**3),
                'usage_percent': (used / total) * 100
            }
        except Exception as e:
            logger.error(f"获取磁盘使用情况失败: {e}")
            return {}


def main() -> None:
    """数据清理CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="BTC碰撞引擎数据清理工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，不实际删除文件"
    )
    parser.add_argument(
        "--temp-days",
        type=int,
        default=7,
        help="临时文件最大保留天数（默认: 7）"
    )
    parser.add_argument(
        "--data-days",
        type=int,
        default=30,
        help="历史数据最大保留天数（默认: 30）"
    )
    parser.add_argument(
        "--log-files",
        type=int,
        default=5,
        help="保留的日志文件数（默认: 5）"
    )
    
    args = parser.parse_args()
    
    cleaner = DataCleaner()
    
    # 显示磁盘使用情况
    disk_usage = cleaner.get_disk_usage()
    if disk_usage:
        print(f"磁盘使用: {disk_usage['used_gb']:.2f}GB / {disk_usage['total_gb']:.2f}GB ({disk_usage['usage_percent']:.1f}%)")
        print(f"可用空间: {disk_usage['free_gb']:.2f}GB")
        print()
    
    # 执行清理
    cleaner.clean_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
