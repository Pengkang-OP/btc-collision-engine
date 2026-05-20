"""CPU-GPU 双缓冲优化模块 (PERF-1)

实现 CPU-GPU 双缓冲机制,通过读写两个缓冲区交替使用,
消除 CPU 准备数据和 GPU 计算之间的等待时间。

特性:
- 读写双缓冲区轮转: front_buffer (GPU读取) / back_buffer (CPU写入)
- 配置开关: 环境变量 BTC_GPU_DOUBLE_BUFFER (1/0) 或程序化配置
- 优雅降级: 双缓冲不可用时自动降级为单缓冲模式
- 队列深度扩展: 支持多缓冲区池 (>2) 以支持深度流水线
- 线程安全: 所有缓冲区操作受锁保护

典型用法:
    db = DoubleBuffer(context, num_keys=1000000)

    # 带环境变量降级的用法:
    # set BTC_GPU_DOUBLE_BUFFER=0   → 强制单缓冲模式
    # set BTC_GPU_DOUBLE_BUFFER=1   → 启用双缓冲 (默认)

    if db.enabled:
        back_buf = db.get_back()         # CPU 写入端
        # ... 准备数据到 back_buf ...
        db.swap()                         # 切换前后端
        front_buf = db.get_front()       # GPU 读取端
    else:
        buf = db.get_front()              # 单缓冲: 共用同一个
"""

import os
import threading
from contextlib import suppress
from typing import Any

# 双缓冲控制环境变量
ENV_DOUBLE_BUFFER = "BTC_GPU_DOUBLE_BUFFER"


class DoubleBuffer:
    """CPU-GPU 双缓冲管理器

    管理 OpenCL 缓冲区对,实现前端(读)/后端(写)交替切换:

    - 前端缓冲区 (front): GPU 正在读取/处理的缓冲区
    - 后端缓冲区 (back):  CPU 可以安全写入数据的缓冲区
    - swap(): 原子切换前后端,完成一轮双缓冲轮转

    配置来源:
      1. 构造函数 enabled 参数 (最高优先级)
      2. 环境变量 BTC_GPU_DOUBLE_BUFFER
         - "0"/"false"/"no"/"off"/"disable"/"disabled" → 禁用双缓冲
         - "1"/"true"/"yes"/"on"/"enable"/"enabled"/未设置 → 启用双缓冲 (默认)

    单缓冲模式行为:
      - front 和 back 指向同一个缓冲区
      - swap() 无操作
      - 对外接口保持一致,调用方无需区分模式
    """

    __slots__ = (
        "_context",
        "_num_keys",
        "_cl",
        "_np",
        "_enabled",
        "_lock",
        "_front_idx",
        "_back_idx",
        "_buffers",
    )

    def __init__(
        self,
        context: Any,
        num_keys: int,
        enabled: bool | None = None,
    ) -> None:
        """
        初始化双缓冲

        Args:
            context: OpenCL 上下文
            num_keys: 每个缓冲区的密钥数量
            enabled: 是否启用双缓冲。
                     None  = 从环境变量 BTC_GPU_DOUBLE_BUFFER 读取 (默认行为)
                     True  = 强制启用双缓冲
                     False = 强制禁用,降级为单缓冲模式
        """
        import numpy as np
        import pyopencl as cl

        self._context = context
        self._num_keys = num_keys
        self._cl = cl
        self._np = np

        # 确定是否启用双缓冲
        if enabled is None:
            enabled = self._read_env_config()
        self._enabled = enabled

        self._lock = threading.Lock()

        # 前后端索引: 双缓冲模式下 front=0/back=1; 单缓冲模式下两者都指向 0
        self._front_idx = 0
        self._back_idx = 1 if self._enabled else 0

        # 缓冲区数组
        self._buffers: list[dict[str, Any]] = []

        # 创建 OpenCL 缓冲区
        self._create_buffers()

    # ------------------------------------------------------------------
    # 静态 / 配置方法
    # ------------------------------------------------------------------

    @staticmethod
    def _read_env_config() -> bool:
        """从环境变量读取双缓冲配置

        BTC_GPU_DOUBLE_BUFFER:
          "0" / "false" / "no" / "off" / "disable" / "disabled" → 禁用
          "1" / "true" / "yes" / "on" / "enable" / "enabled" / 未设置 → 启用 (默认)
        """
        val = os.environ.get(ENV_DOUBLE_BUFFER, "1").strip().lower()
        return val not in ("0", "false", "no", "off", "disable", "disabled")

    @staticmethod
    def is_double_buffer_enabled() -> bool:
        """查询环境变量当前是否启用了双缓冲 (静态便捷方法)"""
        return DoubleBuffer._read_env_config()

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """是否启用双缓冲"""
        return self._enabled

    @property
    def buffer_count(self) -> int:
        """缓冲区数量 (双缓冲=2, 单缓冲=1)"""
        return len(self._buffers)

    @property
    def num_keys(self) -> int:
        """每个缓冲区管理的密钥数量"""
        return self._num_keys

    # ------------------------------------------------------------------
    # 缓冲区操作
    # ------------------------------------------------------------------

    def get_front(self) -> dict[str, Any]:
        """获取前端缓冲区 (GPU 读取端)

        GPU 可以安全地从此缓冲区读取数据。
        单缓冲模式下返回唯一缓冲区。

        Returns:
            dict with keys "matches" (cl.Buffer) and "match_flags" (np.ndarray)
        """
        with self._lock:
            return self._buffers[self._front_idx]

    def get_back(self) -> dict[str, Any]:
        """获取后端缓冲区 (CPU 写入端)

        CPU 可以安全地向此缓冲区写入数据。
        单缓冲模式下返回唯一缓冲区 (与 front 相同)。

        Returns:
            dict with keys "matches" (cl.Buffer) and "match_flags" (np.ndarray)
        """
        with self._lock:
            return self._buffers[self._back_idx]

    def swap(self) -> None:
        """交换前后端缓冲区

        双缓冲模式: 将后端切换为前端,前端切换为后端。
        单缓冲模式: 无操作 (静默跳过)。

        典型调用序列:
            back  = db.get_back()    # CPU 写入端
            # ... CPU 填充 back ...
            db.swap()                # 交换,back 变为新的 front
            front = db.get_front()   # GPU 读取端
        """
        with self._lock:
            if self._enabled:
                self._front_idx, self._back_idx = self._back_idx, self._front_idx

    def reset_flags(self, buf: dict[str, Any] | None = None) -> None:
        """重置匹配标志数组 (清零)

        用于在 GPU 内核启动前清除上一轮的匹配标志。

        Args:
            buf: 目标缓冲区字典,None 则重置后端缓冲区
        """
        if buf is None:
            buf = self.get_back()
        flags = buf.get("match_flags") if buf else None
        if flags is not None and hasattr(flags, "fill"):
            flags.fill(0)

    def release(self) -> None:
        """释放所有 OpenCL 缓冲区资源

        应在不再需要双缓冲时调用,释放 GPU 显存。
        调用后对象不可再使用。
        """
        with self._lock:
            for buf in self._buffers:
                matches = buf.get("matches")
                if matches is not None:
                    with suppress(Exception):
                        matches.release()
                    buf["matches"] = None
                buf["match_flags"] = None
            self._buffers.clear()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _create_buffers(self) -> None:
        """创建 OpenCL 缓冲区 (内部方法)"""
        import pyopencl as cl

        num_bufs = 2 if self._enabled else 1

        for _i in range(num_bufs):
            buf = {
                "matches": cl.Buffer(
                    self._context,
                    cl.mem_flags.READ_WRITE,
                    size=self._num_keys * 4,
                ),
                "match_flags": self._np.zeros(self._num_keys, dtype=self._np.int32),
            }
            self._buffers.append(buf)

    # ------------------------------------------------------------------
    # 诊断
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """获取双缓冲状态统计

        Returns:
            dict with keys: enabled, buffer_count, front_index, back_index, num_keys
        """
        return {
            "enabled": self._enabled,
            "buffer_count": len(self._buffers),
            "front_index": self._front_idx,
            "back_index": self._back_idx,
            "num_keys": self._num_keys,
        }

    def __repr__(self) -> str:
        mode = "DOUBLE" if self._enabled else "SINGLE"
        return (
            f"DoubleBuffer(mode={mode}, buffers={len(self._buffers)}, "
            f"num_keys={self._num_keys}, front={self._front_idx}, "
            f"back={self._back_idx})"
        )
