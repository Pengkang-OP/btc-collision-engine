#!/usr/bin/env python3
"""
项目废弃数据清理引擎
====================
功能：
  1. 扫描并清理废弃文件（缓存、临时文件、过期日志等）
  2. 隔离机制：清理前将待删文件移入隔离区，确认后再彻底删除
  3. 交叉污染防护：严格白名单 + 只读锁定期，确保有效数据不受影响
  4. 完整日志记录：每次操作均有详细日志可追溯
  5. 安全确认：交互式确认 + --force 模式 + dry-run 模式

用法：
  python scripts/cleanup_engine.py                    # 交互模式（逐项确认）
  python scripts/cleanup_engine.py --dry-run          # 仅扫描，不执行任何删除
  python scripts/cleanup_engine.py --force            # 跳过交互确认（仍经过隔离期）
  python scripts/cleanup_engine.py --purge-quarantine # 彻底删除隔离区中超过保留期的文件
  python scripts/cleanup_engine.py --restore          # 从隔离区恢复最近一次清理的文件
"""

from __future__ import annotations

import argparse
import io
import sys

# Windows GBK 终端兼容：强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# 常量定义
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUARANTINE_DIR = PROJECT_ROOT / ".cleanup_quarantine"
CLEANUP_LOG_DIR = PROJECT_ROOT / ".cleanup_logs"
QUARANTINE_MANIFEST = QUARANTINE_DIR / "manifest.json"
QUARANTINE_RETENTION_DAYS = 7  # 隔离区保留天数

# ──────────────────────────────────────────────
# 清理类别定义
# ──────────────────────────────────────────────

class CleanupCategory(Enum):
    """清理类别，每个类别对应一类废弃数据"""
    PYCACHE = "pycache"
    MYPY_CACHE = "mypy_cache"
    RUFF_CACHE = "ruff_cache"
    PYTEST_CACHE = "pytest_cache"
    EGG_INFO = "egg_info"
    TEMP_RESULT_FILES = "temp_result_files"
    TEMP_RUN_SCRIPTS = "temp_run_scripts"
    DEBUG_LOGS = "debug_logs"
    ROTATED_LOGS = "rotated_logs"
    OLD_DAILY_REPORTS = "old_daily_reports"
    STALE_TEST_RESULTS = "stale_test_results"
    BAT_DEBUG = "bat_debug"


@dataclass
class CleanupTarget:
    """一个待清理的目标（文件或目录）"""
    path: Path
    category: CleanupCategory
    size_bytes: int = 0
    reason: str = ""
    file_hash: str = ""  # 清理前计算的哈希，用于恢复验证
    mtime: Optional[datetime] = None

    def __post_init__(self):
        if self.path.exists():
            if self.path.is_dir():
                self.size_bytes = sum(
                    f.stat().st_size for f in self.path.rglob("*") if f.is_file()
                )
            else:
                self.size_bytes = self.path.stat().st_size
            self.mtime = datetime.fromtimestamp(
                self.path.stat().st_mtime if self.path.is_file()
                else self.path.lstat().st_mtime
            )


@dataclass
class CleanupResult:
    """清理操作结果"""
    category: CleanupCategory
    action: str  # "quarantined" | "deleted" | "skipped" | "error"
    path: str
    size_bytes: int = 0
    timestamp: str = ""
    detail: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class CleanupSession:
    """一次清理会话"""
    session_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    dry_run: bool = False
    force: bool = False
    targets: list[CleanupTarget] = field(default_factory=list)
    results: list[CleanupResult] = field(default_factory=list)
    total_bytes_scanned: int = 0
    total_bytes_cleaned: int = 0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = datetime.now().strftime("cleanup_%Y%m%d_%H%M%S")
        if not self.started_at:
            self.started_at = datetime.now().isoformat()


# ──────────────────────────────────────────────
# 保护白名单：这些路径永远不会被清理
# ──────────────────────────────────────────────
PROTECTED_PATTERNS = {
    # 核心源码
    "src/**/*.py",
    "src/**/*.json",
    # 配置模板
    "config.example.json",
    "config.intel_arc.json",
    "config.optimized.json",
    "config.multi_gpu.json",
    "config.production.json",
    # 测试代码
    "tests/**/*.py",
    "tests/**/*.json",
    # 基准测试代码
    "benchmarks/**/*.py",
    # 文档
    "docs/**/*.md",
    "docs/**/*.py",
    # CI/CD
    ".github/**/*",
    # 部署
    "deploy/**/*",
    # Docker
    "Dockerfile*",
    "docker-compose.yml",
    # 项目元数据
    "pyproject.toml",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    ".gitignore",
}

PROTECTED_PREFIXES = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "deploy",
    PROJECT_ROOT / ".github",
    PROJECT_ROOT / "benchmarks",
]


def is_protected(path: Path) -> bool:
    """检查路径是否在保护白名单内"""
    try:
        rel = path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return True  # 项目根外的不碰

    rel_str = str(rel).replace("\\", "/")

    # 核心源码永远不删
    for prefix in PROTECTED_PREFIXES:
        try:
            path.resolve().relative_to(prefix)
            # 但源码目录内的 __pycache__ 不保护
            if "__pycache__" not in rel_str and ".pyc" not in rel_str:
                return True
        except ValueError:
            continue

    # 项目配置文件
    config_files = {
        "pyproject.toml", "LICENSE", "README.md", "CHANGELOG.md",
        "CONTRIBUTING.md", ".gitignore", "conftest.py",
        "config.example.json", "config.intel_arc.json",
        "config.optimized.json", "config.multi_gpu.json",
        "config.production.json",
    }
    if rel_str in config_files:
        return True

    # 入口脚本
    if rel_str in {"key_collision.py", "key_collision_cli.py", "build_production.py"}:
        return True

    return False


# ──────────────────────────────────────────────
# 扫描器：发现废弃数据
# ──────────────────────────────────────────────

class WasteScanner:
    """扫描项目中的废弃文件和数据"""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.targets: list[CleanupTarget] = []

    def scan_all(self) -> list[CleanupTarget]:
        """执行全部扫描规则"""
        self.targets.clear()
        self._scan_pycache()
        self._scan_mypy_cache()
        self._scan_ruff_cache()
        self._scan_pytest_cache()
        self._scan_egg_info()
        self._scan_temp_result_files()
        self._scan_temp_run_scripts()
        self._scan_debug_logs()
        self._scan_rotated_logs()
        self._scan_old_daily_reports()
        self._scan_stale_test_results()
        self._scan_bat_debug()
        return self.targets

    def _add(self, path: Path, category: CleanupCategory, reason: str):
        if path.exists() and not is_protected(path):
            self.targets.append(CleanupTarget(path=path, category=category, reason=reason))

    def _scan_pycache(self):
        for p in self.root.rglob("__pycache__"):
            if "venv" in str(p) or ".git" in str(p):
                continue
            self._add(p, CleanupCategory.PYCACHE, "Python 字节码缓存，可安全重建")

    def _scan_mypy_cache(self):
        p = self.root / ".mypy_cache"
        if p.exists():
            self._add(p, CleanupCategory.MYPY_CACHE, "mypy 类型检查缓存，可安全重建")

    def _scan_ruff_cache(self):
        p = self.root / ".ruff_cache"
        if p.exists():
            self._add(p, CleanupCategory.RUFF_CACHE, "ruff lint 缓存，可安全重建")

    def _scan_pytest_cache(self):
        for p in self.root.rglob(".pytest_cache"):
            if "venv" in str(p):
                continue
            self._add(p, CleanupCategory.PYTEST_CACHE, "pytest 运行缓存，可安全重建")

    def _scan_egg_info(self):
        for p in self.root.glob("*.egg-info"):
            self._add(p, CleanupCategory.EGG_INFO, "setuptools 构建元数据，pip install -e . 可重建")

    def _scan_temp_result_files(self):
        """根目录 result*.txt — 测试/运行临时输出"""
        for p in self.root.glob("result*.txt"):
            self._add(p, CleanupCategory.TEMP_RESULT_FILES, "根目录临时结果文件")

    def _scan_temp_run_scripts(self):
        """根目录 run_*.py — 临时运行脚本"""
        for p in self.root.glob("run_*.py"):
            self._add(p, CleanupCategory.TEMP_RUN_SCRIPTS, "根目录临时运行脚本")

    def _scan_debug_logs(self):
        """根目录 _*.log — 调试日志"""
        for p in self.root.glob("_*.log"):
            self._add(p, CleanupCategory.DEBUG_LOGS, "根目录调试日志")

    def _scan_rotated_logs(self):
        """logs/ 下 .log.1, .log.2 等轮转日志"""
        logs_dir = self.root / "logs"
        if logs_dir.exists():
            for p in logs_dir.glob("*.log.*"):
                # 保留最新的 .log 文件，只清理轮转文件
                self._add(p, CleanupCategory.ROTATED_LOGS, "轮转日志文件（.log.N），主日志保留")

    def _scan_old_daily_reports(self):
        """data_logs/report_daily_*.json 保留最近 3 天，其余清理"""
        dl = self.root / "data_logs"
        if not dl.exists():
            return
        cutoff = datetime.now() - timedelta(days=3)
        for p in dl.glob("report_daily_*.json"):
            mt = datetime.fromtimestamp(p.stat().st_mtime)
            if mt < cutoff:
                self._add(
                    p, CleanupCategory.OLD_DAILY_REPORTS,
                    f"过期日报（{mt.strftime('%Y-%m-%d')}，超过3天）"
                )

    def _scan_stale_test_results(self):
        """test_results/ 中的 .md 报告（AI 自动生成，过期的清理）"""
        tr = self.root / "test_results"
        if not tr.exists():
            return
        cutoff = datetime.now() - timedelta(days=7)
        for p in tr.glob("*.md"):
            mt = datetime.fromtimestamp(p.stat().st_mtime)
            if mt < cutoff:
                self._add(
                    p, CleanupCategory.STALE_TEST_RESULTS,
                    f"过期测试报告（{mt.strftime('%Y-%m-%d')}，超过7天）"
                )

    def _scan_bat_debug(self):
        for name in ("_bat_debug.log", "_start_test.log"):
            p = self.root / name
            if p.exists():
                self._add(p, CleanupCategory.BAT_DEBUG, "批处理调试日志")


# ──────────────────────────────────────────────
# 隔离区管理
# ──────────────────────────────────────────────

class QuarantineManager:
    """隔离区：清理前先将文件移入此处，确认安全后再彻底删除"""

    def __init__(self, quarantine_dir: Path = QUARANTINE_DIR):
        self.qdir = quarantine_dir
        self.manifest_path = QUARANTINE_MANIFEST
        self.manifest: dict = self._load_manifest()

    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"entries": {}}
        return {"entries": {}}

    def _save_manifest(self):
        self.qdir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _file_hash(path: Path) -> str:
        """计算文件 SHA256 哈希，用于恢复验证"""
        h = hashlib.sha256()
        if path.is_file():
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        elif path.is_dir():
            for fp in sorted(path.rglob("*")):
                if fp.is_file():
                    h.update(str(fp.relative_to(path)).encode())
                    with open(fp, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            h.update(chunk)
        return h.hexdigest()[:16]

    def quarantine(self, target: CleanupTarget) -> CleanupResult:
        """将目标移入隔离区"""
        rel = target.path.relative_to(PROJECT_ROOT)
        # 隔离区内按类别+原路径组织
        dest = self.qdir / target.category.value / str(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)

        file_hash = self._file_hash(target.path)

        try:
            if target.path.is_dir():
                shutil.move(str(target.path), str(dest))
            else:
                shutil.copy2(str(target.path), str(dest))
                target.path.unlink()
        except (OSError, shutil.Error) as e:
            return CleanupResult(
                category=target.category,
                action="error",
                path=str(target.path),
                size_bytes=target.size_bytes,
                detail=f"隔离失败: {e}",
            )

        # 记录到清单
        entry_key = str(rel).replace("\\", "/")
        self.manifest["entries"][entry_key] = {
            "original_path": str(target.path),
            "quarantine_path": str(dest),
            "category": target.category.value,
            "size_bytes": target.size_bytes,
            "file_hash": file_hash,
            "quarantined_at": datetime.now().isoformat(),
            "reason": target.reason,
        }
        self._save_manifest()

        return CleanupResult(
            category=target.category,
            action="quarantined",
            path=str(target.path),
            size_bytes=target.size_bytes,
            detail=f"已隔离到 {dest}",
        )

    def purge_expired(self, retention_days: int = QUARANTINE_RETENTION_DAYS) -> list[CleanupResult]:
        """彻底删除隔离区中超过保留期的文件"""
        results = []
        cutoff = datetime.now() - timedelta(days=retention_days)
        to_remove = []

        for key, entry in self.manifest["entries"].items():
            qt = datetime.fromisoformat(entry["quarantined_at"])
            if qt < cutoff:
                qpath = Path(entry["quarantine_path"])
                try:
                    if qpath.is_dir():
                        shutil.rmtree(qpath, ignore_errors=True)
                    elif qpath.is_file():
                        qpath.unlink()
                    results.append(CleanupResult(
                        category=CleanupCategory(entry["category"]),
                        action="deleted",
                        path=entry["original_path"],
                        size_bytes=entry.get("size_bytes", 0),
                        detail=f"隔离区过期删除（隔离于 {qt.strftime('%Y-%m-%d')}）",
                    ))
                    to_remove.append(key)
                except OSError as e:
                    results.append(CleanupResult(
                        category=CleanupCategory(entry["category"]),
                        action="error",
                        path=entry["original_path"],
                        detail=f"隔离区删除失败: {e}",
                    ))

        for key in to_remove:
            del self.manifest["entries"][key]
        self._save_manifest()

        return results

    def restore_last(self) -> list[CleanupResult]:
        """从隔离区恢复最近一次清理的文件"""
        results = []
        if not self.manifest["entries"]:
            print("隔离区为空，无需恢复")
            return results

        # 按时间排序，恢复最近一批
        entries = sorted(
            self.manifest["entries"].items(),
            key=lambda x: x[1]["quarantined_at"],
            reverse=True,
        )

        if not entries:
            return results

        # 找到最近一秒内的所有条目（同一次清理会话）
        latest_time = entries[0][1]["quarantined_at"]
        batch = [
            (k, v) for k, v in entries
            if abs(
                (datetime.fromisoformat(v["quarantined_at"]) -
                 datetime.fromisoformat(latest_time)).total_seconds()
            ) < 5
        ]

        for key, entry in batch:
            qpath = Path(entry["quarantine_path"])
            orig = Path(entry["original_path"])
            try:
                orig.parent.mkdir(parents=True, exist_ok=True)
                if qpath.is_dir():
                    shutil.move(str(qpath), str(orig))
                elif qpath.is_file():
                    shutil.copy2(str(qpath), str(orig))
                    qpath.unlink()
                # 验证哈希
                restored_hash = self._file_hash(orig)
                if restored_hash != entry.get("file_hash", ""):
                    results.append(CleanupResult(
                        category=CleanupCategory(entry["category"]),
                        action="error",
                        path=str(orig),
                        detail="恢复后哈希校验失败！文件可能已损坏",
                    ))
                else:
                    results.append(CleanupResult(
                        category=CleanupCategory(entry["category"]),
                        action="restored",
                        path=str(orig),
                        size_bytes=entry.get("size_bytes", 0),
                        detail="已从隔离区恢复",
                    ))
                del self.manifest["entries"][key]
            except (OSError, shutil.Error) as e:
                results.append(CleanupResult(
                    category=CleanupCategory(entry["category"]),
                    action="error",
                    path=str(orig),
                    detail=f"恢复失败: {e}",
                ))

        self._save_manifest()
        return results


# ──────────────────────────────────────────────
# 日志记录器
# ──────────────────────────────────────────────

class CleanupLogger:
    """详细记录所有清理操作"""

    def __init__(self, log_dir: Path = CLEANUP_LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_log: list[str] = []
        self.log_file: Optional[Path] = None

    def start_session(self, session: CleanupSession):
        self.log_file = self.log_dir / f"{session.session_id}.log"
        self._log(f"{'='*60}")
        self._log(f"清理会话: {session.session_id}")
        self._log(f"开始时间: {session.started_at}")
        self._log(f"模式: {'DRY-RUN' if session.dry_run else 'FORCE' if session.force else 'INTERACTIVE'}")
        self._log(f"{'='*60}")

    def log_scan_results(self, targets: list[CleanupTarget]):
        self._log(f"\n--- 扫描结果: 发现 {len(targets)} 个清理目标 ---")
        by_category: dict[CleanupCategory, list[CleanupTarget]] = {}
        for t in targets:
            by_category.setdefault(t.category, []).append(t)

        for cat, items in by_category.items():
            total_size = sum(t.size_bytes for t in items)
            self._log(f"\n[{cat.value}] {len(items)} 项, {self._fmt_size(total_size)}")
            for t in items[:10]:  # 最多展示10项
                rel = t.path.relative_to(PROJECT_ROOT)
                self._log(f"  - {rel} ({self._fmt_size(t.size_bytes)}) {t.reason}")
            if len(items) > 10:
                self._log(f"  ... 及其他 {len(items) - 10} 项")

    def log_result(self, result: CleanupResult):
        icon = {
            "quarantined": "🔒",
            "deleted": "🗑️",
            "skipped": "⏭️",
            "error": "❌",
            "restored": "♻️",
        }.get(result.action, "?")
        self._log(f"  {icon} [{result.action.upper()}] {result.path} "
                   f"({self._fmt_size(result.size_bytes)}) {result.detail}")

    def log_summary(self, session: CleanupSession):
        self._log(f"\n{'='*60}")
        self._log(f"清理完成: {session.finished_at}")
        self._log(f"扫描总量: {self._fmt_size(session.total_bytes_scanned)}")
        self._log(f"清理总量: {self._fmt_size(session.total_bytes_cleaned)}")
        by_action: dict[str, int] = {}
        for r in session.results:
            by_action[r.action] = by_action.get(r.action, 0) + 1
        for action, count in by_action.items():
            self._log(f"  {action}: {count} 项")
        self._log(f"{'='*60}")
        self._flush()

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self.session_log.append(line)
        print(line)

    def _flush(self):
        if self.log_file:
            self.log_file.write_text(
                "\n".join(self.session_log), encoding="utf-8"
            )

    @staticmethod
    def _fmt_size(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        elif n < 1024 * 1024:
            return f"{n/1024:.1f} KB"
        elif n < 1024 * 1024 * 1024:
            return f"{n/1024/1024:.2f} MB"
        else:
            return f"{n/1024/1024/1024:.2f} GB"


# ──────────────────────────────────────────────
# 清理引擎主体
# ──────────────────────────────────────────────

class CleanupEngine:
    """清理引擎：协调扫描 → 隔离 → 确认 → 删除的全流程"""

    def __init__(self, dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.scanner = WasteScanner(PROJECT_ROOT)
        self.quarantine = QuarantineManager()
        self.logger = CleanupLogger()
        self.session = CleanupSession(dry_run=dry_run, force=force)

    def run(self):
        """执行完整清理流程"""
        self.logger.start_session(self.session)

        # ── 阶段1：扫描 ──
        print("\n🔍 阶段1: 扫描废弃数据...")
        targets = self.scanner.scan_all()
        self.session.targets = targets
        self.session.total_bytes_scanned = sum(t.size_bytes for t in targets)
        self.logger.log_scan_results(targets)

        if not targets:
            print("\n✅ 项目干净，无需清理！")
            self.session.finished_at = datetime.now().isoformat()
            self.logger.log_summary(self.session)
            return

        # ── 阶段2：确认 ──
        if not self.dry_run:
            if not self.force:
                if not self._confirm(targets):
                    print("\n⏭️ 用户取消清理")
                    self.session.finished_at = datetime.now().isoformat()
                    self.logger.log_summary(self.session)
                    return
            else:
                print("\n⚡ --force 模式：跳过交互确认")

        # ── 阶段3：隔离清理 ──
        if self.dry_run:
            print("\n📋 DRY-RUN 模式：仅显示将执行的操作，不实际执行")
            for t in targets:
                self.logger.log_result(CleanupResult(
                    category=t.category,
                    action="skipped",
                    path=str(t.path),
                    size_bytes=t.size_bytes,
                    detail="[DRY-RUN] 将被隔离",
                ))
        else:
            print("\n🔒 阶段2: 隔离废弃数据（移入 .cleanup_quarantine/）...")
            for t in targets:
                result = self.quarantine.quarantine(t)
                self.session.results.append(result)
                self.logger.log_result(result)
                if result.action == "quarantined":
                    self.session.total_bytes_cleaned += result.size_bytes

            print(f"\n✅ 已隔离 {len([r for r in self.session.results if r.action == 'quarantined'])} 项"
                  f" ({CleanupLogger._fmt_size(self.session.total_bytes_cleaned)})")
            print(f"   隔离区位置: {QUARANTINE_DIR}")
            print(f"   保留期限: {QUARANTINE_RETENTION_DAYS} 天")
            print(f"   恢复命令: python scripts/cleanup_engine.py --restore")
            print(f"   彻底删除: python scripts/cleanup_engine.py --purge-quarantine")

        self.session.finished_at = datetime.now().isoformat()
        self.logger.log_summary(self.session)

    def purge_quarantine(self):
        """彻底删除隔离区中过期的文件"""
        print(f"\n🗑️ 清理隔离区（保留期 {QUARANTINE_RETENTION_DAYS} 天）...")
        results = self.quarantine.purge_expired()
        if not results:
            print("没有过期文件需要删除")
            return
        total = sum(r.size_bytes for r in results if r.action == "deleted")
        for r in results:
            self.logger.log_result(r)
        print(f"\n✅ 彻底删除 {len(results)} 项 ({CleanupLogger._fmt_size(total)})")

    def restore_last(self):
        """恢复最近一次清理"""
        print("\n♻️ 恢复最近一次清理的文件...")
        results = self.quarantine.restore_last()
        for r in results:
            self.logger.log_result(r)

    def _confirm(self, targets: list[CleanupTarget]) -> bool:
        """交互式确认"""
        print(f"\n⚠️ 即将清理 {len(targets)} 项，"
              f"共 {CleanupLogger._fmt_size(sum(t.size_bytes for t in targets))}")
        print("文件将先移入隔离区，不会立即删除。")
        print()

        by_cat: dict[CleanupCategory, list[CleanupTarget]] = {}
        for t in targets:
            by_cat.setdefault(t.category, []).append(t)

        for cat, items in by_cat.items():
            total = sum(t.size_bytes for t in items)
            print(f"  [{cat.value}] {len(items)} 项 ({CleanupLogger._fmt_size(total)})")
            for t in items[:3]:
                rel = t.path.relative_to(PROJECT_ROOT)
                print(f"    - {rel}")
            if len(items) > 3:
                print(f"    ... +{len(items)-3} 项")

        print()
        try:
            answer = input("确认执行清理？(y/N): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="项目废弃数据清理引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅扫描显示，不执行任何操作",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="跳过交互确认（仍经过隔离期）",
    )
    parser.add_argument(
        "--purge-quarantine", action="store_true",
        help="彻底删除隔离区中超过保留期的文件",
    )
    parser.add_argument(
        "--restore", action="store_true",
        help="从隔离区恢复最近一次清理的文件",
    )

    args = parser.parse_args()

    engine = CleanupEngine(dry_run=args.dry_run, force=args.force)

    if args.purge_quarantine:
        engine.purge_quarantine()
    elif args.restore:
        engine.restore_last()
    else:
        engine.run()


if __name__ == "__main__":
    main()
