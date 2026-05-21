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

import locale
import platform
import shutil
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..i18n import _t
from ..utils import get_configured_logger

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("PlatformChecker")


# ─────────────────────────────────────────────────────────────────────────────
# 结果数据类
# ─────────────────────────────────────────────────────────────────────────────


class CheckResult:
    """单项检查结果"""

    def __init__(self, name: str, passed: bool, message: str, detail: str = "") -> None:
        self.name = name
        self.passed = passed
        self.message = message
        self.detail = detail

    def __repr__(self) -> str:
        status = "✅" if self.passed else "⚠️"
        return f"{status} {self.name}: {self.message}"


# ─────────────────────────────────────────────────────────────────────────────
# 核心检查器
# ─────────────────────────────────────────────────────────────────────────────


class PlatformChecker:
    """跨平台兼容性检查器"""

    # Windows MAX_PATH 限制
    WINDOWS_MAX_PATH = 260

    def __init__(self, project_root: str | None = None) -> None:
        """初始化检查器

        Args:
            project_root: 项目根目录路径，默认为当前文件向上两级
        """
        if project_root is None:
            project_root = str(Path(__file__).resolve().parent.parent.parent)
        self.project_root = Path(project_root)
        self.results: list[CheckResult] = []

    # -------------------------------------------------------------------------
    # 内部工具
    # -------------------------------------------------------------------------

    def _add(self, name: str, passed: bool, message: str, detail: str = "") -> CheckResult:
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

        detail = _t(
            "platform.check.detail_os",
            system=system,
            release=release,
            machine=machine,
            version=version[:60],
        )

        if system in ("Windows", "Linux", "Darwin"):
            msg = _t("platform.check.os_supported", os_name=f"{system} {release} ({machine})")
            return self._add(_t("platform.check.name_os"), True, msg, detail)
        else:
            msg = _t("platform.check.os_unsupported", os_name=system)
            return self._add(_t("platform.check.name_os"), False, msg, detail)

    def check_python_version(self) -> CheckResult:
        """检查 Python 版本 >= 3.9"""
        major, minor, micro = sys.version_info[:3]
        ver_str = f"Python {major}.{minor}.{micro}"

        if (major, minor) >= (3, 9):
            return self._add(
                _t("platform.check.name_python"),
                True,
                _t("platform.check.python_ok", version=ver_str),
                sys.executable,
            )
        else:
            return self._add(
                _t("platform.check.name_python"),
                False,
                _t("platform.check.python_low", version=ver_str, required="3.9"),
                "参考: https://www.python.org/downloads/",
            )

    def check_path_length(self) -> CheckResult:
        """检查路径长度（Windows 260 字符限制）"""
        system = platform.system()
        root_str = str(self.project_root)
        path_len = len(root_str)

        if system != "Windows":
            return self._add(
                _t("platform.check.name_path"),
                True,
                _t("platform.check.path_length_non_windows", path_len=path_len),
                root_str,
            )

        if path_len > self.WINDOWS_MAX_PATH - 60:
            # 留 60 字符余量给子路径
            msg = _t(
                "platform.check.path_length_long", path_len=path_len, max_path=self.WINDOWS_MAX_PATH
            )
            return self._add(_t("platform.check.name_path"), False, msg, root_str)

        return self._add(
            _t("platform.check.name_path"),
            True,
            _t("platform.check.path_length_ok", path_len=path_len, max_path=self.WINDOWS_MAX_PATH),
            root_str,
        )

    def check_encoding(self) -> CheckResult:
        """检测终端编码，推荐 UTF-8"""
        fs_encoding = sys.getfilesystemencoding()
        preferred = locale.getpreferredencoding(False)
        stdout_enc = getattr(sys.stdout, "encoding", "unknown") or "unknown"

        detail = _t(
            "platform.check.detail_encoding",
            fs_encoding=fs_encoding,
            preferred=preferred,
            stdout_enc=stdout_enc,
        )

        # Windows 旧版控制台可能使用 GBK/CP936
        if stdout_enc.upper() in ("UTF-8", "UTF8", "UTF_8"):
            return self._add(
                _t("platform.check.name_encoding"),
                True,
                _t("platform.check.encoding_ok", encoding=stdout_enc),
                detail,
            )

        # 常见非 UTF-8 编码提示
        hint = ""
        if platform.system() == "Windows":
            hint = _t("platform.check.encoding_win_hint")
        msg = _t("platform.check.encoding_warn", encoding=stdout_enc) + hint
        return self._add(_t("platform.check.name_encoding"), False, msg, detail)

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
                _t("platform.check.name_permission"),
                False,
                _t("platform.check.permission_denied", path=f"{len(failures)} dirs"),
                "\n".join(failures),
            )
        return self._add(
            _t("platform.check.name_permission"), True, _t("platform.check.permission_ok")
        )

    def check_disk_space(self, min_mb: int = 200) -> CheckResult:
        """检查项目目录磁盘可用空间"""
        try:
            usage = shutil.disk_usage(self.project_root)
            free_mb = usage.free / (1024 * 1024)
            total_mb = usage.total / (1024 * 1024)

            detail = _t(
                "platform.check.detail_disk",
                total_mb=total_mb,
                used_mb=usage.used / 1024 / 1024,
                free_mb=free_mb,
            )

            if free_mb < min_mb:
                return self._add(
                    _t("platform.check.name_disk"),
                    False,
                    _t("platform.check.disk_low_mb", free_mb=free_mb, min_mb=min_mb),
                    detail,
                )
            return self._add(
                _t("platform.check.name_disk"),
                True,
                _t("platform.check.disk_ok_mb", free_mb=free_mb),
                detail,
            )
        except Exception as exc:
            return self._add(
                _t("platform.check.name_disk"),
                False,
                _t("platform.check.disk_check_failed", error=exc),
            )

    def check_long_path_support(self) -> CheckResult:
        """仅 Windows：检测是否开启了长路径支持"""
        if platform.system() != "Windows":
            return self._add(
                _t("platform.check.name_long_path"), True, _t("platform.check.long_path_skipped")
            )

        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem"
            )
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            winreg.CloseKey(key)
            if value == 1:
                return self._add(
                    _t("platform.check.name_long_path"),
                    True,
                    _t("platform.check.long_path_enabled"),
                )
            else:
                return self._add(
                    _t("platform.check.name_long_path"),
                    False,
                    _t("platform.check.long_path_disabled"),
                )
        except OSError:
            return self._add(
                _t("platform.check.name_long_path"),
                False,
                _t("platform.check.long_path_check_failed"),
            )

    def check_symlink_support(self) -> CheckResult:
        """检测符号链接支持（Windows 需管理员权限或开发者模式）"""
        test_target = self.project_root / ".platform_test_target"
        test_link = self.project_root / ".platform_test_link"
        try:
            test_target.write_text("test")
            test_link.symlink_to(test_target)
            test_link.unlink()
            test_target.unlink()
            return self._add(
                _t("platform.check.name_symlink"), True, _t("platform.check.symlink_ok")
            )
        except (OSError, NotImplementedError):
            # 清理残留
            for p in (test_link, test_target):
                with suppress(OSError):
                    p.unlink()
            if platform.system() == "Windows":
                msg = _t("platform.check.symlink_unavailable_win")
            else:
                msg = _t("platform.check.symlink_unavailable")
            return self._add(_t("platform.check.name_symlink"), False, msg)
        except Exception as exc:
            return self._add(
                _t("platform.check.name_symlink"),
                False,
                _t("platform.check.symlink_check_failed", error=exc),
            )

    # -------------------------------------------------------------------------
    # 汇总入口
    # -------------------------------------------------------------------------

    def run_all_checks(self) -> tuple[bool, list[str]]:
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

    def get_platform_info(self) -> dict[str, Any]:
        """返回平台信息摘要字典"""
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "python_version": (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            ),
            "python_executable": sys.executable,
            "encoding_fs": sys.getfilesystemencoding(),
            "encoding_stdout": getattr(sys.stdout, "encoding", "unknown"),
            "project_root": str(self.project_root),
            "cwd": str(Path.cwd()),
        }

    def print_report(self) -> None:
        """打印可读的检查报告"""
        # Windows 旧控制台可能不支持 emoji，安全输出
        import sys

        safe_mode = getattr(sys.stdout, "encoding", "utf-8").lower() not in ("utf-8", "utf8")
        ok_mark = "[OK] " if safe_mode else "\u2705"
        bad_mark = "[!]  " if safe_mode else "\u26a0\ufe0f "

        info = self.get_platform_info()
        print("=" * 60)
        print("  " + _t("platform.check.report_title"))
        print("=" * 60)
        print(
            "  "
            + _t(
                "platform.check.report_os",
                os=info["os"],
                release=info["os_release"],
                machine=info["machine"],
            )
        )
        print(
            "  "
            + _t(
                "platform.check.report_python",
                version=info["python_version"],
                executable=info["python_executable"],
            )
        )
        print("  " + _t("platform.check.report_root", root=info["project_root"]))
        print("  " + _t("platform.check.report_encoding", encoding=info["encoding_stdout"]))
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
            print("  " + _t("platform.check.report_all_passed", total=total_count))
        else:
            fail_count = total_count - passed_count
            print(
                "  "
                + _t(
                    "platform.check.report_some_failed",
                    passed=passed_count,
                    total=total_count,
                    failed=fail_count,
                )
            )
        print("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """命令行入口 - python -m src.utils.platform_check"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC碰撞引擎 - 跨平台兼容性检查工具")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检查结果")
    parser.add_argument(
        "--root", metavar="PATH", default=None, help="项目根目录路径（默认：自动检测）"
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
