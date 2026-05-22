"""GPU外观类（GPU Facade）

提供简化的GPU子系统接口，封装GPU驱动管理、设备初始化、
内存管理和碰撞执行等复杂操作，降低碰撞引擎与GPU模块的耦合度。
"""

from typing import Any

# 导入日志配置
from ..utils import get_configured_logger, init_logging

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("GPUFacade")


class GPUFacade:
    """GPU外观类

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

    def __init__(self):
        """初始化GPU外观类"""
        self._driver_manager = None
        self._gpu_device = None
        self._collision_engine = None
        self._is_initialized = False

        logger.debug("GPUFacade已创建")

    def is_available(self) -> bool:
        """检查GPU是否可用

        Returns:
            bool: GPU可用返回True
        """
        try:
            from .driver_manager import DriverManager

            self._driver_manager = DriverManager()
            available = self._driver_manager.detect_gpu()

            if available:
                logger.info("GPU可用")
            else:
                logger.info("GPU不可用")

            return available

        except Exception as e:
            logger.warning(f"GPU可用性检查失败: {e}")
            return False

    def get_device_count(self) -> int:
        """获取可用GPU数量

        Returns:
            int: GPU数量
        """
        if not self._driver_manager:
            self.is_available()

        return self._driver_manager.get_gpu_count() if self._driver_manager else 0

    def list_devices(self) -> list[dict[str, Any]]:
        """列出所有可用GPU设备

        Returns:
            设备信息列表
        """
        if not self._driver_manager:
            self.is_available()

        return self._driver_manager.list_devices()

    def initialize(self, device_index: int = 0, batch_size: int = 1000000) -> bool:
        """初始化GPU设备

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

            self._gpu_device = GPUDevice(device_index=device_index)  # type: ignore[call-arg]

            # 创建碰撞引擎
            from .collision_engine import GPUCollisionEngine  # type: ignore[import-not-found]

            self._collision_engine = GPUCollisionEngine(
                gpu_device=self._gpu_device, device_index=device_index, batch_size=batch_size
            )

            self._is_initialized = True
            logger.info(f"GPU已初始化: 设备={device_index}, 批次={batch_size:,}")
            return True

        except Exception as e:
            logger.error(f"GPU初始化失败: {e}")
            self._is_initialized = False
            return False

    def start_collision(self, targets: list[str], mode: str = "random", batch_size: int = 10000) -> bool:
        """启动GPU碰撞

        Args:
            targets: 目标地址列表
            mode: 碰撞模式
            batch_size: 批次大小

        Returns:
            bool: 启动成功返回True
        """
        if not self._is_initialized:
            logger.error("GPU未初始化，请先调用initialize()")
            return False

        try:
            # 设置目标
            self._collision_engine.set_target_addresses(targets)

            # 启动碰撞
            self._collision_engine.start(mode=mode, batch_size=batch_size)

            logger.info(f"GPU碰撞已启动: 模式={mode}, 目标={len(targets)}")
            return True

        except Exception as e:
            logger.error(f"启动GPU碰撞失败: {e}")
            return False

    def stop(self) -> bool:
        """停止GPU碰撞

        Returns:
            bool: 停止成功返回True
        """
        if not self._collision_engine:
            return True

        try:
            self._collision_engine.stop()
            logger.info("GPU碰撞已停止")
            return True

        except Exception as e:
            logger.error(f"停止GPU碰撞失败: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取碰撞统计信息

        Returns:
            统计信息字典
        """
        if not self._collision_engine:
            return {"status": "not_initialized"}

        try:
            return self._collision_engine.get_stats()
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"status": "error", "message": str(e)}

    def get_device_info(self) -> dict[str, Any]:
        """获取GPU设备信息

        Returns:
            设备信息字典
        """
        if not self._collision_engine:
            return {"status": "not_initialized"}

        try:
            return self._collision_engine.get_device_info()
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            return {"status": "error", "message": str(e)}

    def get_memory_info(self) -> dict[str, Any]:
        """获取GPU内存信息

        Returns:
            内存信息字典
        """
        if not self._gpu_device:
            return {"status": "not_initialized"}

        try:
            return self._gpu_device.get_memory_info()
        except Exception as e:
            logger.error(f"获取内存信息失败: {e}")
            return {"status": "error", "message": str(e)}

    def cleanup(self) -> None:
        """清理GPU资源"""
        try:
            # 停止碰撞
            if self._collision_engine:
                self._collision_engine.stop()

            # 释放GPU设备
            if self._gpu_device:
                self._gpu_device.cleanup()

            self._is_initialized = False
            logger.info("GPU资源已清理")

        except Exception as e:
            logger.error(f"清理GPU资源失败: {e}")

    def is_running(self) -> bool:
        """检查GPU碰撞是否正在运行

        Returns:
            bool: 正在运行返回True
        """
        if not self._collision_engine:
            return False

        return getattr(self._collision_engine, "_running", False)

    def get_performance(self) -> dict[str, Any]:
        """获取性能信息

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

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()
        return False

    def __del__(self):
        """析构函数"""
        import contextlib

        with contextlib.suppress(Exception):
            self.cleanup()


def create_gpu_facade() -> GPUFacade:
    """创建GPU外观实例的工厂函数

    Returns:
        GPUFacade实例
    """
    return GPUFacade()
