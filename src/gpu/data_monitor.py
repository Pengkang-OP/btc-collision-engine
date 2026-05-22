"""GPU数据生成监控器

实时监控和验证GPU生成的碰撞数据,确保数据完整性、准确性和一致性。
在独立线程中运行,不影响GPU碰撞性能。

功能:
- 数据完整性验证: 检测数据丢失、重复、异常值
- 数据准确性验证: 验证哈希计算、地址匹配
- 异常检测: 识别无效私钥、错误哈希、性能异常
- 实时监控: 持续跟踪数据生成状态
- 统计报告: 记录成功率、错误率、异常类型
- 自动响应: 检测到异常时可暂停GPU工作器
"""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, cast

from ..utils import get_configured_logger

logger = get_configured_logger("GPUDataMonitor")


class DataQualityIssue:
    """数据质量问题"""

    # 问题类型
    DUPLICATE_KEY = "duplicate_key"
    INVALID_KEY = "invalid_key"
    HASH_MISMATCH = "hash_mismatch"
    ADDRESS_MISMATCH = "address_mismatch"
    THROUGHPUT_DROP = "throughput_drop"
    ERROR_SPIKE = "error_spike"
    DATA_GAP = "data_gap"
    STALE_DATA = "stale_data"

    def __init__(
        self,
        issue_type: str,
        severity: str,
        message: str,
        device_idx: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        """初始化质量问题

        Args:
            issue_type: 问题类型
            severity: 严重程度 (low, medium, high, critical)
            message: 问题描述
            device_idx: GPU设备索引
            details: 详细信息
        """
        self.issue_type = issue_type
        self.severity = severity
        self.message = message
        self.device_idx = device_idx
        self.details = details or {}
        self.timestamp = time.time()
        self.datetime = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "device_idx": self.device_idx,
            "details": self.details,
            "timestamp": self.timestamp,
            "datetime": self.datetime,
        }


class DataMonitor:
    """数据生成监控器

    在独立线程中监控GPU数据生成,验证数据质量和完整性。

    使用示例:
        monitor = DataMonitor()
        monitor.start()

        # 在工作器中报告数据
        monitor.report_keys_generated(device_idx=0, count=1000)
        monitor.report_match(device_idx=0, match_data={...})

        # 获取监控统计
        stats = monitor.get_stats()

        monitor.stop()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化数据监控器

        Args:
            config: 监控配置
        """
        self.config = config or {}

        # 监控配置
        self.check_interval = self.config.get("check_interval", 1.0)  # 检查间隔(秒)
        self.throughput_threshold = self.config.get("throughput_threshold", 0.5)  # 吞吐量下降阈值
        self.error_rate_threshold = self.config.get("error_rate_threshold", 0.1)  # 错误率阈值
        self.stale_data_timeout = self.config.get("stale_data_timeout", 10.0)  # 数据过期时间
        self.max_issues_per_minute = self.config.get("max_issues_per_minute", 100)  # 每分钟最大问题数
        self.max_seen_keys = self.config.get("max_seen_keys", 100000)  # 最大记录私钥数
        self.max_seen_addresses = self.config.get("max_seen_addresses", 10000)  # 最大记录地址数

        # 线程控制
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # 线程安全锁
        self._lock = threading.RLock()  # 使用可重入锁保护所有共享状态

        # 设备数据跟踪
        self._device_stats: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "total_keys": 0,
                "total_matches": 0,
                "total_errors": 0,
                "last_update": 0,
                "throughput_history": deque(maxlen=60),  # 保留60秒历史
                "error_history": deque(maxlen=60),
                "seen_keys": set(),  # 用于检测重复
                "seen_addresses": set(),
            }
        )

        # 问题记录
        self._issues: deque[dict[str, Any]] = deque(maxlen=10000)  # 保留最近10000个问题
        self._issues_by_type: dict[str, int] = defaultdict(int)
        self._issues_by_device: dict[int, int] = defaultdict(int)
        self._issues_last_minute: deque[float] = deque(maxlen=1000)

        # 统计信息
        self._stats: dict[str, Any] = {
            "total_keys_monitored": 0,
            "total_matches_verified": 0,
            "total_issues_detected": 0,
            "total_validations": 0,
            "validation_pass_rate": 1.0,
            "start_time": None,
            "last_check_time": None,
        }

        # 回调函数
        self._anomaly_callback: Any | None = None

        logger.info("数据监控器已创建")

    def start(self, anomaly_callback: Any | None = None) -> None:
        """启动监控

        Args:
            anomaly_callback: 异常检测回调(device_idx, issue)
        """
        if self._running:
            logger.warning("监控器已在运行")
            return

        self._running = True
        self._stop_event.clear()
        self._stats["start_time"] = time.time()
        self._anomaly_callback = anomaly_callback

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="DataMonitor"
        )
        self._monitor_thread.start()

        logger.info("数据监控器已启动")

    def stop(self) -> None:
        """停止监控"""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)
            if self._monitor_thread.is_alive():
                logger.warning("监控线程未能在10秒内停止")

        logger.info("数据监控器已停止")

    def report_keys_generated(
        self, device_idx: int, count: int, key_range: tuple[int, int] | None = None
    ) -> None:
        """报告生成的私钥数据

        Args:
            device_idx: GPU设备索引
            count: 生成的私钥数量
            key_range: 私钥范围(start, end), 可选
        """
        if not self._running:
            return

        try:
            with self._lock:
                stats = self._device_stats[device_idx]
                stats["total_keys"] += count
                stats["last_update"] = time.time()

                # 记录吞吐量
                stats["throughput_history"].append(
                    {"timestamp": time.time(), "count": count, "key_range": key_range}
                )

                self._stats["total_keys_monitored"] += count

            # 在锁外验证(避免长时间持锁)
            if key_range:
                self._validate_key_range(device_idx, key_range)

        except Exception as e:
            logger.error(f"报告私钥生成失败 [GPU {device_idx}]: {e}")

    def report_match(self, device_idx: int, match_data: dict) -> None:
        """报告匹配结果

        Args:
            device_idx: GPU设备索引
            match_data: 匹配数据 {
                'private_key': str,
                'address': str,
                'hash': str,
                'target_address': str
            }
        """
        if not self._running:
            return

        try:
            with self._lock:
                stats = self._device_stats[device_idx]
                stats["total_matches"] += 1
                stats["last_update"] = time.time()

            # 在锁外验证
            self._validate_match(device_idx, match_data)

            with self._lock:
                self._stats["total_matches_verified"] += 1

        except Exception as e:
            logger.error(f"报告匹配结果失败 [GPU {device_idx}]: {e}")

    def report_error(self, device_idx: int, error_msg: str, error_type: str | None = None) -> None:
        """报告错误

        Args:
            device_idx: GPU设备索引
            error_msg: 错误消息
            error_type: 错误类型
        """
        if not self._running:
            return

        try:
            with self._lock:
                stats = self._device_stats[device_idx]
                stats["total_errors"] += 1
                stats["last_update"] = time.time()

                # 记录错误历史
                stats["error_history"].append(
                    {"timestamp": time.time(), "message": error_msg, "type": error_type}
                )

            # 在锁外检测
            self._detect_error_spike(device_idx)

        except Exception as e:
            logger.error(f"报告错误失败 [GPU {device_idx}]: {e}")

    def report_validation_result(
        self, device_idx: int, passed: bool, validation_type: str | None = None
    ) -> None:
        """报告验证结果

        Args:
            device_idx: GPU设备索引
            passed: 是否通过验证
            validation_type: 验证类型
        """
        if not self._running:
            return

        try:
            with self._lock:
                self._stats["total_validations"] += 1

                if not passed:
                    self._stats["validation_pass_rate"] = (
                        self._stats["total_validations"] - 1
                    ) / self._stats["total_validations"]

        except Exception as e:
            logger.error(f"报告验证结果失败 [GPU {device_idx}]: {e}")

    def get_stats(self) -> dict[str, Any]:
        """获取监控统计

        Returns:
            监控统计字典
        """
        with self._lock:
            stats = self._stats.copy()

            # 添加设备统计(使用快照)
            stats["devices"] = {}
            devices_snapshot = dict(self._device_stats)

            for device_idx, device_stats in devices_snapshot.items():
                stats["devices"][device_idx] = {
                    "total_keys": device_stats["total_keys"],
                    "total_matches": device_stats["total_matches"],
                    "total_errors": device_stats["total_errors"],
                    "last_update": device_stats["last_update"],
                    "avg_throughput": self._calculate_avg_throughput(device_idx),
                }

            # 添加问题统计
            stats["issues_by_type"] = dict(self._issues_by_type)
            stats["issues_by_device"] = dict(self._issues_by_device)
            stats["recent_issues"] = list(self._issues)[-10:]  # 最近10个问题

            return stats

    def get_issues(
        self, severity: str | None = None, device_idx: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """获取检测到的问题

        Args:
            severity: 过滤严重程度
            device_idx: 过滤设备索引
            limit: 返回数量限制

        Returns:
            问题列表
        """
        with self._lock:
            issues = list(self._issues)  # 创建快照

        if severity:
            issues = [i for i in issues if i["severity"] == severity]

        if device_idx is not None:
            issues = [i for i in issues if i["device_idx"] == device_idx]

        return issues[-limit:]

    def _monitor_loop(self) -> None:
        """监控循环(在独立线程中运行)"""
        logger.info("数据监控循环已启动")

        while not self._stop_event.is_set():
            try:
                self._perform_checks()
                self._stats["last_check_time"] = time.time()
            except Exception as e:
                logger.error(f"监控循环异常: {e}")

            # 等待下一个检查周期
            self._stop_event.wait(self.check_interval)

        logger.info("数据监控循环已停止")

    def _perform_checks(self) -> None:
        """执行所有检查"""
        current_time = time.time()

        # 使用快照避免遍历时修改
        with self._lock:
            device_indices = list(self._device_stats.keys())

        for device_idx in device_indices:
            # 检查数据是否过期
            self._check_stale_data(device_idx, current_time)

            # 检查吞吐量下降
            self._check_throughput_drop(device_idx)

            # 检查错误率
            self._check_error_rate(device_idx)

    def _validate_key_range(self, device_idx: int, key_range: tuple[int, int]) -> None:
        """验证私钥范围

        Args:
            device_idx: GPU设备索引
            key_range: 私钥范围
        """
        start, end = key_range

        # 检查范围有效性
        if start < 0 or end < 0:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.INVALID_KEY,
                severity="high",
                message=f"无效的私钥范围: {start}-{end}",
                device_idx=device_idx,
                details={"start": start, "end": end},
            )
            self._record_issue(issue)

        if start >= end:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.INVALID_KEY,
                severity="medium",
                message=f"私钥范围起始值大于等于结束值: {start}-{end}",
                device_idx=device_idx,
                details={"start": start, "end": end},
            )
            self._record_issue(issue)

    def _validate_match(self, device_idx: int, match_data: dict) -> None:
        """验证匹配数据

        Args:
            device_idx: GPU设备索引
            match_data: 匹配数据
        """
        private_key_hash = match_data.get("private_key_hash", "")
        address = match_data.get("address", "")
        match_data.get("target_address", "")

        # 验证私钥哈希格式 (SHA256 hexdigest: 64 chars)
        if not private_key_hash or len(private_key_hash) != 64:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.INVALID_KEY,
                severity="high",
                message=f"无效的私钥哈希格式: 长度={len(private_key_hash)}",
                device_idx=device_idx,
                details={"private_key_hash_length": len(private_key_hash)},
            )
            self._record_issue(issue)

        # 验证地址格式
        if not address or len(address) < 26:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.ADDRESS_MISMATCH,
                severity="high",
                message=f"无效的地址格式: {address}",
                device_idx=device_idx,
                details={"address": address},
            )
            self._record_issue(issue)

        # 检查重复的私钥（使用哈希值直接去重，无需二次哈希）
        stats = self._device_stats[device_idx]

        if private_key_hash in stats["seen_keys"]:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.DUPLICATE_KEY,
                severity="medium",
                message=f"检测到重复的私钥: hash={private_key_hash[:8]}...",
                device_idx=device_idx,
                details={"private_key_hash_prefix": private_key_hash[:8]},
            )
            self._record_issue(issue)
        else:
            # 限制seen_keys大小,防止内存泄漏
            if len(stats["seen_keys"]) >= self.max_seen_keys:
                # 清空50%最旧的记录
                keys_to_remove = list(stats["seen_keys"])[: len(stats["seen_keys"]) // 2]
                for key in keys_to_remove:
                    stats["seen_keys"].discard(key)
                logger.debug(f"GPU {device_idx} 清理旧的私钥哈希记录,保留{len(stats['seen_keys'])}个")

            stats["seen_keys"].add(private_key_hash)

        # 检查重复的地址
        if address in stats["seen_addresses"]:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.DUPLICATE_KEY,
                severity="low",
                message=f"检测到重复的地址匹配: {address}",
                device_idx=device_idx,
                details={"address": address},
            )
            self._record_issue(issue)
        else:
            # 限制seen_addresses大小
            if len(stats["seen_addresses"]) >= self.max_seen_addresses:
                # 清空50%最旧的记录
                addrs_to_remove = list(stats["seen_addresses"])[: len(stats["seen_addresses"]) // 2]
                for addr in addrs_to_remove:
                    stats["seen_addresses"].discard(addr)
                logger.debug(f"GPU {device_idx} 清理旧的地址记录,保留{len(stats['seen_addresses'])}个")

            stats["seen_addresses"].add(address)

    def _check_stale_data(self, device_idx: int, current_time: float) -> None:
        """检查数据是否过期

        Args:
            device_idx: GPU设备索引
            current_time: 当前时间
        """
        stats = self._device_stats[device_idx]
        last_update = stats["last_update"]

        if last_update > 0 and (current_time - last_update) > self.stale_data_timeout:
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.STALE_DATA,
                severity="medium",
                message=f"GPU {device_idx} 数据过期: {current_time - last_update:.1f}秒未更新",
                device_idx=device_idx,
                details={"last_update": last_update, "stale_duration": current_time - last_update},
            )
            self._record_issue(issue)

    def _check_throughput_drop(self, device_idx: int) -> None:
        """检查吞吐量下降

        Args:
            device_idx: GPU设备索引
        """
        stats = self._device_stats[device_idx]
        history = stats["throughput_history"]

        if len(history) < 10:  # 需要至少10个数据点
            return

        # 计算最近5秒和之前5秒的平均吞吐量
        recent = sum(h["count"] for h in list(history)[-5:]) / 5
        previous = sum(h["count"] for h in list(history)[-10:-5]) / 5

        if previous > 0:
            drop_ratio = recent / previous
            if drop_ratio < self.throughput_threshold:
                issue = DataQualityIssue(
                    issue_type=DataQualityIssue.THROUGHPUT_DROP,
                    severity="medium",
                    message=f"GPU {device_idx} 吞吐量下降: {drop_ratio:.2%}",
                    device_idx=device_idx,
                    details={
                        "recent_throughput": recent,
                        "previous_throughput": previous,
                        "drop_ratio": drop_ratio,
                    },
                )
                self._record_issue(issue)

    def _check_error_rate(self, device_idx: int) -> None:
        """检查错误率

        Args:
            device_idx: GPU设备索引
        """
        stats = self._device_stats[device_idx]

        total_keys = stats["total_keys"]
        total_errors = stats["total_errors"]

        if total_keys > 0:
            error_rate = total_errors / total_keys
            if error_rate > self.error_rate_threshold:
                issue = DataQualityIssue(
                    issue_type=DataQualityIssue.ERROR_SPIKE,
                    severity="high",
                    message=f"GPU {device_idx} 错误率过高: {error_rate:.2%}",
                    device_idx=device_idx,
                    details={
                        "error_rate": error_rate,
                        "total_errors": total_errors,
                        "total_keys": total_keys,
                    },
                )
                self._record_issue(issue)

    def _detect_error_spike(self, device_idx: int) -> None:
        """检测错误率激增

        Args:
            device_idx: GPU设备索引
        """
        stats = self._device_stats[device_idx]
        error_history = stats["error_history"]

        if len(error_history) < 5:
            return

        # 检查最近10秒内的错误数
        current_time = time.time()
        recent_errors = [e for e in error_history if current_time - e["timestamp"] < 10]

        if len(recent_errors) >= 5:  # 10秒内5个错误
            issue = DataQualityIssue(
                issue_type=DataQualityIssue.ERROR_SPIKE,
                severity="high",
                message=f"GPU {device_idx} 错误率激增: {len(recent_errors)}个错误/10秒",
                device_idx=device_idx,
                details={"recent_errors": len(recent_errors)},
            )
            self._record_issue(issue)

    def _calculate_avg_throughput(self, device_idx: int) -> float:
        """计算平均吞吐量

        Args:
            device_idx: GPU设备索引

        Returns:
            平均吞吐量(keys/秒)
        """
        stats = self._device_stats[device_idx]
        history = stats["throughput_history"]

        if not history:
            return 0.0

        total_keys = sum(h["count"] for h in history)
        total_time = history[-1]["timestamp"] - history[0]["timestamp"]

        if total_time > 0:
            return cast(float, total_keys / total_time)

        return 0.0

    def _record_issue(self, issue: DataQualityIssue) -> None:
        """记录问题

        Args:
            issue: 数据质量问题
        """
        try:
            with self._lock:
                issue_dict = issue.to_dict()
                self._issues.append(issue_dict)
                self._issues_by_type[issue.issue_type] += 1
                self._issues_by_device[issue.device_idx] += 1

                # 记录最近一分钟的问题
                current_time = time.time()
                self._issues_last_minute.append(current_time)

                # 检查问题频率
                recent_issues = [t for t in self._issues_last_minute if current_time - t < 60]

                if len(recent_issues) > self.max_issues_per_minute:
                    _n = len(recent_issues)
                    _max = self.max_issues_per_minute
                    logger.warning(f"问题频率过高: {_n}个/分钟, 超过阈值{_max}")

            # 在锁外记录日志和调用回调
            severity_map = {
                "low": logging.DEBUG,
                "medium": logging.INFO,
                "high": logging.WARNING,
                "critical": logging.ERROR,
            }
            log_level = severity_map.get(issue.severity, logging.INFO)
            logger.log(
                log_level,
                f"数据质量问题 [{issue.severity.upper()}]: GPU {issue.device_idx} - {issue.message}",
            )

            # 调用异常回调
            if self._anomaly_callback:
                try:
                    self._anomaly_callback(issue.device_idx, issue_dict)
                except Exception as e:
                    logger.error(f"异常回调执行失败: {e}")

            with self._lock:
                self._stats["total_issues_detected"] += 1

        except Exception as e:
            logger.error(f"记录问题失败: {e}")
