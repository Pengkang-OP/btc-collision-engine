#!/usr/bin/env python3
"""
CLI工具命令模块

包含:
- _cmd_validate_addresses: 批量验证文件中所有比特币地址
- _cmd_examples: 显示常用使用示例
- _cmd_config_check: 检查配置文件状态
- _cmd_quick_start: 交互式快速引导
"""

import argparse
import concurrent.futures
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.cli.constants import (
    CONFIG_EXAMPLE_FILE,
    CONFIG_FILE_NAME,
    REQUIRED_CONFIG_SECTIONS,
    SEPARATOR_DASHED,
    SEPARATOR_DASHED_SHORT,
    SEPARATOR_EQUAL,
    WIZARD_MARKER_PATH,
)
from src.cli.output import CLIOutput
from src.cli.validation import validate_file_path
from src.i18n import _t
from src.utils.platform_utils import PlatformUtils

logger = logging.getLogger(__name__)

# 快速模式默认配置常量
QUICK_RUN_DEFAULTS: dict[str, Any] = {
    "target_file": "targets.txt",
    "mode": "random",
    "checkpoint": True,
    "dedup": True,
    "duration": 0,  # 0表示不限制
    "countdown_seconds": 3,  # 倒计时秒数
}

# 预览配置常量
PREVIEW_CONFIG = {
    "max_preview_addresses": 3,  # 最多预览地址数
    "max_address_display_length": 20,  # 地址显示最大长度
}


def _cmd_validate_addresses(file_path: str) -> None:
    """--validate-addresses 命令实现：批量验证文件中所有比特币地址"""
    # 路径安全验证：防止路径遍历攻击
    if not validate_file_path(file_path):
        return
    target_path = Path(file_path)
    if not target_path.exists():
        print(_t("errors.file_not_found", path=file_path), file=sys.stderr)
        sys.exit(1)

    # 尝试导入地址验证器
    try:
        from src.collision.targets.validator import AddressBatchValidator
    except ImportError:
        from ..collision.targets.validator import AddressBatchValidator

    print(f"[BTC地址验证] 文件: {file_path}")
    print(SEPARATOR_DASHED_SHORT)

    # 读取文件
    lines = []
    try:
        with open(target_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        logger.error(_t("errors.io_error", detail=str(exc)))
        print(_t("errors.io_error", detail=str(exc)), file=sys.stderr)
        sys.exit(1)

    addresses = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            addresses.append(stripped)

    if not addresses:
        print(_t("common.warning") + ": " + _t("address.no_match"))
        sys.exit(0)

    # 执行批量验证
    validator = AddressBatchValidator()
    results_dict = validator.validate_batch(addresses)

    valid_list = [r for r in results_dict.values() if r.valid]
    invalid_list = [r for r in results_dict.values() if r.validated and not r.valid]
    skipped_list = [r for r in results_dict.values() if not r.validated]

    print(f"总地址数  : {len(addresses)}")
    print(f"[OK] 有效    : {len(valid_list)}")
    print(f"[!]  无效    : {len(invalid_list)}")
    print(f"[--] 跳过    : {len(skipped_list)}")
    print(SEPARATOR_DASHED_SHORT)

    if valid_list:
        print("\n有效地址示例（最多显示 5 个）:")
        for r in valid_list[:5]:
            fmt = getattr(r, "format_type", "unknown") or "unknown"
            print(f"  [OK] {r.address}  [{fmt}]")

    if invalid_list:
        print("\n无效地址（最多显示 10 个）:")
        for r in invalid_list[:10]:
            err = getattr(r, "error", "") or ""
            print(f"  [!]  {r.address}  原因: {err}")

    print(SEPARATOR_DASHED_SHORT)
    valid_rate = len(valid_list) / len(addresses) * 100 if addresses else 0
    print(f"有效率: {valid_rate:.1f}%")
    if valid_rate < 100:
        print(_t("common.warning") + ": " + _t("cli.commands.invalid_addresses_warning"))


def _cmd_examples() -> None:
    """--examples 命令实现：显示常用使用示例"""
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    print(SEPARATOR_EQUAL)
    print("[Examples] " + _t("cli.commands.examples_title"))
    print(SEPARATOR_EQUAL)

    examples = [
        {
            "title": "1. 快速模式 (推荐新手)",
            "desc": "使用默认配置直接启动（需要targets.txt文件）",
            "cmd": "python key_collision_cli.py --quick-run",
        },
        {
            "title": "2. 基础随机碰撞",
            "desc": "最简单的使用方式，持续运行直到 Ctrl+C",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random",
        },
        {
            "title": "3. 断点续传（推荐）",
            "desc": "启用断点续传和去重，运行1小时后自动停止",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --checkpoint --dedup --duration 3600",  # noqa: E501
        },
        {
            "title": "4. 从文件加载目标",
            "desc": "从文件读取多个目标地址",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --checkpoint",
        },
        {
            "title": "5. GPU加速模式",
            "desc": "启用单GPU加速（速度提升数千倍）",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --use-gpu",
        },
        {
            "title": "6. 多GPU模式",
            "desc": "使用所有可用GPU设备",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --multi-gpu",
        },
        {
            "title": "7. 范围扫描",
            "desc": "在指定私钥范围内搜索",
            "cmd": "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m range --start 1 --end FFFFFFFF",  # noqa: E501
        },
        {
            "title": "8. 交互式向导",
            "desc": "逐步引导配置，适合新手",
            "cmd": "python key_collision_cli.py --quick-start",
        },
        {
            "title": "9. 系统健康检查",
            "desc": "检查系统依赖和配置状态",
            "cmd": "python key_collision_cli.py --health-check",
        },
        {
            "title": "10. 验证地址文件",
            "desc": "批量验证文件中的地址格式",
            "cmd": "python key_collision_cli.py --validate-addresses targets.txt",
        },
    ]

    for ex in examples:
        print(f"\n{ex['title']}")
        print(f"   {ex['desc']}")
        print(f"   $ {ex['cmd']}")

    print("\n" + SEPARATOR_EQUAL)
    print("[TIP] " + _t("cli.commands.examples_tips_title") + ":")
    print("   - " + _t("cli.commands.tip_quick_start"))
    print("   - " + _t("cli.commands.tip_help"))
    print("   - " + _t("cli.commands.tip_config_check"))

    print("\n" + SEPARATOR_DASHED)
    print("[快捷命令别名]")
    print("   qs      = --quick-start  (交互式向导)")
    print("   qr      = --quick-run    (快速模式)")
    print("   hc      = --health-check (健康检查)")
    print("   cc      = --config-check (配置验证)")
    print("   ex      = --examples     (显示示例)")
    print("   rec     = --recommend    (参数推荐)")
    print(SEPARATOR_DASHED)
    print("提示: Windows 用户也可双击 start.bat 启动菜单式快速入口")
    print("      start_engine.bat 提供一键交互式向导")
    print(SEPARATOR_EQUAL)


def _cmd_config_check() -> None:
    """--config-check 命令实现：检查配置文件状态"""
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    config_path = Path(CONFIG_FILE_NAME)
    example_path = Path(CONFIG_EXAMPLE_FILE)

    print(SEPARATOR_EQUAL)
    print("[Config Check] " + _t("cli.commands.config_check_title"))
    print(SEPARATOR_EQUAL)

    # 检查配置文件存在性
    if config_path.exists():
        print("\n[OK] config.json " + _t("cli.commands.file_exists"))

        # 验证JSON格式
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            print("[OK] " + _t("cli.commands.json_valid"))

            # 基本结构验证
            missing_sections = [s for s in REQUIRED_CONFIG_SECTIONS if s not in config]

            if missing_sections:
                print(
                    "[WARN] "
                    + _t("cli.commands.missing_sections")
                    + ": "
                    + ", ".join(missing_sections)
                )
            else:
                print("[OK] " + _t("cli.commands.sections_complete"))

            # 显示关键配置信息
            print("\n[INFO] Key config:")
            collision_cfg = config.get("collision", {})
            engine_cfg = config.get("engine", {})
            workers = collision_cfg.get("max_workers", engine_cfg.get("max_threads", "auto"))
            print("   - workers        : " + str(workers))
            print(
                "   - perf_optimize  : "
                + (
                    "enabled"
                    if collision_cfg.get("use_performance_optimization", True)
                    else "disabled"
                )
            )
            chk = collision_cfg.get(
                "checkpoint_interval", engine_cfg.get("checkpoint_interval", 30)
            )
            print("   - checkpoint_int : " + str(chk) + "s")

            gpu_cfg = config.get("gpu", {})
            print("   - GPU mode       : " + gpu_cfg.get("mode", "auto"))

        except json.JSONDecodeError as e:
            print("[ERROR] " + _t("config.invalid", error=str(e)))
            print("[TIP]   " + _t("cli.commands.fix_copy_example"))
        except Exception as e:
            logger.error(_t("errors.io_error", detail=str(e)))
            print("[ERROR] " + _t("errors.io_error", detail=str(e)))
    else:
        print("\n[MISS] config.json " + _t("cli.commands.file_not_exist"))
        if example_path.exists():
            print("[OK]   config.example.json " + _t("cli.commands.file_exists"))
            print("[TIP]  " + _t("cli.commands.fix_copy_suggestion"))
            print("   Windows: copy config.example.json config.json")
            print("   Linux/Mac: cp config.example.json config.json")
        else:
            print("[MISS] config.example.json " + _t("cli.commands.also_not_exist"))
            print("[TIP]  " + _t("cli.commands.fix_reacquire"))

    # 检查必要目录
    print("\n[INFO] " + _t("cli.commands.dir_check_title") + ":")
    required_dirs = ["logs", "data_logs", "monitoring_data"]
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print("   [OK]  " + dir_name + "/")
        else:
            print("   [MISS] " + dir_name + "/ (" + _t("cli.commands.dir_not_exist") + ")")
            print("          " + _t("cli.commands.dir_fix") + ": mkdir " + dir_name)

    print("\n" + SEPARATOR_EQUAL)


DEFAULT_TARGETS_FILE = "targets.txt"


def _save_address_to_targets_file(address: str, output) -> None:
    """将单个地址去重合并写入 targets.txt。
    - 读取现有地址，若地址已存在则跳过；否则追加到文件末尾。
    - 若文件不存在则自动创建。
    - 使用文件锁实现跨进程安全。
    """
    targets_path = Path(DEFAULT_TARGETS_FILE)
    lock_path = targets_path.with_suffix(".lock")
    existing: set = set()

    # 使用文件锁实现跨进程安全
    lock_file = None
    try:
        import os
        import sys

        # 根据平台选择文件锁实现
        if sys.platform == "win32":
            import msvcrt

            # Windows: 使用独占锁
            lock_file = open(lock_path, "w")
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            # Unix/Linux: 使用 flock
            lock_file = open(lock_path, "w")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        # 读取已有地址
        if targets_path.exists():
            try:
                with open(targets_path, encoding="utf-8-sig", errors="ignore") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            existing.add(stripped)
            except OSError:
                pass

        if address in existing:
            output.print("   [INFO] 地址已存在于 targets.txt，无需重复添加")
            return

        # 将新地址追加到文件
        if not targets_path.exists():
            with open(targets_path, "w", encoding="utf-8") as f:
                f.write("# BTC 目标地址列表\n")
                f.write("# 每行一个地址，支持 # 注释行\n")
                f.write("# 支持 P2PKH (1开头)、P2SH (3开头)、Bech32 (bc1开头) 格式\n#\n")

        # 读取最新内容并追加新地址
        with open(targets_path, encoding="utf-8") as f:
            content = f.read()

        # 追加新地址
        content += address + "\n"

        # 写入临时文件
        temp_path = targets_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 原子替换
        os.replace(temp_path, targets_path)

        output.print(
            "   [green][OK] 地址已保存到 targets.txt（共 "
            + str(len(existing) + 1)
            + " 条）[/green]"
        )
    except OSError as e:
        output.warning("无法写入 targets.txt: " + str(e))
    finally:
        # 释放文件锁
        if lock_file:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass


def _quick_start_select_target(compact: bool = False) -> tuple[list[str], str | None]:
    """步骤1: 选择目标地址来源。返回 (targets_list, target_file)

    Args:
        compact: 紧凑模式，跳过详细帮助信息
    """
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 1/4】[/bold cyan] " + _t("cli.commands.step1_title"))
    output.print("   1. " + _t("cli.commands.step1_single"))
    output.print("   2. " + _t("cli.commands.step1_file"))

    # 紧凑模式下跳过详细帮助信息
    if not compact:
        output.print("\n   [?] " + _t("cli.commands.help_address_formats"))
        output.print("      - P2PKH: " + _t("cli.commands.help_p2pkh"))
        output.print("      - P2SH: " + _t("cli.commands.help_p2sh"))
        output.print("      - Bech32: " + _t("cli.commands.help_bech32") + "\n")
    else:
        output.print("")  # 简单换行
    while True:
        target_type = input("   " + _t("cli.commands.step1_prompt") + " ").strip()
        if target_type in ("1", "2"):
            break
        output.error("请输入 1 或 2")

    targets: list[str] = []
    target_file: str | None = None

    if target_type == "1":
        address = input("   " + _t("cli.commands.input_address") + ": ").strip()
        if not address:
            output.error(_t("cli.commands.address_empty"))
            return [], None
        targets = [address]
        # 将新地址去重合并写入 targets.txt
        _save_address_to_targets_file(address, output)
    elif target_type == "2":
        target_file = input("   " + _t("cli.commands.input_file_path") + ": ").strip()
        if not target_file:
            target_file = "targets.txt"
            output.print("   [INFO] 使用默认文件: targets.txt")
        if not Path(target_file).exists():
            output.warning(_t("errors.file_not_found", path=target_file))
            output.print("   1. " + _t("cli.commands.create_example_file"))
            output.print("   2. 手动输入地址")
            output.print("   3. 返回重新选择")
            while True:
                choice = input("   请选择 [1/2/3]: ").strip()
                if choice in ("1", "2", "3"):
                    break
                output.error("请输入 1、2 或 3")
            if choice == "1":
                try:
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write("# 目标地址文件\n")
                        f.write("# 每行一个地址，支持 # 注释\n")
                        f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
                    output.success(_t("cli.commands.example_file_created", path=target_file))
                    output.print("   [TIP] " + _t("cli.commands.example_file_tip"))
                    # 继续使用创建的文件
                    valid_count = 1
                    output.success(
                        _t(
                            "cli.commands.addresses_loaded",
                            count=str(valid_count),
                            path=Path(target_file).name,
                        )
                    )
                    return [], target_file
                except Exception as e:
                    output.error(f"创建文件失败: {str(e)}")
                    output.print("   [TIP] 请检查文件路径是否正确，以及是否有写入权限")
                    return [], None
            elif choice == "2":
                address = input("   请输入目标地址: ").strip()
                if not address:
                    output.error(_t("cli.commands.address_empty"))
                    return [], None
                targets = [address]
                target_file = None
            else:
                # 选3或其他：返回重新选择
                return _quick_start_select_target()
        else:
            # 文件存在：统计有效地址行数并给予反馈
            valid_count = 0
            truncated = False
            MAX_SCAN_LINES = 50000
            file_basename = Path(target_file).name
            try:
                for enc in ("utf-8", "gbk", "latin-1"):
                    try:
                        with open(target_file, encoding=enc, errors="ignore") as f:
                            for i, line in enumerate(f):
                                if i >= MAX_SCAN_LINES:
                                    truncated = True
                                    break
                                stripped = line.strip()
                                if stripped and not stripped.startswith("#"):
                                    valid_count += 1
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
            except Exception as e:
                output.error(f"读取文件失败: {str(e)}")
                output.print("   [TIP] 请检查文件路径是否正确，以及是否有读取权限")
                return [], None
            if valid_count == 0:
                output.warning(_t("cli.commands.no_valid_addresses", path=file_basename))
                output.print("   " + _t("cli.commands.file_format_hint"))
                return [], None
            else:
                count_display = f"{valid_count}+" if truncated else str(valid_count)
                output.success(
                    _t("cli.commands.addresses_loaded", count=count_display, path=file_basename)
                )
    else:
        output.error(_t("errors.invalid_input", detail=target_type))
        return [], None

    return targets, target_file


def _quick_start_select_mode(compact: bool = False) -> tuple[str, str | None, str | None]:
    """步骤2: 选择碰撞模式。返回 (mode, start_key, end_key)

    Args:
        compact: 紧凑模式，跳过详细帮助信息
    """
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 2/4】[/bold cyan] " + _t("cli.commands.step2_title"))
    output.print("   1. random    - " + _t("cli.commands.mode_random_desc"))
    output.print("   2. range     - " + _t("cli.commands.mode_range_desc"))
    output.print("   3. brute_force - " + _t("cli.commands.mode_brute_desc"))

    # 紧凑模式下跳过详细帮助信息
    if not compact:
        output.print("\n   [?] " + _t("cli.commands.help_mode_description"))
        output.print("      - random: " + _t("cli.commands.help_mode_random_detail"))
        output.print("      - range: " + _t("cli.commands.help_mode_range_detail"))
        output.print("      - brute_force: " + _t("cli.commands.help_mode_brute_detail") + "\n")
    else:
        output.print("")
    while True:
        mode_choice = input("   " + _t("cli.commands.step2_prompt") + " (推荐: 1): ").strip()
        if mode_choice == "":
            mode_choice = "1"
            break
        if mode_choice in ("1", "2", "3"):
            break
        output.error("请输入 1、2 或 3")

    mode_map = {"1": "random", "2": "range", "3": "brute_force"}
    mode = mode_map.get(mode_choice, "random")

    start_key: str | None = None
    end_key: str | None = None

    if mode in ["range", "brute_force"]:
        while True:
            start_key = (
                input("   " + _t("cli.commands.input_start_key") + " (hex): ").strip() or "1"
            )
            if all(c in "0123456789abcdefABCDEF" for c in start_key):
                break
            output.error("请输入有效的十六进制字符串")
        if mode == "range":
            while True:
                end_key = (
                    input("   " + _t("cli.commands.input_end_key") + " (hex): ").strip()
                    or "FFFFFFFF"
                )
                if all(c in "0123456789abcdefABCDEF" for c in end_key):
                    break
                output.error("请输入有效的十六进制字符串")

    return mode, start_key, end_key


def _quick_start_select_options(compact: bool = False) -> tuple[bool, bool, int]:
    """步骤3: 选择功能选项。返回 (checkpoint, dedup, duration)

    Args:
        compact: 紧凑模式，跳过详细帮助信息
    """
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 3/4】[/bold cyan] " + _t("cli.commands.step3_title"))

    # 紧凑模式下跳过详细帮助信息
    if not compact:
        output.print("\n   [?] " + _t("cli.commands.help_feature_description"))
        output.print("      - checkpoint: " + _t("cli.commands.help_checkpoint"))
        output.print("      - dedup: " + _t("cli.commands.help_dedup"))
        output.print("      - duration: " + _t("cli.commands.help_duration") + "\n")
    else:
        output.print("")

    # 启用断点续传（默认Y）
    while True:
        cp = input("   " + _t("cli.commands.enable_checkpoint") + " (推荐: Y): ").strip().lower()
        if cp == "":
            checkpoint = True
            break
        if cp in ("y", "n"):
            checkpoint = cp == "y"
            break
        output.error("请输入 y 或 n")

    # 启用去重过滤（默认Y）
    while True:
        dd = input("   " + _t("cli.commands.enable_dedup") + " (推荐: Y): ").strip().lower()
        if dd == "":
            dedup = True
            break
        if dd in ("y", "n"):
            dedup = dd == "y"
            break
        output.error("请输入 y 或 n")

    # 运行时长选项（天、小时、无限）
    output.print("   运行时长选项:")
    output.print("   1. 无限（默认）")
    output.print("   2. 指定小时")
    output.print("   3. 指定天")
    while True:
        time_choice = input("   请选择 [1/2/3] (推荐: 1): ").strip()
        if time_choice == "":
            duration = 0
            break
        if time_choice == "1":
            duration = 0
            break
        elif time_choice == "2":
            while True:
                hours_str = input("   请输入小时数: ").strip()
                try:
                    hours = int(hours_str)
                    if hours <= 0:
                        output.error("小时数必须大于0")
                        continue
                    duration = hours * 3600
                    break
                except ValueError:
                    output.error("请输入整数")
            break
        elif time_choice == "3":
            while True:
                days_str = input("   请输入天数: ").strip()
                try:
                    days = int(days_str)
                    if days <= 0:
                        output.error("天数必须大于0")
                        continue
                    duration = days * 24 * 3600
                    break
                except ValueError:
                    output.error("请输入整数")
            break
        else:
            output.error("请输入 1、2 或 3")

    return checkpoint, dedup, duration


def _detect_gpu_devices() -> list[dict]:
    """检测可用的GPU设备，失败时返回空列表"""
    try:
        from src.gpu.device import GPUDeviceDetector

        devices = GPUDeviceDetector.detect_devices()
        return devices
    except Exception as e:
        logger.warning(f"GPU device detection failed: {e}")
        return []


def _format_device_label(device: dict, index: int) -> str:
    """格式化设备显示标签，包含名称和显存"""
    name = device.get("name", f"GPU #{index}")
    mem_size = device.get("global_mem_size", 0)
    if mem_size and mem_size > 0:
        mem_gb = mem_size / (1024**3)
        if mem_gb >= 1.0:
            mem_str = f"{mem_gb:.0f}GB"
        else:
            mem_mb = mem_size / (1024**2)
            mem_str = f"{mem_mb:.0f}MB"
        return f"{name} ({mem_str})"
    return name


def _detect_gpu_devices_with_timeout(timeout: float = 5.0) -> list[dict]:
    """带超时的 GPU 检测，超时返回空列表"""
    output = CLIOutput.get_instance()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_detect_gpu_devices)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            output.warning(f"GPU 检测超时（{timeout:.0f}秒），已跳过")
            return []


def _quick_start_select_gpu() -> list[str]:
    """步骤4: 选择GPU加速模式。返回额外的命令行参数列表"""
    output = CLIOutput.get_instance()

    # 预先检测 GPU，决定默认选项
    output.print("\n[bold cyan]【步骤 4/4】[/bold cyan] " + _t("cli.commands.step4_title"))
    output.print("   [INFO] 正在检测可用 GPU 设备（最多等待 5 秒）...")
    detected_devices = _detect_gpu_devices_with_timeout(timeout=5.0)

    if detected_devices:
        gpu_count = len(detected_devices)
        labels_preview = ", ".join(
            _format_device_label(d, i) for i, d in enumerate(detected_devices[:2])
        )
        if gpu_count > 2:
            labels_preview += f" 等{gpu_count}个"
        output.success(f"检测到 {gpu_count} 个 GPU 设备: {labels_preview}")
        default_choice = "2"  # 有 GPU 时默认单 GPU
    else:
        output.warning("未检测到可用 GPU 设备")
        default_choice = "1"  # 无 GPU 时默认 CPU

    output.print("   1. " + _t("cli.commands.mode_cpu"))
    output.print("   2. " + _t("cli.commands.mode_single_gpu"))
    output.print("   3. " + _t("cli.commands.mode_multi_gpu"))
    while True:
        gpu_choice = input(
            "   " + _t("cli.commands.step4_prompt") + f" (推荐: {default_choice}): "
        ).strip()
        if gpu_choice in ("1", "2", "3"):
            break
        output.error("请输入 1、2 或 3")

    gpu_args: list[str] = []

    if gpu_choice == "2":
        # 单GPU模式：使用已检测到的设备
        devices = detected_devices

        if not devices:
            output.warning("未检测到可用 GPU 设备（可能缺少 OpenCL 驱动）")
            output.print("   [INFO] GPU 模式需要安装 pyopencl 和相应的驱动")
            output.print("   [INFO] 请参考文档安装 GPU 驱动和依赖")
            fallback = input("   是否仍然尝试 GPU 模式？[y/N]: ").strip().lower()
            if fallback == "y":
                output.warning("警告：在无 GPU 设备的情况下尝试 GPU 模式可能会导致运行时错误")
                gpu_args.append("--use-gpu")
            else:
                output.success("已回退到 CPU 模式")
        elif len(devices) == 1:
            label = _format_device_label(devices[0], 0)
            output.success(f"将使用 GPU: {label}")
            gpu_args.extend(["--use-gpu", "--gpu-device", "0"])
        else:
            output.print("   检测到以下 GPU 设备:")
            for i, dev in enumerate(devices):
                label = _format_device_label(dev, i)
                output.print(f"     {i + 1}. {label}")
            default_idx = 1  # 默认选择第一个设备
            raw = input(
                f"   请选择 GPU 设备 [1-{len(devices)}，直接回车=选择第一个]: "
            ).strip() or str(default_idx)
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(devices):
                    label = _format_device_label(devices[idx], idx)
                    output.success(f"已选择: {label}")
                    gpu_args.extend(["--use-gpu", "--gpu-device", str(idx)])
                else:
                    output.error(f"无效设备编号: {raw}（有效范围 1-{len(devices)}）")
                    output.warning("将使用第一个 GPU 设备")
                    label = _format_device_label(devices[0], 0)
                    output.success(f"已选择: {label}")
                    gpu_args.extend(["--use-gpu", "--gpu-device", "0"])
            except ValueError:
                output.error(f"无效输入: {raw}")
                output.warning("将使用第一个 GPU 设备")
                label = _format_device_label(devices[0], 0)
                output.success(f"已选择: {label}")
                gpu_args.extend(["--use-gpu", "--gpu-device", "0"])

    elif gpu_choice == "3":
        # 多GPU模式：使用已检测到的设备
        devices = detected_devices

        if not devices:
            output.warning("未检测到可用 GPU 设备（可能缺少 OpenCL 驱动）")
            output.print("   [INFO] GPU 模式需要安装 pyopencl 和相应的驱动")
            output.print("   [INFO] 请参考文档安装 GPU 驱动和依赖")
            fallback = input("   是否仍然尝试多GPU模式？[y/N]: ").strip().lower()
            if fallback == "y":
                output.warning("警告：在无 GPU 设备的情况下尝试多GPU模式可能会导致运行时错误")
                gpu_args.append("--multi-gpu")
            else:
                output.success("已回退到 CPU 模式")
        elif len(devices) == 1:
            label = _format_device_label(devices[0], 0)
            output.success(f"检测到 GPU: {label}，将使用此设备")
            gpu_args.extend(["--use-gpu", "--gpu-device", "0"])
        else:
            output.print("   检测到以下 GPU 设备:")
            for i, dev in enumerate(devices):
                label = _format_device_label(dev, i)
                output.print(f"     {i + 1}. {label}")
            default_indices = " ".join(str(i + 1) for i in range(len(devices)))
            raw = (
                input("   请选择要使用的 GPU 设备编号（空格分隔，如 1 2，直接回车=全部）: ").strip()
                or default_indices
            )
            selected_indices: list[int] = []
            valid = True
            for part in raw.split():
                try:
                    n = int(part) - 1
                    if 0 <= n < len(devices):
                        selected_indices.append(n)
                    else:
                        output.error(f"无效设备编号: {part}（有效范围 1-{len(devices)}）")
                        valid = False
                        break
                except ValueError:
                    output.error(f"无效输入: {part}")
                    valid = False
                    break

            if valid and selected_indices:
                labels = ", ".join(_format_device_label(devices[i], i) for i in selected_indices)
                output.success(f"已选择: {labels}")
                gpu_args.append("--multi-gpu")
                if selected_indices:  # 非空时才追加 --gpu-indices
                    gpu_args.append("--gpu-indices")
                    gpu_args.extend(str(i) for i in selected_indices)
            else:
                output.warning("选择无效，将使用所有 GPU 设备")
                gpu_args.append("--multi-gpu")

    return gpu_args


def _cmd_quick_run(executor: Callable[[], None] | None = None) -> None:
    """--quick-run 命令实现：快速模式，跳过向导直接使用默认配置运行"""
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    output = CLIOutput.get_instance()
    output.header("BTC碰撞引擎 - 快速模式")

    try:
        # 使用默认配置快速启动
        output.print("\n[bold cyan]使用默认配置快速启动...[/bold cyan]\n")

        # 默认目标：检查targets.txt是否存在
        target_file = str(QUICK_RUN_DEFAULTS["target_file"])
        targets: list[str] = []  # noqa: F841
        target_file_exists = Path(target_file).exists()

        if target_file_exists:
            # 统计文件中的地址数量并预览
            address_count = 0
            preview_addresses: list[str] = []
            max_preview = PREVIEW_CONFIG["max_preview_addresses"]
            max_display_len = PREVIEW_CONFIG["max_address_display_length"]
            try:
                with open(target_file, encoding="utf-8") as f:
                    for _line_num, line in enumerate(f, 1):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            address_count += 1
                            if len(preview_addresses) < max_preview:
                                preview_addresses.append(stripped)
            except Exception as e:
                output.error(f"读取文件失败: {str(e)}")
                return

            if address_count == 0:
                output.warning(f"{target_file} 中没有有效的目标地址")
                output.print("\n[TIP] 请先在文件中添加目标地址，或使用以下命令:")
                output.print(
                    "  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random\n"
                )
                return

            output.success(f"发现目标文件: {target_file} ({address_count} 个地址)")

            # 显示地址预览
            if preview_addresses:
                output.print("\n[bold yellow]地址预览:[/bold yellow]")
                for i, addr in enumerate(preview_addresses, 1):
                    # 截断长地址显示
                    display_addr = (
                        addr[:max_display_len] + "..." if len(addr) > max_display_len else addr
                    )
                    output.print(f"  {i}. {display_addr}")
                if address_count > max_preview:
                    output.print(f"  ... 及其他 {address_count - max_preview} 个地址")
                output.print("")

            cmd_parts: list[str] = ["python", "key_collision_cli.py", "-f", target_file]
        else:
            output.warning(f"未找到 {target_file}，请使用 -t 或 -f 指定目标")
            output.print("\n[TIP] 快速模式示例:")
            output.print(
                "  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random"
            )
            output.print("  python key_collision_cli.py -f targets.txt --use-gpu\n")
            return

        # 默认配置：使用常量配置
        cmd_parts.extend(["-m", str(QUICK_RUN_DEFAULTS["mode"])])
        if QUICK_RUN_DEFAULTS["checkpoint"]:
            cmd_parts.append("--checkpoint")
        if QUICK_RUN_DEFAULTS["dedup"]:
            cmd_parts.append("--dedup")

        # 构建配置摘要
        config_summary = {
            "目标文件": target_file,
            "碰撞模式": (
                "随机模式" if QUICK_RUN_DEFAULTS["mode"] == "random" else QUICK_RUN_DEFAULTS["mode"]
            ),
            "断点续传": "启用" if QUICK_RUN_DEFAULTS["checkpoint"] else "禁用",
            "去重过滤": "启用" if QUICK_RUN_DEFAULTS["dedup"] else "禁用",
            "运行时长": (
                "不限制"
                if QUICK_RUN_DEFAULTS["duration"] == 0
                else f"{QUICK_RUN_DEFAULTS['duration']}分钟"
            ),
            "加速模式": "CPU 模式",
        }

        output.print("\n[bold yellow]默认配置:[/bold yellow]")
        for key, value in config_summary.items():
            output.print(f"  {key}: {value}")

        # 询问是否执行（使用可配置的倒计时）
        countdown: int = QUICK_RUN_DEFAULTS["countdown_seconds"]
        output.print(f"\n[bold green]{countdown}秒后自动开始... (按Ctrl+C取消)[/bold green]")
        try:
            import time

            for i in range(countdown, 0, -1):
                output.print(f"  {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            output.warning("已取消")
            return

        # 执行命令
        output.header(_t("cli.messages.starting"))
        if executor is not None:
            argv = list(cmd_parts)
            if argv and argv[0].lower() in ("python", "python3", "python.exe", "python3.exe"):
                argv = argv[1:]
            # 备份原始argv，确保执行后恢复
            original_argv = sys.argv
            try:
                sys.argv = argv
                executor()
            finally:
                sys.argv = original_argv  # 确保恢复原始argv
        else:
            output.print("\n请手动运行: " + " ".join(cmd_parts))

    except KeyboardInterrupt:
        output.warning(_t("errors.keyboard_interrupt"))
    except Exception as e:
        output.error(_t("errors.unexpected", error=str(e)))


def _quick_start_build_and_run(
    cmd_parts: list[str],
    executor: Callable[[], None] | None,
    config_summary: dict | None = None,
) -> None:
    """构建并（可选）执行生成的命令"""
    output = CLIOutput.get_instance()

    cmd_str = " ".join(cmd_parts)

    # 使用 Rich 面板展示配置确认
    if config_summary:
        output.print("")
        output.startup_panel(config_summary)

    output.print("")
    output.rule("[bold green]" + _t("cli.commands.generated_cmd") + "[/bold green]", style="green")
    output.print(f"\n[bold yellow]{cmd_str}[/bold yellow]\n")

    # 询问是否执行（默认 y）
    while True:
        execute = (
            input(_t("cli.commands.execute_now") + " [y/n] (推荐: Y，直接回车=Y): ").strip().lower()
            or "y"
        )
        if execute in ("y", "n"):
            break
        output.error("请输入 y 或 n")
    if execute != "n":
        output.header(_t("cli.messages.starting"))

        if executor is not None:
            # 始终使用 key_collision_cli.py，去掉 "python" 前缀部分
            argv = list(cmd_parts)
            if argv and argv[0].lower() in ("python", "python3", "python.exe", "python3.exe"):
                argv = argv[1:]
            # 备份原始argv，确保执行后恢复
            original_argv = sys.argv
            try:
                sys.argv = argv
                executor()
            finally:
                sys.argv = original_argv  # 确保恢复原始argv
        else:
            output.print("\n" + _t("cli.commands.copy_and_run"))
    else:
        output.print("\n[TIP] " + _t("cli.commands.tip_copy_cmd"))
        output.print("   " + _t("cli.commands.tip_help_cmd"))


def _cmd_quick_start(executor: Callable[[], None] | None = None, compact: bool = False) -> None:
    """--quick-start 命令实现：交互式快速引导

    Args:
        executor: 执行器函数（可选）
        compact: 紧凑模式，跳过详细帮助信息
    """
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    output = CLIOutput.get_instance()
    output.header("BTC碰撞引擎 - 快速启动向导")

    if compact:
        output.print("[INFO] 紧凑模式：已跳过详细帮助信息\n")

    try:
        # 步骤1: 选择目标地址来源
        targets, target_file = _quick_start_select_target(compact=compact)
        if not targets and not target_file:
            output.error("错误：未选择目标地址")
            output.print("[TIP] 请重新启动向导并选择有效的目标地址")
            return

        # 步骤2: 选择碰撞模式
        mode, start_key, end_key = _quick_start_select_mode(compact=compact)

        # 步骤3: 功能选项
        checkpoint, dedup, duration = _quick_start_select_options(compact=compact)

        # 步骤4: GPU加速
        gpu_args = _quick_start_select_gpu()

        # 构建命令（始终使用 key_collision_cli.py，含完整参数）
        cmd_parts = ["python", "key_collision_cli.py"]
        if target_file:
            cmd_parts.extend(["-f", target_file])
        elif targets:
            cmd_parts.extend(["-t"] + targets)
        else:
            output.error("错误：无法构建命令，缺少目标地址")
            return

        # -m 始终显式输出（即使是默认值 random）
        cmd_parts.extend(["-m", mode])

        if start_key:
            cmd_parts.extend(["--start", start_key])
        if end_key:
            cmd_parts.extend(["--end", end_key])

        # 始终显式输出 checkpoint / dedup 状态
        if checkpoint:
            cmd_parts.append("--checkpoint")
        if dedup:
            cmd_parts.append("--dedup")
        if duration > 0:
            cmd_parts.extend(["--duration", str(duration)])

        cmd_parts.extend(gpu_args)

        # 构建配置确认摘要
        mode_names = {"random": "随机模式", "range": "范围扫描", "brute_force": "暴力穷举"}
        gpu_mode_name = "CPU 模式"
        if "--multi-gpu" in gpu_args:
            gpu_mode_name = "多 GPU 加速"
        elif "--use-gpu" in gpu_args:
            gpu_mode_name = "单 GPU 加速"

        target_display = target_file if target_file else ", ".join(targets)
        config_summary = {
            "目标地址": target_display,
            "碰撞模式": mode_names.get(mode, mode),
            "断点续传": "启用" if checkpoint else "禁用",
            "去重过滤": "启用" if dedup else "禁用",
            "运行时长": f"{duration}秒" if duration > 0 else "不限制",
            "加速模式": gpu_mode_name,
        }

        # 构建并执行
        _quick_start_build_and_run(cmd_parts, executor, config_summary=config_summary)

    except KeyboardInterrupt:
        output.warning(_t("errors.keyboard_interrupt"))
    except Exception as e:
        output.error(_t("errors.unexpected", error=str(e)))
        output.print("[TIP] " + _t("cli.commands.direct_cli_tip"))


# ── 命令分发函数 ─────────────────────────────────────────────────────────────


def _handle_info_commands(args: argparse.Namespace) -> bool:
    """处理信息类工具命令：--examples, --config-check, --template, --recommend"""
    from src.cli.advanced_features import apply_template, recommend_parameters

    # --examples
    if getattr(args, "examples", False):
        _cmd_examples()
        sys.exit(0)

    # --config-check
    if getattr(args, "config_check", False):
        _cmd_config_check()
        sys.exit(0)

    # --template
    template_name = getattr(args, "template", None)
    if template_name is not None:
        success = apply_template(template_name)
        sys.exit(0 if success else 1)

    # --recommend
    if getattr(args, "recommend", False):
        rec = recommend_parameters(args)
        print(SEPARATOR_EQUAL)
        print(_t("cli.main.recommend_title"))
        print(SEPARATOR_EQUAL)
        print("\n[Info] " + _t("cli.main.recommend_params"))
        if rec["recommendations"]:
            print(f"   {' '.join(rec['recommendations'])}")
        else:
            print("   " + _t("cli.main.recommend_default"))
        print("\n[Info] " + _t("cli.main.recommend_reasons"))
        for i, reason in enumerate(rec["reasons"], 1):
            print(f"   {i}. {reason}")
        print("\n" + SEPARATOR_EQUAL)
        sys.exit(0)

    return False


def _handle_wizard_and_quickstart(args: argparse.Namespace, run_main_fn=None) -> bool:
    """处理向导和快速启动：--quick-start, --quick-run, 首次运行检测"""
    # --quick-run (快速模式)
    if getattr(args, "quick_run", False):
        _cmd_quick_run(executor=run_main_fn)
        sys.exit(0)

    # --quick-start (支持 --compact 参数)
    if getattr(args, "quick_start", False):
        compact = getattr(args, "compact", False)
        _cmd_quick_start(executor=run_main_fn, compact=compact)
        sys.exit(0)

    # ── 自动检测首次运行 ───────────────────────────────────────
    config_path = Path(CONFIG_FILE_NAME)
    wizard_marker = Path(WIZARD_MARKER_PATH)

    if not config_path.exists() and not wizard_marker.exists():
        print("\n" + _t("cli.main.first_run_detected"))
        print(_t("cli.main.first_run_tip") + "\n")
        try:
            from src.utils.first_run_wizard import FirstRunWizard
        except ImportError:
            from ..utils.first_run_wizard import FirstRunWizard

        wizard = FirstRunWizard()
        wizard.run()
        print("\n" + _t("cli.main.wizard_done"))
        print(_t("cli.main.wizard_tip") + "\n")
        sys.exit(0)

    return False


def _handle_system_commands(args: argparse.Namespace) -> bool:
    """处理系统工具命令：--health-check, --platform-check, --cleanup, --validate-addresses"""
    # --health-check
    if getattr(args, "health_check", False):
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
    if getattr(args, "platform_check", False):
        try:
            from src.utils.platform_check import PlatformChecker
        except ImportError:
            from ..utils.platform_check import PlatformChecker
        platform_checker = PlatformChecker()
        all_passed, _ = platform_checker.run_all_checks()
        platform_checker.print_report()
        sys.exit(0 if all_passed else 1)

    # --cleanup
    if getattr(args, "cleanup", False):
        try:
            from src.utils.data_cleanup import DataCleaner
        except ImportError:
            from ..utils.data_cleanup import DataCleaner
        cleaner = DataCleaner()
        dry_run = getattr(args, "dry_run", False)
        result = cleaner.clean_all(dry_run=dry_run)
        total = result.get("files_removed", 0)
        space_mb = result.get("space_freed_bytes", 0) / 1024 / 1024
        action = _t("cli.main.cleanup_preview") if dry_run else _t("cli.main.cleanup_done")
        tag = _t("cli.main.cleanup_preview_tag") if dry_run else _t("common.completed")
        print(f"[{tag}] {action} {total} 个文件, 释放 {space_mb:.2f}MB")
        sys.exit(0)

    # --validate-addresses
    validate_file = getattr(args, "validate_addresses", None)
    if validate_file is not None:
        _cmd_validate_addresses(validate_file)
        sys.exit(0)

    # --migrate-config
    if getattr(args, "migrate_config", False):
        from src.cli.config_migration import migrate_config_file

        success = migrate_config_file()
        sys.exit(0 if success else 1)

    return False


def _dispatch_utility_commands(args: argparse.Namespace, run_main_fn=None) -> bool:
    """处理所有实用工具命令（不启动碰撞引擎的独立命令）。"""
    return (
        _handle_info_commands(args)
        or _handle_wizard_and_quickstart(args, run_main_fn)
        or _handle_system_commands(args)
    )
