#!/usr/bin/env python3
"""配置一致性验证脚本（支持自动修复）

检查 CONFIG_SCHEMA 和 DEFAULT_CONFIG 之间的一致性，并支持自动修复缺失字段。
"""

import json
import sys
from pathlib import Path
from typing import Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_manager import ConfigManager  # noqa: E402 — 需 sys.path 前置


class ConfigFixer:
    """配置修复器"""

    def __init__(self):
        self.schema = ConfigManager.CONFIG_SCHEMA
        self.defaults = ConfigManager.DEFAULT_CONFIG
        self.fixes_applied: list[str] = []

    def find_missing_fields(self) -> list[dict[str, str]]:
        """查找缺失的配置字段"""
        missing_fields = []

        def check_schema(schema_obj: dict, defaults_obj: dict, path: str = "root"):
            if not isinstance(schema_obj, dict):
                return

            if "properties" in schema_obj:
                for field, field_schema in schema_obj["properties"].items():
                    if field.startswith("_") or field in ("additionalProperties", "patternProperties"):
                        continue

                    full_path = f"{path}.{field}" if path != "root" else field

                    # 检查是否在默认配置中
                    if field not in defaults_obj:
                        missing_fields.append({
                            "path": full_path,
                            "field": field,
                            "suggested_value": self._get_suggested_value(field_schema),
                        })
                    else:
                        # 递归检查嵌套对象
                        if "properties" in field_schema:
                            check_schema(field_schema, defaults_obj[field], full_path)

        check_schema(self.schema, self.defaults)
        return missing_fields

    def _get_suggested_value(self, field_schema: dict) -> Any:
        """根据Schema获取建议值"""
        if "default" in field_schema:
            return field_schema["default"]

        if "type" in field_schema:
            type_map = {
                "string": "",
                "integer": 0,
                "number": 0.0,
                "boolean": False,
                "object": {},
                "array": [],
            }
            return type_map.get(field_schema["type"], "")

        if "enum" in field_schema:
            return field_schema["enum"][0] if field_schema["enum"] else ""

        return ""

    def apply_fixes(self, dry_run: bool = False) -> bool:
        """应用配置修复"""
        missing_fields = self.find_missing_fields()

        if not missing_fields:
            print("✅ 没有需要修复的配置")
            return True

        print(f"\n发现 {len(missing_fields)} 个缺失字段:")
        for field in missing_fields:
            print(f"  - {field['path']} (建议值: {field['suggested_value']})")

        if dry_run:
            print("\n⚠️  模拟运行模式，不实际修改配置")
            return True

        # 应用修复
        for field in missing_fields:
            if self._apply_field_fix(field["path"], field["suggested_value"]):
                self.fixes_applied.append(field["path"])

        print(f"\n✅ 已应用 {len(self.fixes_applied)} 个修复")
        return len(self.fixes_applied) == len(missing_fields)

    def _apply_field_fix(self, path: str, value: Any) -> bool:
        """应用单个字段修复"""
        try:
            path_parts = path.split(".")
            current = ConfigManager.DEFAULT_CONFIG

            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            field_name = path_parts[-1]
            current[field_name] = value
            print(f"  ✅ 修复: {path} = {value}")
            return True
        except Exception as e:
            print(f"  ❌ 修复失败 {path}: {e}")
            return False

    def get_fixes_summary(self) -> str:
        """获取修复摘要"""
        if not self.fixes_applied:
            return "没有应用任何修复"
        return f"已修复 {len(self.fixes_applied)} 个字段: {', '.join(self.fixes_applied)}"


def check_config_consistency(auto_fix: bool = False, dry_run: bool = False):
    """检查配置一致性"""
    print("=" * 70)
    print("配置一致性检查工具")
    print("=" * 70)

    fixer = ConfigFixer()
    missing_fields = fixer.find_missing_fields()

    if missing_fields:
        print(f"\n❌ 发现 {len(missing_fields)} 个配置不一致问题:")
        for i, field in enumerate(missing_fields, 1):
            print(f"{i}. {field['path']}")
            print(f"   建议值: {field['suggested_value']}")
            print()

        if auto_fix:
            print("🔧 开始自动修复...")
            success = fixer.apply_fixes(dry_run=dry_run)
            if success:
                print(f"\n✅ 修复完成: {fixer.get_fixes_summary()}")
            else:
                print(f"\n⚠️  部分修复失败: {fixer.get_fixes_summary()}")
                return False
    else:
        print("\n✅ 配置完全一致！")

    # 验证修复结果
    print("\n" + "=" * 70)
    print("验证修复结果")
    print("=" * 70)

    remaining_missing = fixer.find_missing_fields()
    if remaining_missing:
        print(f"\n❌ 仍有 {len(remaining_missing)} 个字段缺失:")
        for field in remaining_missing:
            print(f"  - {field['path']}")
        return False
    else:
        print("\n✅ 所有配置字段一致！")
        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="配置一致性检查工具")
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="自动修复缺失的配置字段",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，不实际修改配置",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="将修复后的配置保存到文件",
    )

    args = parser.parse_args()

    success = check_config_consistency(auto_fix=args.auto_fix, dry_run=args.dry_run)

    if args.save and not args.dry_run:
        print("\n📤 保存配置到文件...")
        try:
            config_file = project_root / "config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(ConfigManager.DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            print(f"✅ 配置已保存到 {config_file}")
        except Exception as e:
            print(f"❌ 保存失败: {e}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
