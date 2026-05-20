#!/usr/bin/env python3
"""
缓存清理脚本

此脚本用于清理系统中的缓存数据，包括编译后的内核、设备信息、临时文件等。
"""

import glob
import os
import shutil
import sys
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import get_configured_logger, init_logging  # noqa: E402

# 配置日志
init_logging()
logger = get_configured_logger("CacheCleanup")


def clean_compiled_kernels():
    """清理编译后的内核"""
    logger.info("开始清理编译后的内核...")

    # 清理编译后的内核缓存
    kernel_cache_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "src", "gpu", "kernels", "cache"),
        os.path.join(os.path.dirname(__file__), "..", "src", "gpu", "kernels", "compiled"),
    ]

    for dir_path in kernel_cache_dirs:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                logger.info(f"清理编译后的内核缓存: {dir_path}")
            except Exception as e:
                logger.warning(f"清理编译后的内核缓存失败: {e}")


def clean_device_info():
    """清理设备信息"""
    logger.info("开始清理设备信息...")

    # 清理设备信息缓存
    device_info_files = [
        os.path.join(os.path.dirname(__file__), "..", "src", "gpu", "profiles", "device_info.json"),
        os.path.join(
            os.path.dirname(__file__), "..", "src", "gpu", "profiles", "device_cache.json"
        ),
    ]

    for file_path in device_info_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"清理设备信息缓存: {file_path}")
            except Exception as e:
                logger.warning(f"清理设备信息缓存失败: {e}")


def clean_temporary_files():
    """清理临时文件"""
    logger.info("开始清理临时文件...")

    # 清理临时文件（仅清理 .tmp/.temp，日志仅清理超过 max_age 天的）
    max_age_days = 30  # 默认保留30天内的日志
    now = time.time()
    temp_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "*.tmp"),
        os.path.join(os.path.dirname(__file__), "..", "*.temp"),
    ]
    log_patterns = [
        os.path.join(os.path.dirname(__file__), "..", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "data_logs", "*.json"),
        os.path.join(os.path.dirname(__file__), "..", "test_results", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "test_results", "*.json"),
        os.path.join(os.path.dirname(__file__), "..", "tests", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "tests", "data_logs", "*.json"),
        os.path.join(os.path.dirname(__file__), "..", "src", "data_logs", "*.log"),
        os.path.join(os.path.dirname(__file__), "..", "src", "data_logs", "*.json"),
    ]

    for pattern in temp_patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
                logger.info(f"清理临时文件: {file_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

    # 日志/json 文件仅清理超过 max_age 天的，避免误删活跃数据
    age_threshold = max_age_days * 86400
    for pattern in log_patterns:
        for file_path in glob.glob(pattern):
            try:
                file_age = now - os.path.getmtime(file_path)
                if file_age > age_threshold:
                    os.remove(file_path)
                    logger.info(f"清理过期文件 ({file_age/86400:.0f}d): {file_path}")
            except Exception as e:
                logger.warning(f"清理日志文件失败: {e}")


def clean_pycache():
    """清理pycache目录"""
    logger.info("开始清理pycache目录...")

    # 清理pycache目录
    for root, dirs, _files in os.walk(os.path.join(os.path.dirname(__file__), "..")):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                dir_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(dir_path)
                    logger.info(f"清理pycache目录: {dir_path}")
                except Exception as e:
                    logger.warning(f"清理pycache目录失败: {e}")


def clean_benchmark_results():
    """清理基准测试结果"""
    logger.info("开始清理基准测试结果...")

    # 清理基准测试结果
    benchmark_results_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results")
    if os.path.exists(benchmark_results_dir):
        for file_path in os.listdir(benchmark_results_dir):
            file_path = os.path.join(benchmark_results_dir, file_path)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"清理基准测试结果: {file_path}")
                except Exception as e:
                    logger.warning(f"清理基准测试结果失败: {e}")


def clean_test_matches():
    """清理测试匹配结果"""
    logger.info("开始清理测试匹配结果...")

    # 清理测试匹配结果
    test_matches_dir = os.path.join(os.path.dirname(__file__), "..", "test_matches")
    if os.path.exists(test_matches_dir):
        for file_path in os.listdir(test_matches_dir):
            file_path = os.path.join(test_matches_dir, file_path)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"清理测试匹配结果: {file_path}")
                except Exception as e:
                    logger.warning(f"清理测试匹配结果失败: {e}")


def main():
    """主函数"""
    try:
        logger.info("开始清理系统缓存数据...")

        # 清理编译后的内核
        clean_compiled_kernels()

        # 清理设备信息
        clean_device_info()

        # 清理临时文件
        clean_temporary_files()

        # 清理pycache目录
        clean_pycache()

        # 清理基准测试结果
        clean_benchmark_results()

        # 清理测试匹配结果
        clean_test_matches()

        logger.info("✅ 系统缓存数据清理完成")
    except Exception as e:
        logger.error(f"❌ 清理系统缓存数据失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
