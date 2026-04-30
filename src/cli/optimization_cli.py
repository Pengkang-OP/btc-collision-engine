"""优化设置命令行工具

提供命令行接口管理各项优化功能的启用/禁用。
"""

import argparse
from ..config.optimization_config import (
    get_optimization_config,
    enable_feature,
    disable_feature,
    is_feature_enabled,
)


def print_settings() -> None:
    """打印当前设置"""
    config = get_optimization_config()
    all_config = config.get_all()

    print("=" * 60)
    print("              优化设置")
    print("=" * 60)
    print()

    # 功能开关
    print("功能开关:")
    features = [
        ("delta_stats", "增量统计优化", "减少锁竞争，提升并发性能"),
        ("distributed_aggregator", "分布式统计聚合", "支持大规模GPU集群"),
        ("performance_monitor", "性能监控", "实时监控统计系统性能"),
    ]

    for feature, name, desc in features:
        status = "✅ 启用" if is_feature_enabled(feature) else "❌ 禁用"
        print(f"  {name}:")
        print(f"    状态: {status}")
        print(f"    描述: {desc}")
        print()

    # 配置参数
    print("配置参数:")
    params = [
        ("delta_stats_flush_interval", "增量统计刷新间隔(秒)"),
        ("aggregator_interval", "分布式聚合间隔(秒)"),
        ("monitor_interval", "性能监控间隔(秒)"),
    ]

    for param, desc in params:
        value = all_config.get(param)
        print(f"  {desc}: {value}")

    print()
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="优化设置管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python -m src.cli.optimization_cli                 # 查看当前设置
  python -m src.cli.optimization_cli --enable delta_stats
  python -m src.cli.optimization_cli --disable performance_monitor
  python -m src.cli.optimization_cli --list
        """,
    )

    parser.add_argument(
        "--enable",
        choices=["delta_stats", "distributed_aggregator", "performance_monitor"],
        help="启用指定的优化功能",
    )

    parser.add_argument(
        "--disable",
        choices=["delta_stats", "distributed_aggregator", "performance_monitor"],
        help="禁用指定的优化功能",
    )

    parser.add_argument("--list", action="store_true", help="列出所有可用的优化功能")

    args = parser.parse_args()

    if args.enable:
        enable_feature(args.enable)
        print(f"已启用: {args.enable}")

    elif args.disable:
        disable_feature(args.disable)
        print(f"已禁用: {args.disable}")

    elif args.list:
        features = [
            ("delta_stats", "增量统计优化", "减少锁竞争，提升并发性能"),
            ("distributed_aggregator", "分布式统计聚合", "支持大规模GPU集群"),
            ("performance_monitor", "性能监控", "实时监控统计系统性能"),
        ]

        print("可用的优化功能:")
        print("-" * 50)
        for feature, name, desc in features:
            print(f"\n{feature}:")
            print(f"  名称: {name}")
            print(f"  描述: {desc}")

    else:
        print_settings()


if __name__ == "__main__":
    main()
