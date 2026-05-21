"""P2-4: 配置热重载 — 文件监听器

支持两种后端（自动选择）:
1. watchdog (优先): 事件驱动，响应快
2. Polling (降级): 无外部依赖，定期检查 mtime
"""

import os
import threading
import time
from collections.abc import Callable

from ..utils import get_configured_logger

# 日志系统由CLI/main.py入口统一初始化
logger = get_configured_logger("ConfigWatcher")

# ── watchdog 可用性检测 ──────────────────────────────────────────────
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class _WatchdogHandler(FileSystemEventHandler):
        """watchdog 文件变更处理器"""

        def __init__(self, callback: Callable[[], None], watched_path: str):
            super().__init__()
            self._callback = callback
            self._watched_path = os.path.abspath(watched_path)

        def on_modified(self, event):
            if event.is_directory:
                return
            if os.path.abspath(event.src_path) == self._watched_path:
                logger.debug("watchdog 检测到配置文件变更: %s", event.src_path)
                self._callback()

    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    logger.debug("watchdog 库未安装，将使用轮询模式监听配置文件")


class ConfigWatcher:
    """配置文件监听器 — P2-4 配置热重载

    自动选择最佳后端:
    - watchdog (事件驱动, 响应 <1s)
    - polling  (定期检查 mtime, 默认 2s 间隔)

    使用方式:
        watcher = ConfigWatcher("/path/to/config.json", on_reload)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(
        self,
        config_path: str,
        on_reload: Callable[[], None],
        debounce_seconds: float = 2.0,
        poll_interval: float = 2.0,
    ) -> None:
        """初始化配置监听器

        参数:
            config_path: 要监听的配置文件绝对路径
            on_reload: 配置变更回调（在后台线程中调用）
            debounce_seconds: 防抖间隔，短时间内多次变更仅触发一次
            poll_interval: 轮询模式下的检查间隔（秒）
        """
        if not os.path.isabs(config_path):
            raise ValueError(f"config_path 必须是绝对路径: {config_path}")

        self._config_path = os.path.abspath(config_path)
        self._on_reload = on_reload
        self._debounce_seconds = debounce_seconds
        self._poll_interval = poll_interval

        # 状态管理
        # W8修复: 使用 threading.Event 替代 bool，消除 _poll_loop 与 stop() 之间的数据竞争
        # Event.set() = 停止请求, Event.clear() = 运行中, 初始为停止状态
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._lock = threading.Lock()
        self._observer: Observer | None = None
        self._poll_thread: threading.Thread | None = None
        self._last_mtime: float | None = None  # None表示文件不存在
        self._last_reload_time: float = 0.0

        # 记录初始 mtime，避免启动时误触发
        try:
            self._last_mtime = os.path.getmtime(self._config_path)
        except OSError:
            # 文件不存在，设置为None
            self._last_mtime = None

    # ── 公共接口 ─────────────────────────────────────────────────

    def start(self) -> bool:
        """启动文件监听

        返回:
            True 如果启动成功，False 如果已在运行中
        """
        with self._lock:
            if not self._stop_event.is_set():
                logger.warning("ConfigWatcher 已在运行中")
                return False
            self._stop_event.clear()

        started = self._start_watchdog() if HAS_WATCHDOG else self._start_polling()

        if started and self._stop_event.is_set():
            logger.warning("ConfigWatcher 在启动期间收到停止信号，回退")
            self.stop()
            return False

        return started

    def stop(self) -> None:
        """停止文件监听"""
        with self._lock:
            if self._stop_event.is_set():
                return
            self._stop_event.set()

        # 停止 watchdog observer
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5.0)
            except Exception as e:
                logger.debug("停止 watchdog observer 时出错: %s", e)
            self._observer = None

        # 等待轮询线程退出
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=self._poll_interval + 2.0)
            self._poll_thread = None

        logger.info("ConfigWatcher 已停止 (路径: %s)", self._config_path)

    @property
    def backend(self) -> str:
        """返回当前使用的后端名称"""
        return "watchdog" if HAS_WATCHDOG else "polling"

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return not self._stop_event.is_set()

    # ── watchdog 后端 ─────────────────────────────────────────────

    def _start_watchdog(self) -> bool:
        """启动 watchdog 监听"""
        try:
            watch_dir = os.path.dirname(self._config_path)
            handler = _WatchdogHandler(self._on_file_changed, self._config_path)
            self._observer = Observer()
            self._observer.schedule(handler, path=watch_dir, recursive=False)
            self._observer.start()
            logger.info(
                "ConfigWatcher 已启动 (watchdog, 路径: %s, 防抖: %.1fs)",
                self._config_path,
                self._debounce_seconds,
            )
            return True
        except Exception as e:
            logger.error("启动 watchdog 监听失败: %s，降级为轮询模式", e)
            self._observer = None
            return self._start_polling()

    # ── Polling 后端 ──────────────────────────────────────────────

    def _start_polling(self) -> bool:
        """启动轮询监听"""
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="ConfigWatcher-Poll",
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(
            "ConfigWatcher 已启动 (polling, 路径: %s, 间隔: %.1fs, 防抖: %.1fs)",
            self._config_path,
            self._poll_interval,
            self._debounce_seconds,
        )
        return True

    def _poll_loop(self) -> None:
        """轮询主循环"""
        while not self._stop_event.is_set():
            try:
                current_mtime = os.path.getmtime(self._config_path)
                # 只有当_last_mtime不为None且文件变更时才触发回调
                # None表示启动时文件不存在，新创建时不触发
                if self._last_mtime is not None and current_mtime > self._last_mtime:
                    self._last_mtime = current_mtime
                    self._on_file_changed()
                elif self._last_mtime is None:
                    # 文件从不存在变为存在，记录mtime但不触发回调
                    self._last_mtime = current_mtime
            except OSError:
                # 文件可能被临时删除，设置为None
                self._last_mtime = None

            # 分段 sleep，以便快速响应 stop()
            for _ in range(int(self._poll_interval / 0.2)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.2)

    # ── 变更处理 (防抖) ──────────────────────────────────────────

    def _on_file_changed(self) -> None:
        """文件变更回调入口 (防抖)"""
        now = time.time()
        if now - self._last_reload_time < self._debounce_seconds:
            logger.debug("配置变更被防抖忽略 (距上次 %.2fs)", now - self._last_reload_time)
            return
        logger.info("检测到配置文件变更，触发重载: %s", self._config_path)
        try:
            self._on_reload()
            # S11修复: 回调成功后才更新防抖计时器，避免长耗时回调完成后立即触发下一次重载
            self._last_reload_time = time.time()
        except Exception as e:
            logger.error("配置重载回调执行失败: %s", e)

    def __del__(self) -> None:
        """析构时自动停止监听

        W14修复: 改进析构逻辑，避免在析构期间因锁状态不一致导致的死锁或异常
        - 只清理核心资源，不调用可能产生竞态的 stop() 方法
        - 使用超时避免在析构期间永久阻塞
        """
        try:
            # 检查对象是否已完全初始化
            if not hasattr(self, "_stop_event") or not hasattr(self, "_lock"):
                return

            # 设置停止事件（不获取锁，因为锁可能已被其他线程持有）
            # 使用 is_set() 检查当前状态，避免重复操作
            if not self._stop_event.is_set():
                self._stop_event.set()

            # 尝试停止 observer（如果存在）
            if hasattr(self, "_observer") and self._observer is not None:
                try:
                    self._observer.stop()
                    # 使用小超时，避免析构期间永久阻塞
                    self._observer.join(timeout=1.0)
                except Exception:
                    pass
                self._observer = None

            # 注意：不处理 _poll_thread，因为 daemon 线程会在进程退出时自动终止
        except Exception:
            # 析构期间忽略所有异常，避免GC崩溃
            pass
