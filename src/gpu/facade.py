"""GPU外观类（GPU Facade）.

提供简化的GPU子系统接口，封装GPU驱动管理、设备初始化、
内存管理和碰撞执行等复杂操作，降低碰撞引擎与GPU模块的耦合度。
"""

import contextlib
from typing import Any

# 导入日志配置
from ..utils import get_configured_logger, init_logging

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("GPUFacade")

__all__ = ["GPUFacade", "create_gpu_facade"]


class GPUFacade:
    """GPU外观类.

    封装GPU子系统的复杂性，提供简洁的统一接口。

    职责：
    1. GPU驱动管理（自动检测和初始化）
    2. GPU设备管理（设备选择和配置）
    3. GPU内存管理（自动分配和释放）
    4. GPU碰撞执行（简化的启动/停止接口）

    使用示例:
        >>> facade = GPUFacade()
        >>> if facade.is_available():
        ...     facade.initialize(device_index=0)
        ...     facade.start_collision(targets, mode="random")
        ...     facade.stop()
    """

    __slots__ = (
        "_checkpoint_enabled",
        "_collision_engine",
        "_config",
        "_dedup_enabled",
        "_driver_manager",
        "_gpu_device",
        "_is_initialized",
        "_mode",
        "_targets",
    )

    def __init__(
        self,
        targets: Any = None,
        use_gpu: bool = True,
        checkpoint_enabled: bool = False,
        dedup_enabled: bool = False,
        config: Any = None,
        **kwargs: Any,
    ) -> None:
        """初始化GPU外观类.

        Args:
            targets: 目标地址集合/列表（供CLI兼容）
            use_gpu: 是否使用GPU（兼容参数，始终为True）
            checkpoint_enabled: 是否启用断点续传（兼容参数）
            dedup_enabled: 是否启用去重（兼容参数）
            config: 配置字典，可包含 gpu_device 等键
            **kwargs: 其他兼容参数

        """
        self._driver_manager = None
        self._gpu_device = None
        self._collision_engine = None
        self._is_initialized = False
        self._targets = list(targets) if targets else []
        self._mode = "random"
        self._config = config or {}
        self._checkpoint_enabled = checkpoint_enabled
        self._dedup_enabled = dedup_enabled

        logger.debug("GPUFacade已创建")

    def start(
        self,
        mode: str = "random",
        resume: bool = False,
        max_keys: int | None = None,
        **kwargs: Any,
    ) -> None:
        """启动GPU碰撞（兼容 KeyCollisionEngine.start API）.

        Args:
            mode: 碰撞模式 (random/sequential)
            resume: 是否从断点恢复（兼容参数）
            max_keys: 最大检查密钥数（兼容参数）
            **kwargs: 其他兼容参数

        """
        if not self._is_initialized:
            device_index = 0
            gpu_section: dict[str, Any] = {}
            if isinstance(self._config, dict):
                # v5.2.0: 优先读取嵌套 gpu.device_index，回退读扁平的 gpu_device
                gpu_section = self._config.get("gpu", {})
                if not isinstance(gpu_section, dict):
                    gpu_section = {}
                device_index = gpu_section.get("device_index", 0) or self._config.get("gpu_device", 0)
            # v5.2.2: 修复 — batch_size 为 0 时不应使用回退值
            batch_size = kwargs.get("batch_size")
            if batch_size is None:
                batch_size = gpu_section.get("batch_size", 1000000)
            if not batch_size:
                batch_size = 1000000
            self.initialize(device_index=device_index, batch_size=int(batch_size))

        if not self._targets:
            logger.error("GPU碰撞启动失败：未设置目标地址")
            return

        self._mode = mode
        # v5.2.2: 修复 — 统一 batch_size 传递，None 时使用初始化时的值
        batch_size = kwargs.get("batch_size")
        self.start_collision(self._targets, mode=mode, batch_size=batch_size)

    def is_available(self) -> bool:
        """检查GPU是否可用.

        Returns:
            bool: GPU可用返回True

        """
        try:
            from .device import GPUDeviceDetector

            devices = GPUDeviceDetector.detect_devices()
            available = len(devices) > 0

            if available:
                logger.debug("GPU可用，检测到 %d 个设备", len(devices))
            else:
                logger.debug("GPU不可用")

            return available

        except Exception as e:
            logger.warning("GPU可用性检查失败: %s", e)
            return False

    def get_device_count(self) -> int:
        """获取可用GPU数量.

        Returns:
            int: GPU数量

        """
        try:
            from .device import GPUDeviceDetector

            return len(GPUDeviceDetector.detect_devices())
        except Exception:
            return 0

    def list_devices(self) -> list[dict[str, Any]]:
        """列出所有可用GPU设备.

        Returns:
            设备信息列表

        """
        try:
            from .device import GPUDeviceDetector

            return GPUDeviceDetector.detect_devices()
        except Exception:
            return []

    def initialize(self, device_index: int = 0, batch_size: int = 1000000) -> bool:
        """初始化GPU设备.

        Args:
            device_index: GPU设备索引
            batch_size: 批次大小

        Returns:
            bool: 初始化成功返回True

        """
        try:
            if not self._driver_manager:
                self.is_available()

            # 创建GPU设备
            from .device import GPUDevice

            self._gpu_device = GPUDevice()  # __init__() takes no args
            self._gpu_device.initialize(device_index=device_index)

            # 创建碰撞引擎 (使用已保存的 targets)
            from ..collision.gpu import create_gpu_collision_engine

            # v5.2.1: 提取 gpu 配置段，传递给引擎
            gpu_cfg = {}
            if isinstance(self._config, dict):
                gpu_section = self._config.get("gpu", {})
                if isinstance(gpu_section, dict):
                    gpu_cfg = gpu_section

            self._collision_engine = create_gpu_collision_engine(
                targets=set(self._targets) if self._targets else set(),
                device_index=device_index,
                batch_size=batch_size,
                checkpoint_enabled=self._checkpoint_enabled,
                dedup_enabled=self._dedup_enabled,
                gpu_config=gpu_cfg,
            )

            self._is_initialized = True
            logger.debug(
                "GPU已初始化: 设备=%d, 批次=%s",
                device_index,
                f"{batch_size:,}",
            )
            return True

        except Exception as e:
            logger.error("GPU初始化失败: %s", e)
            self._is_initialized = False
            return False

    def start_collision(
        self,
        targets: list[str],
        mode: str = "random",
        batch_size: int | None = None,
    ) -> bool:
        """启动GPU碰撞.

        Args:
            targets: 目标地址列表
            mode: 碰撞模式
            batch_size: 批次大小（None 时使用 initialize 时设置的批次大小）

        Returns:
            bool: 启动成功返回True

        """
        if not self._is_initialized:
            logger.error("GPU未初始化，请先调用initialize()")
            return False

        try:
            # 设置目标
            self._collision_engine.targets = set(targets)

            # v5.2.2: 修复 — 统一 batch_size 传递，None 时使用初始化时的值
            if batch_size is None:
                batch_size = self._collision_engine.batch_size
            # 启动碰撞
            self._collision_engine.start(mode=mode, batch_size=batch_size)
            logger.debug("GPU碰撞已启动: 模式=%s, 目标=%d", mode, len(targets))
            return True

        except Exception as e:
            logger.error("启动GPU碰撞失败: %s", e)
            return False

    def stop(self) -> bool:
        """停止GPU碰撞.

        Returns:
            bool: 停止成功返回True

        """
        if not self._collision_engine:
            return True

        try:
            self._collision_engine.stop()
            logger.debug("GPU碰撞已停止")
            return True

        except Exception as e:
            logger.error("停止GPU碰撞失败: %s", e)
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取碰撞统计信息.

        Returns:
            统计信息字典

        """
        if not self._collision_engine:
            return {"status": "not_initialized"}

        try:
            return self._collision_engine.get_stats()
        except Exception as e:
            logger.error("获取统计信息失败: %s", e)
            return {"status": "error", "message": str(e)}

    def get_device_info(self) -> dict[str, Any]:
        """获取GPU设备信息.

        Returns:
            设备信息字典

        """
        if not self._collision_engine:
            return {"status": "not_initialized"}

        try:
            return self._collision_engine.get_device_info()
        except Exception as e:
            logger.error("获取设备信息失败: %s", e)
            return {"status": "error", "message": str(e)}

    def get_memory_info(self) -> dict[str, Any]:
        """获取GPU内存信息.

        Returns:
            内存信息字典

        """
        if not self._gpu_device:
            return {"status": "not_initialized"}

        try:
            return self._gpu_device.get_memory_info()
        except Exception as e:
            logger.error("获取内存信息失败: %s", e)
            return {"status": "error", "message": str(e)}

    def cleanup(self) -> None:
        """清理GPU资源."""
        try:
            # 停止碰撞
            if self._collision_engine:
                self._collision_engine.stop()

            # 释放GPU设备
            if self._gpu_device:
                self._gpu_device.cleanup()

            self._is_initialized = False
            logger.debug("GPU资源已清理")

        except Exception as e:
            logger.error("清理GPU资源失败: %s", e)

    def is_running(self) -> bool:
        """检查GPU碰撞是否正在运行.

        Returns:
            bool: 正在运行返回True

        """
        if not self._collision_engine:
            return False

        return getattr(self._collision_engine, "_running", False)

    def get_performance(self) -> dict[str, Any]:
        """获取性能信息.

        Returns:
            性能信息字典

        """
        stats = self.get_stats()

        return {
            "speed": stats.get("speed", 0),
            "total_checked": stats.get("total_checked", 0),
            "elapsed_time": stats.get("elapsed_time", 0),
            "matches_found": len(stats.get("matches", [])),
        }

    def __enter__(self) -> Any:
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """上下文管理器出口."""
        self.cleanup()
        return False

    def __del__(self) -> None:
        """析构函数.

        风险说明（评估为低风险，暂不修改）：
        - cleanup() 调用 queue.finish() 等 PyOpenCL 操作，解释器关闭时可能静默失败
        - 但已有 contextlib.suppress(Exception) 保护，不会传播异常
        - 推荐使用上下文管理器（with 语句）确保资源正确释放
        """
        with contextlib.suppress(Exception):
            self.cleanup()
            # A类修复: 析构函数中资源清理失败静默处理
            # 因为此时对象正在销毁，无法做更多处理


def create_gpu_facade() -> GPUFacade:
    """创建GPU外观实例的工厂函数.

    Returns:
        GPUFacade实例

    """
    return GPUFacade()
