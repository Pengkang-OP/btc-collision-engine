#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞工具 - 命令行界面

用法:
    python -m src.cli.main [选项]
    python key_collision_cli.py [选项]

示例:
    # 随机碰撞（无限运行）
    python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf -m random

    # 从文件加载目标，范围扫描
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFF

    # 启用断点续传和去重，运行60秒
    python key_collision_cli.py -t 1A1z... -m random --checkpoint --dedup --duration 60
"""

import argparse
import os
import signal
import sys
import time
import threading
from typing import Optional, Set

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.collision import KeyCollisionEngine, TargetResolver, CollisionStats
from src.utils import init_logging, get_configured_logger

init_logging()
logger = get_configured_logger("CLI")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog="key_collision_cli",
        description="比特币私钥对撞工具 - 命令行界面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  随机碰撞（持续运行直到 Ctrl+C）:
    python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random

  从文件加载目标地址，范围扫描:
    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF

  启用断点续传，运行120秒后自动停止:
    python key_collision_cli.py -t 1A1z... -m random --checkpoint --duration 120

  多线程暴力穷举，自定义进度显示间隔:
    python key_collision_cli.py -t 1A1z... -m brute_force --start 1 --workers 8 --progress-interval 10
        """
    )

    # 目标地址
    target_group = parser.add_argument_group("目标地址")
    target_ex = target_group.add_mutually_exclusive_group(required=True)
    target_ex.add_argument(
        "-t", "--targets",
        metavar="ADDRESS",
        nargs="+",
        help="目标比特币地址（可指定多个，空格分隔）"
    )
    target_ex.add_argument(
        "-f", "--file",
        metavar="FILE",
        help="从文件加载目标地址（每行一个，支持 # 注释）"
    )

    # 运行模式
    mode_group = parser.add_argument_group("碰撞模式")
    mode_group.add_argument(
        "-m", "--mode",
        choices=["random", "range", "brute_force"],
        default="random",
        help="碰撞模式: random=随机, range=范围扫描, brute_force=暴力穷举 (默认: random)"
    )
    mode_group.add_argument(
        "--start",
        metavar="HEX",
        help="范围起始私钥（十六进制，range/brute_force 模式必填）"
    )
    mode_group.add_argument(
        "--end",
        metavar="HEX",
        help="范围结束私钥（十六进制，range 模式必填）"
    )

    # 功能选项
    feature_group = parser.add_argument_group("功能选项")
    feature_group.add_argument(
        "--checkpoint",
        action="store_true",
        default=False,
        help="启用断点续传（程序中断后可从断点继续）"
    )
    feature_group.add_argument(
        "--checkpoint-interval",
        metavar="SECS",
        type=int,
        default=30,
        help="断点自动保存间隔（秒，默认: 30）"
    )
    feature_group.add_argument(
        "--dedup",
        action="store_true",
        default=False,
        help="启用去重过滤（避免重复检测相同私钥，仅 random 模式有效）"
    )
    feature_group.add_argument(
        "--dedup-max-size",
        metavar="N",
        type=int,
        default=1_000_000,
        help="去重过滤器最大容量（默认: 1000000）"
    )

    # 性能选项
    perf_group = parser.add_argument_group("性能选项")
    perf_group.add_argument(
        "--workers",
        metavar="N",
        type=int,
        default=None,
        help="工作线程数（默认: CPU 核数）"
    )
    perf_group.add_argument(
        "--duration",
        metavar="SECS",
        type=int,
        default=0,
        help="运行时长（秒），0 表示无限运行直到 Ctrl+C（默认: 0）"
    )
    perf_group.add_argument(
        "--progress-interval",
        metavar="SECS",
        type=float,
        default=5.0,
        help="进度显示间隔（秒，默认: 5）"
    )
    
    # v2.2.0 性能优化选项
    opt_group = parser.add_argument_group("v2.2.0 性能优化")
    opt_group.add_argument(
        "--no-optimize",
        action="store_true",
        default=False,
        help="禁用性能优化（使用标准引擎）"
    )
    opt_group.add_argument(
        "--window-size",
        metavar="N",
        type=int,
        default=8,
        help="预计算表窗口大小 4-8（默认: 8）"
    )
    opt_group.add_argument(
        "--no-simd",
        action="store_true",
        default=False,
        help="禁用SIMD哈希优化"
    )
    opt_group.add_argument(
        "--no-memory-pool",
        action="store_true",
        default=False,
        help="禁用内存池优化"
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> bool:
    """验证参数合法性，返回 True 表示合法"""
    if args.mode in ("range", "brute_force"):
        if args.start is None:
            print(f"错误: {args.mode} 模式需要 --start 参数", file=sys.stderr)
            return False
        try:
            int(args.start, 16)
        except ValueError:
            print(f"错误: --start 必须是有效的十六进制数 (当前: {args.start})", file=sys.stderr)
            return False

    if args.mode == "range":
        if args.end is None:
            print("错误: range 模式需要 --end 参数", file=sys.stderr)
            return False
        try:
            int(args.end, 16)
        except ValueError:
            print(f"错误: --end 必须是有效的十六进制数 (当前: {args.end})", file=sys.stderr)
            return False

        start_val = int(args.start, 16)
        end_val = int(args.end, 16)
        if start_val >= end_val:
            print(f"错误: --start ({args.start}) 必须小于 --end ({args.end})", file=sys.stderr)
            return False
        if start_val < 1:
            print("错误: --start 必须 >= 1", file=sys.stderr)
            return False

    if args.workers is not None and args.workers < 1:
        print(f"错误: --workers 必须 >= 1 (当前: {args.workers})", file=sys.stderr)
        return False

    if args.duration < 0:
        print(f"错误: --duration 必须 >= 0 (当前: {args.duration})", file=sys.stderr)
        return False

    return True


def load_targets(args: argparse.Namespace) -> Set[str]:
    """加载目标地址集合"""
    resolver = TargetResolver()
    if args.file:
        targets = resolver.load_from_file(args.file)
        if not targets:
            print(f"错误: 从文件 '{args.file}' 未加载到任何有效地址", file=sys.stderr)
            sys.exit(1)
        print(f"从文件加载了 {len(targets)} 个目标地址")
    else:
        targets = resolver.resolve_multiple(args.targets)
        if not targets:
            print("错误: 未能解析任何有效的目标地址", file=sys.stderr)
            sys.exit(1)
        print(f"加载了 {len(targets)} 个目标地址")
    return targets


def format_progress(stats: CollisionStats, mode: str, total_range: Optional[int] = None) -> str:
    """格式化进度信息"""
    elapsed = stats.format_elapsed()
    checked = stats.total_checked
    speed_str = stats.format_speed()
    matches = len(stats.matches)

    # 引擎初始化期间，显示友好提示
    elapsed_sec = stats.elapsed if stats.elapsed > 0 else (
        time.time() - stats.start_time if stats.start_time > 0 else 0
    )
    if checked == 0 and elapsed_sec < 15:
        return f"[{elapsed}] 初始化中... | 速度: -- | 匹配: {matches} | ETA: --"
    eta_str = "--"
    if total_range and total_range > 0 and checked > 0:
        elapsed_sec = time.time() - stats.start_time if stats.start_time else 0
        if elapsed_sec > 0:
            speed = checked / elapsed_sec
            remaining = total_range - checked
            if speed > 0 and remaining > 0:
                eta_sec = remaining / speed
                if eta_sec < 60:
                    eta_str = f"{eta_sec:.0f}s"
                elif eta_sec < 3600:
                    eta_str = f"{eta_sec / 60:.1f}m"
                else:
                    eta_str = f"{eta_sec / 3600:.1f}h"
            elif remaining <= 0:
                eta_str = "完成"

    # 进度百分比
    pct_str = ""
    if total_range and total_range > 0:
        pct = min(100.0, checked / total_range * 100)
        pct_str = f" | 进度: {pct:.1f}%"

    return (
        f"[{elapsed}] 已检查: {checked:,} | 速度: {speed_str}"
        f"{pct_str} | 匹配: {matches} | ETA: {eta_str}"
    )


def on_match_callback(private_key: bytes, address: str, wif: str) -> None:
    """匹配回调（高亮显示）"""
    pk_hex = private_key.hex()
    print("\n" + "=" * 70)
    print("🎯 发现匹配!")
    print(f"  地址     : {address}")
    print(f"  私钥 Hex : {pk_hex}")
    print(f"  WIF      : {wif}")
    print("=" * 70 + "\n")


def main() -> None:
    """CLI 主入口"""
    args = parse_args()

    if not validate_args(args):
        sys.exit(1)

    # 加载目标
    targets = load_targets(args)

    # 计算范围参数
    start_val: Optional[int] = None
    end_val: Optional[int] = None
    total_range: Optional[int] = None
    if args.mode in ("range", "brute_force") and args.start:
        start_val = int(args.start, 16)
    if args.mode == "range" and args.end:
        end_val = int(args.end, 16)
        total_range = end_val - start_val + 1

    # 打印配置信息
    print("-" * 70)
    print(f"碰撞模式     : {args.mode}")
    print(f"目标地址数   : {len(targets)}")
    if start_val is not None:
        print(f"起始私钥     : 0x{start_val:x}")
    if end_val is not None:
        print(f"结束私钥     : 0x{end_val:x}")
        print(f"搜索范围     : {total_range:,} 个私钥")
    workers = args.workers or os.cpu_count() or 4
    print(f"工作线程数   : {workers}")
    print(f"断点续传     : {'启用' if args.checkpoint else '禁用'}")
    print(f"去重过滤     : {'启用' if args.dedup else '禁用'}")
    duration_str = f"{args.duration}秒" if args.duration > 0 else "无限制（Ctrl+C 停止）"
    print(f"运行时长     : {duration_str}")
    # v2.2.0 性能优化信息
    optimize_status = "禁用" if args.no_optimize else "启用"
    print(f"性能优化     : {optimize_status} (v2.2.0)")
    if not args.no_optimize:
        print(f"  - 预计算表   : window_size={args.window_size}")
        print(f"  - SIMD哈希   : {'禁用' if args.no_simd else '启用'}")
        print(f"  - 内存池     : {'禁用' if args.no_memory_pool else '启用'}")
    print("-" * 70)

    # 构建引擎
    engine = KeyCollisionEngine(
        targets=targets,
        on_progress=lambda s: None,  # 启动进度回调，确保 stats 实时更新
        on_match=on_match_callback,
        checkpoint_enabled=args.checkpoint,
        checkpoint_interval=args.checkpoint_interval,
        dedup_enabled=args.dedup,
        dedup_max_size=args.dedup_max_size,
        max_workers=args.workers,
        # v2.2.0 性能优化参数
        use_performance_optimization=not args.no_optimize,
        precomputed_window_size=args.window_size,
        use_simd_hash=not args.no_simd,
        use_memory_pool=not args.no_memory_pool,
    )

    # 信号处理（Ctrl+C 优雅停止）
    stop_event = threading.Event()

    def handle_signal(sig, frame):
        print("\n收到停止信号，正在停止...")
        stop_event.set()
        engine.stop()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    # 启动引擎
    print("开始对撞，按 Ctrl+C 停止...\n")
    engine_kwargs = {}
    if args.mode in ("range", "brute_force"):
        engine_kwargs["start"] = start_val
    if args.mode == "range":
        engine_kwargs["end"] = end_val

    engine.start(mode=args.mode, **engine_kwargs)
    start_time = time.time()

    # 主循环：打印进度
    try:
        while engine.is_running() and not stop_event.is_set():
            time.sleep(args.progress_interval)
            if stop_event.is_set():
                break
            stats = engine.get_stats()
            print(format_progress(stats, args.mode, total_range))

            # 检查运行时长限制
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                print(f"\n已达到运行时长限制 ({args.duration}s)，停止对撞...")
                engine.stop()
                stop_event.set()
                break
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
        engine.stop()

    # 等待引擎完全停止
    if engine.is_running():
        engine.stop()
    time.sleep(0.5)

    # 打印最终统计
    stats = engine.get_stats()
    print("\n" + "=" * 70)
    print("对撞结束 - 最终统计")
    print("-" * 70)
    print(f"  总检查数 : {stats.total_checked:,}")
    print(f"  运行时间 : {stats.format_elapsed()}")
    print(f"  平均速度 : {stats.format_speed()}")
    print(f"  发现匹配 : {len(stats.matches)} 个")
    if stats.matches:
        print("\n  匹配详情:")
        for m in stats.matches:
            print(f"    地址: {m.get('address', 'N/A')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
