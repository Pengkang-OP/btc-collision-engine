#!/usr/bin/env python3
"""监控数据自动清理工具.

定期清理过期的监控数据，防止磁盘空间占用过多
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

from src.utils import get_configured_logger

logger = get_configured_logger("DataCleanup")

# 项目根目录 (tools/../ = 项目根)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MonitoringDataCleaner:
    """监控数据清理器."""

    def __init__(
        self,
        monitoring_dir: str = "monitoring_data",
        data_logs_dir: str = "data_logs",
    ):
        """初始化清理器.

        Args:
            monitoring_dir: 监控数据目录（相对于项目根）
            data_logs_dir: 数据日志目录（相对于项目根）
        """
        self.monitoring_dir = PROJECT_ROOT / monitoring_dir
        self.data_logs_dir = PROJECT_ROOT / data_logs_dir

        logger.info("监控数据清理器初始化完成")
        logger.info("监控数据目录: %s", self.monitoring_dir)
        logger.info("数据日志目录: %s", self.data_logs_dir)

    def cleanup_old_files(self, max_age_days: int = 30, dry_run: bool = False) -> dict:
        """清理过期文件.

        Args:
            max_age_days: 文件最大保存天数
            dry_run: 是否为试运行（不实际删除）

        Returns:
            清理统计信息
        """
        stats = {
            "total_files": 0,
            "deleted_files": 0,
            "skipped_files": 0,
            "freed_space_bytes": 0,
            "errors": [],
        }

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        cutoff_date = datetime.fromtimestamp(cutoff_time)

        logger.info(f"开始清理过期文件（保留{max_age_days}天内的数据）")
        logger.info(f"截止时间: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

        # 清理监控数据目录
        stats["monitoring"] = self._cleanup_directory(self.monitoring_dir, cutoff_time, dry_run)

        # 清理数据日志目录
        stats["data_logs"] = self._cleanup_directory(self.data_logs_dir, cutoff_time, dry_run)

        # 清理日志文件
        logs_dir = PROJECT_ROOT / "logs"
        if logs_dir.exists():
            stats["logs"] = self._cleanup_directory(logs_dir, cutoff_time, dry_run)

        # 汇总统计
        for key in ["monitoring", "data_logs", "logs"]:
            if key in stats:
                stats["total_files"] += stats[key].get("total_files", 0)
                stats["deleted_files"] += stats[key].get("deleted_files", 0)
                stats["skipped_files"] += stats[key].get("skipped_files", 0)
                stats["freed_space_bytes"] += stats[key].get("freed_space_bytes", 0)
                if "errors" in stats[key]:
                    stats["errors"].extend(stats[key]["errors"])

        # 格式化输出
        freed_mb = stats["freed_space_bytes"] / (1024 * 1024)
        logger.info("清理完成:")
        logger.info(f"  总文件数: {stats['total_files']}")
        logger.info(f"  删除文件: {stats['deleted_files']}")
        logger.info(f"  跳过文件: {stats['skipped_files']}")
        logger.info(f"  释放空间: {freed_mb:.2f} MB")

        if stats["errors"]:
            logger.warning(f"  错误数: {len(stats['errors'])}")
            for error in stats["errors"][:5]:  # 只显示前5个错误
                logger.warning(f"    - {error}")

        return stats

    def _cleanup_directory(self, directory: Path, cutoff_time: float, dry_run: bool = False) -> dict:
        """清理指定目录.

        Args:
            directory: 目录路径
            cutoff_time: 截止时间戳
            dry_run: 是否试运行

        Returns:
            清理统计
        """
        stats = {
            "total_files": 0,
            "deleted_files": 0,
            "skipped_files": 0,
            "freed_space_bytes": 0,
            "errors": [],
        }

        if not directory.exists():
            logger.debug("目录不存在: %s", directory)
            return stats

        try:
            for filepath in directory.iterdir():
                if not filepath.is_file():
                    continue

                stats["total_files"] += 1

                file_mtime = filepath.stat().st_mtime

                if file_mtime < cutoff_time:
                    file_size = filepath.stat().st_size

                    if dry_run:
                        logger.info(
                            "[试运行] 将删除: %s (%.1f KB)",
                            filepath.name,
                            file_size / 1024,
                        )
                        stats["skipped_files"] += 1
                    else:
                        try:
                            filepath.unlink()
                            stats["deleted_files"] += 1
                            stats["freed_space_bytes"] += file_size
                            logger.info(
                                "已删除: %s (%.1f KB)",
                                filepath.name,
                                file_size / 1024,
                            )
                        except OSError as e:
                            error_msg = f"删除失败 {filepath.name}: {e}"
                            stats["errors"].append(error_msg)
                            logger.error(error_msg)
                else:
                    stats["skipped_files"] += 1
        except OSError as e:
            error_msg = f"清理目录失败 {directory}: {e}"
            stats["errors"].append(error_msg)
            logger.error(error_msg)

        return stats

    def get_directory_size(self, directory: Path) -> int:
        """获取目录总大小（字节）.

        Args:
            directory: 目录路径

        Returns:
            目录大小（字节）
        """
        if not directory.exists():
            return 0

        return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())

    def get_cleanup_recommendation(self, max_age_days: int = 30) -> dict:
        """获取清理建议.

        Args:
            max_age_days: 建议的保留天数

        Returns:
            清理建议字典
        """
        monitoring_size = self.get_directory_size(self.monitoring_dir)
        data_logs_size = self.get_directory_size(self.data_logs_dir)

        logs_dir = PROJECT_ROOT / "logs"
        logs_size = self.get_directory_size(logs_dir) if logs_dir.exists() else 0

        total_size = monitoring_size + data_logs_size + logs_size

        return {
            "monitoring_data_mb": monitoring_size / (1024 * 1024),
            "data_logs_mb": data_logs_size / (1024 * 1024),
            "logs_mb": logs_size / (1024 * 1024),
            "total_mb": total_size / (1024 * 1024),
            "recommended_max_age_days": max_age_days,
            "estimated_cleanup_savings_mb": total_size / (1024 * 1024) * 0.7,  # 估算可清理70%
        }


def main():
    """主函数."""
    parser = argparse.ArgumentParser(description="监控数据自动清理工具")
    parser.add_argument("--max-age", type=int, default=30, help="数据最大保存天数（默认30天）")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式（不实际删除文件）")
    parser.add_argument("--recommend", action="store_true", help="显示清理建议")

    args = parser.parse_args()

    cleaner = MonitoringDataCleaner()

    if args.recommend:
        print("\n" + "=" * 60)
        print("监控数据清理建议")
        print("=" * 60)

        recommendation = cleaner.get_cleanup_recommendation(args.max_age)
        print(f"\n监控数据目录: {recommendation['monitoring_data_mb']:.2f} MB")
        print(f"数据日志目录: {recommendation['data_logs_mb']:.2f} MB")
        print(f"系统日志目录: {recommendation['logs_mb']:.2f} MB")
        print(f"\n总占用空间: {recommendation['total_mb']:.2f} MB")
        print(f"建议保留天数: {recommendation['recommended_max_age_days']} 天")
        print(f"预计可清理: {recommendation['estimated_cleanup_savings_mb']:.2f} MB")
        print()
    else:
        print("\n" + "=" * 60)
        print("监控数据自动清理")
        print("=" * 60)

        if args.dry_run:
            print("\n[试运行模式] 不会实际删除文件\n")

        stats = cleaner.cleanup_old_files(max_age_days=args.max_age, dry_run=args.dry_run)

        print("\n清理完成!")
        print(f"  总文件数: {stats['total_files']}")
        print(f"  删除文件: {stats['deleted_files']}")
        print(f"  跳过文件: {stats['skipped_files']}")
        print(f"  释放空间: {stats['freed_space_bytes'] / (1024 * 1024):.2f} MB")

        if stats["errors"]:
            print(f"\n  错误数: {len(stats['errors'])}")
            for error in stats["errors"][:3]:
                print(f"    - {error}")

        print()


if __name__ == "__main__":
    main()
