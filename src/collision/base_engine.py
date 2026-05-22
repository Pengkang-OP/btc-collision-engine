"""碰撞引擎抽象基类

定义CPU和GPU碰撞引擎的统一接口。

v4.2.2: 新增 _safe_invoke_match_callback 共享方法，消除 CPU/GPU 引擎中的重复代码。
v5.0.0: 移除 SIGALRM 信号超时方案（线程不安全），统一使用线程超时。
"""

import hashlib
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any

from .collision_stats import CollisionStats

logger = logging.getLogger(__name__)


class BaseCollisionEngine(ABC):
    """碰撞引擎抽象基类

    所有碰撞引擎(CPU/GPU)必须实现此接口。

    v4.2.2 新增共享方法:
        _safe_invoke_match_callback: 安全调用匹配回调（超时控制+异常隔离+审计日志）
    """

    # v4.2.2: 子类可覆盖的默认值
    _match_callback_timeout: float = 5.0
    _match_callback_audit_enabled: bool = True

    def __init__(self, targets: set[str], **kwargs) -> None:  # noqa: ARG002
        """
        初始化碰撞引擎

        参数:
            targets: 目标地址集合
            **kwargs: 引擎特定参数

        注意:
            - 子类必须在其 __init__ 中设置 self.on_match, self.on_progress, self.on_complete
            - v4.2.2: 移除 @abstractmethod 反模式，改为定义具体 __init__ 并显式声明默认回调属性
        """
        self.on_match: Any = None
        self.on_progress: Any = None
        self.on_complete: Any = None

    @abstractmethod
    def start(self, mode: str = "random", resume: bool = False, **kwargs) -> None:
        """
        启动碰撞引擎

        参数:
            mode: 运行模式 ("random", "range", "brute_force")
            resume: 是否从断点恢复
            **kwargs: 模式特定参数
                     - range模式: start, end
                     - brute_force模式: start
        """

    @abstractmethod
    def stop(self, timeout: float | None = None) -> None:
        """
        停止碰撞引擎

        参数:
            timeout: 等待停止的超时时间(秒)
        """

    @abstractmethod
    def is_running(self) -> bool:
        """
        检查引擎是否正在运行

        返回:
            True表示引擎正在运行
        """

    @abstractmethod
    def get_stats(self) -> CollisionStats:
        """
        获取碰撞统计信息

        返回:
            CollisionStats对象
        """

    def get_device_info(self) -> dict[str, Any]:
        """
        获取设备信息

        返回:
            设备信息字典
        """
        return {}

    def get_supported_modes(self) -> list:
        """
        获取支持的运行模式

        返回:
            支持的模式列表
        """
        return ["random", "range", "brute_force"]

    # ========== v4.2.2: 共享匹配回调方法 ==========

    def _safe_invoke_match_callback(self, private_key: bytes, address: str, wif: str) -> bool:
        """安全调用匹配回调函数（CPU/GPU 引擎共享，跨平台）

        功能:
        - 超时控制（防止回调函数卡死）
        - 异常隔离（回调异常不影响引擎运行）
        - 审计日志（记录回调执行情况）
        - v5.0.0: 统一使用线程超时（移除线程不安全的 SIGALRM 方案）

        参数:
            private_key: 私钥字节（32字节）
            address: 比特币地址
            wif: WIF格式私钥

        返回:
            bool: 回调是否成功执行
        """
        # v4.2.2 H1修复: 使用 getattr 防护，避免子类未设置 on_match 时 AttributeError
        on_match = getattr(self, "on_match", None)
        if not on_match:
            return True

        audit_enabled = getattr(self, "_match_callback_audit_enabled", True)

        if audit_enabled:
            key_hash = hashlib.sha256(private_key).hexdigest()[:16]
            logger.debug(f"调用匹配回调: address={address}, key_hash={key_hash}")

        try:
            return self._invoke_match_callback_with_timeout(on_match, private_key, address, wif)
        except Exception as e:
            logger.error(f"匹配回调调用失败: {e}")
            return False

    def _invoke_match_callback_with_timeout(
        self,
        on_match,
        private_key: bytes,
        address: str,
        wif: str,
    ) -> bool:
        """使用线程超时+取消事件调用匹配回调（跨平台，替代 SIGALRM）

        v4.2.2 H7修复: 增加 threading.Event 取消机制，
        join 超时后通知子线程退出，避免资源泄漏。
        v5.0.0: 替代 SIGALRM 方案（线程不安全），统一跨平台行为。
        """
        result: list[Any | None] = [None]
        exception: list[BaseException | None] = [None]
        cancel_event = threading.Event()

        def target() -> None:
            if cancel_event.is_set():
                return
            try:
                result[0] = on_match(private_key, address, wif)
            except Exception as e:
                exception[0] = e

        callback_thread = threading.Thread(target=target, daemon=True)
        callback_thread.start()
        callback_thread.join(timeout=self._match_callback_timeout)

        if callback_thread.is_alive():
            cancel_event.set()
            logger.critical(f"匹配回调执行超时 ({self._match_callback_timeout}秒)，已通知取消")
            return False

        if exception[0]:
            logger.error(f"匹配回调异常: {exception[0]}")
            return False

        return True
