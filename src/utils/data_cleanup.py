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
from typing import List, Tuple

logger = logging.getLogger(__name__)


class DataCleaner:
    """数据清理器
    
    清理策略:
    - 删除7天前的临时文件（.tmp）
    - 保留最近30天的历史数据
    - 日志文件轮转（保留最近5个）
    - 监控数据自动归档
    """
    
    def __init__(self, project_root: str = None):
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
        ]
        
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


def main():
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
