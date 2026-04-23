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
import json
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Set

# 将项目根目录加入路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.collision import KeyCollisionEngine, TargetResolver, CollisionStats
from src.utils import init_logging, get_configured_logger
from src.cli.advanced_features import (
    apply_template,
    recommend_parameters,
    export_progress_data,
    export_matches,
    GPUErrorHandler,
)

# GPU 引擎延迟导入（pyopencl 可选依赖）
try:
    from src.collision.gpu_collision_engine import GPUCollisionEngine
    from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

init_logging()
logger = get_configured_logger("CLI")


def load_config_with_validation() -> Optional[dict]:
    """
    加载并验证配置文件
    
    返回:
        配置字典，如果加载失败则返回None
    """
    config_path = os.path.join(_project_root, 'config.json')
    
    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在: {config_path}")
        logger.info("请运行: copy config.example.json config.json (Windows) 或 cp config.example.json config.json (Linux/macOS)")
        return None
    
    # 尝试加载JSON
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"配置文件加载成功: {config_path}")
        
        # 基本验证
        if not isinstance(config, dict):
            logger.error("配置文件格式错误: 根节点必须是JSON对象")
            return None
        
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"配置文件JSON格式错误: {e}")
        logger.error(f"位置: 行{e.lineno}, 列{e.colno}")
        logger.error("请检查config.json语法，或从config.example.json重新复制")
        return None
    except UnicodeDecodeError as e:
        logger.error(f"配置文件编码错误: {e}")
        logger.error("请确保配置文件使用UTF-8编码")
        return None
    except PermissionError as e:
        logger.error(f"配置文件权限错误: {e}")
        logger.error("请检查文件读取权限")
        return None
    except Exception as e:
        logger.error(f"加载配置文件时发生未知错误: {e}")
        return None


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

  多GPU单GPU GPU加速随机碰撞:
    python key_collision_cli.py -f targets.txt --use-gpu -m random
    python key_collision_cli.py -f targets.txt --multi-gpu -m random

  GPU加速范围扫描:
    python key_collision_cli.py -f targets.txt --use-gpu -m range --start 1 --end FFFFFFFF
        """
    )

    # 目标地址
    target_group = parser.add_argument_group("目标地址")
    target_ex = target_group.add_mutually_exclusive_group(required=False)
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

    # GPU 加速选项
    gpu_group = parser.add_argument_group(
        "GPU 加速",
        "启用 GPU 加速可将速度提升数千倍（需安装 pyopencl）"
    )
    gpu_group.add_argument(
        "--use-gpu",
        action="store_true",
        default=False,
        help="启用单 GPU 加速模式"
    )
    gpu_group.add_argument(
        "--gpu-device",
        metavar="INDEX",
        type=int,
        default=-1,
        help="GPU 设备索引，-1 表示自动选择最佳设备（默认: -1）"
    )
    gpu_group.add_argument(
        "--gpu-batch-size",
        metavar="N",
        type=int,
        default=None,
        help="GPU 每批处理私钥数量，None 表示根据显存自动计算（默认: 自动）"
    )
    gpu_group.add_argument(
        "--multi-gpu",
        action="store_true",
        default=False,
        help="启用多 GPU 模式（自动使用所有可用 GPU，优先级高于 --use-gpu）"
    )
    gpu_group.add_argument(
        "--gpu-count",
        metavar="N",
        type=int,
        default=-1,
        help="多 GPU 模式下使用的 GPU 数量，-1 表示使用全部（默认: -1）"
    )
    gpu_group.add_argument(
        "--gpu-indices",
        metavar="IDX",
        type=int,
        nargs="+",
        default=None,
        help="多 GPU 模式下手动指定 GPU 索引列表，例如: --gpu-indices 0 1（默认: 自动选择）"
    )

    # ── 实用工具选项 ────────────────────────────────────────────────────────
    util_group = parser.add_argument_group(
        "实用工具",
        "独立功能命令，指定后直接执行并退出，不启动碰撞引擎"
    )
    util_group.add_argument(
        "--validate-addresses",
        metavar="FILE",
        default=None,
        help="验证地址文件中的所有比特币地址格式，输出验证报告后退出"
    )
    util_group.add_argument(
        "--health-check",
        action="store_true",
        default=False,
        help="运行系统健康检查（依赖、配置、磁盘等），输出报告后退出"
    )
    util_group.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="清理过期临时文件、历史数据和日志（dry-run 预览请用 --cleanup --dry-run）"
    )
    util_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="与 --cleanup 配合，仅预览将被清理的文件，不实际删除"
    )
    util_group.add_argument(
        "--platform-check",
        action="store_true",
        default=False,
        help="运行跨平台兼容性检查（路径长度、编码、磁盘空间等），输出报告后退出"
    )
    util_group.add_argument(
        "--quick-start",
        action="store_true",
        default=False,
        help="启动交互式快速引导模式，适合新手用户"
    )
    util_group.add_argument(
        "--examples",
        action="store_true",
        default=False,
        help="显示常用使用示例后退出"
    )
    util_group.add_argument(
        "--config-check",
        action="store_true",
        default=False,
        help="检查配置文件状态，验证配置有效性"
    )
    util_group.add_argument(
        "--template",
        metavar="NAME",
        default=None,
        help="使用配置模板创建config.json (可选: gpu-performance, long-running, gpu-multi, quick-test)"
    )
    util_group.add_argument(
        "--export-progress",
        metavar="FILE",
        default=None,
        help="运行结束后导出进度数据到JSON文件"
    )
    util_group.add_argument(
        "--export-matches",
        metavar="FILE",
        default=None,
        help="导出匹配结果到JSON文件"
    )
    util_group.add_argument(
        "--recommend",
        action="store_true",
        default=False,
        help="根据目标和系统信息推荐最优参数组合"
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> bool:
    """验证参数合法性，返回 True 表示合法"""
    # 如果没有 -t/-f，且不是实用工具命令，则报错
    is_util_cmd = (
        getattr(args, 'health_check', False)
        or getattr(args, 'platform_check', False)
        or getattr(args, 'cleanup', False)
        or getattr(args, 'validate_addresses', None) is not None
        or getattr(args, 'examples', False)
        or getattr(args, 'config_check', False)
        or getattr(args, 'quick_start', False)
    )
    if not is_util_cmd and not args.targets and not args.file:
        print("\n[Error] 需要指定目标地址", file=sys.stderr)
        print("\n[Tip] 提示:")
        print("   - 单个地址: python key_collision_cli.py -t <地址> -m random")
        print("   - 文件加载: python key_collision_cli.py -f <文件> -m random")
        print("   - 快速引导: python key_collision_cli.py --quick-start")
        print("   - 查看示例: python key_collision_cli.py --examples")
        print("   - 完整帮助: python key_collision_cli.py --help\n")
        return False
    if args.mode in ("range", "brute_force"):
        if args.start is None:
            print(f"\n[Error] {args.mode} 模式需要 --start 参数", file=sys.stderr)
            print(f"[Tip] 示例: python key_collision_cli.py -t <地址> -m {args.mode} --start 1\n")
            return False
        try:
            int(args.start, 16)
        except ValueError:
            print(f"\n[Error] --start 必须是有效的十六进制数 (当前: {args.start})", file=sys.stderr)
            print(f"[Tip] 示例: --start 1 或 --start 1A2B3C\n")
            return False

    if args.mode == "range":
        if args.end is None:
            print("\n[Error] range 模式需要 --end 参数", file=sys.stderr)
            print("[Tip] 示例: python key_collision_cli.py -t <地址> -m range --start 1 --end FFFFFFFF\n")
            return False
        try:
            int(args.end, 16)
        except ValueError:
            print(f"\n[Error] --end 必须是有效的十六进制数 (当前: {args.end})", file=sys.stderr)
            print(f"[Tip] 示例: --end FFFFFFFF 或 --end 1000000\n")
            return False

        start_val = int(args.start, 16)
        end_val = int(args.end, 16)
        if start_val >= end_val:
            print(f"\n[Error] --start ({args.start}) 必须小于 --end ({args.end})", file=sys.stderr)
            print("[Tip] 提示: 请检查起始和结束私钥的顺序\n")
            return False
        if start_val < 1:
            print("\n[Error] --start 必须 >= 1", file=sys.stderr)
            print("[Tip] 提示: 私钥范围必须从 1 开始\n")
            return False
        
        # M-NEW2修复: 范围过大警告（2^64约需数百年才能穷举）
        total_range = end_val - start_val + 1
        if total_range > 2**64:
            print(f"警告: 搜索范围超过 2^64 ({total_range:,} 个私钥)，任务可能需要极长时间", file=sys.stderr)

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
    """格式化进度信息（带可视化进度条）"""
    elapsed = stats.format_elapsed()
    checked = stats.total_checked
    speed_str = stats.format_speed()
    matches = len(stats.matches)

    # 引擎初始化期间，显示友好提示
    elapsed_sec = stats.elapsed if stats.elapsed > 0 else (
        time.time() - stats.start_time if stats.start_time > 0 else 0
    )
    if checked == 0 and elapsed_sec < 15:
        return f"[{elapsed}] [Initializing] 初始化中... | 速度: -- | 匹配: {matches} | ETA: --"
    
    # 计算进度百分比和 ETA
    pct = 0.0
    eta_str = "--"
    
    if total_range and total_range > 0:
        pct = min(100.0, checked / total_range * 100)
        
        if checked > 0 and elapsed_sec > 0:
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
                eta_str = "[Done] 完成"
    
    # 生成可视化进度条
    bar_length = 20
    if total_range and total_range > 0:
        filled = int(bar_length * pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        pct_str = f" {bar} {pct:5.1f}%"
    else:
        pct_str = ""
    
    # 格式化已检查数量
    if checked >= 1_000_000_000:
        checked_str = f"{checked/1_000_000_000:.2f}B"
    elif checked >= 1_000_000:
        checked_str = f"{checked/1_000_000:.2f}M"
    elif checked >= 1_000:
        checked_str = f"{checked/1_000:.1f}K"
    else:
        checked_str = str(checked)
    
    # 总范围显示
    if total_range and total_range > 0:
        if total_range >= 1_000_000_000:
            total_str = f"{total_range/1_000_000_000:.2f}B"
        elif total_range >= 1_000_000:
            total_str = f"{total_range/1_000_000:.2f}M"
        else:
            total_str = f"{total_range:,}"
        range_info = f" | {checked_str}/{total_str}"
    else:
        range_info = f" | {checked_str}"

    return (
        f"[{elapsed}]{pct_str}{range_info}"
        f" | 速度: {speed_str}"
        f" | ETA: {eta_str}"
        f" | 匹配: {matches}"
    )


def build_engine(args, targets: Set[str]):
    """引擎工厂：根据 CLI 参数分路 CPU / 单GPU / 多GPU 三种引擎

    Returns:
        (engine, engine_type) 元组
        engine_type: 'cpu' | 'gpu' | 'multi_gpu'
    """
    # ── 多GPU 模式 ──────────────────────────────────────────────
    if getattr(args, 'multi_gpu', False):
        if not GPU_AVAILABLE:
            print("错误: 多GPU模式需要安装 pyopencl，当前不可用", file=sys.stderr)
            sys.exit(1)
        engine = MultiGPUCollisionEngine()
        device_indices = getattr(args, 'gpu_indices', None)
        gpu_count = getattr(args, 'gpu_count', -1)
        ok = engine.initialize(
            device_indices=device_indices,
            device_count=gpu_count,
            strategy='performance',
        )
        if not ok:
            print("错误: 多GPU引擎初始化失败，请检查 GPU 驱动和 pyopencl 安装", file=sys.stderr)
            sys.exit(1)
        return engine, 'multi_gpu'

    # ── 单GPU 模式 ──────────────────────────────────────────────
    if getattr(args, 'use_gpu', False):
        if not GPU_AVAILABLE:
            print("错误: GPU模式需要安装 pyopencl，当前不可用", file=sys.stderr)
            sys.exit(1)
        engine = GPUCollisionEngine(
            targets=targets,
            device_index=getattr(args, 'gpu_device', -1),
            batch_size=getattr(args, 'gpu_batch_size', None),
            on_progress=lambda s: None,
            on_match=on_match_callback,
            checkpoint_enabled=args.checkpoint,
            checkpoint_interval=args.checkpoint_interval,
            dedup_enabled=args.dedup,
            dedup_max_size=args.dedup_max_size,
            use_gpu_memory_pool=True,
        )
        return engine, 'gpu'

    # ── CPU 模式（默认）────────────────────────────────────────
    engine = KeyCollisionEngine(
        targets=targets,
        on_progress=lambda s: None,
        on_match=on_match_callback,
        checkpoint_enabled=args.checkpoint,
        checkpoint_interval=args.checkpoint_interval,
        dedup_enabled=args.dedup,
        dedup_max_size=args.dedup_max_size,
        max_workers=args.workers,
        use_performance_optimization=not args.no_optimize,
        precomputed_window_size=args.window_size,
        use_simd_hash=not args.no_simd,
        use_memory_pool=not args.no_memory_pool,
    )
    return engine, 'cpu'


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
    try:
        _run_main()
    except KeyboardInterrupt:
        print("\n用户中断，退出程序。")
        sys.exit(0)
    except SystemExit:
        # 参数验证失败等主动调用 sys.exit() 的情况，直接透传
        raise
    except ValueError as e:
        print(f"\n错误: 参数值无效 - {e}", file=sys.stderr)
        logger.exception("参数值无效")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n错误: 文件不存在 - {e}", file=sys.stderr)
        logger.exception("文件不存在")
        sys.exit(1)
    except PermissionError as e:
        print(f"\n错误: 权限不足 - {e}", file=sys.stderr)
        logger.exception("权限不足")
        sys.exit(1)
    except MemoryError:
        print("\n错误: 内存不足，请减少目标地址数量或降低批次大小", file=sys.stderr)
        logger.exception("内存不足")
        sys.exit(1)
    except ImportError as e:
        print(f"\n错误: 缺少依赖模块 - {e}", file=sys.stderr)
        logger.exception("缺少依赖模块")
        sys.exit(1)
    except OSError as e:
        print(f"\n错误: 系统调用失败 - {e}", file=sys.stderr)
        logger.exception("系统调用失败")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: 未预期的异常 - {type(e).__name__}: {e}", file=sys.stderr)
        logger.exception("CLI 主程序未预期异常")
        sys.exit(2)


def _cmd_validate_addresses(file_path: str) -> None:
    """--validate-addresses 命令实现：批量验证文件中所有比特币地址"""
    from pathlib import Path

    target_path = Path(file_path)
    if not target_path.exists():
        print(f"错误: 文件不存在 - {file_path}", file=sys.stderr)
        sys.exit(1)

    # 尝试导入地址验证器
    try:
        from src.collision.targets.validator import AddressBatchValidator
    except ImportError:
        from ..collision.targets.validator import AddressBatchValidator

    print(f"[BTC地址验证] 文件: {file_path}")
    print("-" * 60)

    # 读取文件
    lines = []
    try:
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as exc:
        print(f"错误: 读取文件失败 - {exc}", file=sys.stderr)
        sys.exit(1)

    addresses = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith('#'):
            addresses.append(stripped)

    if not addresses:
        print("警告: 文件中未找到任何地址（空行/注释行已跳过）")
        sys.exit(0)

    # 执行批量验证
    validator = AddressBatchValidator()
    results_dict = validator.validate_batch(addresses)

    valid_list   = [r for r in results_dict.values() if r.valid]
    invalid_list = [r for r in results_dict.values() if r.validated and not r.valid]
    skipped_list = [r for r in results_dict.values() if not r.validated]

    print(f"总地址数  : {len(addresses)}")
    print(f"[OK] 有效    : {len(valid_list)}")
    print(f"[!]  无效    : {len(invalid_list)}")
    print(f"[--] 跳过    : {len(skipped_list)}")
    print("-" * 60)

    if valid_list:
        print(f"\n有效地址示例（最多显示 5 个）:")
        for r in valid_list[:5]:
            fmt = getattr(r, 'format_type', 'unknown') or 'unknown'
            print(f"  [OK] {r.address}  [{fmt}]")

    if invalid_list:
        print(f"\n无效地址（最多显示 10 个）:")
        for r in invalid_list[:10]:
            err = getattr(r, 'error', '') or ''
            print(f"  [!]  {r.address}  原因: {err}")

    print("-" * 60)
    valid_rate = len(valid_list) / len(addresses) * 100 if addresses else 0
    print(f"有效率: {valid_rate:.1f}%")
    if valid_rate < 100:
        print("警告: 存在无效地址，请检查地址文件格式")


def _cmd_examples() -> None:
    """--examples 命令实现：显示常用使用示例"""
    # 确保UTF-8输出
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("[Examples] BTC碰撞引擎 - 常用示例")
    print("=" * 70)
    
    examples = [
        {
            "title": "1. 基础随机碰撞",
            "desc": "最简单的使用方式，持续运行直到 Ctrl+C",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random"
        },
        {
            "title": "2. 断点续传（推荐）",
            "desc": "启用断点续传和去重，运行1小时后自动停止",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --checkpoint --dedup --duration 3600"
        },
        {
            "title": "3. 从文件加载目标",
            "desc": "从文件读取多个目标地址",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --checkpoint"
        },
        {
            "title": "4. GPU加速模式",
            "desc": "启用单GPU加速（速度提升数千倍）",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --use-gpu"
        },
        {
            "title": "5. 多GPU模式",
            "desc": "使用所有可用GPU设备",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --multi-gpu"
        },
        {
            "title": "6. 范围扫描",
            "desc": "在指定私钥范围内搜索",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m range --start 1 --end FFFFFFFF"
        },
        {
            "title": "7. 系统健康检查",
            "desc": "检查系统依赖和配置状态",
            "cmd": "python key_collision_cli.py --health-check"
        },
        {
            "title": "8. 验证地址文件",
            "desc": "批量验证文件中的地址格式",
            "cmd": "python key_collision_cli.py --validate-addresses targets.txt"
        },
    ]
    
    for ex in examples:
        print(f"\n{ex['title']}")
        print(f"   {ex['desc']}")
        print(f"   $ {ex['cmd']}")
    
    print("\n" + "=" * 70)
    print("💡 提示:")
    print("   - 新手建议使用 --quick-start 进行交互式引导")
    print("   - 查看完整帮助: python key_collision_cli.py --help")
    print("   - 检查配置状态: python key_collision_cli.py --config-check")
    print("=" * 70)


def _cmd_config_check() -> None:
    """--config-check 命令实现：检查配置文件状态"""
    from pathlib import Path
    
    # 确保UTF-8输出
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    config_path = Path("config.json")
    example_path = Path("config.example.json")
    
    print("=" * 70)
    print("[Config Check] 配置文件检查")
    print("=" * 70)
    
    # 检查配置文件存在性
    if config_path.exists():
        print("\n✅ config.json 存在")
        
        # 验证JSON格式
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("✅ JSON格式正确")
            
            # 基本结构验证
            required_sections = ['crypto', 'collision', 'logging']
            missing_sections = [s for s in required_sections if s not in config]
            
            if missing_sections:
                print(f"⚠️  缺少配置段: {', '.join(missing_sections)}")
            else:
                print("✅ 主要配置段完整")
            
            # 显示关键配置信息
            print("\n📊 关键配置信息:")
            collision_cfg = config.get('collision', {})
            print(f"   - 工作线程数: {collision_cfg.get('max_workers', '自动 (CPU核心数)')}")
            print(f"   - 性能优化: {'启用' if collision_cfg.get('use_performance_optimization', True) else '禁用'}")
            print(f"   - 断点续传间隔: {collision_cfg.get('checkpoint_interval', 30)}秒")
            
            gpu_cfg = config.get('gpu', {})
            print(f"   - GPU模式: {gpu_cfg.get('mode', 'auto')}")
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON格式错误: {e}")
            print("💡 修复建议: 从 config.example.json 重新复制")
        except Exception as e:
            print(f"❌ 读取失败: {e}")
    else:
        print("\n❌ config.json 不存在")
        if example_path.exists():
            print("✅ config.example.json 存在")
            print("💡 修复建议: 复制示例配置文件")
            print("   Windows: copy config.example.json config.json")
            print("   Linux/Mac: cp config.example.json config.json")
        else:
            print("❌ config.example.json 也不存在")
            print("💡 修复建议: 从项目仓库重新获取配置文件")
    
    # 检查必要目录
    print("\n📁 必要目录检查:")
    required_dirs = ['logs', 'data_logs', 'monitoring_data']
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ (不存在)")
            print(f"      修复: mkdir {dir_name}")
    
    print("\n" + "=" * 70)


def _cmd_quick_start() -> None:
    """--quick-start 命令实现：交互式快速引导"""
    # 确保UTF-8输出
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("[Quick Start] BTC碰撞引擎 - 快速引导模式")
    print("=" * 70)
    print()
    
    try:
        # 步骤1: 选择目标地址来源
        print("【步骤 1/4】选择目标地址来源")
        print("   1. 单个比特币地址")
        print("   2. 从文件加载多个地址")
        target_type = input("   请选择 [1/2] [默认:1]: ").strip() or '1'
        
        targets = []
        target_file = None
        
        if target_type == '1':
            address = input("   输入比特币地址: ").strip()
            if not address:
                print("   ❌ 地址不能为空")
                return
            targets = [address]
        elif target_type == '2':
            target_file = input("   输入文件路径 [默认: targets.txt]: ").strip() or 'targets.txt'
            if not Path(target_file).exists():
                print(f"   ⚠️  文件不存在: {target_file}")
                create = input("   是否创建示例文件? [y/N]: ").strip().lower()
                if create == 'y':
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write("# 目标地址文件\n")
                        f.write("# 每行一个地址，支持 # 注释\n")
                        f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
                    print(f"   ✅ 已创建示例文件: {target_file}")
                    print("   💡 请编辑文件添加您的目标地址后重新运行")
                    return
                else:
                    return
        else:
            print("   ❌ 无效选择")
            return
        
        # 步骤2: 选择碰撞模式
        print("\n【步骤 2/4】选择碰撞模式")
        print("   1. random    - 随机碰撞（推荐新手）")
        print("   2. range     - 范围扫描（需要指定起始/结束私钥）")
        print("   3. brute_force - 暴力穷举（研究用途）")
        mode_choice = input("   请选择 [1/2/3] [默认:1]: ").strip() or '1'
        
        mode_map = {'1': 'random', '2': 'range', '3': 'brute_force'}
        mode = mode_map.get(mode_choice, 'random')
        
        start_key = None
        end_key = None
        
        if mode in ['range', 'brute_force']:
            start_key = input("   起始私钥 (十六进制) [默认:1]: ").strip() or '1'
            if mode == 'range':
                end_key = input("   结束私钥 (十六进制) [默认:FFFFFFFF]: ").strip() or 'FFFFFFFF'
        
        # 步骤3: 功能选项
        print("\n【步骤 3/4】功能选项")
        checkpoint = input("   启用断点续传? [Y/n] [默认:Y]: ").strip().lower() != 'n'
        dedup = input("   启用去重过滤? [Y/n] [默认:Y]: ").strip().lower() != 'n'
        
        duration_str = input("   运行时长 (秒，0=无限) [默认:0]: ").strip() or '0'
        try:
            duration = int(duration_str)
        except ValueError:
            print("   ⚠️  无效数值，使用默认值 0")
            duration = 0
        
        # 步骤4: GPU加速
        print("\n【步骤 4/4】GPU加速")
        print("   1. CPU 模式（默认）")
        print("   2. 单GPU 加速")
        print("   3. 多GPU 加速")
        gpu_choice = input("   请选择 [1/2/3] [默认:1]: ").strip() or '1'
        
        # 构建命令
        print("\n" + "=" * 70)
        print("✅ 生成的命令:")
        print("=" * 70)
        
        cmd_parts = ["python", "key_collision_cli.py"]
        
        if targets:
            cmd_parts.extend(["-t"] + targets)
        elif target_file:
            cmd_parts.extend(["-f", target_file])
        
        cmd_parts.extend(["-m", mode])
        
        if start_key:
            cmd_parts.extend(["--start", start_key])
        if end_key:
            cmd_parts.extend(["--end", end_key])
        
        if checkpoint:
            cmd_parts.append("--checkpoint")
        if dedup:
            cmd_parts.append("--dedup")
        if duration > 0:
            cmd_parts.extend(["--duration", str(duration)])
        
        if gpu_choice == '2':
            cmd_parts.append("--use-gpu")
        elif gpu_choice == '3':
            cmd_parts.append("--multi-gpu")
        
        cmd_str = " ".join(cmd_parts)
        print(f"\n{cmd_str}\n")
        
        # 询问是否执行
        execute = input("是否立即执行? [Y/n] [默认:Y]: ").strip().lower()
        if execute != 'n':
            print("\n" + "=" * 70)
            print("🚀 启动碰撞引擎...")
            print("=" * 70 + "\n")
            
            # 解析并执行命令
            import shlex
            # 模拟命令行参数
            sys.argv = cmd_parts
            from src.cli.main import _run_main
            _run_main()
        else:
            print("\n💡 提示: 您可以复制上面的命令直接运行")
            print("   查看完整帮助: python key_collision_cli.py --help")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，退出引导模式")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("💡 您可以直接使用命令行参数运行")


def _run_main() -> None:
    """CLI 主逻辑（由 main() 包装异常处理）"""
    args = parse_args()

    # ── 实用工具命令：请在参数验证之前处理，需要 -t/-f 的命令已抚异常 ───────

    # --examples
    if getattr(args, 'examples', False):
        _cmd_examples()
        sys.exit(0)

    # --config-check
    if getattr(args, 'config_check', False):
        _cmd_config_check()
        sys.exit(0)

    # --template
    template_name = getattr(args, 'template', None)
    if template_name is not None:
        from src.cli.advanced_features import apply_template
        success = apply_template(template_name)
        sys.exit(0 if success else 1)

    # --recommend
    if getattr(args, 'recommend', False):
        from src.cli.advanced_features import recommend_parameters
        rec = recommend_parameters(args)
        print("=" * 70)
        print(f"[Recommend] 参数智能推荐")
        print("=" * 70)
        print(f"\n[Info] 推荐参数:")
        if rec['recommendations']:
            print(f"   {' '.join(rec['recommendations'])}")
        else:
            print(f"   （使用默认参数即可）")
        print(f"\n[Info] 推荐原因:")
        for i, reason in enumerate(rec['reasons'], 1):
            print(f"   {i}. {reason}")
        print("\n" + "=" * 70)
        sys.exit(0)

    # --quick-start
    if getattr(args, 'quick_start', False):
        _cmd_quick_start()
        sys.exit(0)

    # ── 自动检测首次运行 ───────────────────────────────────────
    config_path = Path("config.json")
    wizard_marker = Path("data_logs/.wizard_completed")
    
    if not config_path.exists() and not wizard_marker.exists():
        print("\n[First Run] 检测到首次运行，启动配置向导...")
        print("[Tip] 提示: 如果您想直接使用命令行，可以按 Ctrl+C 退出\n")
        try:
            from src.utils.first_run_wizard import FirstRunWizard
        except ImportError:
            from ..utils.first_run_wizard import FirstRunWizard
        
        wizard = FirstRunWizard()
        wizard.run()
        print("\n[OK] 配置完成！现在可以开始使用碰撞引擎")
        print("[Tip] 提示: 运行 'python key_collision_cli.py --quick-start' 开始\n")
        sys.exit(0)

    # --health-check
    if getattr(args, 'health_check', False):
        try:
            from src.utils.health_check import HealthChecker
        except ImportError:
            from ..utils.health_check import HealthChecker
        checker = HealthChecker()
        results = checker.run_all_checks()
        checker.generate_report()
        all_ok = all(passed for passed, _ in results.values())
        sys.exit(0 if all_ok else 1)

    # --platform-check
    if getattr(args, 'platform_check', False):
        try:
            from src.utils.platform_check import PlatformChecker
        except ImportError:
            from ..utils.platform_check import PlatformChecker
        checker = PlatformChecker()
        all_passed, _ = checker.run_all_checks()
        checker.print_report()
        sys.exit(0 if all_passed else 1)

    # --cleanup
    if getattr(args, 'cleanup', False):
        try:
            from src.utils.data_cleanup import DataCleaner
        except ImportError:
            from ..utils.data_cleanup import DataCleaner
        cleaner = DataCleaner()
        dry_run = getattr(args, 'dry_run', False)
        result = cleaner.clean_all(dry_run=dry_run)
        total = result.get('files_removed', 0)
        space_mb = result.get('space_freed_bytes', 0) / 1024 / 1024
        action = '预览' if dry_run else '已清理'
        print(f"[{ '预览' if dry_run else '完成'}] {action} {total} 个文件, 释放 {space_mb:.2f}MB")
        sys.exit(0)

    # --validate-addresses
    validate_file = getattr(args, 'validate_addresses', None)
    if validate_file is not None:
        _cmd_validate_addresses(validate_file)
        sys.exit(0)

    # 对于其他命令，-t/-f 是必填项，此处已由 argparse required=True 保障
    if not validate_args(args):
        sys.exit(1)

    # 加载并验证配置文件
    config = load_config_with_validation()
    if config is None:
        logger.warning("使用默认配置运行")
        config = {}

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
    # ── 确定引擎模式并打印配置 ──────────────────────────────────
    use_multi_gpu = getattr(args, 'multi_gpu', False)
    use_single_gpu = getattr(args, 'use_gpu', False) and not use_multi_gpu
    use_cpu = not use_multi_gpu and not use_single_gpu

    if use_multi_gpu:
        gpu_indices = getattr(args, 'gpu_indices', None)
        gpu_count   = getattr(args, 'gpu_count', -1)
        print(f"加速模式     : 多GPU")
        if gpu_indices:
            print(f"GPU 设备     : 指定索引 {gpu_indices}")
        elif gpu_count > 0:
            print(f"GPU 数量     : {gpu_count} 个（按性能自动选择）")
        else:
            print(f"GPU 数量     : 全部可用（按性能自动选择）")
    elif use_single_gpu:
        gpu_device     = getattr(args, 'gpu_device', -1)
        gpu_batch_size = getattr(args, 'gpu_batch_size', None)
        print(f"加速模式     : 单GPU")
        print(f"GPU 设备索引 : {gpu_device if gpu_device >= 0 else '自动选择'}")
        print(f"GPU 批次大小 : {gpu_batch_size if gpu_batch_size else '自动计算'}")
    else:
        workers = args.workers or os.cpu_count() or 4
        print(f"加速模式     : CPU")
        print(f"工作线程数   : {workers}")

    print(f"断点续传     : {'启用' if args.checkpoint else '禁用'}")
    print(f"去重过滤     : {'启用' if args.dedup else '禁用'}")
    duration_str = f"{args.duration}秒" if args.duration > 0 else "无限制（Ctrl+C 停止）"
    print(f"运行时长     : {duration_str}")

    if use_cpu:
        optimize_status = "禁用" if args.no_optimize else "启用"
        print(f"性能优化     : {optimize_status} (v2.2.0)")
        if not args.no_optimize:
            print(f"  - 预计算表   : window_size={args.window_size}")
            print(f"  - SIMD哈希   : {'禁用' if args.no_simd else '启用'}")
            print(f"  - 内存池     : {'禁用' if args.no_memory_pool else '启用'}")
    print("-" * 70)

    # 构建引擎
    engine, engine_type = build_engine(args, targets)

    # ── 将告警系统集成到引擎主流程 ──────────────────────────────────
    alert_system = None
    try:
        from src.monitoring.alert_system import AlertSystem
    except ImportError:
        try:
            from ..monitoring.alert_system import AlertSystem
        except ImportError:
            AlertSystem = None

    if AlertSystem is not None:
        try:
            alert_system = AlertSystem()
            alert_system.setup_default_rules()

            def _on_alert(alert_record):
                level = getattr(alert_record.level, 'value', str(alert_record.level)).upper()
                msg = getattr(alert_record, 'message', str(alert_record))
                print(f"\n⚠️  [告警/{level}] {msg}")

            alert_system.add_alert_callback(_on_alert)
            logger.info("告警系统已集成：%d 条规则", len(alert_system.rules))
        except Exception as exc:
            logger.warning("告警系统初始化失败，将以没有告警的方式运行: %s", exc)
            alert_system = None

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

    if engine_type == 'multi_gpu':
        # 多GPU 引擎：使用自身的 start(targets, mode, range_start, range_end) 签名
        ok = engine.start(
            targets=targets,
            mode=args.mode,
            range_start=start_val,
            range_end=end_val,
            match_callback=lambda dev_idx, m: print(
                f"\n[GPU {dev_idx}] 发现匹配: 地址={m.get('address', 'N/A')}"
            ),
        )
        if not ok:
            print("错误: 多GPU引擎启动失败", file=sys.stderr)
            sys.exit(1)
    else:
        # 单GPU / CPU 引擎：使用 start(mode, start, end) 签名
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

            if engine_type == 'multi_gpu':
                # 多GPU 引擎使用 get_combined_stats() 返回字典
                combined = engine.get_combined_stats()
                elapsed_sec = combined.get('elapsed_time', 0)
                total_checked = combined.get('total_keys_checked', 0)
                throughput = combined.get('combined_throughput', 0)
                matches = combined.get('total_matches', 0)
                device_count = combined.get('device_count', 0)
                h, rem = divmod(int(elapsed_sec), 3600)
                m_t, s = divmod(rem, 60)
                elapsed_fmt = f"{h:02d}:{m_t:02d}:{s:02d}"
                speed_fmt = (
                    f"{throughput/1_000_000:.2f}M/s"
                    if throughput >= 1_000_000
                    else f"{throughput/1_000:.1f}K/s"
                    if throughput >= 1_000
                    else f"{throughput:.0f}/s"
                )
                print(
                    f"[{elapsed_fmt}] GPU x{device_count} | "
                    f"已检查: {total_checked:,} | "
                    f"速度: {speed_fmt} | "
                    f"匹配: {matches}"
                )
            else:
                stats = engine.get_stats()
                print(format_progress(stats, args.mode, total_range))

                # 告警系统检查（每次刷新进度后执行）
                if alert_system is not None:
                    try:
                        elapsed_sec = stats.elapsed if stats.elapsed > 0 else 1
                        throughput = stats.total_checked / elapsed_sec if elapsed_sec > 0 else 0
                        metrics = {
                            'throughput': throughput,
                            'baseline_throughput': getattr(stats, 'peak_speed', throughput * 1.2),
                            'error_rate': 0.0,
                        }
                        alert_system.check_metrics(metrics)
                    except Exception:
                        pass  # 告警异常不影响主流程

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
    print("\n" + "=" * 70)
    print("对撞结束 - 最终统计")
    print("-" * 70)

    if engine_type == 'multi_gpu':
        combined = engine.get_combined_stats()
        elapsed_sec = combined.get('elapsed_time', 0)
        total_checked = combined.get('total_keys_checked', 0)
        throughput = combined.get('combined_throughput', 0)
        matches_count = combined.get('total_matches', 0)
        device_count = combined.get('device_count', 0)
        h, rem = divmod(int(elapsed_sec), 3600)
        m_t, s = divmod(rem, 60)
        elapsed_fmt = f"{h:02d}:{m_t:02d}:{s:02d}"
        speed_fmt = (
            f"{throughput/1_000_000:.2f}M/s"
            if throughput >= 1_000_000
            else f"{throughput/1_000:.1f}K/s"
            if throughput >= 1_000
            else f"{throughput:.0f}/s"
        )
        print(f"  加速模式  : 多GPU ({device_count} 个设备)")
        print(f"  总检查数  : {total_checked:,}")
        print(f"  运行时间  : {elapsed_fmt}")
        print(f"  平均速度  : {speed_fmt}")
        print(f"  发现匹配  : {matches_count} 个")
        # 每GPU分项
        per_device = combined.get('per_device', {})
        if per_device:
            print("\n  各GPU明细:")
            for dev_idx, dev_stats in sorted(per_device.items()):
                dev_keys = dev_stats.get('keys_checked', 0)
                dev_tp   = dev_stats.get('throughput', 0)
                dev_speed_fmt = (
                    f"{dev_tp/1_000_000:.2f}M/s"
                    if dev_tp >= 1_000_000
                    else f"{dev_tp/1_000:.1f}K/s"
                    if dev_tp >= 1_000
                    else f"{dev_tp:.0f}/s"
                )
                print(f"    GPU {dev_idx}: 检查 {dev_keys:,} | 速度 {dev_speed_fmt}")
        # 清理多GPU引擎
        engine.cleanup()
    else:
        stats = engine.get_stats()
        mode_label = "单GPU" if engine_type == 'gpu' else "CPU"
        print(f"  加速模式  : {mode_label}")
        print(f"  总检查数  : {stats.total_checked:,}")
        print(f"  运行时间  : {stats.format_elapsed()}")
        print(f"  平均速度  : {stats.format_speed()}")
        print(f"  发现匹配  : {len(stats.matches)} 个")
        if stats.matches:
            print("\n  匹配详情:")
            for m in stats.matches:
                print(f"    地址: {m.get('address', 'N/A')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
