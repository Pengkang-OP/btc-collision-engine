"""单GPU工作器

封装单个GPU的碰撞引擎,在线程中独立运行私钥搜索任务。
提供线程安全的状态管理和结果收集。

集成优化：
- 使用 ThreadLocalDeltaStats 减少锁竞争（可配置）
- 使用性能监控装饰器（可配置）
"""

import threading
import time
from collections.abc import Callable
from contextlib import suppress
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..collision.gpu.engine import GPUCollisionEngine

# 统一日志获取
from ..config.optimization_config import is_feature_enabled
from ..utils import get_configured_logger

# 根据配置条件导入优化模块
_delta_stats_available = is_feature_enabled("delta_stats")
_monitor_available = is_feature_enabled("performance_monitor")

if _delta_stats_available:
    from ..collision.delta_stats import ThreadLocalDeltaStats
if _monitor_available:
    from ..cli.stats_performance_monitor import profile_stats_update

from .gpu_config import WorkerConfig  # noqa: E402

logger = get_configured_logger("GPUWorker")


class SingleGPUWorker(threading.Thread):
    """单GPU工作器线程

    在独立线程中运行单个GPU的私钥碰撞搜索。

    使用示例:
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=target_addresses,
            config=gpu_config
        )

        worker.start()  # 启动搜索

        # 获取统计
        stats = worker.get_stats()

        worker.stop_search()  # 停止搜索
        worker.join()  # 等待线程结束
    """

    def __init__(
        self,
        device_idx: int,
        key_range: tuple[int, int],
        targets: set[str],
        config: dict | WorkerConfig,
        result_callback: Callable | None = None,
        data_monitor: Any | None = None,  # 添加数据监控器引用
        mode: str = "random",  # 碰撞模式: random / range / brute_force
        range_start: int | None = None,  # range/brute_force 起始私钥
        range_end: int | None = None,  # range 结束私钥
    ):
        """初始化GPU工作器

        Args:
            device_idx: GPU设备索引
            key_range: 私钥搜索范围(start, end)，用于负载均衡分配
            targets: 目标地址集合
            config: GPU配置参数 (Dict 或 WorkerConfig)
            result_callback: 找到匹配时的回调函数
            data_monitor: 数据监控器引用
            mode: 碰撞模式 ('random' | 'range' | 'brute_force')
            range_start: range/brute_force 模式的起始私钥（十进制整数）
            range_end: range 模式的结束私钥（十进制整数）
        """
        super().__init__(daemon=True)

        self.device_idx = device_idx
        self.key_range = key_range
        self.targets = targets
        # 统一转换为 WorkerConfig（兼容 Dict 旧接口）
        if isinstance(config, WorkerConfig):
            self.config = config
        else:
            self.config = WorkerConfig.from_dict(config)
        self.result_callback = result_callback
        self.data_monitor = data_monitor  # 保存数据监控器引用
        self.mode = mode
        self.range_start = range_start
        self.range_end = range_end

        # 线程控制
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始状态为运行

        # 状态锁
        self._lock = threading.Lock()

        # 结果队列
        self._result_queue: Queue[dict[str, Any]] = Queue()

        # 统计信息
        self._stats: dict[str, Any] = {
            "device_idx": device_idx,
            "status": "initialized",  # initialized, running, paused, stopped, error
            "keys_checked": 0,
            "matches_found": 0,
            "start_time": None,
            "elapsed_time": 0,
            "throughput": 0,
            "error_count": 0,
            "last_error": None,
        }

        # 增量统计器（线程本地，减少锁竞争）- 根据配置启用
        self._delta_stats: Any | None = None
        if _delta_stats_available:
            self._delta_stats = ThreadLocalDeltaStats()
            logger.debug(f"GPU {device_idx}: 增量统计器已启用")

        # GPU引擎实例
        self._gpu_engine: GPUCollisionEngine | None = None

        # 已上报匹配数追踪 (防止 _update_stats 重复上报)
        self._last_reported_match_count: int = 0

        logger.info(f"GPU工作器已创建: 设备={device_idx}, 范围={key_range[0]:,}-{key_range[1]:,}")

    def run(self) -> None:
        """线程主循环"""
        try:
            self._initialize_gpu_engine()
            with self._lock:
                self._stats["status"] = "running"
                self._stats["start_time"] = time.time()

            logger.info(f"GPU {self.device_idx} 开始搜索...")

            # 执行搜索
            self._execute_search()

        except MemoryError as e:
            logger.error(f"GPU {self.device_idx} 内存不足: {e}")
            with self._lock:
                self._stats["status"] = "error"
                self._stats["last_error"] = f"MemoryError: {e}"
                self._stats["error_count"] += 1
        except ImportError as e:
            logger.error(f"GPU {self.device_idx} 模块导入失败: {e}")
            with self._lock:
                self._stats["status"] = "error"
                self._stats["last_error"] = f"ImportError: {e}"
                self._stats["error_count"] += 1
        except RuntimeError as e:
            logger.error(f"GPU {self.device_idx} 运行时错误: {e}")
            with self._lock:
                self._stats["status"] = "error"
                self._stats["last_error"] = f"RuntimeError: {e}"
                self._stats["error_count"] += 1
        except OSError as e:
            logger.error(f"GPU {self.device_idx} 系统I/O错误: {e}")
            with self._lock:
                self._stats["status"] = "error"
                self._stats["last_error"] = f"OSError: {e}"
                self._stats["error_count"] += 1
        except Exception as e:
            logger.exception(f"GPU {self.device_idx} 工作器未知异常: {type(e).__name__}: {e}")
            with self._lock:
                self._stats["status"] = "error"
                self._stats["last_error"] = f"{type(e).__name__}: {e}"
                self._stats["error_count"] += 1

        finally:
            # 确保异常时也清理资源
            self._cleanup()
            with self._lock:
                self._stats["status"] = "stopped"
            logger.info(f"GPU {self.device_idx} 工作器已停止")

    def _initialize_gpu_engine(self):
        """初始化GPU碰撞引擎"""
        try:
            # 导入GPU碰撞引擎
            from ..collision.gpu.engine import GPUCollisionEngine

            # 配置引擎
            batch_size: int | None = self.config.batch_size  # None=自动计算

            # 创建引擎实例（targets 是必填参数，其余通过 __init__ 完成初始化）
            self._gpu_engine = GPUCollisionEngine(
                targets=self.targets,
                device_index=self.device_idx,
                batch_size=cast(int | None, batch_size),
                use_gpu_memory_pool=True,
            )

            logger.info(f"GPU {self.device_idx} 引擎初始化完成: 批次={batch_size or '自动'}")

        except ImportError as e:
            logger.error(f"GPU {self.device_idx} GPU引擎模块导入失败: {e}")
            raise
        except (ValueError, TypeError) as e:
            logger.error(f"GPU {self.device_idx} 引擎配置参数无效: {type(e).__name__}: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"GPU {self.device_idx} 引擎运行时初始化失败: {e}")
            raise
        except Exception as e:
            logger.exception(f"GPU {self.device_idx} 引擎初始化未知异常: {type(e).__name__}: {e}")
            raise

    def _run_monitor_loop(self, total_keys: int) -> None:
        """监控循环：持续更新统计、检测完成条件。"""
        _base_interval = 0.5
        _min_interval = 0.2
        _max_interval = 1.0
        _adaptive_interval = _base_interval

        while not self._stop_event.is_set():
            if not self._pause_event.is_set():
                time.sleep(0.1)
                continue

            self._update_stats()

            current_throughput = self._stats.get("throughput", 0)
            if current_throughput > 1_000_000:
                _adaptive_interval = _min_interval
            elif current_throughput < 10_000:
                _adaptive_interval = _max_interval
            else:
                _adaptive_interval = _base_interval

            if self.mode != "random" and self._stats["keys_checked"] >= total_keys:
                logger.info(f"GPU {self.device_idx} 完成搜索范围")
                self._stop_event.set()
                break

            time.sleep(_adaptive_interval)

    def _handle_memory_error_retry(self, _depth: int = 0) -> None:
        """处理 MemoryError：batch_size 减半后重试。

        最多递归重试 3 次，防止 batch_size 已降至下限后仍 MemoryError 导致无限递归。
        """
        MAX_MEMORY_RETRIES = 3
        if _depth >= MAX_MEMORY_RETRIES:
            logger.error(f"GPU {self.device_idx} 降批重试已达上限 ({MAX_MEMORY_RETRIES})，放弃")
            return

        current_batch = self.config.batch_size or 65536
        new_batch = max(current_batch // 2, 1024)
        logger.warning(
            f"GPU {self.device_idx} 内存不足（MemoryError），"
            f"自动减小 batch_size: {current_batch:,} → {new_batch:,}"
        )
        self.config.batch_size = new_batch
        with self._lock:
            self._stats["error_count"] += 1
            self._stats["last_error"] = f"MemoryError 自动降批至 {new_batch:,}"
        try:
            if self._gpu_engine:
                try:
                    self._gpu_engine.stop()
                except (RuntimeError, OSError) as stop_err:
                    logger.warning(f"GPU {self.device_idx} 引擎停止错误（将强制释放）: {stop_err}")
                self._gpu_engine = None
            self._initialize_gpu_engine()
            self._execute_search(_retry_depth=_depth + 1)
        except Exception as retry_err:
            logger.error(f"GPU {self.device_idx} 降批重试失败: {retry_err}")

    def _record_search_error(self, error: Exception, error_type: str) -> None:
        """记录搜索错误到统计。"""
        logger.error(f"GPU {self.device_idx} 搜索{error_type}错误: {error}")
        with self._lock:
            self._stats["error_count"] += 1
            self._stats["last_error"] = f"{type(error).__name__}: {error}"

    def _execute_search(self, _retry_depth: int = 0):
        """执行私钥搜索（支持 random / range / brute_force 三种模式）。

        _retry_depth: 内部参数，由 _handle_memory_error_retry 传递，外部调用方不应使用。
        """
        if not self._gpu_engine:
            return

        start_key, end_key = self.key_range
        total_keys = end_key - start_key

        try:
            engine_kwargs: dict = {}
            if self.mode in ("range", "brute_force") and self.range_start is not None:
                engine_kwargs["start"] = self.range_start
            if self.mode == "range" and self.range_end is not None:
                engine_kwargs["end"] = self.range_end

            monitor_thread = threading.Thread(
                target=lambda: self._run_monitor_loop(total_keys), daemon=True
            )
            monitor_thread.start()

            self._gpu_engine.start(mode=self.mode, **engine_kwargs)
            logger.info(
                f"GPU {self.device_idx} 引擎已启动: mode={self.mode}, kwargs={engine_kwargs or '无'}"
            )

            monitor_thread.join(timeout=5.0)

            if self._gpu_engine:
                self._gpu_engine.stop()

        except MemoryError:
            self._handle_memory_error_retry(_depth=_retry_depth)
        except RuntimeError as e:
            self._record_search_error(e, "运行时")
        except ValueError as e:
            self._record_search_error(e, "数据")
        except Exception as e:
            logger.exception(f"GPU {self.device_idx} 搜索未知异常: {type(e).__name__}: {e}")
            with self._lock:
                self._stats["error_count"] += 1
                self._stats["last_error"] = f"{type(e).__name__}: {e}"

    def _compute_throughput(self) -> None:
        """计算并更新吞吐量统计（需在锁内调用）。"""
        if self._stats["elapsed_time"] > 0:
            self._stats["throughput"] = self._stats["keys_checked"] / self._stats["elapsed_time"]

    def _report_new_matches(self, matches: list, current_count: int) -> None:
        """上报新增匹配结果（需在锁内调用）。"""
        if current_count <= self._last_reported_match_count:
            return
        for i in range(self._last_reported_match_count, current_count):
            match = matches[i]
            match_dict: dict[str, str] = {
                "address": (
                    match.get("address", "")
                    if isinstance(match, dict)
                    else getattr(match, "address", "")
                ),
                "private_key_hash": (
                    match.get("private_key_hash", "")
                    if isinstance(match, dict)
                    else getattr(match, "private_key_hash", "")
                ),
            }
            self._result_queue.put(match_dict)

            if self._delta_stats:
                self._delta_stats.add_match()

            if self.result_callback:
                try:
                    self.result_callback(self.device_idx, match_dict)
                except Exception as e:
                    logger.error(f"结果回调异常: {e}")

        self._last_reported_match_count = current_count

    def _update_stats(self):
        """更新统计信息"""
        if not self._gpu_engine:
            return

        try:
            # 获取引擎统计
            engine_stats = self._gpu_engine.get_stats()

            # 使用增量统计器（无锁操作）- 根据配置启用
            if self._delta_stats:
                keys_checked = engine_stats.total_checked
                self._delta_stats.add_check(keys_checked - self._stats.get("keys_checked", 0))

            with self._lock:
                self._stats["keys_checked"] = engine_stats.total_checked
                self._stats["matches_found"] = len(engine_stats.matches)

                if self._stats["start_time"]:
                    self._stats["elapsed_time"] = time.time() - self._stats["start_time"]

                self._compute_throughput()

                if self.data_monitor:
                    self.data_monitor.report_keys_generated(
                        device_idx=self.device_idx,
                        count=self._stats["keys_checked"],
                        key_range=self.key_range,
                    )

                self._report_new_matches(engine_stats.matches, len(engine_stats.matches))

        except AttributeError as e:
            logger.debug(f"统计信息属性访问失败: {e}")
            if self.data_monitor:
                self.data_monitor.report_error(
                    device_idx=self.device_idx,
                    error_msg=str(e),
                    error_type="stats_update_attr_error",
                )
        except (ValueError, TypeError) as e:
            logger.debug(f"统计信息数据类型错误: {type(e).__name__}: {e}")
            if self.data_monitor:
                self.data_monitor.report_error(
                    device_idx=self.device_idx,
                    error_msg=str(e),
                    error_type="stats_update_data_error",
                )
        except Exception as e:
            logger.debug(f"更新统计信息失败: {type(e).__name__}: {e}")
            # 报告错误给监控器
            if self.data_monitor:
                self.data_monitor.report_error(
                    device_idx=self.device_idx, error_msg=str(e), error_type="stats_update_error"
                )

    # 根据配置条件应用性能监控装饰器
    if _monitor_available:
        _update_stats = profile_stats_update(_update_stats)

    def _cleanup(self):
        """清理资源"""
        try:
            if self._gpu_engine:
                self._gpu_engine.stop()  # stop() 内部已完整清理 GPU 资源
                self._gpu_engine = None
        except RuntimeError as e:
            logger.error(f"GPU {self.device_idx} 引擎停止时运行时错误: {e}")
        except OSError as e:
            logger.error(f"GPU {self.device_idx} 引擎停止时系统I/O错误: {e}")
        except Exception as e:
            logger.error(f"GPU {self.device_idx} 清理失败: {type(e).__name__}: {e}")

    def stop_search(self) -> None:
        """停止搜索"""
        logger.info(f"GPU {self.device_idx} 收到停止信号")
        self._stop_event.set()

    def pause_search(self) -> None:
        """暂停搜索"""
        logger.info(f"GPU {self.device_idx} 暂停")
        self._pause_event.clear()
        with self._lock:
            self._stats["status"] = "paused"

    def resume_search(self) -> None:
        """恢复搜索"""
        logger.info(f"GPU {self.device_idx} 恢复")
        self._pause_event.set()
        with self._lock:
            self._stats["status"] = "running"

    def get_stats(self) -> dict:
        """获取统计信息(线程安全)

        Returns:
            统计信息字典
        """
        with self._lock:
            return self._stats.copy()

    def get_results(self, max_results: int = 100) -> list:
        """获取搜索结果

        Args:
            max_results: 最大返回数量

        Returns:
            匹配结果列表
        """
        results = []
        with suppress(Empty):
            for _ in range(min(max_results, self._result_queue.qsize())):
                result = self._result_queue.get_nowait()
                results.append(result)

        return results

    def is_running(self) -> bool:
        """检查是否正在运行

        Returns:
            True表示正在运行
        """
        with self._lock:
            return cast(bool, self._stats["status"] == "running")

    def is_alive(self) -> bool:
        """检查线程是否存活

        Returns:
            True表示线程存活
        """
        return threading.Thread.is_alive(self)

    def get_device_idx(self) -> int:
        """获取设备索引

        Returns:
            GPU设备索引
        """
        return self.device_idx

    def get_key_range(self) -> tuple[int, int]:
        """获取私钥搜索范围

        Returns:
            (start, end) 范围
        """
        return self.key_range

    def __repr__(self) -> str:
        return (
            f"<SingleGPUWorker device={self.device_idx} "
            f"status={self._stats['status']} "
            f"throughput={self._stats['throughput']:.0f} keys/s>"
        )
