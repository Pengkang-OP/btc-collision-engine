#!/usr/bin/env python3
"""
比特币私钥对撞引擎监控系统

该模块负责监控对撞引擎的运行状态、性能指标和异常情况，
提供实时数据采集、分析和告警功能。
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional  # noqa: F401

import psutil

from src.monitoring.storage_config import DataStorageConfig

# 配置日志
from src.utils import get_configured_logger

# 高性能JSON序列化
from src.utils.fast_json import fast_dump, fast_dumps, fast_load, fast_loads

from ..utils.trend_utils import calculate_trend

logger = get_configured_logger("MonitoringSystem")


class MonitoringData:
    """监控数据结构"""

    def __init__(self) -> None:
        self.timestamp: float = time.time()
        self.performance: dict[str, Any] = {
            "speed": 0.0,  # 每秒检测速率
            "total_checked": 0,  # 已检测总数
            "matches_found": 0,  # 找到的匹配数
            "cpu_usage": 0.0,  # CPU使用率
            "memory_usage": 0.0,  # 内存使用率
            "thread_count": 0,  # 线程数
        }
        self.system: dict[str, Any] = {
            "os": os.name,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",  # noqa: E501
            "pid": os.getpid(),
            "uptime": 0.0,  # 系统运行时间
        }
        self.engine: dict[str, Any] = {
            "mode": "",  # 对撞模式
            "target_count": 0,  # 目标地址数量
            "is_running": False,  # 引擎是否运行
            "current_position": 0,  # 当前位置
        }
        self.errors: list[dict[str, Any]] = []  # 错误记录

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "timestamp": self.timestamp,
            "performance": self.performance,
            "system": self.system,
            "engine": self.engine,
            "errors": self.errors,
        }


class DataCollector:
    """数据采集器"""

    def __init__(self, engine: Any | None = None) -> None:
        self.engine = engine
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()

        # 优化: 后台线程持续采样CPU使用率，避免阻塞主线程
        self._cpu_usage_value: float = 0.0
        self._cpu_sample_lock = threading.Lock()
        self._cpu_sample_running = True
        self._cpu_sample_thread = threading.Thread(
            target=self._background_cpu_sampling, daemon=True, name="cpu-sampler"
        )
        self._cpu_sample_thread.start()
        logger.debug("后台CPU采样线程已启动")

    def _background_cpu_sampling(self):
        """后台持续采样CPU使用率，避免阻塞主线程"""
        process = psutil.Process(os.getpid())
        while self._cpu_sample_running:
            try:
                cpu_val = process.cpu_percent(interval=0.5)
                with self._cpu_sample_lock:
                    self._cpu_usage_value = cpu_val
            except OSError:
                logger.debug("CPU采样失败（进程可能已终止）")
            time.sleep(0.5)

    def _get_cpu_usage(self) -> float:
        """非阻塞获取CPU使用率"""
        with self._cpu_sample_lock:
            return self._cpu_usage_value

    def stop(self) -> None:
        """停止后台CPU采样线程"""
        self._cpu_sample_running = False

    def collect_performance_data(self) -> dict[str, Any]:
        """收集性能数据"""
        try:
            cpu_usage = (
                self._get_cpu_usage()
            )  # 优化: 非阻塞获取，替代阻塞0.1s的cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_usage = memory_info.rss / (1024 * 1024)  # 转换为MB
            thread_count = len(self.process.threads())

            performance_data = {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "thread_count": thread_count,
            }

            if self.engine and hasattr(self.engine, "get_stats"):
                stats = self.engine.get_stats()
                if stats:
                    performance_data["speed"] = stats.speed
                    performance_data["total_checked"] = stats.total_checked
                    performance_data["matches_found"] = len(stats.matches)

            return performance_data
        except Exception as e:
            logger.error(f"收集性能数据时出错: {e}")
            return {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "thread_count": 0,
                "speed": 0.0,
                "total_checked": 0,
                "matches_found": 0,
            }

    def collect_system_data(self) -> dict[str, Any]:
        """收集系统数据"""
        uptime = time.time() - self.start_time
        return {
            "os": os.name,
            "python_version": (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            ),
            "pid": os.getpid(),
            "uptime": uptime,
        }

    def collect_engine_data(self) -> dict[str, Any]:
        """收集引擎数据"""
        engine_data = {"mode": "", "target_count": 0, "is_running": False, "current_position": 0}

        if self.engine:
            engine_data["is_running"] = (
                self.engine.is_running() if hasattr(self.engine, "is_running") else False
            )
            if hasattr(self.engine, "_current_mode"):
                engine_data["mode"] = self.engine._current_mode
            if hasattr(self.engine, "targets"):
                engine_data["target_count"] = len(self.engine.targets)
            if hasattr(self.engine, "_current_position"):
                engine_data["current_position"] = self.engine._current_position

        return engine_data

    def collect_all_data(self) -> MonitoringData:
        """收集所有数据"""
        data = MonitoringData()
        data.performance.update(self.collect_performance_data())
        data.system.update(self.collect_system_data())
        data.engine.update(self.collect_engine_data())
        return data


class DataStorage:
    """数据存储管理

    P0统一数据源: 支持委托给DataLogger作为唯一持久化层。
    当 data_logger 参数提供时，所有写入委托给 DataLogger，
    读取操作也通过 DataLogger 完成，消除双系统写同一文件的数据不一致风险。

    注意：已统一使用data_logs作为唯一数据源，
    monitoring_data目录已废弃。

    自 v4.3.1 起，支持委托给 DataLogger 实例以消除双写竞争。
    当 data_logger 参数提供时，所有持久化操作委托给 DataLogger，
    本类仅作为兼容性适配层存在。
    """

    def __init__(self, storage_dir: str | None = None, data_logger: Any | None = None) -> None:
        # 使用统一配置，默认使用data_logs
        self.storage_dir = DataStorageConfig.ensure_storage_dir(storage_dir)
        self.current_data_file = os.path.join(self.storage_dir, "current_data.json")
        self.history_data_file = os.path.join(self.storage_dir, "history_data.json")
        self.error_log_file = os.path.join(self.storage_dir, "error_log.json")

        # P0统一数据源: DataLogger委托引用（可选，向后兼容）
        self._data_logger: Any | None = data_logger

        # 当有DataLogger委托时，跳过独立文件初始化（由DataLoader负责）
        if self._data_logger is None:
            # 初始化历史数据文件
            if not os.path.exists(self.history_data_file):
                with open(self.history_data_file, "w", encoding="utf-8") as f:
                    fast_dump([], f)

            # 初始化错误日志文件
            if not os.path.exists(self.error_log_file):
                with open(self.error_log_file, "w", encoding="utf-8") as f:
                    fast_dump([], f)

    def save_current_data(self, data: MonitoringData) -> None:
        """保存当前数据（P0委托DataLogger或原子写入 + 安全权限）"""
        # P0统一数据源: 委托给DataLogger
        if self._data_logger is not None:
            # 线程安全地委托 DataLogger 更新 _current_data
            try:
                self._data_logger.update_current_data_sections(
                    performance=data.performance,
                    system=data.system,
                    engine=data.engine,
                )
                self._data_logger.save_current_data()
            except Exception as e:
                logger.error(f"委托DataLogger保存当前数据失败: {e}")
            return

        try:
            # 使用原子写入：先写临时文件，再重命名
            temp_file = self.current_data_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                fast_dump(data.to_dict(), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘

            # 设置安全权限: 仅所有者可读写 (Unix only; Windows 通过 ACL 控制)
            if os.name != "nt":
                os.chmod(temp_file, 0o600)

            # 原子替换
            if os.path.exists(self.current_data_file):
                os.replace(temp_file, self.current_data_file)
            else:
                os.rename(temp_file, self.current_data_file)
        except Exception as e:
            logger.error(f"保存当前数据失败: {e}")
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")

    def save_history_data(self, data: MonitoringData) -> None:
        """保存历史数据（P0委托DataLogger或原子写入 + 数据恢复）"""
        # P0统一数据源: 委托给DataLogger的缓冲区
        if self._data_logger is not None:
            try:
                self._data_logger._history_buffer.append(data.to_dict())
                # 缓冲区满时DataLogger自动刷写
            except Exception as e:
                logger.error(f"委托DataLogger保存历史数据失败: {e}")
            return

        try:
            # 读取现有历史数据（带恢复机制）
            history = self._load_history_with_recovery()

            # 添加新数据
            history.append(record)

            # 限制历史数据长度（保留最近1000条）
            if len(history) > 1000:
                history = history[-1000:]

            # JSONL 写入，与 DataLogger 保持一致 (v4.3.1)
            temp_file = self.history_data_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                for record_item in history:
                    f.write(fast_dumps(record_item) + "\n")
                f.flush()
                os.fsync(f.fileno())

            # 设置安全权限: 仅所有者可读写 (Unix only; Windows 通过 ACL 控制)
            if os.name != "nt":
                os.chmod(temp_file, 0o600)

            # 原子替换
            if os.path.exists(self.history_data_file):
                os.replace(temp_file, self.history_data_file)
            else:
                os.rename(temp_file, self.history_data_file)
        except Exception as e:
            logger.error(f"保存历史数据失败: {e}")
            # 清理临时文件
            try:
                temp_file = self.history_data_file + ".tmp"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")

    def compress_old_data(self, days_threshold: int = 7, sample_rate: float = 0.1) -> None:
        """P2-3修复: 压缩超过threshold天的历史数据

        参数:
            days_threshold: 超过多少天的数据需要压缩（默认7天）
            sample_rate: 采样率，0.1表示保留10%的数据（默认0.1）

        自 v4.3.1: 压缩文件同样使用 JSONL 格式，与主历史数据文件保持一致。
        """
        try:
            from datetime import datetime, timedelta

            # 计算截止日期
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            cutoff_timestamp = cutoff_date.timestamp()

            # 读取历史数据
            history = self._load_history_with_recovery()

            if not history:
                logger.info("无历史数据需要压缩")
                return

            # 分离新旧数据
            old_data = []
            new_data = []

            for record in history:
                timestamp = record.get("timestamp", 0)
                if timestamp < cutoff_timestamp:
                    old_data.append(record)
                else:
                    new_data.append(record)

            if not old_data:
                logger.info(f"无超过{days_threshold}天的数据需要压缩")
                return

            # 采样压缩旧数据
            compressed_data = self._sample_data(old_data, sample_rate)

            # 保存压缩数据到单独文件 (v4.3.1: JSONL 格式)
            compressed_file = self.history_data_file.replace(".json", "_compressed.json")
            temp_file = compressed_file + ".tmp"

            with open(temp_file, "w", encoding="utf-8") as f:
                for record in compressed_data:
                    f.write(fast_dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(compressed_file):
                os.replace(temp_file, compressed_file)
            else:
                os.rename(temp_file, compressed_file)

            # 保留新数据 (v4.3.1: JSONL 格式)
            temp_file = self.history_data_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                for record in new_data:
                    f.write(fast_dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(self.history_data_file):
                os.replace(temp_file, self.history_data_file)
            else:
                os.rename(temp_file, self.history_data_file)

            logger.info(
                f"数据压缩完成: {len(old_data)}条旧数据 -> {len(compressed_data)}条 "
                f"(采样率{sample_rate * 100:.0f}%), 保留{len(new_data)}条新数据"
            )

        except Exception as e:
            logger.error(f"压缩历史数据失败: {e}")
            # 清理临时文件
            for temp_file in [compressed_file + ".tmp", self.history_data_file + ".tmp"]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as cleanup_error:
                    # A类修复: 资源清理失败添加DEBUG日志
                    logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")

    def _sample_data(self, data: list, sample_rate: float) -> list:
        """P2-3修复: 数据采样

        参数:
            data: 原始数据列表
            sample_rate: 采样率（0.0-1.0）

        返回:
            采样后的数据列表
        """
        if not data or sample_rate >= 1.0:
            return data

        import random

        # 使用实例化Random对象而非全局随机，避免影响其他模块（统计采样，非加密用途）
        _rng = random.Random()  # nosec B311  # 预留: 实例化Random而非全局

        # 计算采样数量
        sample_count = max(1, int(len(data) * sample_rate))

        # 均匀采样：确保覆盖整个时间段
        if sample_count >= len(data):
            return data

        # 计算采样间隔
        interval = len(data) / sample_count
        sampled = []

        for i in range(sample_count):
            index = int(i * interval)
            if index < len(data):
                sampled.append(data[index])

        return sampled

    def save_error(self, error: dict[str, Any]) -> None:
        """保存错误记录（P0委托DataLogger或原子写入）"""
        # P0统一数据源: 委托给DataLogger
        if self._data_logger is not None:
            try:
                error_type = error.get("type", "unknown")
                error_msg = error.get("message", str(error))
                self._data_logger.record_error(
                    error_type=error_type,
                    message=error_msg,
                    context=error,
                )
            except Exception as e:
                logger.error(f"委托DataLogger保存错误记录失败: {e}")
            return

        try:
            # 读取现有错误日志
            errors = []
            if os.path.exists(self.error_log_file):
                with open(self.error_log_file, encoding="utf-8") as f:
                    errors = fast_load(f)

            # 添加新错误
            error["timestamp"] = time.time()
            errors.append(error)

            # 应用轮转：保留最近7天、最多1000条记录
            from src.log_engine.log_rotator import LogRotator

            rotator = LogRotator(max_age_days=7, max_count=1000)
            errors = rotator.rotate(errors)

            # 原子写入
            temp_file = self.error_log_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                fast_dump(errors, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # 设置安全权限: 仅所有者可读写 (Unix only; Windows 通过 ACL 控制)
            if os.name != "nt":
                os.chmod(temp_file, 0o600)

            # 原子替换
            if os.path.exists(self.error_log_file):
                os.replace(temp_file, self.error_log_file)
            else:
                os.rename(temp_file, self.error_log_file)
        except Exception as e:
            logger.error(f"保存错误记录失败: {e}")
            # 清理临时文件
            try:
                temp_file = self.error_log_file + ".tmp"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as cleanup_error:
                # A类修复: 资源清理失败添加DEBUG日志
                logger.debug(f"清理临时文件失败（可忽略）: {cleanup_error}")

    def get_current_data(self) -> dict[str, Any] | None:
        """获取当前数据

        自 v4.3.1: 若委托给 DataLogger，从其获取数据。
        """
        if self._data_logger is not None:
            try:
                return self._data_logger.get_current_data()
            except Exception as e:
                logger.error(f"DataLogger读取当前数据失败: {e}")
        try:
            if os.path.exists(self.current_data_file):
                with open(self.current_data_file, encoding="utf-8") as f:
                    return fast_load(f)
        except Exception as e:
            logger.error(f"读取当前数据失败: {e}")
        return None

    def _load_history_with_recovery(self) -> list:
        """加载历史数据，带损坏恢复机制

        P0统一数据源: DataLogger可用时委托其更强的括号匹配恢复算法。
        """
        # P0委托DataLoader（其恢复算法更强）
        if self._data_logger is not None:
            return self._data_logger._load_history_with_recovery()

        if not os.path.exists(self.history_data_file):
            return []

        try:
            with open(self.history_data_file, encoding="utf-8") as f:
                raw = f.read()
            if not raw.strip():
                return []

            # 尝试 JSON array 格式（向后兼容旧数据）
            if raw.strip().startswith("["):
                try:
                    data = fast_loads(raw)
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    pass

            # JSONL 格式：逐行解析
            records = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = fast_loads(line)
                    if isinstance(record, dict):
                        records.append(record)
                except json.JSONDecodeError:
                    continue
            return records

        except json.JSONDecodeError as e:
            # JSON文件损坏，尝试恢复
            logger.error(f"历史数据JSON损坏，尝试恢复: {e}")
            return self._recover_history_data()
        except Exception as e:
            logger.error(f"读取历史数据失败: {e}")
            return []

    def _recover_history_data(self) -> list:
        """尝试从损坏的JSON文件中恢复数据"""
        try:
            with open(self.history_data_file, encoding="utf-8") as f:
                content = f.read()

            # 尝试找到所有完整的JSON对象
            import re

            # 匹配完整的对象（简化版，不处理嵌套）
            pattern = r'\{[^{}]*"timestamp"[^{}]*\}'
            matches = re.findall(pattern, content, re.DOTALL)

            recovered = []
            for match in matches:
                try:
                    obj = fast_loads(match)
                    recovered.append(obj)
                except json.JSONDecodeError:
                    continue

            logger.info(f"从损坏文件中恢复了 {len(recovered)} 条记录")
            return recovered

        except Exception as e:
            logger.error(f"恢复历史数据失败: {e}")
            return []

    def get_history_data(self) -> list[dict[str, Any]]:
        """获取历史数据

        自 v4.3.1: 若委托给 DataLogger，从其获取数据。
        默认使用 JSONL 逐行解析，兼容传统 JSON array 格式。
        """
        if self._data_logger is not None:
            try:
                return self._data_logger.get_history_data()
            except Exception as e:
                logger.error(f"DataLogger读取历史数据失败: {e}")
        return self._load_history_with_recovery()

    def get_error_logs(self) -> list[dict[str, Any]]:
        """获取错误日志

        自 v4.3.1: 若委托给 DataLogger，从其获取数据。
        """
        if self._data_logger is not None:
            try:
                return self._data_logger.get_error_logs()
            except Exception as e:
                logger.error(f"DataLogger读取错误日志失败: {e}")
        try:
            with open(self.error_log_file, encoding="utf-8") as f:
                return fast_load(f)
        except Exception as e:
            logger.error(f"读取错误日志失败: {e}")
            return []


class AnomalyDetector:
    """异常检测器

    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        detector = AnomalyDetector(storage)

        # 独立使用（仅检测，不保存）
        detector = AnomalyDetector()
    """

    def __init__(self, storage: DataStorage | None = None) -> None:
        """
        初始化异常检测器

        Args:
            storage: 数据存储实例（可选），用于保存异常记录
        """
        # 使用依赖注入，storage变为可选
        self.storage = storage
        # 性能指标正常范围阈值
        self.thresholds = {
            "speed": {"min": 100, "max": 1000000},  # 最低检测速率 # 最高检测速率
            "cpu_usage": {"max": 90},  # CPU使用率上限
            "memory_usage": {"max": 1024},  # 内存使用上限（MB）
        }

    def detect_anomalies(self, current_data: MonitoringData) -> list[dict[str, Any]]:
        """检测异常

        Args:
            current_data: 当前监控数据

        Returns:
            异常列表
        """
        anomalies = []

        # 检测性能异常
        performance = current_data.performance

        # 检测速度异常
        speed = performance.get("speed", 0)
        speed_threshold = self.thresholds["speed"]
        if speed < speed_threshold["min"]:
            anomalies.append(
                {
                    "type": "performance",
                    "metric": "speed",
                    "value": speed,
                    "threshold": speed_threshold["min"],
                    "message": f"检测速率过低: {speed:.2f}/s",
                }
            )
        elif speed > speed_threshold["max"]:
            anomalies.append(
                {
                    "type": "performance",
                    "metric": "speed",
                    "value": speed,
                    "threshold": speed_threshold["max"],
                    "message": f"检测速率过高: {speed:.2f}/s",
                }
            )

        # 检测CPU使用率异常
        cpu_usage = performance.get("cpu_usage", 0)
        if cpu_usage > self.thresholds["cpu_usage"]["max"]:
            anomalies.append(
                {
                    "type": "performance",
                    "metric": "cpu_usage",
                    "value": cpu_usage,
                    "threshold": self.thresholds["cpu_usage"]["max"],
                    "message": f"CPU使用率过高: {cpu_usage:.2f}%",
                }
            )

        # 检测内存使用异常
        memory_usage = performance.get("memory_usage", 0)
        if memory_usage > self.thresholds["memory_usage"]["max"]:
            anomalies.append(
                {
                    "type": "performance",
                    "metric": "memory_usage",
                    "value": memory_usage,
                    "threshold": self.thresholds["memory_usage"]["max"],
                    "message": f"内存使用过高: {memory_usage:.2f}MB",
                }
            )

        # 检测引擎状态异常
        engine = current_data.engine
        if engine.get("is_running", False) and performance.get("speed", 0) == 0:
            anomalies.append(
                {
                    "type": "engine",
                    "metric": "speed",
                    "value": 0,
                    "threshold": 1,
                    "message": "引擎运行但检测速率为0",
                }
            )

        # 如果storage可用，保存异常记录（优化：批量保存）
        # 注意：错误保存已统一由 MonitoringAlertAdapter.generate_alert() 处理，
        # 此处不再重复调用 self.storage.save_error()，避免双重写入。
        return anomalies

    def analyze_trends(self, history_data: list[dict[str, Any]]) -> dict[str, Any]:
        """分析趋势

        自 v4.3.1: 优化为单次遍历，减少不必要的列表推导开销。

        Args:
            history_data: 历史数据列表

        Returns:
            趋势分析结果
        """
        if len(history_data) < 10:
            return {"message": "历史数据不足，无法分析趋势"}

        # 提取最近的100条数据
        recent_data = history_data[-100:]

        # v4.3.1: 单次遍历收集所有指标，避免三次独立的列表推导
        speeds: list[float] = []
        cpu_usages: list[float] = []
        memory_usages: list[float] = []

        for d in recent_data:
            perf = d.get("performance", {})
            if isinstance(perf, dict):
                speeds.append(perf.get("speed", 0))
                cpu_usages.append(perf.get("cpu_usage", 0))
                memory_usages.append(perf.get("memory_usage", 0))

        speed_avg = statistics.mean(speeds) if speeds else 0
        speed_std = statistics.stdev(speeds) if len(speeds) > 1 else 0

        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        cpu_std = statistics.stdev(cpu_usages) if len(cpu_usages) > 1 else 0

        memory_avg = statistics.mean(memory_usages) if memory_usages else 0
        memory_std = statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0

        return {
            "speed": {
                "average": speed_avg,
                "std_dev": speed_std,
                "trend": (
                    "increasing"
                    if speeds and speeds[-1] > speeds[0]
                    else "decreasing"
                    if speeds and speeds[-1] < speeds[0]
                    else "stable"
                ),
            },
            "cpu_usage": {
                "average": cpu_avg,
                "std_dev": cpu_std,
                "trend": (
                    "increasing"
                    if cpu_usages and cpu_usages[-1] > cpu_usages[0]
                    else "decreasing"
                    if cpu_usages and cpu_usages[-1] < cpu_usages[0]
                    else "stable"
                ),
            },
            "memory_usage": {
                "average": memory_avg,
                "std_dev": memory_std,
                "trend": (
                    "increasing"
                    if memory_usages and memory_usages[-1] > memory_usages[0]
                    else (
                        "decreasing"
                        if memory_usages and memory_usages[-1] < memory_usages[0]
                        else "stable"
                    )
                ),
            },
        }


class MonitoringAlertAdapter:
    """监控系统告警适配器

    将监控系统的异常检测结果适配到全局 AlertSystem，
    统一项目中的告警处理逻辑。

    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        adapter = MonitoringAlertAdapter(storage)

        # 独立使用（仅打印，不保存）
        adapter = MonitoringAlertAdapter()
    """

    def __init__(self, storage: DataStorage | None = None) -> None:
        """
        初始化告警适配器

        Args:
            storage: 数据存储实例（可选），用于保存告警记录
        """
        self.storage = storage
        self.alert_history: list = []
        # 使用全局告警系统（延迟导入避免循环引用）
        from src.monitoring.alert_system import get_alert_system

        self._alert_system = get_alert_system()

    def generate_alert(self, anomaly: dict[str, Any]) -> None:
        """从异常记录生成告警

        Args:
            anomaly: 异常信息字典
        """
        alert = {
            "timestamp": time.time(),
            "level": "warning" if anomaly.get("type") == "performance" else "critical",
            "message": anomaly.get("message", ""),
            "details": anomaly,
        }

        # 记录告警
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

        # 通过日志系统输出告警（替代裸 print，支持级别控制和脱敏）
        _timestamp = datetime.fromtimestamp(alert["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(f"[ALERT] {_timestamp} - {alert['message']}")

        # 记录到日志
        logger.warning(f"ALERT: {alert['message']} - Details: {fast_dumps(anomaly)}")

        # 同时通过全局告警系统检查指标
        metrics = self._anomaly_to_metrics(anomaly)
        if metrics:
            self._alert_system.check_metrics(metrics)

        # 如果storage可用，保存告警记录
        if self.storage is not None:
            try:
                self.storage.save_error(
                    {
                        "type": "alert",
                        "level": alert["level"],
                        "message": alert["message"],
                        "alert_data": alert,
                    }
                )
            except Exception as e:
                logger.error(f"保存告警记录失败: {e}")

    def process_anomalies(self, anomalies: list[dict[str, Any]]) -> None:
        """处理异常列表并生成告警"""
        for anomaly in anomalies:
            self.generate_alert(anomaly)

    def get_alert_history(self) -> list[dict[str, Any]]:
        """获取告警历史"""
        return list(self.alert_history)

    @staticmethod
    def _anomaly_to_metrics(anomaly: dict[str, Any]) -> dict[str, Any]:
        """将异常记录转换为性能指标格式"""
        metrics = {}
        mapping = {
            "speed": "throughput",
            "cpu_usage": "cpu_usage_percent",
            "memory_usage": "memory_usage",
            "error_rate": "error_rate",
        }
        for key, mapped_key in mapping.items():
            if key in anomaly:
                metrics[mapped_key] = anomaly[key]
        return metrics


class ReportGenerator:
    """报告生成器

    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        detector = AnomalyDetector(storage)
        generator = ReportGenerator(storage, detector)
        report = generator.generate_daily_report()

        # 独立使用（需要手动注入依赖）
        generator = ReportGenerator()
        generator.storage = custom_storage
        generator.detector = custom_detector
    """

    def __init__(
        self, storage: DataStorage | None = None, detector: AnomalyDetector | None = None
    ) -> None:
        """
        初始化报告生成器

        Args:
            storage: 数据存储实例（可选），用于读取历史数据和保存报告
            detector: 异常检测器实例（可选），用于趋势分析
        """
        # 使用依赖注入，参数变为可选
        self.storage = storage
        self.detector = detector

    def generate_daily_report(self) -> dict[str, Any]:
        """生成每日报告

        Returns:
            报告数据字典，如果依赖未初始化则返回错误信息
        """
        # 检查依赖是否已初始化
        if self.storage is None:
            error_msg = "ReportGenerator: storage未初始化，无法生成报告"
            logger.error(error_msg)
            return {"error": error_msg}

        if self.detector is None:
            logger.warning("ReportGenerator: detector未初始化，使用默认趋势分析")

        # 安全地获取数据
        try:
            history_data = self.storage.get_history_data()
            error_logs = self.storage.get_error_logs()
        except Exception as e:
            error_msg = f"ReportGenerator: 读取数据失败 - {e}"
            logger.error(error_msg)
            return {"error": error_msg}

        # 过滤今天的数据（优化：使用时间戳比较）
        # 注意：使用本地时区，确保所有timestamp都使用同一时区
        # 如果系统跨时区部署，建议使用UTC时区：
        # from datetime import timezone
        # today = datetime.now(timezone.utc).date()
        # today_start_ts = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).timestamp() # noqa: E501
        today = datetime.now().date()
        # 计算今天的开始时间戳（避免每次都调用datetime.fromtimestamp）
        today_start_ts = datetime.combine(today, datetime.min.time()).timestamp()
        today_data = [d for d in history_data if d.get("timestamp", 0) >= today_start_ts]

        if not today_data:
            return {"message": "今天暂无数据"}

        # 计算统计数据（兼容扁平字典和嵌套 performance 两种历史数据格式）
        speeds = [d.get("performance", {}).get("speed", d.get("speed", 0)) for d in today_data]
        total_checked = sum(
            d.get("performance", {}).get("total_checked", d.get("total_checked", 0)) for d in today_data
        )
        matches_found = sum(
            d.get("performance", {}).get("matches_found", d.get("matches_found", 0)) for d in today_data
        )
        cpu_usages = [
            d.get("performance", {}).get("cpu_usage", d.get("cpu_usage", 0)) for d in today_data
        ]
        memory_usages = [
            d.get("performance", {}).get("memory_usage", d.get("memory_usage", 0)) for d in today_data
        ]

        # 计算平均值
        speed_avg = statistics.mean(speeds) if speeds else 0
        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        memory_avg = statistics.mean(memory_usages) if memory_usages else 0

        # 分析趋势（安全调用）
        if self.detector is not None:
            try:
                trends = self.detector.analyze_trends(today_data)
            except Exception as e:
                logger.error(f"趋势分析失败: {e}")
                trends = {"error": f"趋势分析失败: {e}"}
        else:
            # 使用简单的默认趋势分析
            trends = self._simple_trend_analysis(today_data)

        # 生成报告
        report = {
            "date": today.isoformat(),
            "summary": {
                "total_checked": total_checked,
                "matches_found": matches_found,
                "avg_keys_per_second": speed_avg,
                "average_cpu_usage": cpu_avg,
                "average_memory_usage": memory_avg,
                "error_count": len(error_logs),
            },
            "trends": trends,
            "errors": error_logs[-10:] if error_logs else [],  # 最近10个错误
            "recommendations": self._generate_recommendations(trends, today_data),
        }

        # 保存报告（如果storage可用）
        try:
            report_file = os.path.join(self.storage.storage_dir, f"report_{today.isoformat()}.json")
            with open(report_file, "w", encoding="utf-8") as f:
                fast_dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"每日报告已生成: {report_file}")
        except Exception as e:
            logger.error(f"保存报告失败: {e}")

        return report

    def _generate_recommendations(self, trends: dict[str, Any], data: list[dict[str, Any]]) -> list[str]:
        """生成优化建议"""
        recommendations = []

        # 基于速度趋势的建议
        if "speed" in trends:
            speed_trend = trends["speed"].get("trend")
            if speed_trend == "decreasing":
                recommendations.append("检测速率呈下降趋势，建议检查系统资源使用情况")
            elif speed_trend == "increasing":
                recommendations.append("检测速率呈上升趋势，系统性能良好")

        # 基于CPU使用率的建议
        if "cpu_usage" in trends:
            cpu_avg = trends["cpu_usage"].get("average", 0)
            if cpu_avg > 80:
                recommendations.append("CPU使用率较高，建议优化代码或考虑使用GPU加速")

        # 基于内存使用的建议
        if "memory_usage" in trends:
            memory_avg = trends["memory_usage"].get("average", 0)
            if memory_avg > 512:
                recommendations.append("内存使用较高，建议检查内存泄漏或优化数据结构")

        return recommendations

    @staticmethod
    def _calculate_trend(values: list[float]) -> str:
        """计算趋势（委托给共享工具 trend_utils.calculate_trend）

        Args:
            values: 数值列表

        Returns:
            趋势字符串："increasing", "decreasing", 或 "stable"
        """
        return calculate_trend(values)

    def _simple_trend_analysis(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """简单的趋势分析（detector未初始化时的降级方案）

        自 v4.3.1: 优化为单次遍历。

        Args:
            data: 历史数据列表

        Returns:
            趋势分析结果
        """
        if len(data) < 2:
            return {"message": "数据点不足，无法分析趋势"}

        # 提取最近的100条数据
        recent_data = data[-100:]

        # v4.3.1: 单次遍历
        speeds: list[float] = []
        cpu_usages: list[float] = []
        memory_usages: list[float] = []

        for d in recent_data:
            perf = d.get("performance", {})
            if isinstance(perf, dict):
                speeds.append(perf.get("speed", 0))
                cpu_usages.append(perf.get("cpu_usage", 0))
                memory_usages.append(perf.get("memory_usage", 0))

        speed_avg = statistics.mean(speeds) if speeds else 0
        cpu_avg = statistics.mean(cpu_usages) if cpu_usages else 0
        memory_avg = statistics.mean(memory_usages) if memory_usages else 0

        return {
            "speed": {
                "average": speed_avg,
                "trend": self._calculate_trend(speeds) if speeds else "stable",
            },
            "cpu_usage": {
                "average": cpu_avg,
                "trend": self._calculate_trend(cpu_usages) if cpu_usages else "stable",
            },
            "memory_usage": {
                "average": memory_avg,
                "trend": self._calculate_trend(memory_usages) if memory_usages else "stable",
            },
        }


class MonitoringSystem:
    """监控系统主类"""

    def __init__(self, engine: Any | None = None, collection_interval: int = 5) -> None:
        """
        初始化监控系统

        Args:
            engine: 对撞引擎实例
            collection_interval: 数据采集间隔（秒）
        """
        self.engine = engine
        self.collection_interval = collection_interval

        # P0统一数据源: 创建DataLogger并委托给DataStorage
        from .data_logger import DataLogger

        self._data_logger = DataLogger(storage_dir="data_logs")
        self.storage = DataStorage(data_logger=self._data_logger)
        self.collector = DataCollector(engine)
        self.detector = AnomalyDetector(self.storage)
        self.alert_system = MonitoringAlertAdapter(self.storage)
        self.report_generator = ReportGenerator(self.storage, self.detector)

        # 集成日志监控系统
        self.log_integrator: LogMonitoringIntegrator | None = None  # type: ignore[name-defined] # noqa: F821, E501
        try:
            from .log_monitoring_integrator import get_log_monitoring_integrator

            self.log_integrator = get_log_monitoring_integrator()
            self.log_integrator.integrate_with_monitoring_system(self)
        except Exception as e:
            logger.error(f"集成日志监控系统失败: {e}")
            self.log_integrator = None

        # 注册的组件
        self.components: dict[str, Any] = {}

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # 线程等待超时（秒）
        self._thread_join_timeout = 10

        # 优化: 批量缓冲写入机制，降低I/O开销
        self._data_buffer: list = []
        self._buffer_flush_size = 100  # 累积100条后批量写入
        self._buffer_lock = threading.Lock()

        # 时间触发的缓冲刷写（每60秒强制刷写一次）
        self._last_flush_time = time.monotonic()
        self._flush_interval = 60

    def register_component(self, name: str, component: Any) -> None:
        """
        注册组件

        Args:
            name: 组件名称
            component: 组件实例
        """
        self.components[name] = component
        logger.info(f"组件 '{name}' 已注册到监控系统")

    def start(self) -> None:
        """启动监控系统"""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("监控系统已启动")

    def stop(self) -> None:
        """停止监控系统"""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._thread_join_timeout)
        self._running = False

        # 停止后台CPU采样线程
        self.collector.stop()

        # 写入剩余缓冲数据
        self._flush_buffer()
        # 确保 DataLogger 完整刷写（含性能日志缓冲和错误缓冲）
        if hasattr(self, "_data_logger") and self._data_logger is not None:
            self._data_logger.stop()
        logger.info("监控系统已停止")

    def _buffer_data_point(self, data: MonitoringData):
        """缓冲数据点，达到阈值时批量写入"""
        with self._buffer_lock:
            self._data_buffer.append(data.to_dict())
            if len(self._data_buffer) >= self._buffer_flush_size:
                self._flush_buffer_unlocked()

    def _flush_buffer(self):
        """批量写入缓冲数据（线程安全版本，供外部调用）"""
        with self._buffer_lock:
            self._flush_buffer_unlocked()

    def _flush_buffer_unlocked(self):
        """批量写入缓冲数据（内部方法，调用方必须已持有 _buffer_lock）

        自 v4.3.1: 当 DataLogger 可用时，委托给它处理持久化，消除双写竞争。
        """
        if not self._data_buffer:
            return
        buffer_copy = self._data_buffer.copy()
        self._data_buffer.clear()
        # v4.3.1: 委托给 DataLogger 以消除双写竞争
        if self._data_logger is not None:
            try:
                # 将缓冲数据追加到 DataLogger 内部缓冲区后保存
                with self._data_logger._lock:
                    self._data_logger._history_buffer.extend(buffer_copy)
                    if len(self._data_logger._history_buffer) > 1000:
                        while len(self._data_logger._history_buffer) > 1000:
                            self._data_logger._history_buffer.popleft()
                self._data_logger.save_history_data()
                logger.debug(f"缓冲区已刷新(DataLogger): 批量写入{len(buffer_copy)}条历史数据")
                return
            except Exception as e:
                logger.warning(f"DataLogger委托批量写入失败，降级到直接写入: {e}")
        # 一次性批量写入: JSONL 追加写入，与 DataLogger 保持一致 (v4.3.1)
        try:
            history = self.storage._load_history_with_recovery()
            history.extend(buffer_copy)
            if len(history) > 1000:
                history = history[-1000:]
            temp_file = self.storage.history_data_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                for record in history:
                    f.write(fast_dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(self.storage.history_data_file):
                os.replace(temp_file, self.storage.history_data_file)
            else:
                os.rename(temp_file, self.storage.history_data_file)
            logger.debug(f"缓冲区已刷新: 批量写入{len(buffer_copy)}条历史数据")
        except Exception as e:
            logger.error(f"批量写入缓冲数据失败: {e}")
            # 清理临时文件
            try:
                temp_file = self.storage.history_data_file + ".tmp"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                logger.debug("清理临时文件失败: %s", temp_file)

    def _monitoring_loop(self):
        """监控循环

        P2修复: 优化I/O操作,降低历史数据保存频率
        优化: 利用批量缓冲将历史数据批量写入，进一步减少I/O
        """
        history_save_counter = 0  # 历史数据保存计数器
        history_save_interval = 10  # 每10次采集保存一次历史数据

        while not self._stop_event.is_set():
            try:
                # 收集数据
                data = self.collector.collect_all_data()

                # 保存当前数据（每次都保存）
                self.storage.save_current_data(data)

                # 降低历史数据保存频率,减少I/O开销
                # 优化: 利用缓冲机制将数据点缓冲，达到阈值时批量写入
                history_save_counter += 1
                if history_save_counter >= history_save_interval:
                    self._buffer_data_point(data)  # 加入缓冲区
                    history_save_counter = 0

                # 检测异常
                anomalies = self.detector.detect_anomalies(data)
                if anomalies:
                    self.alert_system.process_anomalies(anomalies)

                # 每小时生成一次报告
                current_time = datetime.now()
                if current_time.minute == 0 and current_time.second < self.collection_interval:
                    self.report_generator.generate_daily_report()

            except Exception as e:
                error_info = {"type": "monitoring", "message": f"监控系统错误: {str(e)}"}
                self.storage.save_error(error_info)
                logger.error(f"监控系统错误: {e}")

            # 时间触发的缓冲刷写
            now = time.monotonic()
            if now - self._last_flush_time >= self._flush_interval:
                self._flush_buffer()
                self._last_flush_time = now

            # 等待下一次采集
            time.sleep(self.collection_interval)

    def is_running(self) -> bool:
        """检查监控系统是否运行"""
        return self._running

    def get_current_status(self) -> dict[str, Any]:
        """获取当前状态"""
        current_data = self.storage.get_current_data()
        if not current_data:
            return {"message": "暂无数据"}

        # 分析趋势
        history_data = self.storage.get_history_data()
        trends = self.detector.analyze_trends(history_data)

        # 获取告警历史
        alerts = self.alert_system.get_alert_history()

        return {
            "current_data": current_data,
            "trends": trends,
            "recent_alerts": alerts[-5:] if alerts else [],  # 最近5个告警
        }

    def generate_report(self) -> dict[str, Any]:
        """生成报告"""
        return self.report_generator.generate_daily_report()
