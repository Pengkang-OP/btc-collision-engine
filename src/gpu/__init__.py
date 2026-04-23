"""GPU模块 - 提供GPU设备检测、厂商优化和配置管理

该模块实现了GPU调用的模块化设计,支持:
- GPU设备自动检测(过滤CPU和核显,2015年至今的GPU型号)
- 按厂商分类的GPU处理模块(NVIDIA/AMD/Intel)
- 基于型号数据库的功能配置
- 基于性能表现的差异化配置调用
"""

"""GPU模块 - GPU设备检测、配置管理和厂商优化

提供完整的GPU管理功能:
- GPU设备自动检测和选择
- 厂商特定的优化策略
- 驱动版本检测和健康检查
- 型号数据库驱动的配置
"""

from .device import GPUDeviceDetector, GPUDevice, identify_vendor
from .config import GPUConfig
from .context import GPUContext
from .driver_manager import DriverManager, DriverVersionParser
from .kernel import OPENCL_KERNEL_SOURCE
from .facade import GPUFacade, create_gpu_facade

# 多GPU支持模块
from .selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector
from .load_balancer import GPULoadBalancer
from .worker import SingleGPUWorker
from .multi_gpu_engine import MultiGPUCollisionEngine
from .auto_config import GPUAutoConfigurator, get_gpu_configurator, reset_gpu_configurator
from .lock_monitor import LockMonitor, MonitoredLock, get_lock_monitor, create_monitored_lock
from .data_monitor import DataMonitor, DataQualityIssue

__version__ = "3.1.0"  # 与主项目版本同步

__all__ = [
    'GPUDeviceDetector',
    'GPUDevice',
    'GPUConfig',
    'GPUContext',
    'identify_vendor',
    'DriverManager',
    'DriverVersionParser',
    'OPENCL_KERNEL_SOURCE',
    # GPU外观类（简化接口）
    'GPUFacade',
    'create_gpu_facade',
    # 多GPU支持
    'GPUDeviceSelector',
    'get_gpu_selector',
    'reset_gpu_selector',
    'GPULoadBalancer',
    'SingleGPUWorker',
    'MultiGPUCollisionEngine',
    'GPUAutoConfigurator',
    'get_gpu_configurator',
    'reset_gpu_configurator',
    # 锁监控
    'LockMonitor',
    'MonitoredLock',
    'get_lock_monitor',
    'create_monitored_lock',
    # 数据监控
    'DataMonitor',
    'DataQualityIssue'
]
