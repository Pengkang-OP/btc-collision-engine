"""对撞统计数据管理"""

import hashlib
import threading
import time


class CollisionStats:
    """对撞统计数据

    安全说明:
    - 匹配的私钥信息不会存储在统计对象中
    - 仅保存地址和时间戳用于统计展示
    - 私钥通过 on_match 回调直接传递给调用者，不在内存中持久化
    """

    def __init__(self) -> None:
        self.total_checked: int = 0  # 已检测总数
        self.speed: float = 0.0  # 每秒检测速率
        self.elapsed: float = 0.0  # 已运行时间(秒)
        self.start_time: float = 0.0  # 开始时间戳
        self.matches: list[dict] = []  # 匹配结果列表（仅包含地址，不包含私钥）
        self._lock = threading.Lock()  # 线程锁
        self._match_count: int = 0  # 匹配计数（用于统计，不存储私钥）
        # ETA 相关
        self.total_range: int = 0  # 用于范围扫描的总范围（0表示隐藏ETA）
        self.eta_seconds: float = -1.0  # 预计剩余秒数（-1表示无法估算）
        # 异常统计指标
        self.gpu_errors: int = 0  # GPU计算错误计数
        self.worker_errors: int = 0  # 工作线程错误计数
        self.wif_encode_errors: int = 0  # WIF编码错误计数
        self.resource_errors: int = 0  # 资源不足错误计数
        # 每个match: {"address": str, "timestamp": float, "match_index": int}

    def update(self, checked_count: int, total_range: int = 0) -> None:
        """更新统计数据（赋值语义：设置累计值）

        设计说明:
        - 赋值语义是有意为之。所有调用者传递的是累计检查数量
          （如 engine.stats.update(safe_count)、stats.update(batch_count)），
          而非增量。这避免了调用者需要维护局部计数器。
        - 如需增量累加，请使用 increment() 方法。

        参数:
            checked_count: 已检查的累计数量
            total_range: 总范围（仅 range 模式传入，用于计算 ETA）
        """
        with self._lock:
            self.total_checked = checked_count
            self._refresh_elapsed_and_speed()
            if total_range > 0:
                self.total_range = total_range
            self._calc_eta()

    def increment(self, delta: int, total_range: int = 0) -> None:
        """增量更新统计数据（累加语义）

        用于调用者只知道增量（而非累计值）的场景。
        线程安全：与 update() 共享同一把锁。

        参数:
            delta: 本次新增的检查数量（必须 >= 0）
            total_range: 总范围（仅 range 模式传入，用于计算 ETA）
        """
        if delta < 0:
            raise ValueError(f"delta must be non-negative, got {delta}")
        with self._lock:
            self.total_checked += delta
            self._refresh_elapsed_and_speed()
            if total_range > 0:
                self.total_range = total_range
            self._calc_eta()

    def _refresh_elapsed_and_speed(self) -> None:
        """刷新运行时间和速度（调用者需持有 _lock）"""
        self.elapsed = time.time() - self.start_time
        self.speed = self.total_checked / self.elapsed if self.elapsed > 0 else 0

    def _calc_eta(self) -> None:
        """计算预计剩余时间（调用者需持有 _lock）"""
        if self.total_range > 0 and self.speed > 0:
            remaining = self.total_range - self.total_checked
            self.eta_seconds = remaining / self.speed if remaining > 0 else 0.0
        else:
            self.eta_seconds = -1.0

    def add_match(self, private_key: bytes, address: str) -> None:
        """记录一个匹配结果（不存储私钥）

        安全说明:
        - 私钥信息不会存储在统计对象中
        - 仅记录地址和时间戳用于展示
        - 私钥通过回调函数直接传递给调用者处理

        参数:
            private_key: 匹配的私钥（仅用于计算哈希，不存储）
            address: 匹配的地址
        """
        with self._lock:
            # 计算私钥哈希用于验证（不存储实际私钥）
            private_key_hash = hashlib.sha256(private_key).hexdigest()[:16]

            self._match_count += 1
            match_info = {
                "address": address,
                "timestamp": time.time(),
                "match_index": self._match_count,
                "private_key_hash": private_key_hash,  # 仅保存哈希值用于验证
            }
            self.matches.append(match_info)

    def snapshot(self) -> "CollisionStats":
        """返回当前统计的线程安全快照（用于回调和UI显示）

        注意:
        - 快照包含所有统计属性，确保UI和监控数据完整
        - Q4修复: matches列表使用浅拷贝列表推导式替代深拷贝，
          因为字典中的值都是基本类型（字符串、数字、时间戳），
          浅拷贝足够安全且性能提升约10-50倍
        - _match_count确保快照中match_index的连续性
        """
        with self._lock:
            snap = CollisionStats()

            # 基础统计
            snap.total_checked = self.total_checked
            snap.speed = self.speed
            snap.elapsed = self.elapsed
            snap.start_time = self.start_time
            # Q4修复: 使用列表推导式进行浅拷贝，性能优于 deepcopy
            snap.matches = [dict(m) for m in self.matches]
            snap._match_count = self._match_count  # 复制匹配计数，确保索引连续

            # ETA相关
            snap.total_range = self.total_range
            snap.eta_seconds = self.eta_seconds

            # 异常统计指标（确保UI和监控能获取完整数据）
            snap.gpu_errors = self.gpu_errors
            snap.worker_errors = self.worker_errors
            snap.wif_encode_errors = self.wif_encode_errors
            snap.resource_errors = self.resource_errors

            # 其他属性
            if hasattr(self, "_progress_percent"):
                snap._progress_percent = self._progress_percent

            return snap

    def reset(self) -> None:
        """线程安全地重置所有统计数据

        使用场景:引擎重新启动、测试初始化、监控系统周期性清除。
        注意: 会清空 matches 列表，请确保已保存重要匹配结果。
        """
        with self._lock:
            self.total_checked = 0
            self.speed = 0.0
            self.elapsed = 0.0
            self.start_time = time.time()  # 重置开始时间为当前时间
            self.matches = []
            self._match_count = 0
            self.total_range = 0
            self.eta_seconds = -1.0
            self.gpu_errors = 0
            self.worker_errors = 0
            self.wif_encode_errors = 0
            self.resource_errors = 0
            if hasattr(self, "_progress_percent"):
                self._progress_percent = 0.0

    def get_total_checked(self) -> int:
        """线程安全地获取已检查数量"""
        with self._lock:
            return self.total_checked

    def get_elapsed(self) -> float:
        """线程安全地获取已运行时间（秒）"""
        with self._lock:
            return self.elapsed

    def format_elapsed(self) -> str:
        """格式化已运行时间为 HH:MM:SS"""
        with self._lock:
            elapsed = self.elapsed
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def format_speed(self) -> str:
        """格式化速度（带单位）"""
        with self._lock:
            speed = self.speed
        if speed >= 1_000_000:
            return f"{speed / 1_000_000:.2f}M/s"
        elif speed >= 1_000:
            return f"{speed / 1_000:.2f}K/s"
        else:
            return f"{speed:.2f}/s"

    def get_speed(self) -> float:
        """
        获取当前碰撞速度（次/秒）

        Returns:
            float: 碰撞速度
        """
        with self._lock:
            return self.speed

    def record_gpu_error(self, is_resource_error: bool = False) -> None:
        """记录GPU错误

        Args:
            is_resource_error: 是否为资源不足错误
        """
        with self._lock:
            self.gpu_errors += 1
            if is_resource_error:
                self.resource_errors += 1

    def record_worker_error(self) -> None:
        """记录工作线程错误"""
        with self._lock:
            self.worker_errors += 1

    def record_wif_encode_error(self) -> None:
        """记录WIF编码错误"""
        with self._lock:
            self.wif_encode_errors += 1

    def get_error_rates(self) -> dict[str, float]:
        """获取各类错误率（错误数/总检查数）

        Returns:
            Dict[str, float]: 各类错误率字典
            - total_error_rate: 总错误率（GPU+Worker独立错误数）
            - gpu_error_rate: GPU错误率
            - worker_error_rate: 工作线程错误率
            - wif_encode_error_rate: WIF编码错误率
            - resource_error_rate: 资源不足错误率
        """
        with self._lock:
            if self.total_checked == 0:
                return {
                    "total_error_rate": 0.0,
                    "gpu_error_rate": 0.0,
                    "worker_error_rate": 0.0,
                    "wif_encode_error_rate": 0.0,
                    "resource_error_rate": 0.0,
                }

            return {
                "total_error_rate": (self.gpu_errors + self.worker_errors) / self.total_checked,
                "gpu_error_rate": self.gpu_errors / self.total_checked,
                "worker_error_rate": self.worker_errors / self.total_checked,
                "wif_encode_error_rate": self.wif_encode_errors / self.total_checked,
                "resource_error_rate": self.resource_errors / self.total_checked,
            }

    def is_healthy(self, error_rate_threshold: float = 0.01) -> bool:
        """检查系统健康状态

        Args:
            error_rate_threshold: 错误率阈值（默认1%）

        Returns:
            bool: 是否健康（所有错误率都低于阈值）
        """
        rates = self.get_error_rates()
        # 检查所有错误率（包括总错误率）
        return all(rate < error_rate_threshold for rate in rates.values())

    def error_summary(self) -> str:
        """生成错误统计摘要（用于日志和监控）

        总计计算说明:
        - 总计 = GPU错误 + Worker错误（独立错误事件数）
        - Resource错误是GPU错误的子集，不重复计数
        - WIF编码错误可能交叉于GPU/Worker，单独列出以便追踪

        Returns:
            str: 格式化的错误统计摘要
        """
        with self._lock:
            # 计算独立错误总数（GPU和Worker是顶级分类，Resource是子集）
            total_independent = self.gpu_errors + self.worker_errors
            return (
                f"错误统计: GPU={self.gpu_errors}, "
                f"Worker={self.worker_errors}, "
                f"WIF={self.wif_encode_errors}, "
                f"Resource={self.resource_errors}, "
                f"总计={total_independent}"
            )
