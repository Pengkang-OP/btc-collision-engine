"""First-run wizard module.

When a new user is detected (no config.json or run history),
interactively guides the user through:
1. Welcome message display
2. Collision mode selection (random / range / brute_force)
3. Load test address file or manual address entry
4. 询问是否启用 GPU
5. 生成个性化 config.json

使用方法:
    from src.utils.first_run_wizard import FirstRunWizard
    wizard = FirstRunWizard()
    if wizard.should_run():
        wizard.run()
"""

import json
import os
import re
import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..utils import get_configured_logger
from .logging_config import LOG_DEFAULT_MAX_BYTES

logger = get_configured_logger("FirstRunWizard")


# ─────────────────────────────────────────────────────────────────────────────
# 向导类
# ─────────────────────────────────────────────────────────────────────────────


class FirstRunWizard:
    """首次运行交互式向导."""

    # 已有 config.json 且不为空则认为不是首次运行
    CONFIG_FILE = "config.json"
    CONFIG_EXAMPLE = "config.example.json"
    WIZARD_MARKER = "data_logs/.wizard_completed"  # 标记文件，防止重复弹出

    # 默认配置模板
    DEFAULT_CONFIG: dict[str, Any] = {
        "collision": {
            "mode": "random",
            "batch_size": 10000,
            "workers": None,
            "checkpoint_enabled": False,
            "dedup_enabled": False,
        },
        "gpu": {"enabled": False, "device_index": -1, "batch_size": None},
        "logging": {
            "level": "INFO",
            "file": "logs/collision.log",
            "max_bytes": LOG_DEFAULT_MAX_BYTES,
            "backup_count": 5,
        },
        "monitoring": {"enabled": True, "report_interval": 30},
    }

    def __init__(self, project_root: str | None = None) -> None:
        """初始化首次运行向导。."""
        if project_root is None:
            project_root = str(Path(__file__).resolve().parent.parent.parent)
        self.project_root = Path(project_root)
        self.config_path = self.project_root / self.CONFIG_FILE
        self.example_path = self.project_root / self.CONFIG_EXAMPLE
        self.marker_path = self.project_root / self.WIZARD_MARKER

    # -------------------------------------------------------------------------
    # 是否需要运行向导
    # -------------------------------------------------------------------------

    def should_run(self) -> bool:
        """判断是否应该运行向导."""
        # 非交互式环境（pytest、CI 管道等）不弹出向导
        if not sys.stdin.isatty():
            return False
        # 如果已完成向导，不再运行
        if self.marker_path.exists():
            return False
        # 如果没有 config.json，是首次运行
        if not self.config_path.exists():
            return True
        # 如果 config.json 很小（可能是空文件），也运行向导
        with suppress(OSError):
            size = self.config_path.stat().st_size
            if size < 50:
                return True
        return False

    # -------------------------------------------------------------------------
    # 内部交互工具
    # -------------------------------------------------------------------------

    @staticmethod
    def _prompt(message: str, default: str = "") -> str:
        """获取用户输入，支持默认值."""
        full_msg = f"{message} [{default}]: " if default else f"{message}: "
        try:
            val = input(full_msg).strip()
            return val or default
        except (KeyboardInterrupt, EOFError):
            print("\n[向导中止]")
            sys.exit(0)

    @staticmethod
    def _choose(message: str, options: list[Any], default_idx: int = 0) -> str:
        """让用户从选项列表中选择."""
        print(f"\n{message}")
        for i, opt in enumerate(options, 1):
            marker = " (默认)" if i - 1 == default_idx else ""
            print(f"  {i}. {opt}{marker}")
        while True:
            raw = FirstRunWizard._prompt(f"请输入选项 [1-{len(options)}]", str(default_idx + 1))
            with suppress(ValueError):
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]  # type: ignore[no-any-return]
            print(f"  无效输入，请输入 1 到 {len(options)} 之间的数字")

    @staticmethod
    def _yes_no(message: str, default: bool = True) -> bool:
        """是/否提问."""
        default_str = "Y/n" if default else "y/N"
        raw = FirstRunWizard._prompt(f"{message} [{default_str}]", "").lower()
        if raw in ("y", "yes", "是"):
            return True
        if raw in ("n", "no", "否"):
            return False
        return default

    # -------------------------------------------------------------------------
    # 向导步骤
    # -------------------------------------------------------------------------

    def _welcome(self) -> None:
        """显示欢迎页面."""
        print("\n" + "=" * 65)
        print("  欢迎使用 BTC 碰撞引擎 v4.2.3")
        print("  欢迎使用 BTC 碰撞引擎 v4.2.2")
        print("=" * 65)
        print("""
  首次检测到您没有配置文件，本向导将帮助您快速完成初始配置。
  全程约需 1-2 分钟。

  功能简介:
    - 随机模式   : 随机生成私钥并检测是否匹配目标地址
    - 范围模式   : 在指定私钥范围内穷举搜索
    - 暴力模式   : 从私钥 1 开始顺序穷举（研究用途）

  注意: 本工具仅供学习比特币密码学和地址生成原理使用。
""")
        input("  按 Enter 继续...")

    def _step_mode(self, config: dict[str, Any]) -> None:
        """步骤1：选择碰撞模式."""
        print("\n[步骤 1/4] 选择碰撞模式")
        mode_options = [
            "random   - 随机碰撞（推荐入门）",
            "range    - 范围扫描（指定起始/结束私钥）",
            "brute_force - 暴力穷举（从私钥 1 开始）",
        ]
        choice = self._choose("请选择默认碰撞模式", mode_options, default_idx=0)
        mode = choice.split(" ")[0].strip()
        config["collision"]["mode"] = mode
        print(f"  已设置模式: {mode}")

    def _step_target(self, config: dict[str, Any]) -> str | None:
        """步骤2：设置目标地址."""
        print("\n[步骤 2/4] 设置目标地址")

        # 检查是否有示例地址文件
        test_files = [
            self.project_root / "valid_addresses.txt",
            self.project_root / "test_data" / "test_addresses.txt",
        ]
        found_file = None
        for f in test_files:
            if f.exists():
                found_file = f
                break

        if found_file:
            print(f"\n  发现测试地址文件: {found_file.name}")
            use_file = self._yes_no("  是否使用此文件作为测试目标？", default=True)
            if use_file:
                print(f"  已选择: {found_file}")
                return str(found_file)

        print("\n  请输入目标比特币地址或地址文件路径:")
        print("    - 直接输入地址（如: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa）")
        print("    - 输入文件路径（如: C:\\addresses.txt 或 /home/user/addresses.txt）")
        user_input = self._prompt("  地址/文件路径", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

        # 自动检测：文件路径还是直接地址
        # Windows 绝对路径：盘符格式 C:\ 或 C:/
        _win_abs = bool(re.match(r"^[A-Za-z]:[/\\]", user_input))
        # Unix 绝对路径：以 / 开头
        _unix_abs = user_input.startswith("/")
        # 包含路径分隔符（反斜杠或正斜杠）
        _has_sep = "\\" in user_input or "/" in user_input
        # 以常见文件扩展名结尾
        _has_ext = bool(re.search(r"\.[a-zA-Z0-9]{1,5}$", user_input))
        is_file_path = Path(user_input).is_file() or _win_abs or _unix_abs or _has_sep or _has_ext
        if is_file_path:
            if Path(user_input).is_file():
                print(f"  已识别为地址文件: {user_input}")
            else:
                # 尝试自动修正常见问题
                resolved = self._try_resolve_path(user_input)
                if resolved and resolved != user_input:
                    print(f"  [提示] 文件路径已自动修正: {user_input}")
                    print(f"         → {resolved}")
                    user_input = resolved
                else:
                    print(f"  [警告] 文件路径未找到: {user_input}")
                    retry = self._yes_no("  是否仍然将其作为文件路径使用？", default=True)
                    if not retry:
                        print(f"  将作为单个地址使用: {user_input}")
                    else:
                        print(f"  将使用文件路径（运行时需确保文件存在）: {user_input}")
        else:
            print(f"  目标地址: {user_input}")

        return user_input

    @staticmethod
    def _try_resolve_path(path: str) -> str | None:
        """尝试自动修正常见路径问题，返回修正后的路径或 None.

        处理场景：
        1. Windows 双重扩展名：xxx.txt.txt → xxx.txt
        2. 缺少扩展名：xxx → xxx.txt
        """
        p = Path(path)
        # 场景1：去掉一层重复扩展名（如 .txt.txt → .txt）
        if p.suffix and p.stem.endswith(p.suffix):
            candidate = str(p.with_name(p.stem))  # 去掉最外层后缀
            if Path(candidate).is_file():
                return candidate
        # 场景2：文件名本身不含扩展名，尝试追加 .txt
        if not p.suffix:
            candidate = path + ".txt"
            if Path(candidate).is_file():
                return candidate
        return None

    def _step_gpu(self, config: dict[str, Any]) -> None:
        """步骤3：GPU 设置."""
        print("\n[步骤 3/4] GPU 加速设置")

        # 检查 PyOpenCL 是否可用
        try:
            import pyopencl  # noqa: F401

            has_opencl = True
        except ImportError:
            has_opencl = False

        if not has_opencl:
            print("  PyOpenCL 未安装，跳过 GPU 设置（CPU 模式）")
            config["gpu"]["enabled"] = False
            return

        print("  检测到 PyOpenCL 已安装！")
        enable_gpu = self._yes_no("  是否启用 GPU 加速？（可大幅提升性能）", default=True)
        config["gpu"]["enabled"] = enable_gpu
        if enable_gpu:
            print("  已启用 GPU 加速（自动选择最佳设备）")
        else:
            print("  已选择 CPU 模式")

    def _step_workers(self, config: dict[str, Any], use_gpu: bool = False) -> None:
        """步骤4：CPU 工作线程数."""
        print("\n[步骤 4/4] 性能设置")
        cpu_count = os.cpu_count() or 4
        print(f"  检测到 {cpu_count} 个 CPU 核心")
        if use_gpu:
            # GPU 模式下跳过线程数询问，使用默认值
            workers = cpu_count
            print(f"  GPU 模式已启用，CPU 辅助线程默认使用 {workers} 个")
        else:
            raw = self._prompt(
                f"  CPU 工作线程数（默认: {cpu_count}，建议不超过 CPU 核数）",
                str(cpu_count),
            )
            try:
                workers = int(raw)
                if workers < 1:
                    workers = cpu_count
            except ValueError:
                workers = cpu_count
        config["collision"]["workers"] = workers
        print(f"  已设置工作线程数: {workers}")

    # -------------------------------------------------------------------------
    # 生成配置文件
    # -------------------------------------------------------------------------

    def _write_config(self, config: dict[str, Any]) -> bool:
        """写入配置文件."""
        try:
            # 如果有 example 配置，先复制
            if self.example_path.exists():
                shutil.copy2(self.example_path, self.config_path)
                # 合并向导配置
                with Path(self.config_path).open(encoding="utf-8") as f:
                    base = json.load(f)
                # 深度合并
                self._deep_merge(base, config)
                with Path(self.config_path).open("w", encoding="utf-8") as f:
                    json.dump(base, f, indent=2, ensure_ascii=False)
            else:
                with Path(self.config_path).open("w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error("写入配置文件失败: %s", exc)
            return False

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        """递归合并字典."""
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                FirstRunWizard._deep_merge(base[k], v)
            else:
                base[k] = v

    def _mark_completed(self) -> None:
        """写入向导完成标记."""
        with suppress(OSError):
            self.marker_path.parent.mkdir(parents=True, exist_ok=True)
            self.marker_path.write_text("wizard_completed\n")

    # -------------------------------------------------------------------------
    # 主入口
    # -------------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """运行完整向导，返回最终配置."""
        import copy

        config = copy.deepcopy(self.DEFAULT_CONFIG)

        self._welcome()
        self._step_mode(config)
        target = self._step_target(config)
        self._step_gpu(config)
        use_gpu = config["gpu"].get("enabled", False)
        self._step_workers(config, use_gpu=use_gpu)

        # 写入配置
        print("\n[完成] 正在生成配置文件...")
        ok = self._write_config(config)
        if ok:
            print(f"  [OK] 配置文件已创建: {self.config_path}")
        else:
            print("  [!] 配置文件写入失败，将使用默认配置")

        self._mark_completed()

        # 显示下一步提示
        print("\n" + "=" * 65)
        print("  配置完成！下一步操作：")
        print("=" * 65)
        if target and Path(target).exists():
            print("\n  1. 开始随机碰撞（使用地址文件）:")
            print(f"     python key_collision_cli.py -f {target} -m random\n")
        else:
            addr = target or "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
            print("\n  1. 开始随机碰撞（单个地址）:")
            print(f"     python key_collision_cli.py -t {addr} -m random\n")

        print("  2. 运行健康检查:")
        print("     python key_collision_cli.py --health-check\n")

        if config["gpu"]["enabled"]:
            print("  3. 启用 GPU 加速:")
            print("     python key_collision_cli.py -f targets.txt --use-gpu -m random\n")

        print("  完整帮助: python key_collision_cli.py --help")
        print("=" * 65 + "\n")

        return config


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """命令行入口：强制运行向导（忽略已完成标记）."""
    wizard = FirstRunWizard()
    wizard.run()


if __name__ == "__main__":
    main()
