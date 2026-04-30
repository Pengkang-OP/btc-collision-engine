#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行参数解析模块

提供 parse_args() 函数，定义所有 CLI 参数。
"""

import argparse
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.i18n import _t

# 从包版本读取版本号
try:
    from src import __version__ as _VERSION
except ImportError:
    _VERSION = "3.1.2"


def parse_args() -> argparse.Namespace:  # noqa: D401
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog="key_collision_cli",
        description=_t("cli.help.description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用示例:
  # 随机碰撞单个地址（CPU）
  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

  # 从文件加载地址，启用 GPU
  python key_collision_cli.py -f targets.txt --use-gpu

  # GPU 范围扫描
  python key_collision_cli.py -f targets.txt --use-gpu -m range --start 1 --end FFFFFFFF

  # 限时 5 分钟运行
  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --duration 300

  # 查看更多示例和使用场景
  python key_collision_cli.py --examples
        """,
    )

    # ── 全局选项（最先处理） ─────────────────────────────────────────────────
    parser.add_argument("--version", action="version", version=f"%(prog)s {_VERSION}")
    parser.add_argument(
        "--config",
        metavar="FILE",
        default=None,
        help="指定配置文件路径，默认使用项目根目录的 config.json",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="详细输出级别，可叠加使用：-v 调试，-vv 含配置详情，-vvv 全部调试",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="静默模式，仅输出最终结果（适合脚本/管道使用）",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        # 遵循 https://no-color.org/ 标准：检测环境变量 NO_COLOR
        default=os.environ.get("NO_COLOR", "") != "",
        help="禁用彩色输出；也可设置环境变量 NO_COLOR=1",
    )

    # 语言选项（需要最先处理）
    lang_group = parser.add_argument_group("语言设置")
    lang_group.add_argument(
        "--language", choices=["zh_CN", "en_US"], default=None, help=_t("cli.options.language")
    )

    # ── 1. 核心参数 ──────────────────────────────────────────────────────────
    core_group = parser.add_argument_group("核心参数", "目标地址、碰撞模式、搜索范围和运行时长")
    target_ex = core_group.add_mutually_exclusive_group(required=False)
    target_ex.add_argument(
        "-t", "--targets", metavar="ADDRESS", nargs="+", help="目标比特币地址，多个地址以空格分隔"
    )
    target_ex.add_argument(
        "-f", "--file", metavar="FILE", help="从文件批量加载目标地址，每行一个，支持 # 注释"
    )
    core_group.add_argument(
        "-m",
        "--mode",
        choices=["random", "range", "brute_force"],
        default="random",
        help="碰撞模式: random 随机, range 范围扫描, brute_force 暴力穷举 (默认: random)",
    )
    core_group.add_argument(
        "--start", metavar="HEX", help="扫描起始私钥（十六进制），range/brute_force 模式必填"
    )
    core_group.add_argument("--end", metavar="HEX", help="扫描结束私钥（十六进制），range 模式必填")
    core_group.add_argument(
        "--duration",
        metavar="SECS",
        type=int,
        default=0,
        help="最长运行秒数，0 表示持续运行直到 Ctrl+C (默认: 0)",
    )

    # ── 2. 功能选项 ──────────────────────────────────────────────────────────
    feature_group = parser.add_argument_group("功能选项", "断点续传、去重过滤等运行时功能")
    feature_group.add_argument(
        "--checkpoint",
        action="store_true",
        default=False,
        help="启用断点续传，中断后重启可从上次进度继续",
    )
    feature_group.add_argument(
        "--checkpoint-interval",
        metavar="SECS",
        type=int,
        default=30,
        help="断点自动保存间隔（秒，范围 5-3600，默认: 30）",
    )
    feature_group.add_argument(
        "--dedup",
        action="store_true",
        default=False,
        help="启用去重过滤，避免重复扫描相同私钥（仅 random 模式有效）",
    )
    feature_group.add_argument(
        "--dedup-max-size",
        metavar="N",
        type=int,
        default=1_000_000,
        help="去重过滤器最大容量（默认: 1,000,000）",
    )

    # ── 3. GPU 加速 ──────────────────────────────────────────────────────────
    gpu_group = parser.add_argument_group(
        "GPU 加速",
        "启用 GPU 加速可将速度提升数千倍（需安装 pyopencl）；--use-gpu 与 --multi-gpu 互斥",
    )
    # --use-gpu 与 --multi-gpu 互斥
    gpu_exclusive = gpu_group.add_mutually_exclusive_group()
    gpu_exclusive.add_argument(
        "--use-gpu", action="store_true", default=False, help="启用单 GPU 加速（需安装 pyopencl）"
    )
    gpu_exclusive.add_argument(
        "--multi-gpu",
        action="store_true",
        default=False,
        help="启用多 GPU 模式，自动使用所有可用 GPU（与 --use-gpu 互斥）",
    )
    gpu_group.add_argument(
        "--gpu-device",
        metavar="INDEX",
        type=int,
        default=-1,
        help="指定 GPU 设备索引，-1 自动选择最优设备 (默认: -1)",
    )
    gpu_group.add_argument(
        "--gpu-batch-size",
        metavar="N",
        type=int,
        default=None,
        help="GPU 每批处理私钥数，留空则根据显存自动计算 (默认: 自动)",
    )
    gpu_group.add_argument(
        "--gpu-count",
        metavar="N",
        type=int,
        default=-1,
        help="多 GPU 模式下使用的 GPU 数量，-1 使用全部 (默认: -1)",
    )
    gpu_group.add_argument(
        "--gpu-indices",
        metavar="IDX",
        type=int,
        nargs="+",
        default=None,
        help="手动指定多 GPU 索引，例如: --gpu-indices 0 1 (默认: 自动选择)",
    )

    # ── 4. 性能调优 ──────────────────────────────────────────────────────────
    perf_group = parser.add_argument_group(
        "性能调优", "工作线程、进度刷新频率及 v2.2.0+ 引擎优化开关"
    )
    perf_group.add_argument(
        "--workers",
        metavar="N",
        type=int,
        default=None,
        help="CPU 工作线程数 (默认: 自动，等于逻辑核心数)",
    )
    perf_group.add_argument(
        "--progress-interval",
        metavar="SECS",
        type=float,
        default=5.0,
        help="进度刷新间隔（秒，默认: 5）",
    )
    perf_group.add_argument(
        "--no-optimize",
        action="store_true",
        default=False,
        help="禁用引擎性能优化，使用标准模式（调试用）",
    )
    perf_group.add_argument(
        "--window-size",
        metavar="N",
        type=int,
        default=8,
        help="EC 预计算表窗口大小，范围 4-8 (默认: 8)",
    )
    perf_group.add_argument(
        "--no-simd", action="store_true", default=False, help="禁用 SIMD 哈希优化（调试用）"
    )
    perf_group.add_argument(
        "--no-memory-pool", action="store_true", default=False, help="禁用内存池优化（调试用）"
    )

    # ── 5. 工具命令 ──────────────────────────────────────────────────────────
    util_group = parser.add_argument_group(
        "工具命令", "独立功能命令，指定后直接执行并退出，不启动碰撞引擎"
    )
    util_group.add_argument(
        "--validate-addresses",
        metavar="FILE",
        default=None,
        help="校验地址文件中所有比特币地址格式是否合法，输出报告后退出",
    )
    util_group.add_argument(
        "--health-check",
        action="store_true",
        default=False,
        help="检查系统依赖、配置及磁盘状态，输出健康报告后退出",
    )
    util_group.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="清理过期临时文件和历史日志（加 --dry-run 可预览，不实际删除）",
    )
    util_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="与 --cleanup 配合使用，仅预览待删除文件，不实际删除",
    )
    util_group.add_argument(
        "--platform-check",
        action="store_true",
        default=False,
        help="检查跨平台兼容性（路径、编码、磁盘空间等），输出报告后退出",
    )
    util_group.add_argument(
        "--quick-start",
        action="store_true",
        default=False,
        help="启动交互式引导向导，帮助新手快速上手",
    )
    util_group.add_argument(
        "--quick-run",
        action="store_true",
        default=False,
        help="快速模式：使用默认配置直接启动（需要targets.txt文件）",
    )
    util_group.add_argument(
        "--compact", action="store_true", default=False, help="紧凑模式：在向导中跳过详细帮助信息"
    )
    util_group.add_argument(
        "--examples", action="store_true", default=False, help="显示常用命令示例后退出"
    )
    util_group.add_argument(
        "--config-check",
        action="store_true",
        default=False,
        help="验证 config.json 配置文件的结构和有效性后退出",
    )
    util_group.add_argument(
        "--template",
        metavar="NAME",
        default=None,
        help="从预设模板生成 config.json，可选: gpu-performance, long-running, gpu-multi, quick-test",
    )
    util_group.add_argument(
        "--export-progress",
        metavar="FILE",
        default=None,
        help="运行结束后将进度数据导出为 JSON 文件",
    )
    util_group.add_argument(
        "--export-matches",
        metavar="FILE",
        default=None,
        help="将本次运行的匹配结果导出为 JSON 文件",
    )
    util_group.add_argument(
        "--recommend",
        action="store_true",
        default=False,
        help="根据当前系统和目标数量，推荐最优参数配置后退出",
    )
    util_group.add_argument(
        "--sensitive-mode",
        choices=["full", "masked", "hash_only"],
        default="full",
        help="私钥输出模式: full 完整, masked 部分脱敏, hash_only 仅哈希 (默认: full)",
    )
    util_group.add_argument(
        "--migrate-config",
        action="store_true",
        default=False,
        help="将旧版 config.json 迁移至最新格式（自动备份原文件）后退出",
    )

    return parser.parse_args()
