#!/usr/bin/env python3
"""测试监控和日志系统功能.

此脚本用于测试监控系统和日志系统的功能，确保它们与修改后的资源释放逻辑兼容。
"""

import time

from src.monitoring.monitoring_system import MonitoringSystem
from src.utils import get_configured_logger, init_logging

# 配置日志
init_logging()
logger = get_configured_logger("MonitoringLoggingTest")


def test_logging_system():
    """测试日志系统功能."""
    logger.info("开始测试日志系统功能")

    # 测试不同级别的日志
    logger.debug("这是一条DEBUG级别的日志")
    logger.info("这是一条INFO级别的日志")
    logger.warning("这是一条WARNING级别的日志")
    logger.error("这是一条ERROR级别的日志")
    logger.critical("这是一条CRITICAL级别的日志")

    # 测试异常日志
    try:
        1 / 0  # noqa: B018  # 有意触发 ZeroDivisionError 测试异常日志
    except Exception as e:
        logger.exception("测试异常日志: %s", e)

    logger.info("日志系统测试完成")


def test_monitoring_system():
    """测试监控系统功能."""
    logger.info("开始测试监控系统功能")

    # 创建监控系统实例
    monitoring_system = MonitoringSystem()

    # 启动监控系统
    monitoring_system.start()
    logger.info("监控系统已启动")

    # 等待一段时间，让监控系统收集数据
    time.sleep(10)

    # 获取当前状态
    current_status = monitoring_system.get_current_status()
    logger.info("监控系统当前状态: %s", current_status)

    # 生成报告
    report = monitoring_system.generate_report()
    logger.info("监控系统报告: %s", report)

    # 停止监控系统
    monitoring_system.stop()
    logger.info("监控系统已停止")

    logger.info("监控系统测试完成")


def main():
    """主函数."""
    try:
        # 测试日志系统
        test_logging_system()

        # 测试监控系统
        test_monitoring_system()

        logger.info("OK 监控和日志系统测试成功")
    except Exception as e:
        logger.error("ERR 测试过程中出现错误: %s", e)
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
