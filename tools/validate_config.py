#!/usr/bin/env python3
"""配置验证脚本 — CI/CD 集成用.

双重验证策略:
    1. DEFAULT_CONFIG 自洽性: 始终验证代码中的 DEFAULT_CONFIG 是否与
       config.schema.json 一致（这是最关键的内部一致性检查）。
    2. 用户配置文件: 验证 config.json / config.example.json（如果存在）。

用法:
    python tools/validate_config.py                          # 验证默认配置 + 外部文件
    python tools/validate_config.py config.json              # 只验证指定文件
    python tools/validate_config.py --strict                 # 严格模式：config.example.json 失败也阻塞
    python tools/validate_config.py --defaults-only          # 仅验证 DEFAULT_CONFIG 自洽性
    python tools/validate_config.py --schema-only            # 仅输出 Schema 摘要并退出

退出码:
    0 = 所有验证通过
    1 = 至少一个验证失败
    2 = 脚本运行错误（如依赖缺失等）

依赖:
    - jsonschema>=4.0.0（已在 requirements-base.txt 中声明）
    - 项目 src/ 目录在 Python 路径中
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中，使 CI/任意 CWD 环境下均可导入 src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 路径设置 ──────────────────────────────────────────────────────────
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config.schema.json"


def _load_schema() -> dict:
    """从 config.schema.json 加载 Schema（ROADMAP #5: 单一真相源）。.

    返回:
        完整的 JSON Schema 字典

    异常:
        FileNotFoundError: schema 文件不存在
        json.JSONDecodeError: JSON 语法错误
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 辅助函数 ──────────────────────────────────────────────────────────


def _strip_comments(config: Any) -> Any:
    """递归移除所有以 '_comment' 开头的键。.

    复用自 ConfigManager._strip_comments 的逻辑，确保与加载流程一致。
    """
    if isinstance(config, dict):
        return {k: _strip_comments(v) for k, v in config.items() if not k.startswith("_comment")}
    return config


def _load_json_file(filepath: str) -> dict:
    """安全加载 JSON 文件并去除注释键。.

    参数:
        filepath: JSON 文件路径

    返回:
        去除 _comment 键后的配置字典

    异常:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 语法错误
    """
    with open(filepath, encoding="utf-8") as f:
        raw = json.load(f)
    return _strip_comments(raw)


# ── 导入项目验证器 ────────────────────────────────────────────────────


def _get_config_manager():
    """延迟导入 ConfigManager，避免顶层导入失败时整个模块不可用。."""
    from src.config.config_manager import ConfigManager

    return ConfigManager


def _get_config_manager_instance():
    """延迟导入 ConfigManager 并获取实例，用于获取 DEFAULT_CONFIG。."""
    ConfigManager = _get_config_manager()
    return ConfigManager


# ── 报告格式化 ────────────────────────────────────────────────────────


def _format_error_report(errors: dict[str, str], label: str) -> str:
    """格式化验证错误报告为可读文本。.

    参数:
        errors: {字段路径: 错误信息} 字典，空字典表示通过
        label: 验证目标的标签（文件名或描述）
    """
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  配置验证报告: {label}")
    lines.append("=" * 70)

    if not errors:
        lines.append("  PASS  验证通过，未发现配置错误。")
    else:
        lines.append(f"  FAIL  发现 {len(errors)} 个配置问题:")
        lines.append("")
        for path, msg in sorted(errors.items()):
            lines.append(f"    [{path}]")
            # 多行错误信息缩进对齐
            for sub_line in msg.split("\n"):
                lines.append(f"      {sub_line}")
        lines.append("")
        lines.append(f"  共 {len(errors)} 个问题需要修复。")

    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


# ── 验证逻辑 ──────────────────────────────────────────────────────────


def _validate_with_schema(config: dict, schema: dict) -> dict[str, str]:
    """使用 jsonschema 库直接验证配置。.

    从 config.schema.json（Draft 2020-12）加载 schema。
    优先使用 Draft202012Validator 收集所有错误。

    返回:
        错误信息字典，空字典表示验证通过
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return {"root": "jsonschema 库不可用，无法执行 Schema 验证"}

    errors: dict[str, str] = {}
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        if path not in errors:
            errors[path] = error.message
        else:
            errors[path] += f"; {error.message}"
    return errors


def validate_default_config() -> dict[str, str]:
    """验证 DEFAULT_CONFIG 与 config.schema.json 的自洽性。.

    这是最关键的内部一致性检查 —— 确保代码中定义的默认配置
    与 Schema 声明完全一致。如果这里失败，说明代码存在 bug。

    ROADMAP #5: Schema 从 config.schema.json 文件加载（单一真相源）。

    返回:
        验证错误字典，空字典表示通过
    """
    try:
        schema = _load_schema()
        CM = _get_config_manager_instance()
        default_config = CM.DEFAULT_CONFIG
    except Exception as e:
        return {"root": f"无法加载 Schema 或 ConfigManager: {e}"}

    return _validate_with_schema(default_config, schema)


def validate_config_file(filepath: str) -> dict[str, str]:
    """验证单个配置文件。.

    从 config.schema.json 加载 Schema 进行验证（ROADMAP #5: 单一真相源）。
    如果 Schema 文件缺失，降级为直接使用 jsonschema 验证。

    参数:
        filepath: 配置文件路径

    返回:
        验证错误字典，空字典表示通过
    """
    if not os.path.exists(filepath):
        return {"root": f"文件不存在: {filepath}"}

    # 1. 加载并解析 JSON
    try:
        config = _load_json_file(filepath)
    except json.JSONDecodeError as e:
        return {"root": f"JSON 解析失败: {e}"}
    except Exception as e:
        return {"root": f"加载失败: {e}"}

    # 2. 从 config.schema.json 加载 Schema
    try:
        schema = _load_schema()
    except Exception as e:
        return {"root": f"无法加载 config.schema.json: {e}"}

    return _validate_with_schema(config, schema)


# ── 入口 ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """主入口。.

    验证流程:
        1. 始终验证 DEFAULT_CONFIG 与 CONFIG_SCHEMA 的自洽性
        2. 如果指定了用户配置文件且文件存在，额外验证这些文件
        3. 不存在的配置文件会被跳过（不会导致失败）

    参数:
        argv: 命令行参数列表，None 表示使用 sys.argv
    """
    parser = argparse.ArgumentParser(
        description="验证项目配置文件与 config.schema.json 的一致性 (ROADMAP #5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python tools/validate_config.py
    python tools/validate_config.py config.json
    python tools/validate_config.py config.json config.example.json --strict
    python tools/validate_config.py --defaults-only           # 仅验证代码默认配置
    python tools/validate_config.py --schema-only
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        default=["config.json", "config.example.json"],
        help="要验证的配置文件路径（默认: config.json config.example.json）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：config.example.json 验证失败也会导致非零退出码",
    )
    parser.add_argument(
        "--defaults-only",
        action="store_true",
        help="仅验证 DEFAULT_CONFIG 与 config.schema.json 的自洽性，不检查外部文件",
    )
    parser.add_argument(
        "--no-defaults",
        action="store_true",
        help="跳过 DEFAULT_CONFIG 自洽性验证（不推荐，仅用于调试）",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="仅输出 config.schema.json 摘要并退出（不执行验证）",
    )

    args = parser.parse_args(argv)

    # ── Schema 摘要模式 ──
    if args.schema_only:
        try:
            schema = _load_schema()
        except Exception as e:
            print(f"ERROR: 无法加载 config.schema.json: {e}", file=sys.stderr)
            return 2

        print("=== config.schema.json 摘要 ===")
        print(f"  类型: {schema.get('type', 'N/A')}")
        top_props = schema.get("properties", {})
        print(f"  顶层区块数: {len(top_props)}")
        for section_name in sorted(top_props):
            section = top_props[section_name]
            field_count = len(section.get("properties", {}))
            extra = " (禁止额外属性)" if not section.get("additionalProperties", True) else ""
            print(f"    - {section_name}: {field_count} 字段{extra}")
        print(f"  patternProperties 允许: {list(schema.get('patternProperties', {}).keys())}")
        return 0

    all_passed = True
    error_count = 0
    files_checked = 0

    # ── 第一步: 验证 DEFAULT_CONFIG 自洽性 (始终执行，除非 --no-defaults) ──
    if not args.no_defaults:
        errors = validate_default_config()
        report = _format_error_report(errors, "DEFAULT_CONFIG (代码内置默认配置)")
        print(report)

        if errors:
            error_count += len(errors)
            all_passed = False

    # ── 第二步: 验证用户指定的配置文件 ──
    if args.defaults_only:
        # 仅验证默认配置，跳过外部文件
        pass
    else:
        for filepath in args.files:
            # 文件不存在时优雅跳过，不视为错误
            if not os.path.exists(filepath):
                print()
                print(f"  SKIP   文件不存在，跳过: {filepath}")
                print("         (仅当文件存在时才进行验证)")
                continue

            files_checked += 1
            errors = validate_config_file(filepath)

            # ---- 输出报告 ----
            report = _format_error_report(errors, filepath)
            print(report)

            # ---- 判定结果 ----
            if not errors:
                continue  # 通过

            error_count += len(errors)
            if filepath == "config.example.json" and not args.strict:
                print(
                    f"  WARNING  config.example.json 存在 {len(errors)} 个 Schema 不一致"
                    f"（非严格模式仅警告，不会阻塞 CI）\n",
                )
                continue

            all_passed = False

    # ── 汇总 ──
    if all_passed:
        parts = ["DEFAULT_CONFIG 自洽性验证通过"]
        if files_checked > 0:
            parts.append(f"{files_checked} 个外部配置文件验证通过")
        print(f"SUMMARY  {'; '.join(parts)}。")
        return 0
    print(f"SUMMARY  配置验证失败，共 {error_count} 个问题待修复。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
