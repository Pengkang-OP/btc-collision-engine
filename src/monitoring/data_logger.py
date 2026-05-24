#!/usr/bin/env python3
"""Bitcoin key collision detection data logging system.

Provides comprehensive data logging including performance data,
system status, engine information, and error records.
Supports data storage, rotation, and report generation.
"""

import copy
import json
import os
import pathlib
import shutil
import statistics
import sys
import tempfile
import threading
import time
from collections import deque
from contextlib import suppress
from datetime import datetime
from typing import Any

from src.log_engine.log_rotator import LogRotator
from src.monitoring.storage_config import DataStorageConfig

# 导入现有日志系统
from src.utils import get_configured_logger
from src.utils.fast_json import fast_dump, fast_load, fast_loads


class DataLogger:
    """数据日志记录器

    注意：已统一使用data_logs作为唯一数据源，
    monitoring_data目录已废弃。
    """

    # P0: history_data.json 数据结构版本号
    HISTORY_SCHEMA_VERSION: str = "1.0"

    # 文件原子替换重试的指数退避延迟序列（秒）
    _REPLACE_BACKOFF_DELAYS: list[float] = [1.0, 2.0, 4.0]
    # performance.log 轮转阈值（字节），超过此大小自动轮转
    _PERF_LOG_MAX_SIZE: int = 50 * 1024 * 1024  # 50 MB
    # performance.log 最大保留的轮转副本数
    _PERF_LOG_MAX_ROTATIONS: int = 3
    # v4.3.1: 性能日志批量化写入参数
    _PERF_BATCH_MAX_LINES: int = 10  # 累积行数阈值
    _PERF_BATCH_MAX_AGE_SEC: float = 5.0  # 累积时间阈值(秒)
    _PERF_BATCH_ENABLED: bool = True  # 是否启用批量化

    # 报告推荐阈值常量
    _REC_SPEED_THRESHOLD_LOW: int = 100
    _REC_SPEED_THRESHOLD_HIGH: int = 100000
    _REC_CPU_THRESHOLD_HIGH: int = 80
    _REC_CPU_THRESHOLD_LOW: int = 20
    _REC_MEM_THRESHOLD_HIGH_MB: int = 1024
    _REC_MEM_THRESHOLD_MEDIUM_MB: int = 512

    def __init__(self, storage_dir: str | None = None) -> None:
        """初始化数据日志记录器

        Args:
            storage_dir: 数据存储目录（可选，默认使用data_logs）

        """
        # 使用统一配置
        self.storage_dir = DataStorageConfig.ensure_storage_dir(storage_dir)

        # 初始化日志记录器
        # v4.2.1修复: Python的logging.Logger本身是线程安全的，无需ThreadSafeLogger包装
        self.logger = get_configured_logger("DataLogger")

        # 数据文件路径
        self.current_data_file = os.path.join(self.storage_dir, "current_data.json")
        self.history_data_file = os.path.join(self.storage_dir, "history_data.json")
        self.error_log_file = os.path.join(self.storage_dir, "error_log.json")
        self.performance_log_file = os.path.join(self.storage_dir, "performance.log")

        # 初始化文件
        self._initialize_files()

        # 清理上次会话遗留的 .tmp 文件（延迟 1 小时，避免误删正在写入的文件）
        self._cleanup_stale_temp_files(max_age_seconds=3600)

        # 数据缓存
        self._current_data: dict[str, Any] = {}
        self._history_buffer: deque = deque(maxlen=1000)  # 限制历史数据数量
        self._error_buffer: deque = deque(maxlen=500)  # 限制错误日志数量

        # 线程锁
        self._lock = threading.Lock()

        # 错误日志轮转器：保留最近7天、最多1000条
        self._error_rotator = LogRotator(max_age_days=7, max_count=1000)

        # 性能统计
        self._start_time = time.time()
        self._total_checks = 0
        self._matches_found = 0
        self._match_event_count = 0  # P1-1: 独立匹配事件计数器
        self._speed_samples: list[float] = []

        # P1-4: 写入失败计数器（在__init__初始化避免竞态）
        self._write_failure_count: int = 0
        self._write_failure_last_reset: float = 0.0
        self._write_failure_lock = threading.Lock()  # P1-4: 保护计数器线程安全

        # v4.3.1: 性能日志批量化写入属性
        self._perf_buffer_lock = threading.Lock()
        self._perf_line_buffer: list[str] = []
        self._perf_buffer_start_time: float = 0.0

        # v4.3.1: 管道运营指标
        self._pipeline_lock = threading.Lock()
        self._save_counts: dict[str, int] = {}
        self._last_save_times: dict[str, float] = {}
        self._pipeline_error_count: int = 0
        self._pipeline_metrics: list[dict[str, Any]] = []

        self.logger.info("数据日志系统初始化完成")

    def _atomic_write_json(self, filepath: str, data: Any) -> None:
        """原子写入JSON文件

        使用临时文件+重命名的方式确保数据完整性，
        避免写入中断导致文件损坏。

        Args:
            filepath: 目标文件路径
            data: 要写入的数据

        """
        temp_file = filepath + ".tmp"
        try:
            with pathlib.Path(temp_file).open("w", encoding="utf-8") as f:
                fast_dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘

            # 原子替换（带重试和回退机制，应对 Windows 杀毒软件锁定）
            if not self._safe_file_replace(temp_file, filepath):
                raise OSError(f"原子替换失败: {filepath}")

            # 设置文件权限（仅所有者可读写，Windows 跳过）
            if os.name != "nt":
                try:
                    pathlib.Path(filepath).chmod(0o600)
                except (OSError, PermissionError) as e:
                    self.logger.debug("设置文件权限失败: %s", e)
        except Exception as e:
            self.logger.error("原子写入失败: %s", e)
            # 清理临时文件
            try:
                if pathlib.Path(temp_file).exists():
                    pathlib.Path(temp_file).unlink()
            except Exception as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                self.logger.debug("清理临时文件失败（可忽略）: %s", cleanup_error)

    def _initialize_files(self) -> None:
        """初始化数据文件"""
        try:
            # 初始化当前数据文件
            if not pathlib.Path(self.current_data_file).exists():
                with pathlib.Path(self.current_data_file).open("w", encoding="utf-8") as f:
                    fast_dump({}, f)
                if os.name != "nt":
                    pathlib.Path(self.current_data_file).chmod(0o600)

            # 初始化历史数据文件 (P0: 带schema_version)
            if not pathlib.Path(self.history_data_file).exists():
                init_data = {
                    "schema_version": self.HISTORY_SCHEMA_VERSION,
                    "data": [],
                }
                with pathlib.Path(self.history_data_file).open("w", encoding="utf-8") as f:
                    fast_dump(init_data, f)

            # 初始化错误日志文件
            if not pathlib.Path(self.error_log_file).exists():
                with pathlib.Path(self.error_log_file).open("w", encoding="utf-8") as f:
                    fast_dump([], f)
                if os.name != "nt":
                    pathlib.Path(self.error_log_file).chmod(0o600)

            # 初始化性能日志文件
            if not pathlib.Path(self.performance_log_file).exists():
                with pathlib.Path(self.performance_log_file).open("w", encoding="utf-8") as f:
                    f.write("# 性能日志 - 比特币密钥碰撞检测\n")
                    f.write(f"# 创建时间: {datetime.now().isoformat()}\n")
                    f.write(
                        "# 格式: timestamp,speed,total_checked,matches,"
                        "cpu_usage,memory_usage,threads,gpu_temp,gpu_mem,gpu_util\n",
                    )
                if os.name != "nt":
                    pathlib.Path(self.performance_log_file).chmod(0o600)
        except Exception as e:
            self.logger.error("初始化数据文件失败: %s", e)

    def record_performance_data(
        self,
        speed: float,
        total_checked: int,
        matches_found: int,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        thread_count: int = 0,
        # P1-2: GPU性能指标
        gpu_temperature: float = 0.0,
        gpu_memory_usage: float = 0.0,
        gpu_utilization: float = 0.0,
    ) -> None:
        """记录性能数据（添加数据验证）

        Args:
            speed: 每秒检测速率
            total_checked: 已检测总数
            matches_found: 找到的匹配数
            cpu_usage: CPU使用率
            memory_usage: 内存使用率(MB)
            thread_count: 线程数
            gpu_temperature: GPU温度(°C) (P1-2)
            gpu_memory_usage: GPU显存使用(MB) (P1-2)
            gpu_utilization: GPU利用率(%) (P1-2)

        """
        # 数据验证
        if not isinstance(speed, (int, float)) or speed < 0:
            self.logger.warning("无效的速度值: %s，使用0代替", speed)
            speed = 0.0

        if not isinstance(total_checked, int) or total_checked < 0:
            self.logger.warning("无效的total_checked值: %s，使用0代替", total_checked)
            total_checked = 0

        if not isinstance(matches_found, int) or matches_found < 0:
            self.logger.warning("无效的matches_found值: %s，使用0代替", matches_found)
            matches_found = 0

        if not isinstance(cpu_usage, (int, float)) or cpu_usage < 0:
            self.logger.warning("无效的cpu_usage值: %s，使用0代替", cpu_usage)
            cpu_usage = 0.0

        if not isinstance(memory_usage, (int, float)) or memory_usage < 0:
            self.logger.warning("无效的memory_usage值: %s，使用0代替", memory_usage)
            memory_usage = 0.0

        if not isinstance(thread_count, int) or thread_count < 0:
            self.logger.warning("无效的thread_count值: %s，使用0代替", thread_count)
            thread_count = 0

        # P1-2: GPU数据验证
        if not isinstance(gpu_temperature, (int, float)) or gpu_temperature < 0:
            self.logger.warning("无效的gpu_temperature值: %s，使用0代替", gpu_temperature)
            gpu_temperature = 0.0
        if not isinstance(gpu_memory_usage, (int, float)) or gpu_memory_usage < 0:
            self.logger.warning("无效的gpu_memory_usage值: %s，使用0代替", gpu_memory_usage)
            gpu_memory_usage = 0.0
        if not isinstance(gpu_utilization, (int, float)) or gpu_utilization < 0:
            self.logger.warning("无效的gpu_utilization值: %s，使用0代替", gpu_utilization)
            gpu_utilization = 0.0

        # 在锁内更新数据
        with self._lock:
            timestamp = time.time()

            # 更新统计数据
            self._total_checks = total_checked
            self._matches_found = matches_found
            self._speed_samples.append(speed)

            # 保留最近100个速度样本
            if len(self._speed_samples) > 100:
                self._speed_samples = self._speed_samples[-100:]

            # 创建性能数据记录
            perf_data = {
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                "speed": float(speed),
                "total_checked": int(total_checked),
                "matches_found": int(matches_found),
                "cpu_usage": float(cpu_usage),
                "memory_usage": float(memory_usage),
                "thread_count": int(thread_count),
                # P1-2: GPU性能指标
                "gpu_temperature": float(gpu_temperature),
                "gpu_memory_usage": float(gpu_memory_usage),
                "gpu_utilization": float(gpu_utilization),
                "avg_speed": statistics.mean(self._speed_samples) if self._speed_samples else 0,
            }

            # 更新当前数据
            self._current_data["performance"] = perf_data

            # 添加到历史缓冲区
            self._history_buffer.append(perf_data)

        # 在锁外写入CSV日志 — v4.3.1: 批量化写入减少 I/O 频率
        try:
            csv_line = (
                f"{timestamp},{speed},{total_checked},{matches_found},"
                f"{cpu_usage},{memory_usage},{thread_count},"
                f"{gpu_temperature},{gpu_memory_usage},{gpu_utilization}\n"
            )
            if self._PERF_BATCH_ENABLED:
                self._buffered_perf_write(csv_line)
            else:
                self._direct_perf_write(csv_line)
        except Exception as e:
            self.logger.error("写入性能日志失败: %s", e)

        # 记录到标准日志
        self.logger.debug(f"性能数据: 速度={speed:.2f}/s, 总计={total_checked}, 匹配={matches_found}")

    # ==== v4.3.1: 性能日志批量化写入 ====

    def _buffered_perf_write(self, csv_line: str) -> None:
        """缓冲性能日志行，累积到阈值后批量写入

        设计目标：将 0.5s/次的文件打开+写入 降低为 ~5s/次
        """
        with self._perf_buffer_lock:
            self._perf_line_buffer.append(csv_line)
            if self._perf_buffer_start_time == 0.0:
                self._perf_buffer_start_time = time.time()
            should_flush = (
                len(self._perf_line_buffer) >= self._PERF_BATCH_MAX_LINES
                or (time.time() - self._perf_buffer_start_time) >= self._PERF_BATCH_MAX_AGE_SEC
            )
        if should_flush:
            self._flush_perf_buffer()

    def _direct_perf_write(self, csv_line: str) -> None:
        """直接写入性能日志（非批量化模式）"""
        self._rotate_perf_log_if_needed()
        with pathlib.Path(self.performance_log_file).open("a", encoding="utf-8") as f:
            f.write(csv_line)

    def _flush_perf_buffer(self) -> None:
        """将缓冲的性能日志行批量写入文件"""
        lines_to_write: list[str] = []
        with self._perf_buffer_lock:
            if not self._perf_line_buffer:
                return
            lines_to_write = self._perf_line_buffer[:]
            self._perf_line_buffer.clear()
            self._perf_buffer_start_time = 0.0
        if not lines_to_write:
            return
        try:
            self._rotate_perf_log_if_needed()
            with pathlib.Path(self.performance_log_file).open("a", encoding="utf-8") as f:
                f.writelines(lines_to_write)
            self._record_pipeline_metric(
                "performance_log", success=True, extra={"batched_lines": len(lines_to_write)},
            )
        except Exception as e:
            self.logger.error("批量写入性能日志失败: %s", e)
            self._record_pipeline_metric("performance_log", success=False, error=str(e)[:200])

    def record_system_data(
        self, os_name: str = "", python_version: str = "", pid: int = 0, uptime: float = 0.0,
    ) -> None:
        """记录系统数据

        Args:
            os_name: 操作系统名称
            python_version: Python版本
            pid: 进程ID
            uptime: 系统运行时间(秒)

        """
        with self._lock:
            if not os_name:
                os_name = os.name
            if not python_version:
                python_version = (
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                )
            if not pid:
                pid = os.getpid()
            if not uptime:
                uptime = time.time() - self._start_time

            system_data = {
                "timestamp": time.time(),
                "os": os_name,
                "python_version": python_version,
                "pid": pid,
                "uptime": uptime,
            }

            self._current_data["system"] = system_data
            self.logger.debug("系统数据: OS=%s, Python=%s, PID=%s", os_name, python_version, pid)

    def record_engine_data(
        self,
        mode: str = "",
        target_count: int = 0,
        is_running: bool = False,
        current_position: int = 0,
        additional_info: dict[str, Any] | None = None,
    ) -> None:
        """记录引擎状态数据

        Args:
            mode: 对撞模式
            target_count: 目标地址数量
            is_running: 引擎运行状态
            current_position: 当前位置
            additional_info: 额外信息

        """
        # 类型验证/强制转换（防御 Mock 对象等非标准输入）
        if not isinstance(mode, str):
            mode = str(mode) if mode else ""
        if not isinstance(target_count, int):
            try:
                target_count = int(target_count)
            except (TypeError, ValueError):
                target_count = 0
        if not isinstance(is_running, bool):
            is_running = bool(is_running)
        if not isinstance(current_position, int):
            try:
                current_position = int(current_position)
            except (TypeError, ValueError):
                current_position = 0

        with self._lock:
            engine_data = {
                "timestamp": time.time(),
                "mode": mode,
                "target_count": target_count,
                "is_running": is_running,
                "current_position": current_position,
            }

            if additional_info:
                engine_data.update(additional_info)

            self._current_data["engine"] = engine_data
            self.logger.debug("引擎数据: 模式=%s, 目标数=%s, 运行中=%s", mode, target_count, is_running)

    # P2-3: 在engine_data中记录去重效率
    def set_dedup_stats(self, skipped: int = 0, hit_rate: float = 0.0) -> None:
        """P2-3: 设置去重/过滤统计指标

        Args:
            skipped: 去重跳过的密钥数量
            hit_rate: Bloom Filter命中率 (0.0-1.0)

        """
        with self._lock:
            if "engine" in self._current_data:
                self._current_data["engine"]["dedup_skipped"] = int(skipped)
                self._current_data["engine"]["bloom_hit_rate"] = float(hit_rate)
            else:
                self.logger.debug("set_dedup_stats: engine数据未初始化，跳过去重统计设置")

    def log_match(self, event) -> None:
        """Alias for record_match_event, called from event bus."""
        # Extract address from event object
        addr = getattr(event, "address", "") or getattr(event, "target_address", "")
        self.record_match_event(addr)

    def log_progress(self, event) -> None:
        """Called from event bus on progress events."""

    def log_error(self, event) -> None:
        """Called from event bus on error events."""
        msg = getattr(event, "error_message", "") or str(getattr(event, "exception", ""))
        self.record_error(msg)

    def record_match_event(
        self,
        matched_address: str,
        collision_mode: str = "",
        match_type: str = "address",
    ) -> None:
        """P1-1: 记录碰撞匹配详情

        记录脱敏后的匹配地址和碰撞时间，不存储私钥原文。
        私钥过滤由SecurityLogFilter在日志层防护。

        Args:
            matched_address: 匹配到的BTC地址（仅地址，不含私钥）
            collision_mode: 碰撞模式("random"/"range_scan"/"brute_force")
            match_type: 匹配类型("address"/"hash160")

        """
        # 安全脱敏：只保留地址前6位+后4位用于日志审计
        if len(matched_address) > 10:
            safe_addr = matched_address[:6] + "..." + matched_address[-4:]
        else:
            safe_addr = matched_address[:3] + "..."

        with self._lock:
            match_record = {
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "matched_address_masked": safe_addr,
                "collision_mode": collision_mode,
                "match_type": match_type,
            }

            # 追加到current_data
            if "matches" not in self._current_data:
                self._current_data["matches"] = []
            self._current_data["matches"].append(match_record)

            # 限制匹配记录数
            if len(self._current_data["matches"]) > 100:
                self._current_data["matches"] = self._current_data["matches"][-100:]

            # P1-1: 使用独立计数器，避免与record_performance_data赋值冲突
            self._match_event_count += 1

        self.logger.info(
            "碰撞匹配事件: 地址=%s, 模式=%s, 类型=%s",
            safe_addr, collision_mode, match_type,
        )

    def record_error(
        self,
        error_type: str,
        message: str,
        exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """记录错误信息

        Args:
            error_type: 错误类型
            message: 错误消息
            exception: 异常对象
            context: 错误上下文信息

        """
        timestamp = time.time()

        error_record = {
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp).isoformat(),
            "type": error_type,
            "message": message,
            "exception_type": type(exception).__name__ if exception else None,
            "exception_message": str(exception) if exception else None,
            "context": context or {},
        }

        # 仅锁内更新内存缓冲区，文件 I/O 移到锁外
        with self._lock:
            self._error_buffer.append(error_record)

        # 在锁外执行文件I/O，避免阻塞高频路径（record_performance_data/save_history_data）
        try:
            errors = []
            if pathlib.Path(self.error_log_file).exists():
                with pathlib.Path(self.error_log_file).open(encoding="utf-8") as f:
                    errors = fast_load(f)

            errors.append(error_record)
            errors = self._error_rotator.rotate(errors)

            with pathlib.Path(self.error_log_file).open("w", encoding="utf-8") as f:
                fast_dump(errors, f, ensure_ascii=False, indent=2)
            self._record_pipeline_metric("record_error", success=True)
        except Exception as e:
            self.logger.error("保存错误日志失败: %s", e)
            self._record_pipeline_metric("record_error", success=False, error=str(e)[:200])

        # 记录到标准日志
        if exception:
            self.logger.error("错误记录 [%s]: %s - %s", error_type, message, exception)
        else:
            self.logger.error("错误记录 [%s]: %s", error_type, message)

    def update_current_data_sections(
        self,
        performance: dict[str, Any] | None = None,
        system: dict[str, Any] | None = None,
        engine: dict[str, Any] | None = None,
    ) -> None:
        """v4.2.2: 线程安全地更新 _current_data 的子区域

        替代外部直接访问 _current_data["performance"]/["system"]/["engine"]，
        内部使用 self._lock 保护，避免竞态和覆盖风险。

        Args:
            performance: 性能数据子字典
            system: 系统数据子字典
            engine: 引擎数据子字典

        """
        with self._lock:
            if performance is not None:
                self._current_data["performance"] = performance
            if system is not None:
                self._current_data["system"] = system
            if engine is not None:
                self._current_data["engine"] = engine

    def save_current_data(self) -> None:
        """保存当前数据到文件

        使用原子写入（临时文件 + os.replace），
        _safe_file_replace 内部包含完整的重试+回退机制，
        无需外层重复重试。
        """
        # 在锁内深拷贝数据，确保嵌套字典的一致性
        with self._lock:
            save_data = {
                "saved_at": datetime.now().isoformat(),
                "uptime": time.time() - self._start_time,
                **copy.deepcopy(self._current_data),
            }

        temp_file = None
        try:
            temp_fd, temp_file = tempfile.mkstemp(
                dir=os.path.dirname(self.current_data_file),
                suffix=".tmp",
                prefix=".current_data_",
            )
            os.close(temp_fd)

            with pathlib.Path(temp_file).open("w", encoding="utf-8") as f:
                fast_dump(save_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            if not self._safe_file_replace(temp_file, self.current_data_file):
                self.logger.error("保存当前数据失败: 文件替换所有方案均失败")
                self._record_pipeline_metric("save_current_data", success=False, error="replace_failed")
            else:
                self._record_pipeline_metric("save_current_data", success=True)
        except Exception as e:
            self.logger.error("保存当前数据失败: %s", e)
            self._record_pipeline_metric("save_current_data", success=False, error=str(e)[:200])
        finally:
            if temp_file and pathlib.Path(temp_file).exists():
                with suppress(OSError):
                    pathlib.Path(temp_file).unlink()

    def _cleanup_stale_temp_files(self, max_age_seconds: int = 3600) -> None:
        """清理上次会话遗留的过期 .tmp 临时文件

        原子写入操作（save_current_data/save_history_data/_safe_file_replace）
        在正常流程中会清理临时文件，但进程崩溃或杀毒软件锁定可能导致遗
        留。此方法在 DataLogger 初始化时清理超过 max_age_seconds 的 .tmp
        文件，避免累积占用磁盘空间。

        Args:
            max_age_seconds: 临时文件最大保留时间（秒），默认 1 小时

        """
        try:
            now = time.time()
            removed = 0
            freed = 0
            for entry in os.scandir(self.storage_dir):
                if not entry.is_file(follow_symlinks=False):
                    continue
                if not entry.name.endswith((".tmp", ".last.tmp", ".direct.tmp")):
                    continue
                with suppress(OSError):
                    age = now - entry.stat().st_mtime
                    if age < max_age_seconds:
                        continue
                    size = entry.stat().st_size
                    pathlib.Path(entry.path).unlink()
                    removed += 1
                    freed += size
            if removed > 0:
                self.logger.info(f"清理了 {removed} 个过期临时文件，释放 {freed / 1024 / 1024:.2f} MB")
        except Exception as e:
            self.logger.debug("清理过期临时文件时出错（非致命）: %s", e)

    def _rotate_perf_log_if_needed(self) -> None:
        """检查 performance.log 大小，超过阈值时自动轮转

        轮转策略:
        - 超过 _PERF_LOG_MAX_SIZE 时轮转
        - 保留最近 _PERF_LOG_MAX_ROTATIONS 个副本
        - 副本命名为 performance.log.1, performance.log.2, ...

        线程安全: 使用 self._lock 保护整个轮转操作，双重检查防止 TOCTOU 竞态。
        """
        try:
            # 快速路径：锁外初步检查，避免不必要的锁竞争
            if not pathlib.Path(self.performance_log_file).exists():
                return
            if pathlib.Path(self.performance_log_file).stat().st_size < self._PERF_LOG_MAX_SIZE:
                return

            with self._lock:
                # 双重检查：锁内再次确认（防止 TOCTOU 竞态）
                if not pathlib.Path(self.performance_log_file).exists():
                    return
                size = pathlib.Path(self.performance_log_file).stat().st_size
                if size < self._PERF_LOG_MAX_SIZE:
                    return

                # 执行级联轮转：.2 -> .3, .1 -> .2, current -> .1
                # 使用 os.replace 原子操作，避免 remove+rename 中的中间态丢失
                for i in range(self._PERF_LOG_MAX_ROTATIONS, 0, -1):
                    old_name = (
                        f"{self.performance_log_file}.{i - 1}" if i > 1 else self.performance_log_file
                    )
                    new_name = f"{self.performance_log_file}.{i}"
                    if pathlib.Path(old_name).exists():
                        pathlib.Path(old_name).replace(new_name)

                # 写入新文件头
                with pathlib.Path(self.performance_log_file).open("w", encoding="utf-8") as f:
                    f.write("# 性能日志 - 比特币密钥碰撞检测 (轮转)\n")
                    f.write(f"# 轮转时间: {datetime.now().isoformat()}\n")
                    f.write(
                        "# 格式: timestamp,speed,total_checked,matches,"
                        "cpu_usage,memory_usage,threads,gpu_temp,gpu_mem,gpu_util\n",
                    )

                self.logger.info(f"performance.log 达到 {size / 1024 / 1024:.1f} MB，已轮转")
        except Exception as e:
            self.logger.warning("performance.log 轮转失败（非致命）: %s", e)

    def _safe_file_replace(self, src: str, dst: str, max_retries: int = 3) -> bool:
        """安全的原子文件替换，带指数退避重试和回退机制

        Windows 上 os.replace() 可能因杀毒软件/文件索引服务
        临时锁定目标文件而失败 (WinError 5)。此方法先尝试
        os.replace()，失败后使用指数退避重试，最后回退到
        直接写入（非原子但确保数据不丢失）。

        Args:
            src: 源文件路径（临时文件）
            dst: 目标文件路径
            max_retries: 最大重试次数

        Returns:
            True 如果替换成功，False 如果所有尝试都失败

        """
        delays = self._REPLACE_BACKOFF_DELAYS

        for attempt in range(max_retries):
            try:
                pathlib.Path(src).replace(dst)
                return True
            except PermissionError:
                if attempt < max_retries - 1:
                    delay = delays[min(attempt, len(delays) - 1)]
                    self.logger.warning(
                        f"文件替换被拒绝 (尝试 {attempt + 1}/{max_retries})，{delay:.0f}s 后重试: {dst}",
                    )
                    time.sleep(delay)
                    continue
                # 最后一次尝试失败，使用回退方案
                self.logger.warning(
                    "原子替换全部失败 (%s/%s)，回退到直接写入: %s", max_retries, max_retries, dst,
                )
                return self._fallback_direct_write(src, dst)
            except OSError as e:
                if attempt < max_retries - 1:
                    delay = delays[min(attempt, len(delays) - 1)]
                    _attempt = attempt + 1
                    self.logger.warning(
                        f"文件替换失败 (尝试 {_attempt}/{max_retries}), {delay:.0f}s后重试: {e} - {dst}",
                    )
                    time.sleep(delay)
                    continue
            # 最后一次尝试失败，也尝试回退方案
            # （某些杀毒软件返回非标准 OSError 而非 PermissionError）
            self.logger.warning(
                "原子替换全部失败 (%s/%s)，回退到直接写入: %s - %s",
                max_retries, max_retries, e, dst,
            )
            return self._fallback_direct_write(src, dst)

        return False

    def _fallback_direct_write(self, src: str, dst: str) -> bool:
        """回退方案：通过读取源文件内容然后直接写入目标文件

        当 os.replace() 因外部锁定失败时使用此方法。
        虽然非原子操作，但可以绕过文件替换权限问题。

        Args:
            src: 源文件路径（临时文件）
            dst: 目标文件路径

        Returns:
            True 如果写入成功

        """
        try:
            # 读取临时文件内容
            content = pathlib.Path(src).read_text(encoding="utf-8")

            # 使用唯一临时文件名，避免并发竞争
            dst_fd, dst_tmp = tempfile.mkstemp(
                dir=os.path.dirname(dst),
                suffix=".direct.tmp",
                prefix=".fallback_",
            )
            os.close(dst_fd)

            with pathlib.Path(dst_tmp).open("w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # 尝试替换
            try:
                pathlib.Path(dst_tmp).replace(dst)
            except (PermissionError, OSError):
                # 连替换都失败，使用新临时文件做最后一次原子替换尝试
                # （避免直接 open(dst, "w") 的线程安全隐患）
                dst_fd2, dst_tmp2 = tempfile.mkstemp(
                    dir=os.path.dirname(dst),
                    suffix=".last.tmp",
                    prefix=".final_",
                )
                os.close(dst_fd2)
                try:
                    with pathlib.Path(dst_tmp2).open("w", encoding="utf-8") as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
                    try:
                        pathlib.Path(dst_tmp2).replace(dst)
                    except (PermissionError, OSError):
                        # 绝对最后手段：直接覆盖（非原子但确保数据不丢失）
                        with pathlib.Path(dst).open("w", encoding="utf-8") as f:
                            f.write(content)
                            f.flush()
                            os.fsync(f.fileno())
                finally:
                    # 清理第二级临时文件（无论成功或失败）
                    if pathlib.Path(dst_tmp2).exists():
                        with suppress(OSError):
                            pathlib.Path(dst_tmp2).unlink()
                # 清理第一级回退临时文件
                if pathlib.Path(dst_tmp).exists():
                    with suppress(OSError):
                        pathlib.Path(dst_tmp).unlink()

            # 清理源临时文件（回退路径下 src 不会被 os.replace 移动）
            if pathlib.Path(src).exists():
                with suppress(OSError):
                    pathlib.Path(src).unlink()

            return True
        except Exception as e:
            self.logger.error("回退直接写入也失败: %s", e)
            return False

    def save_history_data(self) -> None:
        """保存历史数据到文件

        P0: 使用 {schema_version, data} 版本化 JSON 格式存储（与 flush() 一致）。
        P1: 写入失败累计计数，超过阈值触发告警。

        _safe_file_replace 内部包含完整的重试+回退机制，
        无需外层重复重试。
        """
        # 在锁内获取数据
        with self._lock:
            new_data = list(self._history_buffer)
            self._history_buffer.clear()

        if not new_data:
            return

        try:
            # 加载现有历史数据，追加新记录，写入版本化格式
            existing = self._load_history_with_recovery()
            existing.extend(new_data)
            if len(existing) > 1000:
                existing = existing[-1000:]
            versioned = {
                "schema_version": self.HISTORY_SCHEMA_VERSION,
                "data": existing,
            }
            self._atomic_write_json(self.history_data_file, versioned)

            self.logger.debug(f"版本化写入: {len(new_data)}条历史数据 (总计{len(existing)}条)")
            self._record_pipeline_metric("save_history_data", success=True, record_count=len(new_data))
        except Exception as e:
            self.logger.error("保存历史数据失败: %s", e)
            self._record_pipeline_metric("save_history_data", success=False, error=str(e)[:200])
            # 写入失败将数据放回缓冲区（使用 extendleft 保持顺序）
            with self._lock:
                self._history_buffer.extendleft(reversed(new_data))

    def _compact_history_if_needed(self) -> None:
        """压缩历史数据：超过 1200 条时保留最近 1000 条

        阈值设为 1200（超过目标 20%）以减少频繁压缩。
        支持版本化 JSON 格式（{schema_version, data}），
        使用原子替换确保数据完整性。
        """
        try:
            history = self._load_history_with_recovery()
            if len(history) <= 1200:
                return

            # 保留最近 1000 条
            compacted = history[-1000:]

            # 原子写入版本化格式
            versioned = {
                "schema_version": self.HISTORY_SCHEMA_VERSION,
                "data": compacted,
            }
            temp_file = self.history_data_file + ".compact.tmp"
            with pathlib.Path(temp_file).open("w", encoding="utf-8") as f:
                fast_dump(versioned, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            if not self._safe_file_replace(temp_file, self.history_data_file):
                self.logger.error("历史数据压缩失败: 文件替换所有方案均失败")
                self._count_write_failure()
            else:
                self.logger.info(f"历史数据压缩: {len(history)} → {len(compacted)} 条")
        except Exception as e:
            self.logger.error("历史数据压缩失败: %s", e)
            self._count_write_failure()
        finally:
            # 清理临时文件
            temp_file = self.history_data_file + ".compact.tmp"
            if pathlib.Path(temp_file).exists():
                with suppress(OSError):
                    pathlib.Path(temp_file).unlink()

    def _load_history_with_recovery(self) -> list:
        """加载历史数据，带损坏恢复机制

        P0: 支持新旧两种格式：
        - 旧格式（无版本号）: 直接返回JSON数组
        - 新格式（v1.0+）: 返回 {"schema_version": ..., "data": [...]} 中的data
        """
        if not pathlib.Path(self.history_data_file).exists():
            return []

        try:
            with pathlib.Path(self.history_data_file).open(encoding="utf-8") as f:
                data = fast_load(f)
            if isinstance(data, list):
                # 旧格式（无版本号），直接返回
                return data
            if isinstance(data, dict) and "data" in data:
                # 新格式（P0 schema_version）
                version = data.get("schema_version", "unknown")
                self.logger.debug("加载历史数据 (schema_version=%s)", version)
                return data["data"]
            self.logger.warning("历史数据格式错误，重置为空列表")
            return []
        except json.JSONDecodeError as e:
            self.logger.warning("历史数据JSON损坏，尝试恢复: %s", e)
            return self._recover_history_data()
        except Exception as e:
            self.logger.warning("读取历史数据失败: %s", e)
            return []

    @staticmethod
    def _scan_bracket_pairs(content: str) -> list[dict[str, Any]]:
        """从损坏的 JSON 文本中扫描匹配括号的完整对象。

        使用字符级状态机提取所有顶层 JSON 对象，跳过无法解析的片段。
        """
        recovered: list[dict[str, Any]] = []
        i = 0
        while i < len(content):
            if content[i] == "{":
                brace_count = 0
                in_string = False
                escape_next = False
                start = i

                for j in range(i, len(content)):
                    char = content[j]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == "\\":
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            try:
                                obj_str = content[start : j + 1]
                                obj = fast_loads(obj_str)
                                if isinstance(obj, dict) and "timestamp" in obj:
                                    recovered.append(obj)
                            except json.JSONDecodeError:
                                pass
                            i = j + 1
                            break
                else:
                    i += 1
            else:
                i += 1
        return recovered

    def _recover_history_data(self) -> list:
        """尝试从损坏的JSON文件中恢复数据（健壮的逐行解析）"""
        recovered = []

        try:
            # 防御性编程：检查文件大小，避免读取超大文件耗尽内存
            file_size = pathlib.Path(self.history_data_file).stat().st_size
            max_size = 10 * 1024 * 1024  # 10MB限制
            if file_size > max_size:
                self.logger.warning(
                    f"历史文件过大({file_size / 1024 / 1024:.2f}MB)，"
                    f"超过限制({max_size / 1024 / 1024:.0f}MB)，跳过恢复",
                )
                return []

            content = pathlib.Path(self.history_data_file).read_text(encoding="utf-8")

            # P0: 尝试先解析版本化外层，提取内层数组用于字符级恢复
            try:
                outer = fast_loads(content)
                if isinstance(outer, dict) and "data" in outer:
                    content = json.dumps(outer["data"])
            except json.JSONDecodeError:
                pass  # 继续原有字符级恢复

            # 使用括号匹配算法找到完整的JSON对象
            recovered = self._scan_bracket_pairs(content)

            self.logger.info(f"从损坏文件中恢复了 {len(recovered)} 条记录")
            return recovered

        except Exception as e:
            self.logger.error("恢复历史数据失败: %s", e)
            return []

    def get_current_data(self) -> dict[str, Any]:
        """获取当前数据"""
        with self._lock:
            return self._current_data.copy()

    def get_history_data(self) -> list[dict[str, Any]]:
        """获取历史数据（从文件读取，支持 JSONL 格式）"""
        return self._load_history_with_recovery()

    def get_error_logs(self) -> list[dict[str, Any]]:
        """获取错误日志（从文件读取）"""
        try:
            if pathlib.Path(self.error_log_file).exists():
                with pathlib.Path(self.error_log_file).open(encoding="utf-8") as f:
                    return fast_load(f)
        except Exception as e:
            self.logger.error("读取错误日志失败: %s", e)
        return []

    @property
    def storage_dir_prop(self) -> str:
        """公开存储目录路径"""
        return self.storage_dir

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            if not self._speed_samples:
                return {
                    "total_checks": self._total_checks,
                    "matches_found": self._matches_found + self._match_event_count,
                    "avg_speed": 0,
                    "max_speed": 0,
                    "min_speed": 0,
                    "uptime": time.time() - self._start_time,
                }

            return {
                "total_checks": self._total_checks,
                "matches_found": self._matches_found + self._match_event_count,
                "avg_speed": statistics.mean(self._speed_samples),
                "max_speed": max(self._speed_samples),
                "min_speed": min(self._speed_samples),
                "uptime": time.time() - self._start_time,
                "speed_std_dev": (
                    statistics.stdev(self._speed_samples) if len(self._speed_samples) > 1 else 0
                ),
            }

    def generate_report(self, report_type: str = "daily") -> dict[str, Any]:
        """生成报告

        Args:
            report_type: 报告类型 (daily, weekly, monthly)

        Returns:
            报告数据字典

        """
        # 在锁内获取必要数据
        with self._lock:
            error_count = len(self._error_buffer)

        # 在锁外执行I/O操作和报告生成
        try:
            # 读取历史数据（通过统一加载器，支持版本化 JSON 和 JSONL）
            history = self._load_history_with_recovery()

            if not history:
                return {"message": "无历史数据可供生成报告"}

            # 根据报告类型过滤数据
            now = datetime.now()
            if report_type == "daily":
                cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif report_type == "weekly":
                cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                cutoff = cutoff.replace(day=cutoff.day - cutoff.weekday())
            elif report_type == "monthly":
                cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

            cutoff_ts = cutoff.timestamp()
            filtered_data = [d for d in history if d.get("timestamp", 0) >= cutoff_ts]

            if not filtered_data:
                return {"message": f"在指定时间范围内无数据 ({report_type})"}

            # 计算统计数据（单次遍历提取所有字段）
            speeds: list[float] = []
            cpu_usages: list[float] = []
            memory_usages: list[float] = []
            total_checked = 0
            matches_found = 0
            for d in filtered_data:
                speeds.append(d.get("speed", 0))
                cpu_usages.append(d.get("cpu_usage", 0))
                memory_usages.append(d.get("memory_usage", 0))
                tc = d.get("total_checked", 0)
                total_checked = max(total_checked, tc)
                mf = d.get("matches_found", 0)
                matches_found = max(matches_found, mf)

            report = {
                "report_type": report_type,
                "generated_at": now.isoformat(),
                "period_start": cutoff.isoformat(),
                "period_end": now.isoformat(),
                "data_points": len(filtered_data),
                "summary": {
                    "total_checked": total_checked,
                    "matches_found": matches_found,
                    "avg_speed": statistics.mean(speeds) if speeds else 0,
                    "max_speed": max(speeds) if speeds else 0,
                    "min_speed": min(speeds) if speeds else 0,
                    "avg_cpu_usage": statistics.mean(cpu_usages) if cpu_usages else 0,
                    "avg_memory_usage": statistics.mean(memory_usages) if memory_usages else 0,
                    "error_count": error_count,  # 使用之前获取的值
                },
                "trends": self._analyze_trends(filtered_data),
                "recommendations": self._generate_recommendations(speeds, cpu_usages, memory_usages),
            }

            # 保存报告
            report_filename = f"report_{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.json"
            report_path = os.path.join(self.storage_dir, report_filename)

            with pathlib.Path(report_path).open("w", encoding="utf-8") as f:
                fast_dump(report, f, ensure_ascii=False, indent=2)

            self.logger.info("%s报告已生成: %s", report_type, report_path)
            self._auto_cleanup_if_needed()
            return report

        except Exception as e:
            self.logger.error("生成报告失败: %s", e)
            return {"error": str(e)}

    def _analyze_trends(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """分析数据趋势

        P1-3: 使用线性回归替代简单的前半/后半均值比较，
        提高趋势判断的准确性和灵敏度（阈值2%）。
        """
        if len(data) < 2:
            return {"message": "数据点不足，无法分析趋势"}

        # 分析速度趋势
        speeds = [d.get("speed", 0) for d in data]
        cpu_usages = [d.get("cpu_usage", 0) for d in data]
        memory_usages = [d.get("memory_usage", 0) for d in data]

        # P1-3: 使用线性回归计算趋势
        def calculate_trend(values: list[float]) -> str:
            if len(values) < 3:
                return "stable"
            try:
                n = len(values)
                x_sum = sum(range(n))
                y_sum = sum(values)
                xy_sum = sum(i * v for i, v in enumerate(values))
                x2_sum = sum(i * i for i in range(n))
                denominator = n * x2_sum - x_sum * x_sum
                if denominator == 0:
                    return "stable"
                slope = (n * xy_sum - x_sum * y_sum) / denominator
                avg = y_sum / n if n > 0 else 0
                if avg == 0:
                    return "stable"
                normalized_slope = slope / abs(avg)
                threshold = 0.02  # 2%阈值
                if normalized_slope > threshold:
                    return "increasing"
                if normalized_slope < -threshold:
                    return "decreasing"
                return "stable"
            except (OverflowError, statistics.StatisticsError, ValueError):
                # 降级：前半/后半均值比较
                if len(values) < 2:
                    return "stable"
                first_half_avg = statistics.mean(values[: len(values) // 2])
                second_half_avg = statistics.mean(values[len(values) // 2 :])
                if second_half_avg > first_half_avg * 1.05:
                    return "increasing"
                if second_half_avg < first_half_avg * 0.95:
                    return "decreasing"
                return "stable"

        return {
            "speed": {
                "trend": calculate_trend(speeds),
                "average": statistics.mean(speeds) if speeds else 0,
                "std_dev": statistics.stdev(speeds) if len(speeds) > 1 else 0,
            },
            "cpu_usage": {
                "trend": calculate_trend(cpu_usages),
                "average": statistics.mean(cpu_usages) if cpu_usages else 0,
                "std_dev": statistics.stdev(cpu_usages) if len(cpu_usages) > 1 else 0,
            },
            "memory_usage": {
                "trend": calculate_trend(memory_usages),
                "average": statistics.mean(memory_usages) if memory_usages else 0,
                "std_dev": statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0,
            },
        }

    def _generate_recommendations(
        self, speeds: list[float], cpu_usages: list[float], memory_usages: list[float],
    ) -> list[str]:
        """生成优化建议"""
        recommendations = []

        # 基于速度的建议
        if speeds:
            avg_speed = statistics.mean(speeds)
            if avg_speed < self._REC_SPEED_THRESHOLD_LOW:
                recommendations.append("检测速率较低，建议检查系统配置或考虑使用GPU加速")
            elif avg_speed > self._REC_SPEED_THRESHOLD_HIGH:
                recommendations.append("检测速率很高，系统性能良好")

        # 基于CPU使用率的建议
        if cpu_usages:
            avg_cpu = statistics.mean(cpu_usages)
            if avg_cpu > self._REC_CPU_THRESHOLD_HIGH:
                recommendations.append("CPU使用率较高，建议优化算法或减少并发线程数")
            elif avg_cpu < self._REC_CPU_THRESHOLD_LOW:
                recommendations.append("CPU使用率较低，可以增加并发线程数提高性能")

        # 基于内存使用的建议
        if memory_usages:
            avg_memory = statistics.mean(memory_usages)
            if avg_memory > self._REC_MEM_THRESHOLD_HIGH_MB:  # 1GB
                recommendations.append("内存使用较高，建议检查内存泄漏或优化数据结构")
            elif avg_memory > self._REC_MEM_THRESHOLD_MEDIUM_MB:
                recommendations.append("内存使用适中，注意监控内存增长趋势")

        return recommendations

    def _load_auto_cleanup_config(self) -> tuple[bool, int]:
        """从 ConfigManager 读取 monitoring.auto_cleanup 配置

        返回:
            (enabled: bool, max_age_days: int) 元组，读取失败时返回默认值 (True, 7)
        """
        # 默认值（向后兼容）
        default_enabled = True
        default_max_age_days = 7
        try:
            # 尝试定位配置文件路径（相对于当前工作目录或脚本目录）
            import pathlib

            from src.config.config_manager import ConfigManager

            candidates = [
                pathlib.Path("config.json"),
                pathlib.Path(__file__).parent.parent.parent / "config.json",
            ]
            config_file = None
            for candidate in candidates:
                if candidate.exists():
                    config_file = str(candidate)
                    break

            cfg = ConfigManager(config_file)
            enabled = cfg.get("monitoring.auto_cleanup.enabled", default_enabled)
            max_age_days = cfg.get("monitoring.auto_cleanup.max_age_days", default_max_age_days)

            # 类型安全检查，防止配置值类型异常
            if not isinstance(enabled, bool):
                enabled = default_enabled
            if not isinstance(max_age_days, int) or max_age_days <= 0:
                max_age_days = default_max_age_days

            return enabled, max_age_days
        except Exception as e:
            # 配置读取失败时静默回退到默认值
            self.logger.debug(
                "auto_cleanup配置回退: enabled=%s, max_age_days=%s, 原因: %s",
                default_enabled, default_max_age_days, e,
            )
            return default_enabled, default_max_age_days

    def _auto_cleanup_if_needed(self):
        """自动清理过期报告文件（每24小时最多执行一次）

        从 config.json 的 monitoring.auto_cleanup 读取：
          - enabled: 是否启用自动清理（默认 True）
          - max_age_days: 归档保留天数（默认 7 天）
        配置读取失败时静默回退到默认值，保持向后兼容。
        """
        current_time = time.time()
        if not hasattr(self, "_last_cleanup_time"):
            self._last_cleanup_time: float = 0.0

        # 每24小时最多执行一次清理
        if current_time - self._last_cleanup_time < 86400:
            return

        # 读取配置（失败时使用默认值）
        cleanup_enabled, max_age_days = self._load_auto_cleanup_config()

        # 如果配置禁用了自动清理，直接跳过
        if not cleanup_enabled:
            self.logger.debug("自动清理已通过配置禁用，跳过本次清理")
            self._last_cleanup_time = current_time
            return

        try:
            archive_dir = os.path.join(self.storage_dir, "archive")
            pathlib.Path(archive_dir).mkdir(exist_ok=True, parents=True)

            cutoff_time = current_time - (max_age_days * 86400)
            moved_count = 0

            for filename in os.listdir(self.storage_dir):
                if filename.startswith("report_") and filename.endswith(".json"):
                    filepath = os.path.join(self.storage_dir, filename)
                    if (
                    pathlib.Path(filepath).is_file()
                    and pathlib.Path(filepath).stat().st_mtime < cutoff_time
                ):
                        dest = os.path.join(archive_dir, filename)
                        shutil.move(filepath, dest)
                        moved_count += 1

            if moved_count > 0:
                self.logger.info(
                "自动归档了 %s 个过期报告文件（保留期: %s 天）",
                moved_count, max_age_days,
            )

            self._last_cleanup_time = current_time
        except Exception as e:
            self.logger.warning("自动清理报告文件时出错: %s", e)

    def cleanup_old_data(self, max_age_days: int = 30) -> None:
        """清理旧数据

        Args:
            max_age_days: 数据最大保存天数

        """
        # 计算截止时间
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        # 在锁外执行I/O操作
        try:
            # 清理历史数据（通过统一加载器，与 flush()/save_history_data() 一致）
            history = self._load_history_with_recovery()
            if history:
                cleaned_history = [d for d in history if d.get("timestamp", 0) >= cutoff_time]

                if len(cleaned_history) != len(history):
                    # P0: 写回时保留版本号
                    versioned = {
                        "schema_version": self.HISTORY_SCHEMA_VERSION,
                        "data": cleaned_history,
                    }
                    with pathlib.Path(self.history_data_file).open("w", encoding="utf-8") as f:
                        fast_dump(versioned, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"清理了 {len(history) - len(cleaned_history)} 条过期历史数据")

            # 清理错误日志
            if pathlib.Path(self.error_log_file).exists():
                with pathlib.Path(self.error_log_file).open(encoding="utf-8") as f:
                    errors = fast_load(f)

                cleaned_errors = [e for e in errors if e.get("timestamp", 0) >= cutoff_time]

                if len(cleaned_errors) != len(errors):
                    with pathlib.Path(self.error_log_file).open("w", encoding="utf-8") as f:
                        fast_dump(cleaned_errors, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"清理了 {len(errors) - len(cleaned_errors)} 条过期错误日志")

        except Exception as e:
            self.logger.error("清理旧数据失败: %s", e)

    def _record_pipeline_metric(
        self,
        operation: str,
        success: bool = True,
        record_count: int = 0,
        error: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        """记录管道运营指标 (v4.3.1)

        追踪每次数据持久化操作的关键指标，支持延迟、吞吐量分析。

        Args:
            operation: 操作名称 (save_current_data, save_history_data, record_error, flush, stop)
            success: 操作是否成功
            record_count: 处理的记录数
            error: 错误信息 (失败时)
            extra: 额外上下文数据 (如 batched_lines 等)

        """
        now = time.time()
        with self._pipeline_lock:
            self._save_counts[operation] = self._save_counts.get(operation, 0) + 1
            self._last_save_times[operation] = now

            if not success:
                self._pipeline_error_count += 1

            metric_entry = {
                "timestamp": now,
                "datetime": datetime.fromtimestamp(now).isoformat(),
                "operation": operation,
                "success": success,
                "record_count": record_count,
                "error": error,
            }
            if extra:
                metric_entry["extra"] = extra
            self._pipeline_metrics.append(metric_entry)

    def get_observability_stats(self) -> dict[str, Any]:
        """获取数据管道可观测性统计 (v4.3.1)

        返回数据管道的完整运营指标，包括保存次数、最后保存时间、
        缓冲区大小、错误计数等。用于监控面板和告警系统。

        Returns:
            管道运营指标字典:
            - save_counts: 各操作类型保存次数
            - last_save_times: 各操作最后保存时间 (ISO 8601)
            - buffer_sizes: 内存缓冲区当前大小
            - pipeline_error_count: 管道持久化总错误数
            - recent_metrics: 最近 50 条管道操作记录
            - uptime_seconds: 管道运行时长
            - throughput: 最近 60s 内各操作吞吐量 (ops/min)

        """
        now = time.time()
        # 统一锁顺序: _lock → _pipeline_lock（与其他方法一致）
        with self._lock:
            buffer_sizes = {
                "history_buffer": len(self._history_buffer),
                "error_buffer": len(self._error_buffer),
                "current_data_keys": len(self._current_data),
            }

        with self._pipeline_lock:
            save_counts = dict(self._save_counts)
            last_save_times = {
                k: datetime.fromtimestamp(v).isoformat() if v else None
                for k, v in self._last_save_times.items()
            }
            error_count = self._pipeline_error_count
            recent_metrics = list(self._pipeline_metrics)[-50:]

        # 计算最近 60s 内各操作吞吐量
        cutoff = now - 60
        throughput: dict[str, int] = {}
        for m in recent_metrics:
            op = m["operation"]
            if m["timestamp"] >= cutoff:
                throughput[op] = throughput.get(op, 0) + 1

        return {
            "save_counts": save_counts,
            "last_save_times": last_save_times,
            "buffer_sizes": buffer_sizes,
            "pipeline_error_count": error_count,
            "recent_metrics": recent_metrics,
            "uptime_seconds": now - self._start_time,
            "throughput_ops_per_min": throughput,
        }

    def flush(self) -> None:
        """刷写所有缓冲数据到磁盘

        自 v4.3.1: 使用版本化 JSON 格式（{schema_version, data}），与 save_history_data() 一致。
        """
        pending_history = None
        pending_errors = None

        with self._lock:
            if self._history_buffer:
                pending_history = list(self._history_buffer)
                self._history_buffer.clear()
            if self._error_buffer:
                pending_errors = list(self._error_buffer)
                self._error_buffer.clear()

        # 在锁外执行 I/O 操作: 先刷写性能日志缓冲
        self._flush_perf_buffer()

        if pending_history:
            try:
                history = self._load_history_with_recovery()
                history.extend(pending_history)
                if len(history) > 1000:
                    history = history[-1000:]
                # P0: 使用带版本号的格式
                versioned = {
                    "schema_version": self.HISTORY_SCHEMA_VERSION,
                    "data": history,
                }
                self._atomic_write_json(self.history_data_file, versioned)
                self.logger.debug(f"flush: 写入 {len(pending_history)} 条历史数据")
            except Exception as e:
                self.logger.error("flush 写入历史数据失败: %s", e)
                # P1: 写入失败计数
                self._count_write_failure()
                # 写入失败则将数据放回缓冲区
                with self._lock:
                    self._history_buffer.extendleft(reversed(pending_history))

        if pending_errors:
            try:
                errors = []
                if pathlib.Path(self.error_log_file).exists():
                    try:
                        with pathlib.Path(self.error_log_file).open(encoding="utf-8") as f:
                            errors = fast_load(f)
                    except (json.JSONDecodeError, OSError) as e:
                        self.logger.warning("读取错误日志文件失败，将覆盖: %s", e)
                        errors = []
                errors.extend(pending_errors)
                errors = self._error_rotator.rotate(errors)
                self._atomic_write_json(self.error_log_file, errors)
                self.logger.debug(f"flush: 写入 {len(pending_errors)} 条错误数据")
            except Exception as e:
                self.logger.error("flush 写入错误数据失败: %s", e)
                # 写入失败则将数据放回缓冲区
                with self._lock:
                    self._error_buffer.extendleft(reversed(pending_errors))

    def _count_write_failure(self) -> None:
        """P1-4: 累计写入失败次数，超过阈值告警（线程安全）"""
        with self._write_failure_lock:
            self._write_failure_count += 1

            # 每小时重置计数器
            if time.time() - self._write_failure_last_reset > 3600:
                self._write_failure_count = 1
                self._write_failure_last_reset = time.time()

            # 超过3次写入失败触发告警
            if self._write_failure_count >= 3:
                self.logger.warning(
                    f"数据写入失败次数累积: {self._write_failure_count}次 "
                    f"（可能磁盘空间不足或权限问题）",
                )

    def stop(self) -> None:
        """停止数据记录器，确保所有数据已写入"""
        try:
            self._flush_perf_buffer()
            self.flush()
            self._record_pipeline_metric("stop", success=True)
            self.logger.info("数据记录器已停止，所有缓冲数据已写入")
        except Exception as e:
            self.logger.error("数据记录器停止时刷写失败: %s", e)
            self._record_pipeline_metric("stop", success=False, error=str(e)[:200])
