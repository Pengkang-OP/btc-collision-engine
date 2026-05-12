"""多进程并行碰撞引擎

使用multiprocessing绕过Python GIL限制，
实现真正的多核并行碰撞检测。

性能提升:
- 4核CPU: ~3-4倍加速
- 8核CPU: ~6-8倍加速
- 16核CPU: ~12-16倍加速

适用场景:
- 多核CPU环境
- 大批量碰撞任务
- 需要最大化CPU利用率
"""

import gc
import json
import multiprocessing as mp
import os
import signal
import threading
import time
from multiprocessing import Process, Queue
from queue import Empty, Full
from typing import Any

# 导入日志配置
from ..utils import get_configured_logger, init_logging

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("MultiprocessEngine")


def _worker_process(
    worker_id: int,
    target_addresses: list[str],
    task_queue: Queue,
    result_queue: Queue,
    stats_queue: Queue,
    stop_event: "mp.synchronize.Event",
    generator_func_name: str,
    batch_size: int = 10000,
    encryption_key: bytes | None = None,
    enable_encryption: bool = False,
):
    """工作进程

    Args:
        worker_id: 工作进程ID
        target_addresses: 目标地址列表
        task_queue: 任务队列
        result_queue: 结果队列（匹配结果）
        stats_queue: 统计队列（性能数据）
        stop_event: 停止事件
        generator_func_name: 私钥生成函数名称（'random'或'sequential'）
        batch_size: 批次大小

    注意：
    - 使用函数名称而非函数对象，避免pickle序列化问题
    - 在子进程中本地初始化address_generator
    """
    # 设置进程名称
    try:
        from setproctitle import setproctitle

        setproctitle(f"btc-collision-worker-{worker_id}")
    except ImportError:
        pass  # setproctitle可选

    logger.info(f"工作进程 {worker_id} 启动")

    # 尝试锁定内存，防止私钥被交换到磁盘（仅Linux）
    try:
        import ctypes
        import sys

        if sys.platform.startswith("linux"):
            libc = ctypes.CDLL("libc.so.6")
            # 使用正确的mlockall标志
            MCL_CURRENT = 1  # 锁定当前所有内存
            MCL_FUTURE = 2  # 锁定未来分配的内存
            ret = libc.mlockall(MCL_CURRENT | MCL_FUTURE)
            if ret == 0:
                logger.debug(f"工作进程 {worker_id} 内存已锁定")
            else:
                import errno

                if errno.errno == errno.EPERM:
                    logger.debug(f"工作进程 {worker_id} 内存锁定需要root权限")
                else:
                    logger.debug(f"工作进程 {worker_id} 内存锁定失败: errno={errno.errno}")
        # macOS和Windows不支持mlockall，静默跳过
    except (OSError, AttributeError, ImportError) as e:
        # OSError: mlockall系统调用失败
        # AttributeError: ctypes找不到mlockall函数
        # ImportError: 库导入失败
        logger.debug(f"工作进程 {worker_id} 内存锁定失败: {type(e).__name__}: {e}")

    # 在子进程中本地初始化生成器（避免pickle问题）
    # 使用bytearray以支持私钥清零
    if generator_func_name == "random":
        # SEVERE-3修复: 使用secrets模块替代os.urandom以获得更好的安全性
        import secrets

        def generator_func(n: int) -> list[bytearray]:
            return [bytearray(secrets.token_bytes(32)) for _ in range(n)]

    elif generator_func_name == "sequential":
        start_key = 1

        def sequential_gen(n: int) -> list[bytearray]:
            nonlocal start_key
            keys = [bytearray(start_key.to_bytes(32, "big")) for _ in range(n)]
            start_key += n
            return keys

        generator_func = sequential_gen
    else:
        raise ValueError(f"未知的生成器函数: {generator_func_name}")

    # 在子进程中初始化地址生成器
    from ..core.optimized_address_generator import OptimizedP2PKHAddressGenerator

    address_generator = OptimizedP2PKHAddressGenerator()

    # 转换为集合加速查找
    target_set = set(target_addresses)

    # 统计信息
    total_checked = 0
    start_time = time.time()
    matches_found = 0

    try:
        while not stop_event.is_set():
            try:
                # 从任务队列获取任务（超时避免永久阻塞）
                task = task_queue.get(timeout=1.0)

                if task is None:  # 毒丸信号
                    break

                # 处理任务
                batch_size = task.get("batch_size", batch_size)
                private_keys = generator_func(batch_size)

                # 批量生成地址并检测碰撞
                batch_matches = []
                for pk in private_keys:
                    try:
                        # pk是bytearray类型，可以清零
                        # 创建bytes副本用于计算（不可变）
                        pk_bytes = bytes(pk)

                        # 使用子进程本地初始化的address_generator
                        address = address_generator.generate_from_private_key(pk_bytes)
                        total_checked += 1

                        if address in target_set:
                            matches_found += 1

                            # 安全处理：仅存储地址和私钥哈希，不存储明文私钥
                            # 使用32字符（128位）哈希，更安全
                            import hashlib

                            pk_hash = hashlib.sha256(pk_bytes).hexdigest()[:32]

                            batch_matches.append(
                                {
                                    "private_key_hash": pk_hash,  # 仅存储128位哈希
                                    "address": address,
                                    "worker_id": worker_id,
                                    "timestamp": time.time(),
                                }
                            )

                            # 安全日志：不记录完整私钥
                            logger.warning(
                                f"🎉 匹配发现 [Worker-{worker_id}]: 地址={address[:10]}...{address[-6:]}"
                            )
                    except Exception as e:
                        # 安全的错误日志（不包含私钥）
                        error_type = type(e).__name__
                        logger.error(f"工作进程 {worker_id} 处理失败: 类型={error_type}")
                        continue
                    finally:
                        # 清零私钥内存（现在有效，因为pk是bytearray）
                        try:
                            if isinstance(pk, bytearray):
                                pk[:] = b"\x00" * len(pk)
                        except (TypeError, ValueError, MemoryError) as e:
                            logger.debug(f"私钥清零失败: {e}")

                        # 删除引用，加速GC
                        try:
                            del pk_bytes
                        except NameError:
                            pass  # 变量已不存在

                # 发送匹配结果
                if batch_matches:
                    # 如果启用加密，则加密后发送
                    if enable_encryption and encryption_key:
                        try:
                            from cryptography.fernet import Fernet

                            fernet = Fernet(encryption_key)
                            encrypted_data = fernet.encrypt(json.dumps(batch_matches).encode())
                            result_queue.put(encrypted_data)
                        except Exception as e:
                            # 加密失败时丢弃数据，不发送明文（安全优先）
                            logger.error(f"工作进程 {worker_id} 加密失败，丢弃匹配数据: {e}")
                            # 不降级发送明文，保护数据安全
                    else:
                        result_queue.put(batch_matches)

                # 定期发送统计信息（每10000次）
                if total_checked % 10000 == 0:
                    elapsed = time.time() - start_time
                    speed = total_checked / elapsed if elapsed > 0 else 0

                    stats_queue.put(
                        {
                            "worker_id": worker_id,
                            "total_checked": total_checked,
                            "matches_found": matches_found,
                            "speed": speed,
                            "elapsed": elapsed,
                        }
                    )

                    # 定期强制GC，清理敏感对象（增大间隔减少性能影响）
                    # 每200,000次触发一次，降低GC频率
                    if total_checked % 200000 == 0:
                        gc.collect()

            except Exception as e:
                logger.error(f"工作进程 {worker_id} 异常: {e}")
                continue

    except KeyboardInterrupt:
        logger.info(f"工作进程 {worker_id} 收到中断信号")
    except Exception as e:
        logger.error(f"工作进程 {worker_id} 致命错误: {type(e).__name__}")
    finally:
        # 清理所有私钥内存（异常退出时也需要清理）
        try:
            if "private_keys" in locals():
                for pk in private_keys:
                    if isinstance(pk, bytearray):
                        pk[:] = b"\x00" * len(pk)
                del private_keys
        except (NameError, TypeError, ValueError) as e:
            logger.debug(f"清理私钥内存失败: {e}")

        logger.info(f"工作进程 {worker_id} 退出: 检测={total_checked:,}, 匹配={matches_found}")


class MultiprocessCollisionEngine:
    """多进程碰撞引擎

    使用multiprocessing实现真正的多核并行碰撞检测，
    绕过Python GIL限制。

    架构:
    - 主进程: 任务分发、结果聚合、统计收集
    - 工作进程: 私钥生成、地址计算、碰撞检测

    性能:
    - N核CPU: 接近N倍线性加速
    - 内存隔离: 每个进程独立内存空间
    - 进程间通信: Queue + Manager
    - 加密传输: Fernet对称加密（可选）
    """

    def __init__(
        self,
        num_workers: int | None = None,
        batch_size: int = 10000,
        target_addresses: list[str] | None = None,
    ) -> None:
        """
        初始化多进程碰撞引擎

        Args:
            num_workers: 工作进程数量（默认=CPU核心数）
            batch_size: 每批次处理的私钥数量
            target_addresses: 目标地址列表
        """
        # 自动检测CPU核心数
        if num_workers is None:
            num_workers = mp.cpu_count()

        self.num_workers = num_workers
        self.batch_size = batch_size
        self.target_addresses = target_addresses or []

        # 进程间通信
        self.task_queue: Queue | None = None
        self.result_queue: Queue | None = None
        self.stats_queue: Queue | None = None
        self.stop_event: Any | None = None

        # 工作进程
        self.workers: list[Process] = []

        # 统计信息
        self.total_checked: int = 0
        self.total_matches: list[dict[str, Any]] = []
        self.worker_stats: dict[int, dict[str, Any]] = {}

        # 线程锁（保护统计信息）
        self._stats_lock = threading.Lock()

        # 状态
        self._running = False
        self._generator_func: Any | None = None
        self._address_generator: Any | None = None

        # Queue监控
        self._queue_overflow_warnings = 0

        # 加密配置（可选）
        self._encryption_key: bytearray | None = None  # 使用bytearray存储，支持清零
        self._enable_encryption = False

        logger.info(f"多进程引擎初始化: workers={num_workers}, batch_size={batch_size:,}")

    def start(
        self,
        generator_func_name: str = "random",
        mode: str = "random",
        enable_encryption: bool = False,
    ) -> bool:
        """
        启动多进程碰撞

        Args:
            generator_func_name: 私钥生成函数名称（'random'或'sequential'）
            mode: 碰撞模式
            enable_encryption: 是否启用Queue传输加密（默认False）

        Returns:
            bool: 启动成功返回True

        注意：
        - 不再传递generator_func和address_generator对象
        - 在子进程中本地初始化，避免pickle序列化问题
        - 启用加密会增加约5-10%的性能开销
        """
        if self._running:
            logger.warning("引擎已在运行")
            return False

        self._generator_func_name = generator_func_name
        self._enable_encryption = enable_encryption

        # 如果启用加密，生成密钥
        if enable_encryption:
            try:
                from cryptography.fernet import Fernet

                # 使用bytearray存储密钥，支持安全清零
                key_bytes = Fernet.generate_key()
                self._encryption_key = bytearray(key_bytes)
                logger.info("已启用Queue传输加密")
            except ImportError:
                logger.warning("cryptography库未安装，禁用加密")
                self._enable_encryption = False

        # 创建进程间通信对象（设置有界Queue，防止内存泄漏）
        self.task_queue = Queue(maxsize=100)
        self.result_queue = Queue(maxsize=1000)  # 限制结果队列
        self.stats_queue = Queue(maxsize=50)  # 限制统计队列
        self.stop_event = mp.Event()

        # 启动工作进程
        self.workers = []
        for i in range(self.num_workers):
            p = Process(
                target=_worker_process,
                args=(
                    i,
                    self.target_addresses,
                    self.task_queue,
                    self.result_queue,
                    self.stats_queue,
                    self.stop_event,
                    generator_func_name,  # 传递函数名称而非对象
                    self.batch_size,
                    self._encryption_key,  # 传递加密密钥（可选）
                    self._enable_encryption,  # 传递加密开关
                ),
                daemon=True,
            )
            p.start()
            self.workers.append(p)
            logger.info(f"启动工作进程 {i} (PID={p.pid})")

        self._running = True
        logger.info(f"多进程引擎已启动: {self.num_workers}个工作进程")

        return True

    def submit_task(self, batch_size: int | None = None) -> None:
        """提交任务到工作队列

        Args:
            batch_size: 批次大小（可选，使用默认值）
        """
        if not self._running:
            logger.warning("引擎未启动，无法提交任务")
            return

        task = {
            "batch_size": batch_size or self.batch_size
            # 不再需要address_generator，子进程本地初始化
        }

        try:
            assert self.task_queue is not None
            self.task_queue.put(task, timeout=1.0)
        except Exception as e:
            logger.error(f"提交任务失败: {e}")

    def get_results(self, timeout: float = 0.1) -> list[dict]:
        """获取匹配结果

        Args:
            timeout: 超时时间（秒）

        Returns:
            匹配结果列表
        """
        results = []

        # 监控队列大小
        if self.result_queue and self.result_queue.qsize() > 800:
            if self._queue_overflow_warnings % 10 == 0:
                logger.warning(f"结果队列接近满载: {self.result_queue.qsize()}/1000")
            self._queue_overflow_warnings += 1

        try:
            while True:
                assert self.result_queue is not None
                batch = self.result_queue.get(timeout=timeout)

                # 如果启用加密，则解密
                if self._enable_encryption and isinstance(batch, bytes):
                    try:
                        from cryptography.fernet import Fernet, InvalidToken

                        assert self._encryption_key is not None
                        fernet = Fernet(bytes(self._encryption_key))
                        decrypted_data = fernet.decrypt(batch)
                        batch = json.loads(decrypted_data)
                    except InvalidToken:
                        logger.critical("解密失败：密钥不匹配或数据损坏，丢弃数据")
                        continue
                    except json.JSONDecodeError:
                        logger.error("解密后数据格式错误，丢弃数据")
                        continue
                    except Exception as e:
                        logger.error(f"解密异常: {type(e).__name__}, 丢弃数据")
                        continue

                results.extend(batch)
        except Empty:
            # 队列为空
            pass
        except Exception as e:
            logger.warning(f"收集结果时异常: {e}")

        # 更新总匹配数（线程安全）
        with self._stats_lock:
            self.total_matches.extend(results)

        return results

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        # 使用锁保护统计信息更新（线程安全）
        with self._stats_lock:
            # 收集所有工作进程的统计
            try:
                while True:
                    assert self.stats_queue is not None
                    stats = self.stats_queue.get_nowait()
                    self.worker_stats[stats["worker_id"]] = stats
            except Empty:
                # 队列为空，收集完毕
                pass
            except (KeyError, TypeError) as e:
                logger.warning(f"统计数据处理异常: {e}")

            # 聚合统计
            total_checked = sum(s["total_checked"] for s in self.worker_stats.values())
            total_matches = sum(s["matches_found"] for s in self.worker_stats.values())
            total_speed = sum(s["speed"] for s in self.worker_stats.values())

            self.total_checked = total_checked

            return {
                "total_checked": total_checked,
                "total_matches": total_matches,
                "total_speed": total_speed,
                "num_workers": self.num_workers,
                "worker_stats": dict(self.worker_stats),
                "matches": list(self.total_matches),  # 返回副本
            }

    def stop(self, timeout: float = 10.0) -> None:
        """停止多进程引擎

        Args:
            timeout: 等待工作进程退出的超时时间（秒）
        """
        if not self._running:
            return

        logger.info("停止多进程引擎...")

        # 设置停止事件
        assert self.stop_event is not None
        self.stop_event.set()

        # 发送毒丸信号
        for _ in self.workers:
            try:
                assert self.task_queue is not None
                self.task_queue.put(None, timeout=1.0)
            except Full:
                logger.warning("任务队列已满，跳过毒丸信号")
            except Exception as e:
                logger.error(f"发送停止信号失败: {e}")

        # 等待工作进程退出
        zombie_processes = []  # 记录僵尸进程
        for i, p in enumerate(self.workers):
            p.join(timeout=timeout / len(self.workers))
            if p.is_alive():
                logger.warning(f"工作进程 {i} (PID={p.pid}) 未按时退出，强制终止")
                p.terminate()
                p.join(timeout=2.0)  # 等待terminate生效

                # 检查是否成为僵尸进程
                if p.is_alive() or p.exitcode is None:
                    zombie_processes.append({"id": i, "pid": p.pid})
                    logger.error(f"工作进程 {i} (PID={p.pid}) 可能已成为僵尸进程")

        # #12修复: 僵尸进程清理报告
        if zombie_processes:
            logger.critical(
                f"发现{len(zombie_processes)}个僵尸进程: "
                f"{', '.join([f'Worker-{z['id']}(PID={z['pid']})' for z in zombie_processes])}"
            )
            # 尝试发送SIGKILL（Unix）
            if os.name != "nt":
                for z in zombie_processes:
                    try:
                        assert z["pid"] is not None
                        os.kill(z["pid"], int(getattr(signal, "SIGKILL", 9)))
                        logger.info(f"已发送SIGKILL到进程 {z['pid']}")
                    except Exception as e:
                        logger.error(f"发送SIGKILL失败 {z['pid']}: {e}")

        self._running = False

        # 清理Queue资源
        self._cleanup_queues()

        # 清零加密密钥（安全清理）
        if self._encryption_key:
            try:
                self._encryption_key[:] = b"\x00" * len(self._encryption_key)
                del self._encryption_key
                logger.debug("加密密钥已安全清零")
            except Exception as e:
                logger.debug(f"清理加密密钥时出错: {e}")

        logger.info("多进程引擎已停止")

    def is_running(self) -> bool:
        """检查引擎是否在运行"""
        return self._running

    def _cleanup_queues(self):
        """清理队列资源"""
        try:
            # 清空队列
            for queue in [self.task_queue, self.result_queue, self.stats_queue]:
                if queue:
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except Empty:
                            break  # 队列已空
                        except Exception as e:
                            logger.debug(f"清理队列项失败: {e}")
                            break
        except Exception as e:
            logger.debug(f"清理队列时出错: {e}")

    def cleanup(self) -> None:
        """清理资源"""
        if self._running:
            self.stop()

        # 清理Queue
        self._cleanup_queues()

        self.workers.clear()
        self.worker_stats.clear()

        with self._stats_lock:
            self.total_matches.clear()

        self._queue_overflow_warnings = 0

        logger.info("多进程引擎资源已清理")

    def __enter__(self) -> "MultiprocessCollisionEngine":
        """上下文管理器入口"""
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        """上下文管理器出口

        始终返回 None，表示不抑制异常（让异常传播给调用者）。
        """
        self.cleanup()
        return None


class HybridCollisionEngine:
    """混合碰撞引擎

    结合多线程（I/O密集型）和多进程（CPU密集型）的优势，
    自动选择最优执行策略。

    策略:
    - CPU密集型任务: 使用多进程
    - I/O密集型任务: 使用多线程
    - GPU可用: 使用GPU引擎
    """

    def __init__(
        self,
        use_multiprocess: bool = True,
        num_workers: int | None = None,
        batch_size: int = 10000,
    ) -> None:
        """
        初始化混合引擎

        Args:
            use_multiprocess: 是否使用多进程（否则使用多线程）
            num_workers: 工作进程/线程数量
            batch_size: 批次大小
        """
        self.use_multiprocess = use_multiprocess
        self.num_workers = num_workers or (mp.cpu_count() if use_multiprocess else None)
        self.batch_size = batch_size

        # 引擎实例
        self.mp_engine: MultiprocessCollisionEngine | None = None
        self.thread_engine: Any | None = None

        logger.info(f"混合引擎初始化: multiprocess={use_multiprocess}, workers={self.num_workers}")

    def start(self, **kwargs) -> bool:
        """启动引擎

        Args:
            **kwargs: 传递给底层引擎的参数

        Returns:
            bool: 启动成功返回True
        """
        if self.use_multiprocess:
            self.mp_engine = MultiprocessCollisionEngine(
                num_workers=self.num_workers, batch_size=self.batch_size
            )
            return self.mp_engine.start(**kwargs)
        else:
            # 使用多线程引擎（从现有代码）
            from ..collision import KeyCollisionEngine

            self.thread_engine = KeyCollisionEngine(
                targets=kwargs.get("targets", []), max_workers=self.num_workers or 4
            )
            self.thread_engine.start(**kwargs)
            return True

    def stop(self, **kwargs) -> None:
        """停止引擎"""
        if self.mp_engine:
            self.mp_engine.stop(**kwargs)
        if self.thread_engine:
            self.thread_engine.stop(**kwargs)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        if self.mp_engine:
            return self.mp_engine.get_stats()
        if self.thread_engine:
            return dict(self.thread_engine.get_stats())
        return {}

    def cleanup(self) -> None:
        """清理资源"""
        if self.mp_engine:
            self.mp_engine.cleanup()
        if self.thread_engine:
            self.thread_engine.stop()


def create_multiprocess_engine(
    num_workers: int | None = None, batch_size: int = 10000, targets: list[str] | None = None
) -> MultiprocessCollisionEngine:
    """创建多进程引擎的工厂函数

    Args:
        num_workers: 工作进程数量
        batch_size: 批次大小
        targets: 目标地址列表

    Returns:
        MultiprocessCollisionEngine实例
    """
    return MultiprocessCollisionEngine(
        num_workers=num_workers, batch_size=batch_size, target_addresses=targets
    )


def create_hybrid_engine(
    use_multiprocess: bool = True, num_workers: int | None = None, batch_size: int = 10000
) -> HybridCollisionEngine:
    """创建混合引擎的工厂函数

    Args:
        use_multiprocess: 是否使用多进程
        num_workers: 工作进程/线程数量
        batch_size: 批次大小

    Returns:
        HybridCollisionEngine实例
    """
    return HybridCollisionEngine(
        use_multiprocess=use_multiprocess, num_workers=num_workers, batch_size=batch_size
    )
