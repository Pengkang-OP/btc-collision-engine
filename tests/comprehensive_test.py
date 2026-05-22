#!/usr/bin/env python3
"""深度全面测试脚本

执行系统的深度全面测试，包括：
1. 功能测试：验证基本功能
2. 性能测试：不同配置下的性能表现
3. 稳定性测试：长时间运行稳定性
4. 边界测试：各种边界条件
5. 错误处理测试：错误处理能力
测试结果将生成详细的测试报告。
"""

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

# 添加项目根目录到Python模块路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine  # noqa: E402

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ComprehensiveTest:
    """全面测试套件"""

    def __init__(self):
        """初始化测试类"""
        self.test_results = []
        self.start_time = None
        self.end_time = None

    def generate_test_targets(self, count: int = 100) -> set[str]:
        """生成测试目标地址

        Args:
            count: 目标地址数量

        Returns:
            目标地址集合
        """
        # 使用格式正确的比特币地址作为测试目标
        sample_addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            "1N5czHm9q7wSjzM7X4GCe4yi7z14L9tK8",
            "1M8s2S5bgAzSSzVTeL7zruvMPLvzSkEAuv",
            "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvM",
        ]

        targets = set()
        for i in range(count):
            address = sample_addresses[i % len(sample_addresses)]
            targets.add(address)

        return targets

    def run_test(self, test_name: str, test_func):
        """运行单个测试

        Args:
            test_name: 测试名称
            test_func: 测试函数
        """
        logger.info(f"开始测试: {test_name}")
        start_time = time.time()

        try:
            result = test_func()
            duration = time.time() - start_time

            test_result = {
                "name": test_name,
                "status": "pass",
                "duration": duration,
                "result": result,
            }
            logger.info(f"测试通过: {test_name} (耗时: {duration:.2f}秒)")

        except Exception as e:
            duration = time.time() - start_time

            test_result = {
                "name": test_name,
                "status": "fail",
                "duration": duration,
                "error": str(e),
            }
            logger.error(f"测试失败: {test_name} (耗时: {duration:.2f}秒) - 错误: {e}")

        self.test_results.append(test_result)
        return test_result

    def test_basic_functionality(self):
        """测试基本功能"""
        targets = self.generate_test_targets(10)

        engine = MultiGPUCollisionEngine({"enable_async_execution": True})

        # 初始化引擎
        if not engine.initialize(device_count=1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        # 启动碰撞
        if not engine.start(targets=targets, mode="random", total_keys=100000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行一小段时间
        time.sleep(5)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()

        # 清理资源
        engine.cleanup()

        return stats

    def test_multi_gpu_functionality(self):
        """测试多GPU功能"""
        targets = self.generate_test_targets(10)

        engine = MultiGPUCollisionEngine({"enable_async_execution": True, "auto_rebalance": True})

        # 初始化引擎，使用所有可用GPU
        if not engine.initialize(device_count=-1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        # 启动碰撞
        if not engine.start(targets=targets, mode="random", total_keys=500000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行一小段时间
        time.sleep(10)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()

        # 清理资源
        engine.cleanup()

        return stats

    def test_performance_variations(self):
        """测试不同配置下的性能变化"""
        targets = self.generate_test_targets(10)

        # 测试不同批次大小
        batch_sizes = [65536, 131072, 262144]
        results = []

        for batch_size in batch_sizes:
            engine = MultiGPUCollisionEngine(
                {
                    "enable_async_execution": True,
                    "per_device_config": {"0": {"batch_size": batch_size}},
                }
            )

            if not engine.initialize(device_count=1):
                try:
                    engine.cleanup()
                except (OSError, RuntimeError) as e:
                    logger.debug(f"GPU清理失败（非致命）: {e}")
                raise Exception(f"引擎初始化失败(批次大小: {batch_size})")

            if not engine.start(targets=targets, mode="random", total_keys=200000):
                try:
                    engine.cleanup()
                except (OSError, RuntimeError) as e:
                    logger.debug(f"GPU清理失败（非致命）: {e}")
                raise Exception(f"引擎启动失败 (批次大小: {batch_size})")

            # 运行一小段时间
            time.sleep(5)

            # 停止引擎
            engine.stop()

            # 获取统计信息
            stats = engine.get_combined_stats()
            results.append({"batch_size": batch_size, "throughput": stats.get("combined_throughput", 0)})

            # 清理资源
            engine.cleanup()

        return results

    def test_stability(self):
        """测试系统稳定性"""
        targets = self.generate_test_targets(10)

        engine = MultiGPUCollisionEngine(
            {"enable_async_execution": True, "workload_monitor_interval": 2}
        )

        if not engine.initialize(device_count=1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        if not engine.start(targets=targets, mode="random", total_keys=1000000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行较长时间
        time.sleep(30)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()

        # 清理资源
        engine.cleanup()

        return stats

    def test_boundary_conditions(self):
        """测试边界条件"""
        # 测试最小目标数量
        min_targets = set(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])

        engine = MultiGPUCollisionEngine({"enable_async_execution": True})

        if not engine.initialize(device_count=1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        if not engine.start(targets=min_targets, mode="random", total_keys=50000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行一小段时间
        time.sleep(3)

        # 停止引擎
        engine.stop()

        # 清理资源
        engine.cleanup()

        return "边界条件测试通过"

    def test_error_handling(self):
        """测试错误处理能力"""
        # 测试空目标集合
        empty_targets = set()

        engine = MultiGPUCollisionEngine({"enable_async_execution": True})

        if not engine.initialize(device_count=1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        # 启动应该失败，但系统应该能正常处理
        try:
            engine.start(targets=empty_targets, mode="random", total_keys=50000)
        except Exception as e:
            logger.info(f"预期的错误: {e}")
        finally:
            engine.stop()
            engine.cleanup()

        return "错误处理测试通过"

    def test_memory_management(self):
        """测试内存管理"""
        targets = self.generate_test_targets(10)

        engine = MultiGPUCollisionEngine(
            {"enable_async_execution": True, "total_pool_mb": 256}  # 较小的内存池，测试内存管理
        )

        if not engine.initialize(device_count=1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        if not engine.start(targets=targets, mode="random", total_keys=300000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行一小段时间
        time.sleep(15)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()

        # 清理资源
        engine.cleanup()

        return stats

    def test_load_balancing(self):
        """测试负载均衡"""
        targets = self.generate_test_targets(10)

        engine = MultiGPUCollisionEngine(
            {"enable_async_execution": True, "auto_rebalance": True, "workload_monitor_interval": 2}
        )

        # 初始化引擎，使用所有可用GPU
        if not engine.initialize(device_count=-1):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎初始化失败")

        if not engine.start(targets=targets, mode="random", total_keys=1000000):
            try:
                engine.cleanup()
            except (OSError, RuntimeError) as e:
                logger.debug(f"GPU清理失败（非致命）: {e}")
            raise Exception("引擎启动失败")

        # 运行一段时间，让负载均衡器工作
        time.sleep(20)

        # 停止引擎
        engine.stop()

        # 获取统计信息
        stats = engine.get_combined_stats()
        workload_stats = engine.get_workload_stats()

        # 清理资源
        engine.cleanup()

        return {"performance_stats": stats, "workload_stats": workload_stats}

    def run_all_tests(self):
        """运行所有测试"""
        self.start_time = time.time()
        logger.info("开始深度全面测试...")

        # 运行各个测试
        tests = [
            ("基本功能测试", self.test_basic_functionality),
            ("多GPU功能测试", self.test_multi_gpu_functionality),
            ("性能变化测试", self.test_performance_variations),
            ("稳定性测试", self.test_stability),
            ("边界条件测试", self.test_boundary_conditions),
            ("错误处理测试", self.test_error_handling),
            ("内存管理测试", self.test_memory_management),
            ("负载均衡测试", self.test_load_balancing),
        ]

        for test_name, test_func in tests:
            self.run_test(test_name, test_func)

        self.end_time = time.time()
        logger.info("深度全面测试完成")

        # 生成测试报告
        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        total_time = self.end_time - self.start_time if self.end_time else 0
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "pass")
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0

        report = f"""# 深度全面测试报告

## 测试摘要
- 测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
- 总测试时间: {total_time:.2f}秒
- 总测试数: {total_tests}
- 通过测试数: {passed_tests}
- 失败测试数: {failed_tests}
- 测试通过率: {pass_rate:.1f}%

## 详细测试结果
"""

        for result in self.test_results:
            status = "[PASS]" if result["status"] == "pass" else "[FAIL]"
            report += f"\n### {result['name']}\n"
            report += f"状态: {status}\n"
            report += f"耗时: {result['duration']:.2f}秒\n"

            if result["status"] == "pass":
                if "result" in result:
                    report += f"结果: {result['result']}\n"
            else:
                if "error" in result:
                    report += f"错误: {result['error']}\n"

        # 保存测试报告
        report_path = os.path.join(os.path.dirname(__file__), "test_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"测试报告已生成: {report_path}")

        # 打印测试摘要
        logger.info("测试摘要:")
        logger.info(f"- 总测试时间: {total_time:.2f}秒")
        logger.info(f"- 总测试数: {total_tests}")
        logger.info(f"- 通过测试数: {passed_tests}")
        logger.info(f"- 失败测试数: {failed_tests}")
        logger.info(f"- 测试通过率: {pass_rate:.1f}%")


def main():
    """主测试函数"""
    test = ComprehensiveTest()
    test.run_all_tests()


if __name__ == "__main__":
    main()
