"""断点管理器"""

import json
import os
import threading
import time
import traceback
import zlib
from datetime import datetime
from typing import Any, cast

# 导入日志配置
from .. import __version__ as PROJECT_VERSION
from ..utils import get_configured_logger
from ..utils.fast_json import fast_dumps, fast_loads
from ..utils.platform_utils import PlatformUtils

# 日志系统由CLI/main.py入口统一初始化
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
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
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
        logger.debug(
            f"CheckpointManager 初始化: 文件={self.filepath}, 自动保存间隔={
                auto_save_interval
            }秒, pywin32可用={self._has_win32_security}"
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

            # 构建断点数据
            self._buffer = {
                "version": 1,  # 格式版本
                "project_version": PROJECT_VERSION,  # 项目版本 (C-02: 版本兼容性修复)
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

            # 标记为脏
            self._dirty = True

            # 只有在强制保存或时间间隔达到时才写入文件
            if force or self.should_auto_save():
                self._flush_buffer()

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

            # 写入临时文件 — v4.3.1: 支持大文件 zlib 压缩
            serialized = fast_dumps(self._buffer, ensure_ascii=False, indent=2)
            if isinstance(serialized, bytes):
                serialized = serialized.decode("utf-8")
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
            logger.debug("临时文件写入成功")

            # Q3修复: 临时文件安全权限 - 虽然原子重命名后临时文件不再存在，
            # 但在写入期间提供权限保护是安全最佳实践（防止写入被中断时的短暂暴露窗口）
            if not PlatformUtils.is_windows():
                try:
                    os.chmod(temp_filepath, 0o600)
                    logger.debug("已设置临时文件权限: 0o600")
                except OSError as e:
                    logger.debug(f"临时文件权限设置失败（非致命）: {e}")

            # 原子重命名（跨平台兼容）
            logger.debug(f"原子重命名: {temp_filepath} -> {self.filepath}")
            os.replace(temp_filepath, self.filepath)
            logger.debug("原子重命名成功")

            # 设置文件权限（跨平台兼容）
            try:
                if not PlatformUtils.is_windows():
                    # Linux/macOS: 设置为仅所有者可读写
                    os.chmod(self.filepath, 0o600)
                    logger.debug("已设置文件权限: 0o600 (仅所有者可读写)")
                else:
                    # Windows: 尝试设置ACL（仅所有者可访问）
                    if self._has_win32_security:
                        try:
                            import getpass

                            import ntsecuritycon as con
                            import win32security

                            # 获取文件句柄
                            handle = win32security.GetFileSecurity(
                                self.filepath, win32security.DACL_SECURITY_INFORMATION
                            )

                            # 创建新的DACL
                            dacl = win32security.ACL()

                            # 获取当前用户SID
                            username = getpass.getuser()
                            sid, _, _ = win32security.LookupAccountName(None, username)

                            # 添加访问控制项（仅当前用户可完全控制）
                            dacl.AddAccessAllowedAce(
                                win32security.ACL_REVISION, con.FILE_ALL_ACCESS, sid
                            )

                            # 设置新的DACL
                            handle.SetSecurityDescriptorDacl(1, dacl, 0)
                            win32security.SetFileSecurity(
                                self.filepath, win32security.DACL_SECURITY_INFORMATION, handle
                            )
                            logger.debug("已设置Windows文件权限（仅当前用户可访问）")
                        except Exception as e:
                            # pywin32权限设置失败，尝试icacls
                            logger.debug(f"pywin32权限设置失败: {e}，尝试使用icacls")
                            try:
                                import getpass

                                username = getpass.getuser()
                                import subprocess  # nosec B404: icacls is hardcoded, safe

                                # 使用icacls命令设置权限：移除所有继承的权限，只允许当前用户访问
                                cmd = [
                                    "icacls",
                                    self.filepath,
                                    "/inheritance:r",  # 移除继承
                                    "/grant:r",
                                    f"{username}:F",  # 授予当前用户完全控制权限
                                    "/Q",  # 静默执行
                                ]

                                result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
                                if result.returncode == 0:
                                    logger.debug(
                                        "已使用icacls设置Windows文件权限（仅当前用户可访问）"
                                    )
                                else:
                                    logger.warning(f"icacls权限设置失败: {result.stderr}")
                            except Exception:
                                # icacls命令也失败，跳过Windows权限设置
                                logger.debug("icacls命令执行失败，跳过Windows权限设置")
                    else:
                        # pywin32未安装，尝试使用icacls命令
                        try:
                            import getpass

                            username = getpass.getuser()
                            import subprocess  # nosec B404: icacls is hardcoded, safe

                            # 使用icacls命令设置权限：移除所有继承的权限，只允许当前用户访问
                            cmd = [
                                "icacls",
                                self.filepath,
                                "/inheritance:r",  # 移除继承
                                "/grant:r",
                                f"{username}:F",  # 授予当前用户完全控制权限
                                "/Q",  # 静默执行
                            ]

                            result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
                            if result.returncode == 0:
                                logger.debug("已使用icacls设置Windows文件权限（仅当前用户可访问）")
                            else:
                                logger.warning(f"icacls权限设置失败: {result.stderr}")
                        except Exception:
                            # icacls命令也失败，跳过Windows权限设置
                            logger.debug("pywin32未安装且icacls命令执行失败，跳过Windows权限设置")
            except Exception as e:
                # 权限设置失败不影响主流程，只记录警告
                logger.warning(f"文件权限设置失败: {e}")

            # 清理可能的旧临时文件
            self._cleanup_temp_file(temp_filepath)

            self._last_save_time = time.time()
            self._dirty = False
            logger.debug(
                f"断点已保存: {self.filepath}, 位置={self._buffer.get('current_position')}, 已检查={
                    self._buffer.get('total_checked')
                }"
            )
        except PermissionError as e:
            logger.error(f"保存断点失败（权限不足）: {e}")
            logger.error(f"文件路径: {self.filepath}")
            # Q9修复: traceback 已在文件顶部导入
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        except OSError as e:
            logger.error(f"保存断点失败（I/O错误）: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"保存断点失败（未知错误）: {e}", exc_info=True)
        finally:
            # 清理临时文件（无论成功还是失败都需要清理）
            if "temp_filepath" in locals() and temp_filepath:
                self._cleanup_temp_file(temp_filepath)

    def _cleanup_temp_file(self, temp_filepath: str) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
        except OSError:
            pass

    def load(self) -> dict | None:
        """从文件加载断点，文件不存在或格式错误返回 None（线程安全）"""
        with self._lock:
            try:
                # 检查临时文件是否存在（可能上次写入中断）
                temp_filepath = self.filepath + ".tmp"
                if os.path.exists(temp_filepath) and not os.path.exists(self.filepath):
                    # 尝试恢复临时文件
                    try:
                        # S7修复: 使用 os.replace 实现跨平台原子操作（Windows/Linux兼容）
                        os.replace(temp_filepath, self.filepath)
                        # 设置文件权限
                        if not PlatformUtils.is_windows():
                            try:
                                os.chmod(self.filepath, 0o600)
                            except OSError:
                                pass
                        logger.warning(f"从临时文件恢复断点: {temp_filepath}")
                    except OSError as e:
                        # 文件系统错误：记录日志并清理临时文件
                        logger.error(f"断点恢复失败: {e}，将重新开始")
                        try:
                            os.remove(temp_filepath)
                        except OSError:
                            pass  # 清理失败不影响主流程
                    except Exception as e:
                        # 未知错误：记录完整信息
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
                    logger.debug(
                        f"断点已解压加载: {len(raw):,}B -> {len(decompressed):,}B"
                    )
                else:
                    data = fast_loads(raw.decode("utf-8"))

                if data.get("version") != 1:
                    logger.warning(f"断点文件格式版本不兼容: {data.get('version')}")
                    return None

                # C-02: 检查项目版本兼容性
                checkpoint_project_version = data.get("project_version")
                if checkpoint_project_version and checkpoint_project_version != PROJECT_VERSION:
                    logger.warning(
                        f"断点文件项目版本不匹配: checkpoint={checkpoint_project_version}, "
                        f"current={PROJECT_VERSION}。可能会出现兼容性问题。"
                    )
                    # 不返回 None，允许用户决定是否继续

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
        """检查是否该自动保存（基于时间间隔）"""
        return (time.time() - self._last_save_time) >= self.auto_save_interval
