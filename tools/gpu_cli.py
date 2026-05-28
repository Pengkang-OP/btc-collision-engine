#!/usr/bin/env python3
"""多GPU选择命令行工具.

提供GPU设备列表、选择和配置生成功能。

使用方法:
    # 列出所有GPU设备
    python tools/gpu_cli.py list

    # 自动选择最佳GPU
    python tools/gpu_cli.py auto

    # 测试多GPU模式
    python tools/gpu_cli.py test-multi

    # 生成配置文件
    python tools/gpu_cli.py generate-config --mode multi --output config.multi.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def cmd_list_devices(args):
    """列出所有GPU设备."""
    from src.gpu.selector import get_gpu_selector

    selector = get_gpu_selector()
    devices = selector.detect_all_devices(force_refresh=True)

    if not devices:
        print("❌ 未检测到GPU设备")
        print("\n请检查:")
        print("  1. GPU驱动是否正确安装")
        print("  2. pyopencl是否安装: pip install pyopencl")
        print("  3. GPU是否支持OpenCL")
        return 1

    # 打印设备列表
    print(selector.format_all_devices(devices))

    return 0


def cmd_auto_select(args):
    """自动选择最佳GPU."""
    from src.gpu.selector import get_gpu_selector

    selector = get_gpu_selector()
    best_device = selector.select_best_device()

    if not best_device:
        print("❌ 未找到可用GPU")
        return 1

    print("✅ 自动选择最佳GPU:")
    print(selector.format_device_info(best_device, detailed=True))

    # 生成配置建议
    from src.gpu.auto_config import get_gpu_configurator

    configurator = get_gpu_configurator()
    config = configurator.configure_for_device(best_device)

    print("\n" + configurator.get_config_summary(config))

    return 0


def cmd_test_multi(args):
    """测试多GPU模式."""
    from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine
    from src.gpu.selector import get_gpu_selector

    selector = get_gpu_selector()
    devices = selector.detect_all_devices()

    if not devices:
        print("❌ 未检测到GPU设备")
        return 1

    if len(devices) < 2:
        print(f"⚠️  仅检测到 {len(devices)} 个GPU,多GPU模式需要至少2个GPU")
        print("但可以测试单GPU功能:")
        device_count = 1
    else:
        device_count = min(len(devices), args.gpu_count)

    print(f"🚀 测试多GPU模式: {device_count}个GPU")
    print(f"   GPU列表: {[d['name'] for d in devices[:device_count]]}")

    # 创建多GPU引擎
    engine = MultiGPUCollisionEngine()

    # 初始化
    if not engine.initialize(device_count=device_count, strategy="performance"):
        print("❌ 多GPU引擎初始化失败")
        return 1

    print("✅ 多GPU引擎初始化成功")

    # 显示设备信息
    for device in engine.get_devices():
        print(f"\n  GPU {device['global_index']}: {device['name']}")
        print(f"    显存: {device['global_mem_gb']:.2f} GB")
        print(f"    评分: {device['score']:.1f}")

    # 显示负载均衡
    balancer = engine.get_load_balancer()
    if balancer:
        weights = balancer.calculate_weights()
        print("\n📊 负载分配:")
        for idx, weight in weights.items():
            print(f"  GPU {idx}: {weight:.1%}")

    print("\n✅ 多GPU测试通过!")

    # 清理
    engine.cleanup()

    return 0


def cmd_generate_config(args):
    """生成配置文件."""
    from src.gpu.selector import get_gpu_selector

    selector = get_gpu_selector()
    devices = selector.detect_all_devices()

    if not devices:
        print("❌ 未检测到GPU设备")
        return 1

    # 生成简单配置 (config_validator 模块已移除)
    config = {
        "mode": args.mode if hasattr(args, "mode") else "single",
        "device_indices": [d["global_index"] for d in devices],
    }

    # 添加元数据
    config["_metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "device_count": len(devices),
        "devices": [
            {
                "index": d["global_index"],
                "name": d["name"],
                "vendor": d["vendor"],
                "memory_gb": d["global_mem_gb"],
            }
            for d in devices
        ],
    }

    # 输出配置
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ 配置文件已生成: {output_path}")
    print("\n配置内容:")
    print(json.dumps(config, indent=2, ensure_ascii=False))

    # 验证配置 (config_validator 模块已移除，跳过验证)
    # print("\n" + validator.format_validation_report(config, devices))

    return 0


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="BTC碰撞引擎 - 多GPU选择工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有GPU
  python gpu_cli.py list

  # 自动选择最佳GPU
  python gpu_cli.py auto

  # 测试多GPU模式
  python gpu_cli.py test-multi --gpu-count 2

  # 生成多GPU配置
  python gpu_cli.py generate-config --mode multi --output config.multi.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # list命令
    list_parser = subparsers.add_parser("list", help="列出所有GPU设备")
    list_parser.set_defaults(func=cmd_list_devices)

    # auto命令
    auto_parser = subparsers.add_parser("auto", help="自动选择最佳GPU")
    auto_parser.set_defaults(func=cmd_auto_select)

    # test-multi命令
    test_parser = subparsers.add_parser("test-multi", help="测试多GPU模式")
    test_parser.add_argument("--gpu-count", type=int, default=2, help="测试的GPU数量(默认2)")
    test_parser.set_defaults(func=cmd_test_multi)

    # generate-config命令
    gen_parser = subparsers.add_parser("generate-config", help="生成配置文件")
    gen_parser.add_argument(
        "--mode",
        choices=["auto", "single", "multi"],
        default="auto",
        help="GPU模式(默认auto)",
    )
    gen_parser.add_argument(
        "--output",
        default="config.gpu.json",
        help="输出文件路径(默认config.gpu.json)",
    )
    gen_parser.set_defaults(func=cmd_generate_config)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    try:
        return args.func(args)
    except Exception as e:
        print(f"❌ 命令执行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
