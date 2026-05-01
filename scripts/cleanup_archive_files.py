#!/usr/bin/env python3
"""
清理归档文件脚本

此脚本用于清理系统中的归档文件，包括data_logs/archive目录中的报告文件。
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import init_logging, get_configured_logger  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("ArchiveCleanup")


def clean_archive_files():
    """清理归档文件"""
    logger.info("开始清理归档文件...")

    # 清理data_logs/archive目录中的报告文件
    archive_dir = os.path.join(os.path.dirname(__file__), "..", "data_logs", "archive")

    if os.path.exists(archive_dir):
        for file_name in os.listdir(archive_dir):
            file_path = os.path.join(archive_dir, file_name)
            if os.path.isfile(file_path):
                # 清理report_daily_*.json文件
                if file_name.startswith("report_daily_") and file_name.endswith(".json"):
                    try:
                        os.remove(file_path)
                        logger.info(f"清理归档文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"清理归档文件失败: {e}")


def main():
    """主函数"""
    try:
        logger.info("开始清理系统归档文件...")

        # 清理归档文件
        clean_archive_files()

        logger.info("✅ 系统归档文件清理完成")
    except Exception as e:
        logger.error(f"❌ 清理系统归档文件失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
