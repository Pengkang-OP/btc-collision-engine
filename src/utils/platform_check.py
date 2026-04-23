"""跨平台兼容性检查模块

检查运行环境的兼容性，包括:
- 操作系统类型检测
- 路径长度限制（Windows MAX_PATH）
- 文件权限支持
- 终端编码检测（UTF-8/GBK）
- Python 版本兼容性
- 关键目录可写性

使用方法:
    # 命令行运行
    python -m src.utils.platform_check

    # 代码中调用
    from src.utils.platform_check import PlatformChecker
    checker = PlatformChecker()
    ok, issues = checker.run_all_checks()
"""

import os
import sys
import platform
import locale
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from ..utils import init_logging, get_configured_logger

init_logging()
logger = get_configured_logger("PlatformChecker")


# ─────────────────────────────────────────────────────────────────────────────
# 结果数据类
# ─────────────────────────────────────────────────────────────────────────────

class CheckResult:
    """单项检查结果"""

    def __init__(self, name: str, passed: bool, message: str, detail: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.detail = detail

    def __repr__(self):
        status = "✅" if self.passed else "⚠️"
        return f"{status} {self.name}: {self.message}"


# ─────────────────────────────────────────────────────────────────────────────
# 核心检查器
# ─────────────────────────────────────────────────────────────────────────────

class PlatformChecker:
    """跨平台兼容性检查器"""

    # Windows MAX_PATH 限制
    WINDOWS_MAX_PATH = 260

    def __init__(self, project_root: Optional[str] = None):
        """初始化检查器

        Args:
            project_root: 项目根目录路径，默认为当前文件向上两级
        """
        if project_root is None:
            project_root = str(Path(__file__).resolve().parent.parent.parent)
        self.project_root = Path(project_root)
        self.results: List[CheckResult] = []

    # -------------------------------------------------------------------------
    # 内部工具
    # -------------------------------------------------------------------------

    def _add(self, name: str, passed: bool, message: str, detail: str = ""):
        r = CheckResult(name, passed, message, detail)
        self.results.append(r)
        logger.debug(repr(r))
        return r

    # -------------------------------------------------------------------------
    # 各项检查
    # -------------------------------------------------------------------------

    def check_os(self) -> CheckResult:
        """检测操作系统类型"""
        system = platform.system()
        release = platform.release()
        machine = platform.machine()
        version = platform.version()

        detail = (
            f"系统={system}, 版本={release}, "
            f"架构={machine}, 详情={version[:60]}"
        )

        if system in ("Windows", "Linux", "Darwin"):
            msg = f"{system} {release} ({machine}) — 已支持"
            return self._add("操作系统", True, msg, detail)
        else:
            msg = f"{system} — 未经测试，可能出现兼容问题"
            return self._add("操作系统", False, msg, detail)

    def check_python_version(self) -> CheckResult:
        """检查 Python 版本 >= 3.9"""
        major, minor, micro = sys.version_info[:3]
        ver_str = f"Python {major}.{minor}.{micro}"

        if (major, minor) >= (3, 9):
            return self._add("Python 版本", True, f"{ver_str} >= 3.9 OK", sys.executable)
        else:
            return self._add(
                "Python 版本",
                False,
                f"{ver_str} < 3.9，请升级 Python",
                "参考: https://www.python.org/downloads/"
            )

    def check_path_length(self) -> CheckResult:
        """检查路径长度（Windows 260 字符限制）"""
        system = platform.system()
        root_str = str(self.project_root)
        path_len = len(root_str)

        if system != "Windows":
            return self._add(
                "路径长度",
                True,
                f"非 Windows 系统，无路径长度限制 (当前路径长 {path_len})",
                root_str
            )

        if path_len > self.WINDOWS_MAX_PATH - 60:
            # 留 60 字符余量给子路径
            msg = (
                f"项目路径较长 ({path_len} 字符)，可能触发 Windows MAX_PATH={self.WINDOWS_MAX_PATH} 限制。"
                " 建议开启「长路径支持」或将项目移至更短路径。"
            )
            return self._add("路径长度", False, msg, root_str)

        return self._add(
            "路径长度",
            True,
            f"路径长度 {path_len} 字符，在 Windows 限制 {self.WINDOWS_MAX_PATH} 内",
            root_str
        )

    def check_encoding(self) -> CheckResult:
        """检测终端编码，推荐 UTF-8"""
        fs_encoding = sys.getfilesystemencoding()
        preferred = locale.getpreferredencoding(False)
        stdout_enc = getattr(sys.stdout, "encoding", "unknown") or "unknown"

        detail = (
            f"文件系统编码={fs_encoding}, "
            f"系统首选编码={preferred}, "
            f"stdout编码={stdout_enc}"
        )

        # Windows 旧版控制台可能使用 GBK/CP936
        if stdout_enc.upper() in ("UTF-8", "UTF8", "UTF_8"):
            return self._add("终端编码", True, f"stdout 编码为 UTF-8 OK", detail)

        # 常见非 UTF-8 编码提示
        hint = ""
        if platform.system() == "Windows":
            hint = " 可在 PowerShell 执行 `chcp 65001` 切换为 UTF-8"
        msg = f"stdout 编码为 {stdout_enc}，中文显示可能异常。{hint}"
        return self._add("终端编码", False, msg, detail)

    def check_directory_permissions(self) -> CheckResult:
        """检查关键目录的读写权限"""
        required_dirs = [
            self.project_root / "data_logs",
            self.project_root / "logs",
        ]

        failures = []
        for d in required_dirs:
            # 目录存在则测试写入，不存在则测试父目录可创建
            test_dir = d if d.exists() else d.parent
            try:
                with tempfile.NamedTemporaryFile(dir=test_dir, delete=True):
                    pass  # 写入成功
            except (OSError, PermissionError) as exc:
                failures.append(f"{d}: {exc}")

        if failures:
            return self._add(
                "目录权限",
                False,
                f"{len(failures)} 个目录权限不足",
                "\n".join(failures)
            )
        return self._add(
            "目录权限",
            True,
            f"已检查 {len(required_dirs)} 个关键目录，权限正常"
        )

    def check_disk_space(self, min_mb: int = 200) -> CheckResult:
        """检查项目目录磁盘可用空间"""
        try:
            usage = shutil.disk_usage(self.project_root)
            free_mb = usage.free / (1024 * 1024)
            total_mb = usage.total / (1024 * 1024)

            detail = (
                f"总容量={total_mb:.0f}MB, "
                f"已用={( usage.used / 1024 / 1024):.0f}MB, "
                f"可用={free_mb:.0f}MB"
            )

            if free_mb < min_mb:
                return self._add(
                    "磁盘空间",
                    False,
                    f"可用空间不足！{free_mb:.0f}MB < {min_mb}MB",
                    detail
                )
            return self._add("磁盘空间", True, f"可用 {free_mb:.0f}MB OK", detail)
        except Exception as exc:
            return self._add("磁盘空间", False, f"检查失败: {exc}")

    def check_long_path_support(self) -> CheckResult:
        """仅 Windows：检测是否开启了长路径支持"""
        if platform.system() != "Windows":
            return self._add("长路径支持", True, "非 Windows 系统，跳过此检查")

        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\FileSystem"
            )
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            winreg.CloseKey(key)
            if value == 1:
                return self._add("长路径支持", True, "Windows 长路径支持已启用 OK")
            else:
                return self._add(
                    "长路径支持",
                    False,
                    "Windows 长路径支持未启用，深层嵌套路径可能失败。"
                    " 建议在「组策略 > 计算机配置 > 管理模板 > 系统 > 文件系统」中开启",
                )
        except Exception:
            return self._add("长路径支持", False, "无法读取注册表，请手动确认长路径设置")

    def check_symlink_support(self) -> CheckResult:
        """检测符号链接支持（Windows 需管理员权限或开发者模式）"""
        test_target = self.project_root / ".platform_test_target"
        test_link = self.project_root / ".platform_test_link"
        try:
            test_target.write_text("test")
            test_link.symlink_to(test_target)
            test_link.unlink()
            test_target.unlink()
            return self._add("符号链接", True, "符号链接支持正常 OK")
        except (OSError, NotImplementedError):
            # 清理残留
            for p in (test_link, test_target):
                try:
                    p.unlink()
                except Exception:
                    pass
            if platform.system() == "Windows":
                msg = "符号链接不可用（Windows 需开发者模式或管理员权限），项目功能不受影响"
            else:
                msg = "符号链接不可用，请检查文件系统和权限"
            return self._add("符号链接", False, msg)
        except Exception as exc:
            return self._add("符号链接", False, f"检查失败: {exc}")

    # -------------------------------------------------------------------------
    # 汇总入口
    # -------------------------------------------------------------------------

    def run_all_checks(self) -> Tuple[bool, List[str]]:
        """运行所有检查，返回 (全部通过, 问题列表)"""
        self.results.clear()

        self.check_os()
        self.check_python_version()
        self.check_path_length()
        self.check_encoding()
        self.check_directory_permissions()
        self.check_disk_space()
        self.check_long_path_support()
        self.check_symlink_support()

        issues = [r.message for r in self.results if not r.passed]
        all_passed = len(issues) == 0
        return all_passed, issues

    def get_platform_info(self) -> Dict[str, Any]:
        """返回平台信息摘要字典"""
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_executable": sys.executable,
            "encoding_fs": sys.getfilesystemencoding(),
            "encoding_stdout": getattr(sys.stdout, "encoding", "unknown"),
            "project_root": str(self.project_root),
            "cwd": str(Path.cwd()),
        }

    def print_report(self):
        """打印可读的检查报告"""
        # Windows 旧控制台可能不支持 emoji，安全输出
        import sys
        safe_mode = getattr(sys.stdout, 'encoding', 'utf-8').lower() not in ('utf-8', 'utf8')
        ok_mark  = '[OK] ' if safe_mode else '\u2705'
        bad_mark = '[!]  ' if safe_mode else '\u26a0\ufe0f '

        info = self.get_platform_info()
        print("=" * 60)
        print("  跨平台兼容性检查报告")
        print("=" * 60)
        print(f"  操作系统  : {info['os']} {info['os_release']} ({info['machine']})")
        print(f"  Python    : {info['python_version']} ({info['python_executable']})")
        print(f"  项目根目录 : {info['project_root']}")
        print(f"  终端编码  : {info['encoding_stdout']}")
        print("-" * 60)

        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)

        for r in self.results:
            icon = ok_mark if r.passed else bad_mark
            print(f"  {icon}  {r.name}: {r.message}")
            if r.detail and not r.passed:
                for line in r.detail.splitlines():
                    print(f"       -> {line}")

        print("-" * 60)
        if passed_count == total_count:
            print(f"  [成功] 所有 {total_count} 项检查通过！平台兼容性良好。")
        else:
            fail_count = total_count - passed_count
            print(
                f"  [注意] {passed_count}/{total_count} 项通过，"
                f"{fail_count} 项需关注（见上方 [!] 条目）"
            )
        print("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """命令行入口 - python -m src.utils.platform_check"""
    import argparse

    parser = argparse.ArgumentParser(
        description="BTC碰撞引擎 - 跨平台兼容性检查工具"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出检查结果"
    )
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=None,
        help="项目根目录路径（默认：自动检测）"
    )
    args = parser.parse_args()

    checker = PlatformChecker(project_root=args.root)
    all_passed, issues = checker.run_all_checks()

    if args.json:
        import json
        result = {
            "all_passed": all_passed,
            "platform": checker.get_platform_info(),
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "detail": r.detail,
                }
                for r in checker.results
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        checker.print_report()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
