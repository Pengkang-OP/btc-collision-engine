#!/usr/bin/env python3
"""
临时文件清理脚本

此脚本用于清理系统中的临时文件，包括日志文件、测试文件、临时配置文件等。
"""

import os
import shutil
import glob
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import init_logging, get_configured_logger  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("TemporaryFileCleanup")


def clean_log_files():
    """清理日志文件"""
    logger.info("开始清理日志文件...")

    # 清理日志文件
    log_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "src", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "tests", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "logs", "*.log"),
    ]

    for pattern in log_patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
                logger.info(f"清理日志文件: {file_path}")
            except Exception as e:
                logger.warning(f"清理日志文件失败: {e}")


def clean_test_files():
    """清理测试文件"""
    logger.info("开始清理测试文件...")

    # 清理测试文件
    test_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "test_results", "*.txt"),
        os.path.join(os.path.dirname(__file__), "..", "test_results", "*.xml"),
        os.path.join(os.path.dirname(__file__), "..", "test_results", "*.json"),
        os.path.join(os.path.dirname(__file__), "..", "test_matches", "*.json"),
        os.path.join(os.path.dirname(__file__), "..", "tests", "*.pyc"),
        os.path.join(os.path.dirname(__file__), "..", "tests", "__pycache__"),
    ]

    for pattern in test_patterns:
        for file_path in glob.glob(pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"清理测试文件: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.info(f"清理测试目录: {file_path}")
            except Exception as e:
                logger.warning(f"清理测试文件失败: {e}")


def clean_temporary_configs():
    """清理临时配置文件"""
    logger.info("开始清理临时配置文件...")

    # 清理临时配置文件
    config_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "config.*.json"),
        os.path.join(os.path.dirname(__file__), "..", "*.tmp.json"),
        os.path.join(os.path.dirname(__file__), "..", "*.temp.json"),
    ]

    for pattern in config_patterns:
        for file_path in glob.glob(pattern):
            # 保留 config.json 和 config.example.json
            if os.path.basename(file_path) in ["config.json", "config.example.json"]:
                continue
            try:
                os.remove(file_path)
                logger.info(f"清理临时配置文件: {file_path}")
            except Exception as e:
                logger.warning(f"清理临时配置文件失败: {e}")


def clean_benchmark_files():
    """清理基准测试文件"""
    logger.info("开始清理基准测试文件...")

    # 清理基准测试文件
    benchmark_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results"),
    ]

    for dir_path in benchmark_dirs:
        if os.path.exists(dir_path):
            for file_path in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_path)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"清理基准测试文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"清理基准测试文件失败: {e}")


def clean_build_files():
    """清理构建文件"""
    logger.info("开始清理构建文件...")

    # 清理构建文件
    build_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "build", "*"),
        os.path.join(os.path.dirname(__file__), "..", "dist", "*"),
        os.path.join(os.path.dirname(__file__), "..", "*.egg-info"),
    ]

    for pattern in build_patterns:
        for file_path in glob.glob(pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"清理构建文件: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    logger.info(f"清理构建目录: {file_path}")
            except Exception as e:
                logger.warning(f"清理构建文件失败: {e}")


def main():
    """主函数"""
    try:
        logger.info("开始清理系统临时文件...")

        # 清理日志文件
        clean_log_files()

        # 清理测试文件
        clean_test_files()

        # 清理临时配置文件
        clean_temporary_configs()

        # 清理基准测试文件
        clean_benchmark_files()

        # 清理构建文件
        clean_build_files()

        logger.info("✅ 系统临时文件清理完成")
    except Exception as e:
        logger.error(f"❌ 清理系统临时文件失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
