#!/usr/bin/env python3
"""GPU加速模式性能验证测试.

对比CPU和GPU模式的性能差异，验证GPU加速效果。
测试内容：
- CPU模式基准性能
- GPU模式加速性能
- 性能提升倍数
- 监控数据记录
"""

import logging
import os
import time
from typing import Any

import pytest

pytestmark = pytest.mark.gpu

import pathlib

from src.collision.collision_stats import CollisionStats
from src.collision.gpu.engine import GPUCollisionEngine
from src.collision.key_collision_engine import KeyCollisionEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GPUPerformanceTest")


class GPUPerformanceBenchmark:
    """GPU性能对比测试类."""

    def __init__(self):
        self.cpu_stats = None
        self.gpu_stats = None
        self.cpu_time = 0
        self.gpu_time = 0

    def test_cpu_mode(self, targets: set, duration: int = 10) -> dict[str, Any]:
        """测试CPU模式性能.

        Args:
            targets: 目标地址集合
            duration: 测试时长（秒）

        Returns:
            性能统计数据

        """
        logger.info("=" * 70)
        logger.info("[BLUE] 开始CPU模式性能测试")
        logger.info("=" * 70)
        logger.info(f"目标地址数: {len(targets)}")
        logger.info("测试时长: %s秒", duration)

        stats_data = {"total_checked": 0, "speed": 0.0, "elapsed": 0.0, "matches": 0}

        def on_progress(stats: CollisionStats):
            stats_data["total_checked"] = stats.total_checked
            stats_data["speed"] = stats.speed
            stats_data["elapsed"] = stats.elapsed  # 修复: 使用elapsed而非elapsed_time
            stats_data["matches"] = len(stats.matches)

        def on_match(private_key: bytes, address: str, wif: str):
            logger.info("TARGET 发现匹配: %s", address)

        try:
            # 创建CPU引擎
            engine = KeyCollisionEngine(
                targets=targets,
                on_progress=on_progress,
                on_match=on_match,
                checkpoint_enabled=False,
                dedup_enabled=False,
                data_logging_enabled=True,
                data_logging_interval=1,
                use_enhanced_monitoring=True,
            )

            logger.info("OK CPU引擎初始化完成")
            logger.info(f"   加密后端: {type(engine.generator).__name__}")
            logger.info("   工作线程: 默认(CPU核心数)")

            # 启动引擎（brute_force模式，从1开始）
            engine.start(mode="brute_force")

            # 运行指定时长
            start_time = time.time()
            try:
                while (time.time() - start_time) < duration:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\n收到中断信号")
            finally:
                engine.stop()

            self.cpu_time = time.time() - start_time
            self.cpu_stats = stats_data

            logger.info("\nSTATS CPU模式测试结果:")
            logger.info(f"   总检测数: {stats_data['total_checked']:,}")
            logger.info(f"   平均速度: {stats_data['speed']:.2f} keys/s")
            logger.info(f"   运行时间: {self.cpu_time:.2f}秒")
            logger.info(f"   匹配数: {stats_data['matches']}")

            return stats_data

        except Exception as e:
            logger.error("ERR CPU模式测试失败: %s", e)
            import traceback

            traceback.print_exc()
            return stats_data

    def test_gpu_mode(self, targets: set, duration: int = 10) -> dict[str, Any]:
        """测试GPU模式性能.

        Args:
            targets: 目标地址集合
            duration: 测试时长（秒）

        Returns:
            性能统计数据

        """
        logger.info("\n" + "=" * 70)
        logger.info("GREEN 开始GPU模式性能测试")
        logger.info("=" * 70)
        logger.info(f"目标地址数: {len(targets)}")
        logger.info("测试时长: %s秒", duration)

        stats_data = {"total_checked": 0, "speed": 0.0, "elapsed": 0.0, "matches": 0}

        def on_progress(stats: CollisionStats):
            stats_data["total_checked"] = stats.total_checked
            stats_data["speed"] = stats.speed
            stats_data["elapsed"] = stats.elapsed  # 修复: 使用elapsed而非elapsed_time
            stats_data["matches"] = len(stats.matches)

        def on_match(private_key: bytes, address: str, wif: str):
            logger.info("TARGET 发现匹配: %s", address)

        try:
            # 检查GPU可用性
            try:
                import pyopencl as cl

                platforms = cl.get_platforms()
                gpu_devices = []
                for platform in platforms:
                    devices = platform.get_devices(device_type=cl.device_type.GPU)
                    gpu_devices.extend(devices)

                if not gpu_devices:
                    logger.warning("WARN 未检测到GPU设备，跳过GPU测试")
                    return stats_data

                logger.info(f"OK 检测到 {len(gpu_devices)} 个GPU设备")
                for i, dev in enumerate(gpu_devices):
                    logger.info(f"   GPU {i}: {dev.name} ({dev.vendor})")

            except ImportError:
                logger.warning("WARN PyOpenCL未安装，跳过GPU测试")
                return stats_data
            except Exception as e:
                logger.warning("WARN GPU检测失败: %s，跳过GPU测试", e)
                return stats_data

            # 创建GPU引擎
            engine = GPUCollisionEngine(
                targets=targets,
                device_index=-1,  # 自动选择
                batch_size=65536,
                on_progress=on_progress,
                on_match=on_match,
                checkpoint_enabled=False,
                dedup_enabled=False,
                data_logging_enabled=True,
                data_logging_interval=1,
                use_enhanced_monitoring=True,
            )

            logger.info("OK GPU引擎初始化完成")
            logger.info(f"   设备: {engine._gpu_device.get_device_info().get('name', 'Unknown')}")
            logger.info(f"   Batch Size: {engine.batch_size}")

            # 启动引擎（brute_force模式）
            engine.start(mode="brute_force")

            # 运行指定时长
            start_time = time.time()
            try:
                while (time.time() - start_time) < duration:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\n收到中断信号")
            finally:
                engine.stop()

            self.gpu_time = time.time() - start_time
            self.gpu_stats = stats_data

            logger.info("\nSTATS GPU模式测试结果:")
            logger.info(f"   总检测数: {stats_data['total_checked']:,}")
            logger.info(f"   平均速度: {stats_data['speed']:.2f} keys/s")
            logger.info(f"   运行时间: {self.gpu_time:.2f}秒")
            logger.info(f"   匹配数: {stats_data['matches']}")

            return stats_data

        except Exception as e:
            logger.error("ERR GPU模式测试失败: %s", e)
            import traceback

            traceback.print_exc()
            return stats_data

    def print_comparison_report(self):
        """打印性能对比报告."""
        logger.info("\n" + "=" * 70)
        logger.info("UP GPU加速性能对比报告")
        logger.info("=" * 70)

        if self.cpu_stats and self.cpu_stats["speed"] > 0:
            cpu_speed = self.cpu_stats["speed"]
            logger.info("\n[BLUE] CPU模式:")
            logger.info(f"   速度: {cpu_speed:,.2f} keys/s")
            logger.info(f"   检测数: {self.cpu_stats['total_checked']:,}")
            logger.info(f"   时间: {self.cpu_time:.2f}秒")

        if self.gpu_stats and self.gpu_stats["speed"] > 0:
            gpu_speed = self.gpu_stats["speed"]
            logger.info("\nGREEN GPU模式:")
            logger.info(f"   速度: {gpu_speed:,.2f} keys/s")
            logger.info(f"   检测数: {self.gpu_stats['total_checked']:,}")
            logger.info(f"   时间: {self.gpu_time:.2f}秒")

        if self.cpu_stats and self.gpu_stats:
            cpu_speed = self.cpu_stats.get("speed", 0)
            gpu_speed = self.gpu_stats.get("speed", 0)

            if cpu_speed > 0 and gpu_speed > 0:
                speedup = gpu_speed / cpu_speed
                improvement = ((gpu_speed - cpu_speed) / cpu_speed) * 100

                logger.info("\nFAST 性能提升:")
                logger.info(f"   加速倍数: {speedup:.2f}x")
                logger.info(f"   性能提升: {improvement:.1f}%")

                if speedup >= 10:
                    logger.info("   OK GPU加速效果显著!")
                elif speedup >= 2:
                    logger.info("   OK GPU加速效果良好")
                else:
                    logger.info("   WARN GPU加速效果一般，可能需要优化")

        logger.info("\n" + "=" * 70)


def create_test_targets() -> set:
    """创建测试目标地址."""
    # 使用多个测试地址
    test_addresses = {
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # 私钥=1
        "1EHNa6Q4Jz2uvNExL497mE43efXmU6aRq6",  # 私钥=2
    }

    logger.info(f"测试目标地址: {len(test_addresses)} 个")
    for addr in test_addresses:
        logger.info("   - %s", addr)

    return test_addresses


def main():
    """主函数."""
    logger.info("=" * 70)
    logger.info("FAST GPU加速模式性能验证测试")
    logger.info("=" * 70)
    logger.info(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 创建测试实例
    benchmark = GPUPerformanceBenchmark()

    # 创建测试目标
    targets = create_test_targets()

    # 测试时长（秒）
    test_duration = 15

    logger.info("\nTIP 测试策略:")
    logger.info("   - 先测试CPU模式 %s秒", test_duration)
    logger.info("   - 再测试GPU模式 %s秒", test_duration)
    logger.info("   - 对比性能差异")
    logger.info("   - 记录监控数据")

    time.sleep(2)

    # 1. 测试CPU模式
    cpu_stats = benchmark.test_cpu_mode(targets, duration=test_duration)  # noqa: F841

    # 等待2秒让系统稳定
    logger.info("\n[HOURGLASS] 等待系统稳定...")
    time.sleep(2)

    # 2. 测试GPU模式
    gpu_stats = benchmark.test_gpu_mode(targets, duration=test_duration)  # noqa: F841

    # 3. 打印对比报告
    benchmark.print_comparison_report()

    # 4. 验证监控数据
    logger.info("\n" + "=" * 70)
    logger.info("[CLIPBOARD] 验证监控数据")
    logger.info("=" * 70)

    data_logs_dir = "data_logs"
    files_to_check = [
        "current_data.json",
        "history_data.json",
        "performance.log",
    ]

    for filename in files_to_check:
        filepath = os.path.join(data_logs_dir, filename)
        if pathlib.Path(filepath).exists():
            size = pathlib.Path(filepath).stat().st_size
            logger.info(f"OK {filename}: {size:,} bytes")
        else:
            logger.warning("ERR %s: 不存在", filename)

    logger.info("\n" + "=" * 70)
    logger.info("OK GPU性能验证测试完成")
    logger.info("=" * 70)

    # 保存测试结果
    test_result = {
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_stats": benchmark.cpu_stats,
        "gpu_stats": benchmark.gpu_stats,
        "cpu_time": benchmark.cpu_time,
        "gpu_time": benchmark.gpu_time,
    }

    if benchmark.cpu_stats and benchmark.gpu_stats:
        cpu_speed = benchmark.cpu_stats.get("speed", 0)
        gpu_speed = benchmark.gpu_stats.get("speed", 0)
        if cpu_speed > 0:
            test_result["speedup"] = gpu_speed / cpu_speed

    result_file = os.path.join(data_logs_dir, "gpu_benchmark_result.json")
    import json

    with pathlib.Path(result_file).open("w", encoding="utf-8") as f:
        json.dump(test_result, f, indent=2, ensure_ascii=False)

    logger.info("[SAVE] 测试结果已保存: %s", result_file)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
