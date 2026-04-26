#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from src.i18n import _t
from src.utils.platform_utils import PlatformUtils
from src.cli.output import CLIOutput
from src.cli.constants import (
    REQUIRED_CONFIG_SECTIONS,
    REQUIRED_DIRECTORIES,
    SEPARATOR_EQUAL,
    SEPARATOR_DASHED,
    SEPARATOR_DASHED_SHORT,
    CONFIG_FILE_NAME,
    CONFIG_EXAMPLE_FILE,
    WIZARD_MARKER_PATH,
)
from src.cli.validation import validate_file_path

logger = logging.getLogger(__name__)


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
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as exc:
        logger.error(_t("errors.io_error", detail=str(exc)))
        print(_t("errors.io_error", detail=str(exc)), file=sys.stderr)
        sys.exit(1)

    addresses = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith('#'):
            addresses.append(stripped)

    if not addresses:
        print(_t("common.warning") + ": " + _t("address.no_match"))
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
    print(SEPARATOR_DASHED_SHORT)

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

    print("\n" + SEPARATOR_EQUAL)
    print("💡 " + _t("cli.commands.examples_tips_title") + ":")
    print("   - " + _t("cli.commands.tip_quick_start"))
    print("   - " + _t("cli.commands.tip_help"))
    print("   - " + _t("cli.commands.tip_config_check"))
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
        print("\n✅ config.json " + _t("cli.commands.file_exists"))

        # 验证JSON格式
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("✅ " + _t("cli.commands.json_valid"))

            # 基本结构验证
            missing_sections = [s for s in REQUIRED_CONFIG_SECTIONS if s not in config]

            if missing_sections:
                print(f"⚠️  " + _t("cli.commands.missing_sections") + f": {', '.join(missing_sections)}")
            else:
                print("✅ " + _t("cli.commands.sections_complete"))

            # 显示关键配置信息
            print("\n📊 关键配置信息:")
            collision_cfg = config.get('collision', {})
            print(f"   - 工作线程数: {collision_cfg.get('max_workers', '自动 (CPU核心数)')}")
            print(f"   - 性能优化: {'启用' if collision_cfg.get('use_performance_optimization', True) else '禁用'}")
            print(f"   - 断点续传间隔: {collision_cfg.get('checkpoint_interval', 30)}秒")

            gpu_cfg = config.get('gpu', {})
            print(f"   - GPU模式: {gpu_cfg.get('mode', 'auto')}")

        except json.JSONDecodeError as e:
            print(f"❌ " + _t("config.invalid", error=str(e)))
            print("💡 " + _t("cli.commands.fix_copy_example"))
        except Exception as e:
            logger.error(_t("errors.io_error", detail=str(e)))
            print(f"❌ " + _t("errors.io_error", detail=str(e)))
    else:
        print("\n❌ config.json " + _t("cli.commands.file_not_exist"))
        if example_path.exists():
            print("✅ config.example.json " + _t("cli.commands.file_exists"))
            print("💡 " + _t("cli.commands.fix_copy_suggestion"))
            print("   Windows: copy config.example.json config.json")
            print("   Linux/Mac: cp config.example.json config.json")
        else:
            print("❌ config.example.json " + _t("cli.commands.also_not_exist"))
            print("💡 " + _t("cli.commands.fix_reacquire"))

    # 检查必要目录
    print("\n📁 " + _t("cli.commands.dir_check_title") + ":")
    required_dirs = ['logs', 'data_logs', 'monitoring_data']
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ (" + _t("cli.commands.dir_not_exist") + ")")
            print(f"      " + _t("cli.commands.dir_fix") + f": mkdir {dir_name}")

    print("\n" + SEPARATOR_EQUAL)


def _quick_start_select_target() -> Tuple[List[str], Optional[str]]:
    """步骤1: 选择目标地址来源。返回 (targets_list, target_file)"""
    output = CLIOutput.get_instance()
    output.print("[bold cyan]【步骤 1/4】[/bold cyan] " + _t("cli.commands.step1_title"))
    output.print("   1. " + _t("cli.commands.step1_single"))
    output.print("   2. " + _t("cli.commands.step1_file"))
    target_type = input("   " + _t("cli.commands.step1_prompt") + " ").strip() or '1'

    targets: List[str] = []
    target_file: Optional[str] = None

    if target_type == '1':
        address = input("   " + _t("cli.commands.input_address") + ": ").strip()
        if not address:
            output.error(_t("cli.commands.address_empty"))
            return [], None
        targets = [address]
    elif target_type == '2':
        target_file = input("   " + _t("cli.commands.input_file_path") + " [targets.txt]: ").strip() or 'targets.txt'
        if not Path(target_file).exists():
            output.warning(_t("errors.file_not_found", path=target_file))
            output.print("   1. " + _t("cli.commands.create_example_file"))
            output.print("   2. 手动输入地址")
            output.print("   3. 返回重新选择")
            choice = input("   请选择 [1/2/3]: ").strip() or '1'
            if choice == '1':
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write("# 目标地址文件\n")
                    f.write("# 每行一个地址，支持 # 注释\n")
                    f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
                output.success(_t("cli.commands.example_file_created", path=target_file))
                output.print("   💡 " + _t("cli.commands.example_file_tip"))
                return [], None
            elif choice == '2':
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
                for enc in ('utf-8', 'gbk', 'latin-1'):
                    try:
                        with open(target_file, 'r', encoding=enc, errors='ignore') as f:
                            for i, line in enumerate(f):
                                if i >= MAX_SCAN_LINES:
                                    truncated = True
                                    break
                                stripped = line.strip()
                                if stripped and not stripped.startswith('#'):
                                    valid_count += 1
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
            except OSError:
                pass
            if valid_count == 0:
                output.warning(_t("cli.commands.no_valid_addresses", path=file_basename))
                output.print("   " + _t("cli.commands.file_format_hint"))
                return [], None
            else:
                count_display = f"{valid_count}+" if truncated else str(valid_count)
                output.success(_t("cli.commands.addresses_loaded", count=count_display, path=file_basename))
    else:
        output.error(_t("errors.invalid_input", detail=target_type))
        return [], None

    return targets, target_file


def _quick_start_select_mode() -> Tuple[str, Optional[str], Optional[str]]:
    """步骤2: 选择碰撞模式。返回 (mode, start_key, end_key)"""
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 2/4】[/bold cyan] " + _t("cli.commands.step2_title"))
    output.print("   1. random    - " + _t("cli.commands.mode_random_desc"))
    output.print("   2. range     - " + _t("cli.commands.mode_range_desc"))
    output.print("   3. brute_force - " + _t("cli.commands.mode_brute_desc"))
    mode_choice = input("   " + _t("cli.commands.step2_prompt") + " ").strip() or '1'

    mode_map = {'1': 'random', '2': 'range', '3': 'brute_force'}
    mode = mode_map.get(mode_choice, 'random')

    start_key: Optional[str] = None
    end_key: Optional[str] = None

    if mode in ['range', 'brute_force']:
        start_key = input("   " + _t("cli.commands.input_start_key") + " [1]: ").strip() or '1'
        if mode == 'range':
            end_key = input("   " + _t("cli.commands.input_end_key") + " [FFFFFFFF]: ").strip() or 'FFFFFFFF'

    return mode, start_key, end_key


def _quick_start_select_options() -> Tuple[bool, bool, int]:
    """步骤3: 选择功能选项。返回 (checkpoint, dedup, duration)"""
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 3/4】[/bold cyan] " + _t("cli.commands.step3_title"))
    checkpoint = input("   " + _t("cli.commands.enable_checkpoint") + " [Y/n]: ").strip().lower() != 'n'
    dedup = input("   " + _t("cli.commands.enable_dedup") + " [Y/n]: ").strip().lower() != 'n'

    duration_str = input("   " + _t("cli.commands.input_duration") + " [0]: ").strip() or '0'
    try:
        duration = int(duration_str)
    except ValueError:
        output.warning(_t("errors.value_error", detail=duration_str) + _t("cli.commands.use_default_0"))
        duration = 0

    return checkpoint, dedup, duration


def _detect_gpu_devices() -> List[dict]:
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
    name = device.get('name', f'GPU #{index}')
    mem_size = device.get('global_mem_size', 0)
    if mem_size and mem_size > 0:
        mem_gb = mem_size / (1024 ** 3)
        if mem_gb >= 1.0:
            mem_str = f"{mem_gb:.0f}GB"
        else:
            mem_mb = mem_size / (1024 ** 2)
            mem_str = f"{mem_mb:.0f}MB"
        return f"{name} ({mem_str})"
    return name


def _detect_gpu_devices_with_timeout(timeout: float = 5.0) -> List[dict]:
    """带超时的 GPU 检测，超时返回空列表"""
    output = CLIOutput.get_instance()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_detect_gpu_devices)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            output.warning(f"GPU 检测超时（{timeout:.0f}秒），已跳过")
            return []


def _quick_start_select_gpu() -> List[str]:
    """步骤4: 选择GPU加速模式。返回额外的命令行参数列表"""
    output = CLIOutput.get_instance()

    # 预先检测 GPU，决定默认选项
    output.print("\n[bold cyan]【步骤 4/4】[/bold cyan] " + _t("cli.commands.step4_title"))
    output.print("   🔍 正在检测可用 GPU 设备（最多等待 5 秒）...")
    detected_devices = _detect_gpu_devices_with_timeout(timeout=5.0)

    if detected_devices:
        gpu_count = len(detected_devices)
        labels_preview = ", ".join(_format_device_label(d, i) for i, d in enumerate(detected_devices[:2]))
        if gpu_count > 2:
            labels_preview += f" 等{gpu_count}个"
        output.success(f"检测到 {gpu_count} 个 GPU 设备: {labels_preview}")
        default_choice = '2'  # 有 GPU 时默认单 GPU
    else:
        output.warning("未检测到可用 GPU 设备")
        default_choice = '1'  # 无 GPU 时默认 CPU

    output.print("   1. " + _t("cli.commands.mode_cpu"))
    output.print("   2. " + _t("cli.commands.mode_single_gpu"))
    output.print("   3. " + _t("cli.commands.mode_multi_gpu"))
    gpu_choice = input(
        "   " + _t("cli.commands.step4_prompt") + f" [默认:{default_choice}]: "
    ).strip() or default_choice

    gpu_args: List[str] = []

    if gpu_choice == '2':
        # 单GPU模式：使用已检测到的设备
        devices = detected_devices

        if not devices:
            output.warning("未检测到可用 GPU 设备（可能缺少 OpenCL 驱动）")
            fallback = input("   是否仍然尝试 GPU 模式？[y/N]: ").strip().lower()
            if fallback == 'y':
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
            while True:
                raw = input(f"   请选择 GPU 设备 [1-{len(devices)}] [默认:1]: ").strip() or '1'
                try:
                    idx = int(raw) - 1
                    if 0 <= idx < len(devices):
                        label = _format_device_label(devices[idx], idx)
                        output.success(f"已选择: {label}")
                        gpu_args.extend(["--use-gpu", "--gpu-device", str(idx)])
                        break
                except ValueError:
                    pass
                output.error(f"无效输入，请输入 1 到 {len(devices)} 之间的数字")

    elif gpu_choice == '3':
        # 多GPU模式：使用已检测到的设备
        devices = detected_devices

        if not devices:
            output.warning("未检测到可用 GPU 设备（可能缺少 OpenCL 驱动）")
            fallback = input("   是否仍然尝试多GPU模式？[y/N]: ").strip().lower()
            if fallback == 'y':
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
            raw = input(
                f"   请选择要使用的 GPU 设备编号（空格分隔，如 1 2）[默认: 全部={default_indices}]: "
            ).strip() or default_indices
            selected_indices: List[int] = []
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


def _quick_start_build_and_run(
    cmd_parts: List[str],
    executor: Optional[Callable[[], None]],
    config_summary: Optional[dict] = None,
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

    # 询问是否执行
    execute = input(_t("cli.commands.execute_now") + " [Y/n]: ").strip().lower()
    if execute != 'n':
        output.header(_t("cli.messages.starting"))

        if executor is not None:
            # 始终使用 key_collision_cli.py，去掉 "python" 前缀部分
            argv = list(cmd_parts)
            if argv and argv[0].lower() in ("python", "python3", "python.exe", "python3.exe"):
                argv = argv[1:]
            sys.argv = argv
            executor()
        else:
            output.print("\n" + _t("cli.commands.copy_and_run"))
    else:
        output.print("\n💡 " + _t("cli.commands.tip_copy_cmd"))
        output.print("   " + _t("cli.commands.tip_help_cmd"))


def _cmd_quick_start(executor: Optional[Callable[[], None]] = None) -> None:
    """--quick-start 命令实现：交互式快速引导"""
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    output = CLIOutput.get_instance()
    output.header("BTC碰撞引擎 - 快速启动向导")

    try:
        # 步骤1: 选择目标地址来源
        targets, target_file = _quick_start_select_target()
        if not targets and not target_file:
            return

        # 步骤2: 选择碰撞模式
        mode, start_key, end_key = _quick_start_select_mode()

        # 步骤3: 功能选项
        checkpoint, dedup, duration = _quick_start_select_options()

        # 步骤4: GPU加速
        gpu_args = _quick_start_select_gpu()

        # 构建命令（始终使用 key_collision_cli.py，含完整参数）
        cmd_parts = ["python", "key_collision_cli.py"]
        if target_file:
            cmd_parts.extend(["-f", target_file])
        else:
            cmd_parts.extend(["-t"] + targets)

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
        mode_names = {'random': '随机模式', 'range': '范围扫描', 'brute_force': '暴力穷举'}
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
        output.print("💡 " + _t("cli.commands.direct_cli_tip"))


# ── 命令分发函数 ─────────────────────────────────────────────────────────────


def _handle_info_commands(args: argparse.Namespace) -> bool:
    """处理信息类工具命令：--examples, --config-check, --template, --recommend"""
    from src.cli.advanced_features import apply_template, recommend_parameters

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
        success = apply_template(template_name)
        sys.exit(0 if success else 1)

    # --recommend
    if getattr(args, 'recommend', False):
        rec = recommend_parameters(args)
        print(SEPARATOR_EQUAL)
        print(_t("cli.main.recommend_title"))
        print(SEPARATOR_EQUAL)
        print(f"\n[Info] " + _t("cli.main.recommend_params"))
        if rec['recommendations']:
            print(f"   {' '.join(rec['recommendations'])}")
        else:
            print(f"   " + _t("cli.main.recommend_default"))
        print(f"\n[Info] " + _t("cli.main.recommend_reasons"))
        for i, reason in enumerate(rec['reasons'], 1):
            print(f"   {i}. {reason}")
        print("\n" + SEPARATOR_EQUAL)
        sys.exit(0)

    return False


def _handle_wizard_and_quickstart(args: argparse.Namespace, run_main_fn=None) -> bool:
    """处理向导和快速启动：--quick-start, 首次运行检测"""
    # --quick-start
    if getattr(args, 'quick_start', False):
        _cmd_quick_start(executor=run_main_fn)
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
            from ..utils.first_run_wizard import FirstRunWizard  # type: ignore

        wizard = FirstRunWizard()
        wizard.run()
        print("\n" + _t("cli.main.wizard_done"))
        print(_t("cli.main.wizard_tip") + "\n")
        sys.exit(0)

    return False


def _handle_system_commands(args: argparse.Namespace) -> bool:
    """处理系统工具命令：--health-check, --platform-check, --cleanup, --validate-addresses"""
    # --health-check
    if getattr(args, 'health_check', False):
        try:
            from src.utils.health_check import HealthChecker
        except ImportError:
            from ..utils.health_check import HealthChecker  # type: ignore
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
            from ..utils.platform_check import PlatformChecker  # type: ignore
        checker = PlatformChecker()
        all_passed, _ = checker.run_all_checks()
        checker.print_report()
        sys.exit(0 if all_passed else 1)

    # --cleanup
    if getattr(args, 'cleanup', False):
        try:
            from src.utils.data_cleanup import DataCleaner
        except ImportError:
            from ..utils.data_cleanup import DataCleaner  # type: ignore
        cleaner = DataCleaner()
        dry_run = getattr(args, 'dry_run', False)
        result = cleaner.clean_all(dry_run=dry_run)
        total = result.get('files_removed', 0)
        space_mb = result.get('space_freed_bytes', 0) / 1024 / 1024
        action = _t("cli.main.cleanup_preview") if dry_run else _t("cli.main.cleanup_done")
        tag = _t("cli.main.cleanup_preview_tag") if dry_run else _t("common.completed")
        print(f"[{tag}] {action} {total} 个文件, 释放 {space_mb:.2f}MB")
        sys.exit(0)

    # --validate-addresses
    validate_file = getattr(args, 'validate_addresses', None)
    if validate_file is not None:
        _cmd_validate_addresses(validate_file)
        sys.exit(0)

    # --migrate-config
    if getattr(args, 'migrate_config', False):
        from src.cli.config_migration import migrate_config_file
        success = migrate_config_file()
        sys.exit(0 if success else 1)

    return False


def _dispatch_utility_commands(args: argparse.Namespace, run_main_fn=None) -> bool:
    """处理所有实用工具命令（不启动碰撞引擎的独立命令）。"""
    return (
        _handle_info_commands(args) or
        _handle_wizard_and_quickstart(args, run_main_fn) or
        _handle_system_commands(args)
    )
