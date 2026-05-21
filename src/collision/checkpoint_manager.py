"""断点管理器"""

import binascii
import json
import os
import threading
import time
import traceback
import zlib
from contextlib import suppress
from datetime import datetime
from typing import Any, cast

# 导入日志配置
from .. import __version__ as _project_version
from ..utils import get_configured_logger
from ..utils.fast_json import fast_dumps, fast_loads
from ..utils.platform_utils import PlatformUtils

# 获取模块日志记录器
logger = get_configured_logger("CheckpointManager")


class CheckpointManager:
    """断点管理器 - 保存和恢复对撞进度"""

    DEFAULT_FILE = "collision_checkpoint.json"
    # v4.3.1: zlib 压缩阈值 (字节)，超过此大小自动压缩；0 表示禁用
    COMPRESSION_THRESHOLD_BYTES: int = 1024 * 1024  # 1 MB
    # 压缩级别 (1-9, 默认 6 平衡速度和压缩比)
    COMPRESSION_LEVEL: int = 6
    # 压缩魔数 (3 bytes) + 版本号 (1 byte)
    COMPRESSION_MAGIC: bytes = b"CMP"
    COMPRESSION_VERSION: int = 1

    # 类级别的pywin32可用性检查
    _has_win32_security = None

    @classmethod
    def _check_win32_security(cls) -> bool:
        """检查pywin32是否可用（类级别的一次性检查）"""
        if cls._has_win32_security is None:
            try:
                import ntsecuritycon  # noqa: F401
                import win32security  # noqa: F401

                cls._has_win32_security = True
            except ImportError:
                cls._has_win32_security = False
        return cls._has_win32_security

    def __init__(self, filepath: str | None = None, auto_save_interval: int = 30) -> None:
        # 确保pywin32可用性检查已执行
        self._has_win32_security = self._check_win32_security()

        # 修复: 默认断点路径使用data_logs目录（有写入权限）
        if filepath is None:
            # 获取项目根目录（src的父目录）
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_logs_dir = os.path.join(project_root, "data_logs")
            # 确保data_logs目录存在
            os.makedirs(data_logs_dir, exist_ok=True)
            self.filepath = os.path.join(data_logs_dir, self.DEFAULT_FILE)
        else:
            self.filepath = filepath
        self.auto_save_interval = auto_save_interval
        self._last_save_time = 0.0
        self._lock = threading.Lock()  # 线程锁保护文件操作
        self._dirty = False  # 脏标志，标记是否有未保存的更改
        self._buffer: dict[str, Any] | None = None  # 缓冲区，用于批量保存
        _interval = auto_save_interval
        _win32 = self._has_win32_security
        logger.debug(
            f"CheckpointManager 初始化: 文件={self.filepath}, 自动保存={_interval}s, pywin32={_win32}"
        )

    def save(
        self,
        mode: str,
        targets: set[str],
        current_position: int,
        total_checked: int,
        matches: list[dict],
        range_start: int | None = None,
        range_end: int | None = None,
        force: bool = False,
    ) -> None:
        """保存断点到 JSON 文件（线程安全）

        安全说明:
        - 匹配的私钥信息不会被保存到断点文件
        - 仅保存地址和时间戳用于统计
        - 敏感数据通过回调单独处理

        参数:
            mode: 对撞模式
            targets: 目标地址集合
            current_position: 当前位置
            total_checked: 已检查数量
            matches: 匹配列表
            range_start: 范围起始值
            range_end: 范围结束值
            force: 是否强制保存（忽略缓冲区）
        """
        with self._lock:  # 确保线程安全
            # 清理敏感信息：仅保存地址，不保存私钥
            sanitized_matches = []
            for match in matches:
                # 只保留非敏感字段
                safe_match = {
                    "address": match.get("address", ""),
                    "timestamp": match.get("timestamp", 0),
                }
                # 可选：保存私钥的哈希值用于验证（不包含实际私钥）
                if "private_key_hash" in match:
                    safe_match["private_key_hash"] = match["private_key_hash"]
                sanitized_matches.append(safe_match)

            # 构建断点数据（不含校验和，校验和在序列化后计算）
            self._buffer = {
                "version": 1,  # 格式版本
                "project_version": _project_version,  # 项目版本 (C-02: 版本兼容性修复)
                "timestamp": datetime.now().isoformat(),
                "mode": mode,
                "targets": list(targets),
                "current_position": current_position,
                "total_checked": total_checked,
                "matches": sanitized_matches,  # 使用清理后的数据
                "range_start": range_start,
                "range_end": range_end,
                "security_note": "私钥信息未保存，仅用于运行时内存处理",
            }
            # v4.5.1: 添加 CRC32 校验和以检测文件损坏
            self._buffer["checksum"] = self._compute_checksum(self._buffer)

            # 标记为脏
            self._dirty = True

            # 只有在强制保存或时间间隔达到时才写入文件
            if force or self.should_auto_save():
                self._flush_buffer()

    # ── _flush_buffer 辅助方法（提取以降低 C901） ─────────────────

    def _write_checkpoint_to_temp(self, temp_filepath: str, serialized: str) -> None:
        """将序列化数据写入临时文件（支持压缩）。"""
        use_compression = (
            self.COMPRESSION_THRESHOLD_BYTES > 0
            and len(serialized.encode("utf-8")) > self.COMPRESSION_THRESHOLD_BYTES
        )
        if use_compression:
            compressed = zlib.compress(serialized.encode("utf-8"), self.COMPRESSION_LEVEL)
            header = self.COMPRESSION_MAGIC + bytes([self.COMPRESSION_VERSION])
            with open(temp_filepath, "wb") as f:
                f.write(header)
                f.write(compressed)
            logger.debug(
                f"断点压缩保存: {len(serialized):,}B -> {len(compressed):,}B "
                f"({len(compressed) / max(len(serialized), 1) * 100:.1f}%)"
            )
        else:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                f.write(serialized)

    def _set_posix_file_permissions(self, filepath: str) -> None:
        """在 POSIX 系统上设置文件权限为 0o600。"""
        if PlatformUtils.is_windows():
            return
        try:
            os.chmod(filepath, 0o600)
            logger.debug("已设置文件权限: 0o600")
        except OSError as e:
            logger.debug(f"文件权限设置失败（非致命）: {e}")

    def _set_windows_file_permissions(self) -> None:
        """在 Windows 上设置文件 ACL（pywin32 优先，fallback icacls）。"""
        if self._has_win32_security:
            self._set_windows_acl_via_pywin32()
        else:
            self._set_windows_acl_via_icacls()

    def _set_windows_acl_via_pywin32(self) -> None:
        """通过 pywin32 设置 Windows 文件 DACL。"""
        try:
            import getpass

            import ntsecuritycon as con
            import win32security

            handle = win32security.GetFileSecurity(
                self.filepath, win32security.DACL_SECURITY_INFORMATION
            )
            dacl = win32security.ACL()
            username = getpass.getuser()
            sid, _, _ = win32security.LookupAccountName(None, username)
            dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, sid)
            handle.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                self.filepath, win32security.DACL_SECURITY_INFORMATION, handle
            )
            logger.debug("已设置Windows文件权限（仅当前用户可访问）")
        except Exception as e:
            logger.debug(f"pywin32权限设置失败: {e}，尝试使用icacls")
            self._set_windows_acl_via_icacls()

    def _set_windows_acl_via_icacls(self) -> None:
        """通过 icacls 命令设置 Windows 文件权限。"""
        try:
            import getpass
            import subprocess  # nosec B404

            username = getpass.getuser()
            cmd = [
                "icacls", self.filepath,
                "/inheritance:r", "/grant:r", f"{username}:F", "/Q",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
            if result.returncode == 0:
                logger.debug("已使用icacls设置Windows文件权限（仅当前用户可访问）")
            else:
                logger.warning(f"icacls权限设置失败: {result.stderr}")
        except (OSError, FileNotFoundError, RuntimeError):
            logger.debug("icacls命令执行失败，跳过Windows权限设置")

    def _set_file_permissions(self) -> None:
        """跨平台设置目标文件权限（不影响主流程）。"""
        try:
            self._set_posix_file_permissions(self.filepath)
            if PlatformUtils.is_windows():
                self._set_windows_file_permissions()
        except (OSError, RuntimeError) as e:
            logger.warning(f"文件权限设置失败: {e}")

    # ── _flush_buffer 主方法（C901 已清零） ────────────────────────

    def _flush_buffer(self) -> None:
        """将缓冲区数据写入文件（内部方法）"""
        if not self._dirty or self._buffer is None:
            return

        try:
            logger.debug(f"开始保存断点: {self.filepath}")

            # 确保目录存在
            dir_path = os.path.dirname(self.filepath)
            if not os.path.exists(dir_path):
                logger.debug(f"创建目录: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)

            # 使用临时文件+原子重命名机制，确保文件完整性
            temp_filepath = f"{self.filepath}.tmp"
            logger.debug(f"写入临时文件: {temp_filepath}")

            # 序列化并写入临时文件
            serialized = fast_dumps(self._buffer, ensure_ascii=False, indent=2)
            if isinstance(serialized, bytes):
                serialized = serialized.decode("utf-8")
            self._write_checkpoint_to_temp(temp_filepath, serialized)
            logger.debug("临时文件写入成功")

            # Q3修复: 临时文件安全权限
            self._set_posix_file_permissions(temp_filepath)

            # 原子重命名（跨平台兼容）
            logger.debug(f"原子重命名: {temp_filepath} -> {self.filepath}")
            os.replace(temp_filepath, self.filepath)
            logger.debug("原子重命名成功")

            # 设置文件权限（跨平台兼容）
            self._set_file_permissions()

            # 清理可能的旧临时文件
            self._cleanup_temp_file(temp_filepath)

            # v4.2.2 M10: 使用 monotonic 时间
            self._last_save_time = time.monotonic()
            self._dirty = False
            _pos = self._buffer.get("current_position")
            _checked = self._buffer.get("total_checked")
            logger.debug(f"断点已保存: {self.filepath}, 位置={_pos}, 已检查={_checked}")
        except PermissionError as e:
            logger.error(f"保存断点失败（权限不足）: {e}")
            logger.error(f"文件路径: {self.filepath}")
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        except OSError as e:
            logger.error(f"保存断点失败（I/O错误）: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"保存断点失败（未知错误）: {e}", exc_info=True)
        finally:
            if "temp_filepath" in locals() and temp_filepath:
                self._cleanup_temp_file(temp_filepath)

    def _cleanup_temp_file(self, temp_filepath: str) -> None:
        """清理临时文件"""
        with suppress(OSError):
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

    def load(self) -> dict | None:
        """从文件加载断点，文件不存在或格式错误返回 None（线程安全）"""
        with self._lock:
            try:
                # 检查临时文件是否存在（可能上次写入中断）
                temp_filepath = self.filepath + ".tmp"
                if os.path.exists(temp_filepath) and not os.path.exists(self.filepath):
                    try:
                        os.replace(temp_filepath, self.filepath)
                        if not PlatformUtils.is_windows():
                            with suppress(OSError):
                                os.chmod(self.filepath, 0o600)
                        logger.warning(f"从临时文件恢复断点: {temp_filepath}")
                    except OSError as e:
                        logger.error(f"断点恢复失败: {e}，将重新开始")
                        with suppress(OSError):
                            os.remove(temp_filepath)
                    except Exception as e:
                        logger.error(f"断点恢复未知错误: {type(e).__name__}: {e}")

                with open(self.filepath, "rb") as f:
                    raw = f.read()
                # v4.3.1: 检测压缩魔数（magic 3B + version 1B）并自动解压
                if raw[:3] == self.COMPRESSION_MAGIC:
                    version = raw[3] if len(raw) > 3 else 0
                    if version != self.COMPRESSION_VERSION:
                        logger.warning(
                            f"压缩格式版本不兼容: checkpoint={version}, "
                            f"current={self.COMPRESSION_VERSION}，尝试解压"
                        )
                    decompressed = zlib.decompress(raw[4:])
                    data = fast_loads(decompressed.decode("utf-8"))
                    logger.debug(f"断点已解压加载: {len(raw):,}B -> {len(decompressed):,}B")
                else:
                    data = fast_loads(raw.decode("utf-8"))

                # v4.5.1: 校验 CRC32 校验和以检测文件损坏
                stored_checksum = data.pop("checksum", None)
                if stored_checksum is not None:
                    computed = self._compute_checksum(data)
                    if stored_checksum != computed:
                        logger.error(
                            f"断点文件校验和失败（可能已损坏）: "
                            f"存储={stored_checksum}, 计算={computed}"
                        )
                        return None
                else:
                    logger.warning("断点文件无校验和字段（旧版本格式）")

                if data.get("version") != 1:
                    logger.warning(f"断点文件格式版本不兼容: {data.get('version')}")
                    return None

                # C-02: 检查项目版本兼容性
                checkpoint_project_version = data.get("project_version")
                if checkpoint_project_version and checkpoint_project_version != _project_version:
                    logger.warning(
                        f"断点文件项目版本不匹配: checkpoint={checkpoint_project_version}, "
                        f"current={_project_version}。可能会出现兼容性问题。"
                    )

                logger.info(
                    f"断点已加载: {self.filepath}, 模式={data.get('mode')}, "
                    f"已检查={data.get('total_checked', 0)}, 匹配数={len(data.get('matches', []))}"
                )
                return cast(dict[str, Any], data)
            except FileNotFoundError:
                logger.debug(f"断点文件不存在: {self.filepath}")
                return None
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"加载断点失败: {e}", exc_info=True)
                return None

    def delete(self) -> None:
        """删除断点文件（线程安全）"""
        with self._lock:
            try:
                if os.path.exists(self.filepath):
                    os.remove(self.filepath)
                    logger.info(f"断点文件已删除: {self.filepath}")

                # 同时删除临时文件
                temp_filepath = self.filepath + ".tmp"
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                    logger.debug(f"临时断点文件已删除: {temp_filepath}")

                # 清空缓冲区和脏标志
                self._buffer = None
                self._dirty = False

            except Exception as e:
                logger.error(f"删除断点文件失败: {e}", exc_info=True)

    def exists(self) -> bool:
        """检查断点文件是否存在"""
        return os.path.exists(self.filepath)

    def should_auto_save(self) -> bool:
        """检查是否达到自动保存间隔"""
        return time.monotonic() - self._last_save_time >= self.auto_save_interval

    @staticmethod
    def _compute_checksum(data: dict) -> str:
        """计算断点数据的 CRC32 校验和（排除 checksum 自引用）

        Args:
            data: 断点数据字典（不含 checksum 键）

        Returns:
            十六进制 CRC32 校验和字符串（8 字符）
        """
        serialized = fast_dumps(data, sort_keys=True, ensure_ascii=False)
        if isinstance(serialized, bytes):
            serialized = serialized.decode("utf-8")
        crc = binascii.crc32(serialized.encode("utf-8")) & 0xFFFFFFFF
        return f"{crc:08x}"

