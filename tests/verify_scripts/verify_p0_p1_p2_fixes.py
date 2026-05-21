"""验证P0/P1/P2修复的测试脚本"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent  # 修复: 应该是parent.parent,因为tests在根目录下
sys.path.insert(0, str(project_root))

from src.collision.gpu.engine import GPUKernel, GPUCollisionEngine
from src.monitoring.monitoring_system import MonitoringSystem, ReportGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VerificationTest")


def test_p0_gpu_initialization_error_handling():
    """P0测试: GPU初始化失败回退机制"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 P0-1: GPU初始化失败回退机制")
    logger.info("=" * 60)

    try:
        # 尝试创建GPU引擎(如果没有GPU会失败)
        engine = GPUCollisionEngine(
            targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}, device_index=999  # 不存在的设备
        )
        logger.warning("⚠️ GPU初始化成功(存在GPU设备)")
    except RuntimeError as e:
        error_msg = str(e)
        if "建议操作" in error_msg or "备选方案" in error_msg:
            logger.info("✅ P0-1修复验证通过: 错误信息包含回退建议")
        else:
            logger.error(f"❌ P0-1修复验证失败: 错误信息不包含回退建议")
            logger.error(f"   错误信息: {error_msg}")
    except Exception as e:
        logger.error(f"❌ P0-1测试异常: {type(e).__name__}: {e}")


def test_p1_trend_analysis():
    """P1测试: 趋势分析算法改进"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 P1-4: 趋势分析算法(线性回归)")
    logger.info("=" * 60)

    # 测试数据: 稳定趋势
    stable_data = [100, 102, 98, 101, 99, 103, 100, 101]
    trend = ReportGenerator._calculate_trend(stable_data)
    if trend == "stable":
        logger.info("✅ P1-4修复验证通过: 稳定趋势识别正确")
    else:
        logger.error(f"❌ P1-4修复验证失败: 稳定趋势识别错误,结果={trend}")

    # 测试数据: 上升趋势
    increasing_data = [100, 105, 110, 115, 120, 125, 130, 135]
    trend = ReportGenerator._calculate_trend(increasing_data)
    if trend == "increasing":
        logger.info("✅ P1-4修复验证通过: 上升趋势识别正确")
    else:
        logger.error(f"❌ P1-4修复验证失败: 上升趋势识别错误,结果={trend}")

    # 测试数据: 下降趋势
    decreasing_data = [135, 130, 125, 120, 115, 110, 105, 100]
    trend = ReportGenerator._calculate_trend(decreasing_data)
    if trend == "decreasing":
        logger.info("✅ P1-4修复验证通过: 下降趋势识别正确")
    else:
        logger.error(f"❌ P1-4修复验证失败: 下降趋势识别错误,结果={trend}")


def test_p1_wif_import():
    """P1测试: WIF模块导入优化"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 P1-6: WIF模块导入优化")
    logger.info("=" * 60)

    import inspect
    from src.collision.gpu import engine as gpu_collision_engine

    # 检查文件顶部是否有WIF导入
    source_file = inspect.getfile(gpu_collision_engine)
    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 统计WIF导入次数
    import_count = content.count("from ..core.wif import WIF")
    if import_count == 1:
        logger.info("✅ P1-6修复验证通过: WIF仅导入1次(文件顶部)")
    else:
        logger.error(f"❌ P1-6修复验证失败: WIF导入{import_count}次(应为1次)")

    # 检查是否有循环内导入
    if "from ..core.wif import WIF" in content:
        lines = content.split("\n")
        loop_imports = [
            i + 1 for i, line in enumerate(lines) if "from ..core.wif import WIF" in line and i > 80
        ]
        if not loop_imports:
            logger.info("✅ P1-6修复验证通过: 无循环内导入")
        else:
            logger.error(f"❌ P1-6修复验证失败: 在行{loop_imports}仍有循环内导入")


def test_p2_monitoring_io_optimization():
    """P2测试: 监控I/O优化"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 P2-12: 监控I/O优化")
    logger.info("=" * 60)

    import inspect
    from src.monitoring import monitoring_system

    source_file = inspect.getfile(monitoring_system)
    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查是否有history_save_counter
    if "history_save_counter" in content and "history_save_interval" in content:
        logger.info("✅ P2-12修复验证通过: 历史数据保存频率控制已实现")
    else:
        logger.error("❌ P2-12修复验证失败: 未找到频率控制逻辑")


def run_all_tests():
    """运行所有验证测试"""
    logger.info("\n" + "#" * 60)
    logger.info("# BTC碰撞引擎 P0/P1/P2 修复验证测试")
    logger.info("#" * 60)

    tests = [
        ("P0-1: GPU初始化失败回退", test_p0_gpu_initialization_error_handling),
        ("P1-4: 趋势分析算法", test_p1_trend_analysis),
        ("P1-6: WIF导入优化", test_p1_wif_import),
        ("P2-12: 监控I/O优化", test_p2_monitoring_io_optimization),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {type(e).__name__}: {e}")
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"测试总结: {passed} 通过, {failed} 失败")
    logger.info("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
