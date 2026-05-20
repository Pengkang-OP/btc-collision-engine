#!/usr/bin/env python3
"""
清理src目录中的归档文件脚本

此脚本用于清理src/data_logs/archive目录中的报告文件。
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import get_configured_logger, init_logging  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("SrcArchiveCleanup")


def clean_src_archive_files():
    """清理src目录中的归档文件"""
    logger.info("开始清理src目录中的归档文件...")

    # 清理src/data_logs/archive目录中的报告文件
    src_archive_dir = os.path.join(os.path.dirname(__file__), "..", "src", "data_logs", "archive")

    if os.path.exists(src_archive_dir):
        for file_name in os.listdir(src_archive_dir):
            file_path = os.path.join(src_archive_dir, file_name)
            is_target = file_name.startswith("report_") and file_name.endswith(".json")
            if os.path.isfile(file_path) and is_target:
                    try:
                        os.remove(file_path)
                        logger.info(f"清理src归档文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"清理src归档文件失败: {e}")


def main():
    """主函数"""
    try:
        logger.info("开始清理src目录中的归档文件...")

        # 清理src归档文件
        clean_src_archive_files()

        logger.info("✅ src目录中的归档文件清理完成")
    except Exception as e:
        logger.error(f"❌ 清理src目录中的归档文件失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
