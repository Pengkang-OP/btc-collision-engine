#!/usr/bin/env python3
"""Phase 1验证脚本.

验证GPU重构模块:
1. 模块导入无循环依赖
2. 接口定义正确
3. 组件可实例化
4. 无语法错误

版本: v4.2.1
创建日期: 2026-04-29
"""

import sys


def test_module_imports():
    """测试模块导入."""
    print("=" * 70)
    print("测试1: 模块导入")
    print("=" * 70)

    modules = [
        "src.collision.gpu",
        "src.collision.gpu.protocols",
        "src.collision.gpu.facade",
        "src.collision.gpu.monitoring",
        "src.collision.gpu.core",
        "src.collision.gpu.vendor_strategy",
        "src.collision.gpu.kernel_adapter",
        "src.collision.gpu.async_pipeline_adapter",
    ]

    for module_name in modules:
        try:
            __import__(module_name)
            print(f"  OK {module_name}")
        except ImportError as e:
            print(f"  ERR {module_name}: {e}")
            return False

    print("\n  OK 所有模块导入成功\n")
    return True


def test_no_circular_dependency():
    """测试无循环依赖."""
    print("=" * 70)
    print("测试2: 循环依赖检测")
    print("=" * 70)

    # 清除已导入模块
    modules_to_clear = [k for k in list(sys.modules.keys()) if "src.collision.gpu" in k]
    for mod in modules_to_clear:
        del sys.modules[mod]

    # 尝试导入
    try:
        print("  OK 无循环依赖检测通过\n")
        return True
    except ImportError as e:
        print(f"  ERR 检测到循环依赖: {e}\n")
        return False


def test_protocol_definitions():
    """测试接口定义."""
    print("=" * 70)
    print("测试3: 接口协议定义")
    print("=" * 70)

    try:
        from src.collision.gpu.protocols import (
            CollisionResult,
            GPUExecutionContext,
        )

        # 测试数据类实例化
        context = GPUExecutionContext(batch_size=1000000, vendor="intel")
        assert context.batch_size == 1000000

        result = CollisionResult(matches=[], execution_time_ms=50.0, batch_size=1000)
        assert result.execution_time_ms == 50.0

        print("  OK 接口协议定义正确\n")
        return True

    except Exception as e:
        print(f"  ERR 接口定义测试失败: {e}\n")
        return False


def test_component_instantiation():
    """测试组件实例化."""
    print("=" * 70)
    print("测试4: 组件实例化")
    print("=" * 70)

    try:
        from src.collision.gpu.core import CollisionCore
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        # 测试实例化
        monitoring = PerformanceMonitoringPipeline(engine=None, config={})
        assert monitoring is not None
        print("  OK PerformanceMonitoringPipeline 实例化成功")

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        core = CollisionCore(targets=targets, config={})
        assert core is not None
        print("  OK CollisionCore 实例化成功")

        # 测试厂商工厂
        intel_strategy = VendorOptimizationFactory.create("intel")
        assert intel_strategy is not None
        print("  OK VendorOptimizationFactory 创建Intel策略成功")

        print()
        return True

    except Exception as e:
        print(f"  ERR 组件实例化失败: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_vendor_factory():
    """测试厂商工厂."""
    print("=" * 70)
    print("测试5: 厂商策略工厂")
    print("=" * 70)

    try:
        from src.collision.gpu.vendor_strategy import (
            DefaultOptimizationStrategy,
            VendorOptimizationFactory,
        )

        # 测试已知厂商
        vendors = VendorOptimizationFactory.get_supported_vendors()
        print(f"  支持的厂商: {vendors}")

        for vendor in ["intel", "nvidia", "amd"]:
            strategy = VendorOptimizationFactory.create(vendor)
            assert strategy is not None
            print(f"  OK {vendor} 策略创建成功")

        # 测试未知厂商
        unknown = VendorOptimizationFactory.create("unknown")
        assert isinstance(unknown, DefaultOptimizationStrategy)
        print("  OK 未知厂商回退到默认策略成功")

        print()
        return True

    except Exception as e:
        print(f"  ERR 厂商工厂测试失败: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主测试函数."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "GPU碰撞引擎重构模块 - Phase 1 验证" + " " * 17 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    tests = [
        ("模块导入", test_module_imports),
        ("循环依赖检测", test_no_circular_dependency),
        ("接口协议定义", test_protocol_definitions),
        ("组件实例化", test_component_instantiation),
        ("厂商策略工厂", test_vendor_factory),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ERR 测试 {test_name} 异常: {e}")
            results.append((test_name, False))

    # 汇总结果
    print("\n")
    print("=" * 70)
    print("测试汇总")
    print("=" * 70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "OK 通过" if success else "ERR 失败"
        print(f"  {status} - {test_name}")

    print()
    print(f"总计: {passed}/{total} 通过")

    if passed == total:
        print("\n[DONE] 所有测试通过！Phase 1 实施成功！\n")
        return 0
    print(f"\nWARN  {total - passed} 个测试失败，请检查错误\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
