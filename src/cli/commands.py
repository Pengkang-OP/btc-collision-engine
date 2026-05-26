#!/usr/bin/env python3
"""CLI tool commands module.

包含:
- _cmd_validate_addresses: 批量验证文件中所有比特币地址
- _cmd_examples: 显示常用使用示例
- _cmd_config_check: 检查配置文件状态
- _cmd_quick_start: 交互式快速引导
"""

import argparse
import concurrent.futures
import json
import string
import sys
import time
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

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)

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


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小为可读字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _cmd_validate_addresses(file_path: str) -> None:
    """--validate-addresses 命令实现：批量验证文件中所有比特币地址"""
    # 路径安全验证：防止路径遍历攻击
    # v4.2.2 P2修复: 路径验证失败应返回非零退出码
    if not validate_file_path(file_path):
        sys.exit(1)
    target_path = Path(file_path)
    if not target_path.exists():
        print(_t("errors.file_not_found", path=file_path), file=sys.stderr)
        sys.exit(1)

    # 导入地址验证器（优先使用相对导入）
    from ..collision.targets.validator import AddressBatchValidator

    print(f"[BTC地址验证] 文件: {file_path}")
    print(SEPARATOR_DASHED_SHORT)

    # 读取文件
    lines = []
    try:
        with Path(target_path).open(encoding="utf-8", errors="replace") as f:
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
    """--examples 命令实现：显示常用使用示例（带分页）"""
    # 确保UTF-8输出
    PlatformUtils.ensure_utf8_output()

    # 构建所有输出行
    all_lines: list[str] = []
    all_lines.append(SEPARATOR_EQUAL)
    all_lines.append("[Examples] " + _t("cli.commands.examples_title"))
    all_lines.append(SEPARATOR_EQUAL)

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
            "cmd": (
                "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa "
                "-m random --checkpoint --dedup --duration 3600"
            ),
        },
        {
            "title": "4. 从文件加载目标",
            "desc": "从文件读取多个目标地址",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --checkpoint",
        },
        {
            "title": "5. GPU加速模式",
            "desc": "启用单GPU加速（速度提升数千倍）",
            "cmd": "python key_collision_cli.py -t 1A1zP1...DivfNa -m random --use-gpu",
        },
        {
            "title": "6. 多GPU模式",
            "desc": "使用所有可用GPU设备",
            "cmd": "python key_collision_cli.py -f targets.txt -m random --multi-gpu",
        },
        {
            "title": "7. 范围扫描",
            "desc": "在指定私钥范围内搜索",
            "cmd": (
                "python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa "
                "-m range --start 1 --end FFFFFFFF"
            ),
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
        all_lines.append("")
        all_lines.append(ex["title"])
        all_lines.append(f"   {ex['desc']}")
        all_lines.append(f"   $ {ex['cmd']}")

    all_lines.append("")
    all_lines.append(SEPARATOR_EQUAL)
    all_lines.append("[TIP] " + _t("cli.commands.examples_tips_title") + ":")
    all_lines.append("   - " + _t("cli.commands.tip_quick_start"))
    all_lines.append("   - " + _t("cli.commands.tip_help"))
    all_lines.append("   - " + _t("cli.commands.tip_config_check"))

    all_lines.append("")
    all_lines.append(SEPARATOR_DASHED)
    all_lines.append("[快捷命令别名]")
    all_lines.append("   qs      = --quick-start  (交互式向导)")
    all_lines.append("   qr      = --quick-run    (快速模式)")
    all_lines.append("   hc      = --health-check (健康检查)")
    all_lines.append("   cc      = --config-check (配置验证)")
    all_lines.append("   ex      = --examples     (显示示例)")
    all_lines.append("   rec     = --recommend    (参数推荐)")
    all_lines.append(SEPARATOR_DASHED)
    all_lines.append("提示: Windows 用户也可双击 start.bat 启动统一菜单入口")
    all_lines.append(SEPARATOR_EQUAL)

    # 使用分页显示（内容较长）
    from .output import paginate

    paginate(all_lines, title="使用示例", page_size=18)


# JSON Schema 路径 (P2-9: 配置文件 schema 验证)
_CONFIG_SCHEMA_PATH = str(Path(__file__).resolve().parent.parent.parent / "config.schema.json")


def _validate_config_schema(config: dict[str, Any]) -> list[str]:
    """使用 JSON Schema 验证 config 结构和类型。

    返回错误信息列表，空列表表示验证通过。
    若 jsonschema 库不可用，返回提示信息。
    """
    try:
        import jsonschema
    except ImportError:
        logger.debug("jsonschema not available, skipping schema validation (optional dependency)")
        return []  # 静默跳过（jsonschema 为可选依赖）

    schema_path = Path(_CONFIG_SCHEMA_PATH)
    if not schema_path.exists():
        return []

    try:
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(config))
        return [
            f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in errors
            if not (e.absolute_path and str(e.absolute_path[0]).startswith("_comment"))
        ]
    except Exception:
        logger.warning("Schema validation failed, returning empty list")
        return []  # schema 文件损坏时静默跳过


def _cmd_config_check() -> None:
    """--config-check 命令实现：检查配置文件状态 (含 JSON Schema 验证)"""
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
            with Path(config_path).open(encoding="utf-8") as f:
                config = json.load(f)
            print("[OK] " + _t("cli.commands.json_valid"))

            # 基本结构验证
            missing_sections = [s for s in REQUIRED_CONFIG_SECTIONS if s not in config]

            if missing_sections:
                print(
                    "[WARN] " + _t("cli.commands.missing_sections") + ": " + ", ".join(missing_sections),
                )
            else:
                print("[OK] " + _t("cli.commands.sections_complete"))

            # JSON Schema 验证 (P2-9)
            schema_errors = _validate_config_schema(config)
            if schema_errors:
                print("\n[WARN] Schema validation issues:")
                for err in schema_errors[:10]:  # 最多显示10条
                    print(f"   - {err}")
                if len(schema_errors) > 10:
                    print(f"   ... 及其他 {len(schema_errors) - 10} 个问题")
            else:
                print("[OK] Schema validation passed")

            # 显示关键配置信息
            print("\n[INFO] Key config:")
            collision_cfg = config.get("collision", {})
            engine_cfg = config.get("engine", {})
            workers = collision_cfg.get("max_workers", engine_cfg.get("max_threads", "auto"))
            print("   - workers        : " + str(workers))
            print(
                "   - perf_optimize  : "
                + ("enabled" if collision_cfg.get("use_performance_optimization", True) else "disabled"),
            )
            chk = collision_cfg.get("checkpoint_interval", engine_cfg.get("checkpoint_interval", 30))
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
    required_dirs = ["logs", "data_logs"]
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
        # 根据平台选择文件锁实现
        if sys.platform == "win32":
            import msvcrt

            # Windows: 使用独占锁
            lock_file = Path(lock_path).open("w")  # noqa: SIM115 — 文件锁需保持打开
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            # Unix/Linux: 使用 flock
            lock_file = Path(lock_path).open("w")  # noqa: SIM115 — 文件锁需保持打开
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        # 读取已有地址
        if targets_path.exists():
            try:
                with Path(targets_path).open(encoding="utf-8-sig", errors="ignore") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            existing.add(stripped)
            except OSError as e:
                logger.debug("Failed to read existing targets file for dedup: %s", e)

        if address in existing:
            output.print("   [INFO] 地址已存在于 targets.txt，无需重复添加")
            return

        # 将新地址追加到文件
        if not targets_path.exists():
            with Path(targets_path).open("w", encoding="utf-8") as f:
                f.write("# BTC 目标地址列表\n")
                f.write("# 每行一个地址，支持 # 注释行\n")
                f.write("# 支持 P2PKH (1开头)、P2SH (3开头)、Bech32 (bc1开头) 格式\n#\n")

        # 读取最新内容并追加新地址
        content = Path(targets_path).read_text(encoding="utf-8")

        # 追加新地址
        content += address + "\n"

        # 写入临时文件
        temp_path = targets_path.with_suffix(".tmp")
        Path(temp_path).write_text(content, encoding="utf-8")

        # 原子替换
        Path(temp_path).replace(targets_path)

        output.print(
            "   [green][OK] 地址已保存到 targets.txt（共 " + str(len(existing) + 1) + " 条）[/green]",
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
            except (OSError, RuntimeError) as e:
                logger.debug("Failed to release file lock: %s", e)
            try:
                # 清理锁文件
                if lock_path.exists():
                    lock_path.unlink()
            except OSError as e:
                logger.debug("Failed to remove lock file: %s", e)


def _scan_target_file_lines(target_file: str, max_scan: int = 50000) -> tuple[int, bool]:
    """用多编码扫描目标文件中的有效地址行数。返回 (valid_count, truncated)。"""
    valid_count = 0
    truncated = False
    for enc in ("utf-8", "gbk"):
        try:
            with Path(target_file).open(encoding=enc, errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= max_scan:
                        truncated = True
                        break
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        valid_count += 1
            break
        except (UnicodeDecodeError, LookupError) as e:
            logger.debug("Failed to read file with encoding '%s': %s", enc, e)
            continue
    return valid_count, truncated


def _handle_missing_target_file(
    output: CLIOutput,
    target_file: str,
) -> tuple[list[str], str | None] | None:
    """处理目标文件不存在时的菜单交互。
    返回 (targets, target_file) 或 None（需要继续后续流程）。
    """
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
            with Path(target_file).open("w", encoding="utf-8") as f:
                f.write("# 目标地址文件\n")
                f.write("# 每行一个地址，支持 # 注释\n")
                f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            output.success(_t("cli.commands.example_file_created", path=target_file))
            output.print("   [TIP] " + _t("cli.commands.example_file_tip"))
            output.success(
                _t(
                    "cli.commands.addresses_loaded",
                    count="1",
                    path=Path(target_file).name,
                ),
            )
            return [], target_file
        except Exception as e:
            output.error(f"创建文件失败: {e!s}")
            output.print("   [TIP] 请检查文件路径是否正确，以及是否有写入权限")
            return [], None
    elif choice == "2":
        address = input("   请输入目标地址: ").strip()
        if not address:
            output.error(_t("cli.commands.address_empty"))
            return [], None
        return [address], None
    else:
        # 选3：返回重新选择
        return _quick_start_select_target()


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
        help_lines = [
            "[?] " + _t("cli.commands.help_address_formats"),
            "   - P2PKH: " + _t("cli.commands.help_p2pkh"),
            "   - P2SH: " + _t("cli.commands.help_p2sh"),
            "   - Bech32: " + _t("cli.commands.help_bech32") + "",
        ]
        from .output import paginate

        paginate(help_lines, title="支持的地址格式", page_size=8)
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
            result = _handle_missing_target_file(output, target_file)
            if result is not None:
                return result
        else:
            # 文件存在：统计有效地址行数并给予反馈
            file_basename = Path(target_file).name
            try:
                valid_count, truncated = _scan_target_file_lines(target_file)
            except Exception as e:
                output.error(f"读取文件失败: {e!s}")
                output.print("   [TIP] 请检查文件路径是否正确，以及是否有读取权限")
                return [], None
            if valid_count == 0:
                output.warning(_t("cli.commands.no_valid_addresses", path=file_basename))
                output.print("   " + _t("cli.commands.file_format_hint"))
                return [], None
            count_display = f"{valid_count}+" if truncated else str(valid_count)
            output.success(
                _t("cli.commands.addresses_loaded", count=count_display, path=file_basename),
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
        help_lines = [
            "[?] " + _t("cli.commands.help_mode_description"),
            "   - random: " + _t("cli.commands.help_mode_random_detail"),
            "   - range: " + _t("cli.commands.help_mode_range_detail"),
            "   - brute_force: " + _t("cli.commands.help_mode_brute_detail") + "",
        ]
        from .output import paginate

        paginate(help_lines, title="碰撞模式说明", page_size=8)
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
            start_key = input("   " + _t("cli.commands.input_start_key") + " (hex): ").strip() or "1"
            if all(c in string.hexdigits for c in start_key):
                break
            output.error("请输入有效的十六进制字符串")
        if mode == "range":
            while True:
                end_key = (
                    input("   " + _t("cli.commands.input_end_key") + " (hex): ").strip() or "FFFFFFFF"
                )
                if all(c in string.hexdigits for c in end_key):
                    break
                output.error("请输入有效的十六进制字符串")

    return mode, start_key, end_key


def _yn_prompt(output: CLIOutput, prompt: str, default: str = "y") -> bool:
    """提示 yes/no，默认 Y。"""
    while True:
        val = input(f"   {prompt} (推荐: Y): ").strip().lower()
        if val == "":
            return True
        if val in ("y", "n"):
            return val == "y"
        output.error("请输入 y 或 n")


def _duration_prompt(output: CLIOutput) -> int:
    """提示运行时长（天/小时/无限），返回秒数（0=无限）。"""
    output.print("   运行时长选项:")
    output.print("   1. 无限（默认）")
    output.print("   2. 指定小时")
    output.print("   3. 指定天")
    while True:
        choice = input("   请选择 [1/2/3] (推荐: 1): ").strip()
        if choice in ("", "1"):
            return 0
        if choice == "2":
            while True:
                try:
                    hours = int(input("   请输入小时数: ").strip())
                    if hours > 0:
                        return hours * 3600
                    output.error("小时数必须大于0")
                except ValueError:
                    output.error("请输入整数")
        elif choice == "3":
            while True:
                try:
                    days = int(input("   请输入天数: ").strip())
                    if days > 0:
                        return days * 86400
                    output.error("天数必须大于0")
                except ValueError:
                    output.error("请输入整数")
        else:
            output.error("请输入 1、2 或 3")


def _quick_start_select_options(compact: bool = False) -> tuple[bool, bool, int]:
    """步骤3: 选择功能选项。返回 (checkpoint, dedup, duration)"""
    output = CLIOutput.get_instance()
    output.print("\n[bold cyan]【步骤 3/4】[/bold cyan] " + _t("cli.commands.step3_title"))
    if not compact:
        help_lines = [
            "[?] " + _t("cli.commands.help_feature_description"),
            "   - checkpoint: " + _t("cli.commands.help_checkpoint"),
            "   - dedup: " + _t("cli.commands.help_dedup"),
            "   - duration: " + _t("cli.commands.help_duration") + "",
        ]
        from .output import paginate

        paginate(help_lines, title="功能选项说明", page_size=8)
    else:
        output.print("")
    checkpoint = _yn_prompt(output, _t("cli.commands.enable_checkpoint"))
    dedup = _yn_prompt(output, _t("cli.commands.enable_dedup"))
    duration = _duration_prompt(output)
    return checkpoint, dedup, duration


def _detect_gpu_devices() -> list[dict]:
    """检测可用的GPU设备，失败时返回空列表"""
    try:
        from src.gpu.device import GPUDeviceDetector

        devices = GPUDeviceDetector.detect_devices()
        return devices
    except Exception as e:
        logger.warning("GPU device detection failed: %s", e)
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


def _gpu_no_devices_confirm(
    output: CLIOutput,
    mode_label: str,
    arg: str,
) -> list[str]:
    """无GPU设备时的确认交互。"""
    output.warning("未检测到可用 GPU 设备（可能缺少 OpenCL 驱动）")
    output.print("   [INFO] GPU 模式需要安装 pyopencl 和相应的驱动")
    output.print("   [INFO] 请参考文档安装 GPU 驱动和依赖")
    fallback = input(f"   是否仍然尝试{mode_label}？[y/N]: ").strip().lower()
    if fallback == "y":
        output.warning(f"警告：在无 GPU 设备的情况下尝试{mode_label}可能会导致运行时错误")
        return [arg]
    output.success("已回退到 CPU 模式")
    return []


def _single_gpu_select(output: CLIOutput, devices: list[dict]) -> list[str]:
    """单GPU模式设备选择。"""
    if not devices:
        return _gpu_no_devices_confirm(output, "GPU 模式", "--use-gpu")
    if len(devices) == 1:
        label = _format_device_label(devices[0], 0)
        output.success(f"将使用 GPU: {label}")
        return ["--use-gpu", "--gpu-device", "0"]
    # 多设备选一
    output.print("   检测到以下 GPU 设备:")
    for i, dev in enumerate(devices):
        output.print(f"     {i + 1}. {_format_device_label(dev, i)}")
    raw = input(f"   请选择 GPU 设备 [1-{len(devices)}，直接回车=选择第一个]: ").strip() or "1"
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(devices):
            output.success(f"已选择: {_format_device_label(devices[idx], idx)}")
            return ["--use-gpu", "--gpu-device", str(idx)]
    except ValueError:
        pass
    output.warning("将使用第一个 GPU 设备")
    output.success(f"已选择: {_format_device_label(devices[0], 0)}")
    return ["--use-gpu", "--gpu-device", "0"]


def _multi_gpu_select(output: CLIOutput, devices: list[dict]) -> list[str]:
    """多GPU模式设备选择。"""
    if not devices:
        return _gpu_no_devices_confirm(output, "多GPU模式", "--multi-gpu")
    if len(devices) == 1:
        label = _format_device_label(devices[0], 0)
        output.success(f"检测到 GPU: {label}，将使用此设备")
        return ["--use-gpu", "--gpu-device", "0"]
    # 多设备多选
    output.print("   检测到以下 GPU 设备:")
    for i, dev in enumerate(devices):
        output.print(f"     {i + 1}. {_format_device_label(dev, i)}")
    default_indices = " ".join(str(i + 1) for i in range(len(devices)))
    raw = (
        input("   请选择要使用的 GPU 设备编号（空格分隔，如 1 2，直接回车=全部）: ").strip()
        or default_indices
    )
    selected_indices: list[int] = []
    valid_sel = True
    for part in raw.split():
        try:
            n = int(part) - 1
            if 0 <= n < len(devices):
                selected_indices.append(n)
            else:
                output.error(f"无效设备编号: {part}（有效范围 1-{len(devices)}）")
                valid_sel = False
                break
        except ValueError:
            output.error(f"无效输入: {part}")
            valid_sel = False
            break
    if valid_sel and selected_indices:
        labels = ", ".join(_format_device_label(devices[i], i) for i in selected_indices)
        output.success(f"已选择: {labels}")
        return ["--multi-gpu", "--gpu-indices", *[str(i) for i in selected_indices]]
    output.warning("选择无效，将使用所有 GPU 设备")
    return ["--multi-gpu"]


def _quick_start_select_gpu() -> list[str]:
    """步骤4: 选择GPU加速模式。返回额外的命令行参数列表"""
    output = CLIOutput.get_instance()
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
        default_choice = "2"
    else:
        output.warning("未检测到可用 GPU 设备")
        default_choice = "1"
    output.print("   1. " + _t("cli.commands.mode_cpu"))
    output.print("   2. " + _t("cli.commands.mode_single_gpu"))
    output.print("   3. " + _t("cli.commands.mode_multi_gpu"))
    while True:
        gpu_choice = input(
            "   " + _t("cli.commands.step4_prompt") + f" (推荐: {default_choice}): ",
        ).strip()
        if gpu_choice in ("1", "2", "3"):
            break
        output.error("请输入 1、2 或 3")
    gpu_args: list[str] = []
    if gpu_choice == "2":
        gpu_args = _single_gpu_select(output, detected_devices)
    elif gpu_choice == "3":
        gpu_args = _multi_gpu_select(output, detected_devices)
    return gpu_args


def _quick_run_scan_target(
    target_file: str,
    output: CLIOutput,
) -> tuple[int, list[str]] | None:
    """扫描目标文件获取地址预览。返回 (count, preview_list) 或 None (失败/无数据)"""
    address_count = 0
    preview_addresses: list[str] = []
    max_preview = PREVIEW_CONFIG["max_preview_addresses"]
    try:
        with Path(target_file).open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    address_count += 1
                    if len(preview_addresses) < max_preview:
                        preview_addresses.append(stripped)
    except Exception as e:
        output.error(f"读取文件失败: {e!s}")
        return None
    if address_count == 0:
        output.warning(f"{target_file} 中没有有效的目标地址")
        output.print("\n[TIP] 请先在文件中添加目标地址，或使用以下命令:")
        output.print("  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random\n")
        return None
    return address_count, preview_addresses


def _quick_run_config_summary(target_file: str) -> dict:
    """构建默认配置摘要。"""
    return {
        "目标文件": target_file,
        "碰撞模式": (
            "随机模式" if QUICK_RUN_DEFAULTS["mode"] == "random" else QUICK_RUN_DEFAULTS["mode"]
        ),
        "断点续传": "启用" if QUICK_RUN_DEFAULTS["checkpoint"] else "禁用",
        "去重过滤": "启用" if QUICK_RUN_DEFAULTS["dedup"] else "禁用",
        "运行时长": (
            "不限制" if QUICK_RUN_DEFAULTS["duration"] == 0 else f"{QUICK_RUN_DEFAULTS['duration']}分钟"
        ),
        "加速模式": "CPU 模式",
    }


def _cmd_quick_run(executor: Callable[[], None] | None = None) -> None:
    """--quick-run 命令实现：快速模式，跳过向导直接使用默认配置运行"""
    PlatformUtils.ensure_utf8_output()
    output = CLIOutput.get_instance()
    output.header("BTC碰撞引擎 - 快速模式")
    try:
        output.print("\n[bold cyan]使用默认配置快速启动...[/bold cyan]\n")
        target_file = str(QUICK_RUN_DEFAULTS["target_file"])
        target_file_exists = Path(target_file).exists()
        if target_file_exists:
            scan_result = _quick_run_scan_target(target_file, output)
            if scan_result is None:
                return
            address_count, preview_addresses = scan_result
            output.success(f"发现目标文件: {target_file} ({address_count} 个地址)")
            if preview_addresses:
                output.print("\n[bold yellow]地址预览:[/bold yellow]")
                max_display_len = PREVIEW_CONFIG["max_address_display_length"]
                for i, addr in enumerate(preview_addresses, 1):
                    display_addr = (
                        addr[:max_display_len] + "..." if len(addr) > max_display_len else addr
                    )
                    output.print(f"  {i}. {display_addr}")
                if address_count > PREVIEW_CONFIG["max_preview_addresses"]:
                    output.print(
                        f"  ... 及其他 {address_count - PREVIEW_CONFIG['max_preview_addresses']} 个地址",
                    )
                output.print("")
            cmd_parts: list[str] = ["python", "-m", "src.cli", "-f", target_file]
        else:
            output.warning(f"未找到 {target_file}，请使用 -t 或 -f 指定目标")
            output.print("\n[TIP] 快速模式示例:")
            output.print("  python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random")
            output.print("  python key_collision_cli.py -f targets.txt --use-gpu\n")
            return
        cmd_parts.extend(["-m", str(QUICK_RUN_DEFAULTS["mode"])])
        if QUICK_RUN_DEFAULTS["checkpoint"]:
            cmd_parts.append("--checkpoint")
        if QUICK_RUN_DEFAULTS["dedup"]:
            cmd_parts.append("--dedup")
        config_summary = _quick_run_config_summary(target_file)
        output.print("\n[bold yellow]默认配置:[/bold yellow]")
        for key, value in config_summary.items():
            output.print(f"  {key}: {value}")
        # 倒计时
        countdown = QUICK_RUN_DEFAULTS["countdown_seconds"]
        output.print(f"\n[bold green]{countdown}秒后自动开始... (按Ctrl+C取消)[/bold green]")
        import time

        try:
            for i in range(countdown, 0, -1):
                output.print(f"  {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            output.warning("已取消")
            return
        output.header(_t("cli.messages.starting"))
        if executor is not None:
            argv = list(cmd_parts)
            if argv and argv[0].lower() in ("python", "python3", "python.exe", "python3.exe"):
                argv = argv[1:]
            original_argv = sys.argv
            try:
                sys.argv = argv
                executor()
            finally:
                sys.argv = original_argv
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

        # 构建命令（使用入口模块名，兼容 pip install -e . 安装方式）
        cmd_parts = ["python", "-m", "src.cli"]
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

        target_display = target_file or ", ".join(targets)
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
    # v5.2.2: 使用项目根目录下的路径，支持绝对/相对路径
    wizard_marker = Path(WIZARD_MARKER_PATH)
    if not wizard_marker.is_absolute():
        try:
            from ._path_setup import _get_project_root as _pr
            wizard_marker = Path(_pr()) / WIZARD_MARKER_PATH
        except Exception:
            logger.debug("Path setup failed, using default path")

    # v5.2.2: wizard marker 有效期 7 天，过期后重新触发
    _should_show_wizard = not config_path.exists()
    if _should_show_wizard and wizard_marker.exists():
        try:
            marker_age = time.time() - wizard_marker.stat().st_mtime
            if marker_age > 604800:  # 7 天
                wizard_marker.unlink()
            else:
                _should_show_wizard = False
        except OSError:
            _should_show_wizard = False

    if _should_show_wizard:
        print("\n" + _t("cli.main.first_run_detected"))
        print(_t("cli.main.first_run_tip") + "\n")
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
        from ..utils.health_check import HealthChecker
        checker = HealthChecker()
        results = checker.run_all_checks()
        checker.generate_report()
        all_ok = all(passed for passed, _ in results.values())
        sys.exit(0 if all_ok else 1)

    # --platform-check
    if getattr(args, "platform_check", False):
        try:
            from ..utils.platform_check import PlatformChecker
        except ImportError:
            logger.error("PlatformChecker not available in platform_check module")
            print("[ERROR] PlatformChecker 类未在 platform_check 中实现", file=sys.stderr)
            sys.exit(1)
        platform_checker = PlatformChecker()
        all_passed, _ = platform_checker.run_all_checks()
        platform_checker.print_report()
        sys.exit(0 if all_passed else 1)

    # --cleanup
    if getattr(args, "cleanup", False):
        from ..utils.data_cleanup import DataCleaner
        cleaner = DataCleaner()
        dry_run = getattr(args, "dry_run", False)
        if dry_run:
            # 预览模式：收集并列出实际待删除文件
            from datetime import datetime, timedelta
            from pathlib import Path

            print("[预览模式] 扫描待清理文件 (超过 7 天)...")
            print(SEPARATOR_DASHED)
            scan_dirs = ["data_logs", "logs", "temp"]
            cutoff_time = datetime.now() - timedelta(days=7)
            total_files = 0
            total_size = 0
            found_any = False
            for dir_name in scan_dirs:
                dir_path = Path(dir_name)
                if not dir_path.is_dir():
                    continue
                files_in_dir = 0
                for f in dir_path.rglob("*"):
                    if f.is_file():
                        try:
                            mtime = datetime.fromtimestamp(f.stat().st_mtime)
                            if mtime < cutoff_time:
                                size = f.stat().st_size
                                if not found_any:
                                    found_any = True
                                print(f"  [待删除] {f} ({_format_file_size(size)}, {mtime.strftime('%Y-%m-%d')})")
                                files_in_dir += 1
                                total_size += size
                        except OSError:
                            pass
                if files_in_dir > 0:
                    total_files += files_in_dir
            print(SEPARATOR_DASHED)
            if not found_any:
                print("[预览] 没有发现需要清理的过期文件")
            else:
                print(f"[预览] 共 {total_files} 个文件, 约 {_format_file_size(total_size)}")
                print("[预览] 实际清理请运行: python key_collision_cli.py --cleanup")
        else:
            total = cleaner.clean_all()
            print(f"[完成] 清理完成: {total} 个文件")
        sys.exit(0)

    # --validate-addresses
    validate_file = getattr(args, "validate_addresses", None)
    if validate_file is not None:
        _cmd_validate_addresses(validate_file)
        sys.exit(0)

    # --migrate-config
    if getattr(args, "migrate_config", False):
        try:
            from ..config.config_migration import migrate_config_file
        except ImportError:
            logger.error("config_migration module not available")
            print("[ERROR] 配置迁移模块不可用", file=sys.stderr)
            sys.exit(1)
        success = migrate_config_file()
        if success:
            print("[完成] 配置已成功迁移至最新格式（原文件已备份）")
        else:
            print("[提示] 配置文件已是最新格式，无需迁移")
        sys.exit(0 if success else 0)

    return False


def _dispatch_utility_commands(args: argparse.Namespace, run_main_fn=None) -> bool:
    """处理所有实用工具命令（不启动碰撞引擎的独立命令）。"""
    return (
        _handle_info_commands(args)
        or _handle_wizard_and_quickstart(args, run_main_fn)
        or _handle_system_commands(args)
    )
