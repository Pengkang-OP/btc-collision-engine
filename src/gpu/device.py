"""GPU设备检测和管理

提供GPU设备自动检测、过滤、选择功能。
复用现有gpu_engine.py的逻辑并保持API兼容。
"""

import logging
from typing import List, Dict, Optional

# 尝试导入pyopencl
try:
    import pyopencl as cl
    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False

from .profiles.loader import GPUProfileLoader
from .driver_manager import DriverManager, DriverVersionParser

logger = logging.getLogger(__name__)


def identify_vendor(device_name: str, vendor_str: str = '') -> str:
    """
    识别GPU厂商
    
    Args:
        device_name: 设备名称
        vendor_str: 厂商标识字符串
        
    Returns:
        厂商标识: 'nvidia', 'amd', 'intel', 或 'unknown'
    """
    name_lower = device_name.lower()
    vendor_lower = vendor_str.lower()
    
    # NVIDIA
    if 'nvidia' in vendor_lower or 'nvidia' in name_lower or \
       'geforce' in name_lower or 'rtx' in name_lower or 'gtx' in name_lower:
        return 'nvidia'
    
    # AMD
    elif 'amd' in vendor_lower or 'amd' in name_lower or \
         'radeon' in name_lower or 'radeon' in vendor_lower:
        return 'amd'
    
    # Intel
    elif 'intel' in vendor_lower or 'intel' in name_lower:
        return 'intel'
    
    # 未知
    else:
        return 'unknown'


class GPUDeviceDetector:
    """GPU设备检测器"""
    
    # 可用性检测缓存
    _availability_cache = None
    _cache_timestamp = 0
    _cache_ttl = 30  # 缓存有效期30秒(从60秒缩短,提高响应性)
    
    # 设备信息缓存（避免重复检测）
    _devices_cache = None
    _devices_cache_timestamp = 0
    _devices_cache_ttl = 30  # 设备缓存TTL(明确配置)
    
    @staticmethod
    def is_gpu_available() -> bool:
        """
        检查GPU是否可用
        
        使用缓存机制避免频繁检测，缓存有效期60秒。
        
        Returns:
            True如果GPU可用
        """
        import time
        
        # 检查缓存是否有效
        now = time.time()
        if (GPUDeviceDetector._availability_cache is not None and
            now - GPUDeviceDetector._cache_timestamp < GPUDeviceDetector._cache_ttl):
            logger.debug(f"使用GPU可用性缓存: {GPUDeviceDetector._availability_cache}")
            return GPUDeviceDetector._availability_cache
        
        if not PYOPENCL_AVAILABLE:
            logger.debug("pyopencl不可用，GPU检测跳过")
            GPUDeviceDetector._availability_cache = False
            GPUDeviceDetector._cache_timestamp = now
            return False
        
        try:
            devices = GPUDeviceDetector.detect_devices()
            available = len(devices) > 0
            if available:
                logger.debug(f"GPU可用，检测到 {len(devices)} 个设备")
                # 缓存设备信息供get_gpu_health_status()使用
                GPUDeviceDetector._devices_cache = devices
                GPUDeviceDetector._devices_cache_timestamp = time.time()
            else:
                logger.debug("GPU不可用，未检测到设备")
            
            # 更新缓存
            GPUDeviceDetector._availability_cache = available
            GPUDeviceDetector._cache_timestamp = now
            
            return available
        except (ImportError, RuntimeError, OSError) as e:
            # 预期的设备检测异常
            logger.debug(f"GPU检测失败: {type(e).__name__}: {e}")
            GPUDeviceDetector._availability_cache = False
            GPUDeviceDetector._cache_timestamp = now
            return False
        except Exception as e:
            # 未知错误：记录警告日志
            logger.warning(f"GPU检测未知错误: {type(e).__name__}: {e}")
            GPUDeviceDetector._availability_cache = False
            GPUDeviceDetector._cache_timestamp = now
            return False
    
    @staticmethod
    def get_gpu_health_status() -> Dict:
        """
        获取GPU健康状态信息
        
        用于监控系统和运维诊断，提供详细的GPU状态信息。
        复用is_gpu_available()的缓存，避免重复检测。
        
        Returns:
            Dict: 包含GPU健康状态的字典，字段包括：
                - available (bool): GPU是否可用
                - device_count (int): 检测到的设备数量
                - devices (List[str]): 设备名称列表
                - status (str): 健康状态 ('healthy'/'unavailable'/'error')
                - error (str, optional): 错误信息（仅在status='error'时存在）
        """
        import time
        
        try:
            available = GPUDeviceDetector.is_gpu_available()
            
            if available:
                # 复用缓存的设备信息，避免重复检测
                now = time.time()
                if (GPUDeviceDetector._devices_cache is not None and
                    now - GPUDeviceDetector._devices_cache_timestamp < GPUDeviceDetector._cache_ttl):
                    # 使用缓存的设备信息
                    devices = GPUDeviceDetector._devices_cache
                else:
                    # 缓存失效，重新检测
                    devices = GPUDeviceDetector.detect_devices()
                    GPUDeviceDetector._devices_cache = devices
                    GPUDeviceDetector._devices_cache_timestamp = now
                
                device_names = [dev['name'] for dev in devices]
                
                return {
                    'available': True,
                    'device_count': len(devices),
                    'devices': device_names,
                    'status': 'healthy'
                }
            else:
                return {
                    'available': False,
                    'device_count': 0,
                    'devices': [],
                    'status': 'unavailable'
                }
        except Exception as e:
            logger.error(f"GPU健康检查失败: {type(e).__name__}: {e}")
            return {
                'available': False,
                'device_count': 0,
                'devices': [],
                'status': 'error',
                'error': f"{type(e).__name__}: {e}"
            }
    
    @staticmethod
    def clear_availability_cache():
        """
        清除GPU可用性缓存和设备信息缓存
        
        在GPU状态可能发生变化时调用（如驱动更新、设备插拔），
        强制下次is_gpu_available()重新检测。
        """
        GPUDeviceDetector._availability_cache = None
        GPUDeviceDetector._cache_timestamp = 0
        GPUDeviceDetector._devices_cache = None
        GPUDeviceDetector._devices_cache_timestamp = 0
        logger.debug("GPU可用性缓存和设备信息缓存已清除")
    
    @staticmethod
    def detect_devices() -> List[Dict]:
        """
        检测所有可用的GPU设备
        
        过滤规则:
        1. 跳过CPU设备
        2. 跳过Intel HD/UHD/Iris核显
        3. 只保留GPU设备
        
        Returns:
            设备信息列表
        """
        if not PYOPENCL_AVAILABLE:
            logger.warning("pyopencl不可用,无法检测设备")
            return []
        
        devices = []
        try:
            platforms = cl.get_platforms()
            
            for platform in platforms:
                try:
                    platform_devices = platform.get_devices()
                    
                    for device in platform_devices:
                        device_type = device.get_info(cl.device_info.TYPE)
                        
                        # 过滤掉CPU设备
                        if device_type == cl.device_type.CPU:
                            cpu_name = device.get_info(cl.device_info.NAME)
                            logger.debug(f"跳过CPU设备: {cpu_name}")
                            continue
                        
                        # 只保留GPU设备
                        if device_type != cl.device_type.GPU:
                            continue
                        
                        device_name = device.get_info(cl.device_info.NAME)
                        device_name_lower = device_name.lower()
                        
                        # 过滤掉核显/亮机显卡
                        if "intel" in device_name_lower and (
                            "hd graphics" in device_name_lower or 
                            "uhd graphics" in device_name_lower or 
                            "iris" in device_name_lower
                        ):
                            logger.debug(f"跳过核显设备: {device_name}")
                            continue
                        
                        # 构建设备信息字典
                        device_info = {
                            'name': device_name,
                            'vendor': device.get_info(cl.device_info.VENDOR),
                            'platform': platform.get_info(cl.platform_info.NAME),
                            'device': device,
                            'platform_obj': platform,
                            'global_mem_size': device.global_mem_size,
                            'max_compute_units': device.max_compute_units,
                            'type': 'GPU'
                        }
                        
                        devices.append(device_info)
                        
                except Exception as e:
                    logger.warning(f"获取平台设备时出错: {e}")
                    
        except Exception as e:
            logger.error(f"检测OpenCL设备失败: {e}")
        
        logger.info(f"检测到 {len(devices)} 个GPU设备")
        return devices
    
    @staticmethod
    def _select_best_device(devices: List[Dict]) -> Dict:
        """
        选择最佳GPU设备
        
        优先级: NVIDIA > AMD > Intel Arc > Intel其他 > 其他GPU
        
        Args:
            devices: 设备列表
            
        Returns:
            最佳设备信息
        """
        if not devices:
            raise RuntimeError("没有可用的GPU设备")
        
        def priority_score(dev):
            """
            计算设备优先级分数
            
            综合考虑:
            1. 显存大小 (主要因素,每GB 10分)
            2. 计算单元 (次要因素,每100个CU 5分)
            3. 厂商偏好 (辅助因素)
            
            这样可以确保:
            - Intel Arc A770 (16GB) > NVIDIA GTX 1660 Ti (6GB)
            - 大显存GPU优先被选择
            """
            name_lower = dev['name'].lower()
            vendor_lower = dev.get('vendor', '').lower()
            
            # 显存分数 (每GB 10分) - 这是最重要的因素
            global_mem_gb = dev.get('global_mem_size', 0) / (1024**3)
            memory_score = global_mem_gb * 10
            
            # 计算单元分数 (每100个CU 5分)
            compute_units = dev.get('max_compute_units', 0)
            cu_score = (compute_units / 100.0) * 5
            
            # 厂商基础分 (辅助因素,不超过20分)
            if "nvidia" in name_lower or "nvidia" in vendor_lower:
                vendor_score = 20
            elif "amd" in name_lower or "amd" in vendor_lower:
                vendor_score = 15
            elif "intel" in name_lower and "arc" in name_lower:
                vendor_score = 10
            elif "intel" in name_lower:
                vendor_score = 5
            else:
                vendor_score = 0
            
            # 总分 = 显存(主要) + 计算单元(次要) + 厂商(辅助)
            total_score = memory_score + cu_score + vendor_score
            
            return total_score
        
        # 按分数排序
        devices.sort(key=priority_score, reverse=True)
        best_device = devices[0]
        
        # 记录选择原因
        logger.info(
            f"自动选择最佳设备: {best_device['name']}\n"
            f"  - 显存: {best_device.get('global_mem_size', 0)/(1024**3):.1f} GB\n"
            f"  - 计算单元: {best_device.get('max_compute_units', 'N/A')}\n"
            f"  - 优先级分数: {priority_score(best_device):.1f}"
        )
        
        return best_device


class GPUDevice:
    """
    GPU设备封装类
    
    保持与现有gpu_engine.py和gpu_collision_engine.py的API完全兼容
    """
    
    def __init__(self):
        """初始化GPU设备对象"""
        self.context = None
        self.queue = None  # 向后兼容: 默认队列
        self.compute_queue = None  # 计算队列(异步优化)
        self.transfer_queue = None  # 传输队列(异步优化)
        self.device = None
        self.device_info = {}
        self.vendor = None
        self.profile = None
        self.profile_loader = GPUProfileLoader()
        
        # 驱动相关
        self.driver_version = None
        self.driver_health = None
        self.driver_optimization_flags = {}
        
        # 异步优化配置
        self.enable_async_execution = False  # 是否启用异步执行
    
    def initialize(self, device_index: int = -1, enable_async: bool = False):
        """
        初始化GPU设备
        
        Args:
            device_index: 设备索引
                         -1 = 自动选择最佳设备
                         >=0 = 使用指定索引的设备
            enable_async: 是否启用异步执行(双队列)
        """
        # 设置异步标志
        self.enable_async_execution = enable_async
        if not PYOPENCL_AVAILABLE:
            raise RuntimeError("pyopencl不可用")
        
        # 检测所有设备
        devices = GPUDeviceDetector.detect_devices()
        if not devices:
            raise RuntimeError("未找到OpenCL设备")
        
        # 选择设备
        if device_index == -1:
            # 自动选择最佳设备
            device_info = GPUDeviceDetector._select_best_device(devices)
            logger.info(f"自动选择最佳GPU设备: {device_info['name']}")
            
        elif device_index >= 0:
            # 使用指定设备,严格模式(不静默回退)
            if device_index >= len(devices):
                # 抛出异常,提供可用设备列表
                available = [
                    f"  [{i}] {d['name']} ({d.get('global_mem_size', 0)/(1024**3):.1f}GB)"
                    for i, d in enumerate(devices)
                ]
                raise ValueError(
                    f"设备索引 {device_index} 超出范围 (0-{len(devices)-1})\n"
                    f"可用设备:\n" + "\n".join(available)
                )
            else:
                device_info = devices[device_index]
                logger.info(f"使用指定GPU设备 [{device_index}]: {device_info['name']}")
                
        else:
            # 其他负数索引,视为无效
            raise ValueError(
                f"无效的设备索引 {device_index}\n"
                f"有效值: -1(自动选择) 或 0-{len(devices)-1}(指定设备)"
            )
        
        # 保存设备对象
        self.device = device_info['device']
        self.vendor = device_info.get('vendor', 'Unknown')
        
        # 构建设备信息字典
        self.device_info = {
            'name': device_info.get('name', 'Unknown'),
            'type': device_info.get('type', 'GPU'),
            'vendor': self.vendor,
            'platform': device_info.get('platform', 'Unknown'),
            'global_mem_size': device_info['device'].global_mem_size,
            'max_compute_units': device_info['device'].max_compute_units
        }
        
        # 验证设备能力
        self._validate_device_capabilities(device_info)
        
        # 加载厂商配置
        self._load_vendor_profile(device_info['name'])
        
        # 检测和验证驱动
        self._detect_and_validate_driver()
        
        # 创建OpenCL上下文和命令队列
        self.context = cl.Context([self.device])
        
        # 异步优化: 创建双队列(计算+传输)
        if self.enable_async_execution:
            logger.info("启用GPU异步执行: 创建双队列(计算+传输)")
            # 计算队列 - 用于内核执行
            self.compute_queue = cl.CommandQueue(
                self.context, 
                self.device,
                properties=cl.command_queue_properties.PROFILING_ENABLE
            )
            # 传输队列 - 用于数据传输
            self.transfer_queue = cl.CommandQueue(
                self.context,
                self.device,
                properties=cl.command_queue_properties.PROFILING_ENABLE
            )
            # 向后兼容: 默认使用计算队列
            self.queue = self.compute_queue
            logger.info("  - 计算队列: 已创建(支持性能分析)")
            logger.info("  - 传输队列: 已创建(支持异步传输)")
        else:
            # 传统模式: 单一队列
            self.queue = cl.CommandQueue(self.context, self.device)
            logger.info("使用传统单队列模式(同步执行)")
        
        logger.info(
            f"GPU设备初始化成功: {self.device_info['name']} "
            f"({self.device_info['vendor']})\n"
            f"  - 显存: {self.device_info['global_mem_size']/(1024**3):.1f} GB\n"
            f"  - 计算单元: {self.device_info['max_compute_units']}\n"
            f"  - 平台: {self.device_info['platform']}\n"
            f"  - 异步执行: {'已启用' if self.enable_async_execution else '未启用'}"
        )
    
    def _validate_device_capabilities(self, device_info: Dict):
        """
        验证设备能力是否满足最低要求
        
        Args:
            device_info: 设备信息
        """
        min_compute_units = 2
        min_global_mem = 512 * 1024 * 1024  # 512MB
        
        compute_units = device_info['device'].max_compute_units
        global_mem = device_info['device'].global_mem_size
        
        # 检查计算单元
        if compute_units < min_compute_units:
            logger.warning(
                f"设备计算单元过少: {compute_units} (建议 >= {min_compute_units}), "
                f"性能可能受限"
            )
        
        # 检查显存
        if global_mem < min_global_mem:
            logger.warning(
                f"设备显存过小: {global_mem / (1024**2):.0f} MB "
                f"(建议 >= {min_global_mem / (1024**2):.0f} MB), "
                f"可能需要减小batch_size"
            )
        
        logger.debug(
            f"设备能力: 计算单元={compute_units}, "
            f"显存={global_mem / (1024**3):.2f} GB"
        )
    
    def _load_vendor_profile(self, device_name: str):
        """
        加载厂商型号配置
        
        Args:
            device_name: 设备名称
        """
        # 使用共享函数识别厂商
        vendor = identify_vendor(device_name, self.vendor)
        
        # 加载配置
        self.profile = self.profile_loader.get_profile(vendor, device_name)
        
        if self.profile:
            logger.info(
                f"已加载GPU配置: {device_name} -> {vendor}, "
                f"recommended_batch_size={self.profile.get('recommended_batch_size', 'N/A')}"
            )
        else:
            logger.warning(f"未找到 {device_name} 的配置,使用默认参数")
    
    def _detect_and_validate_driver(self):
        """
        检测驱动版本并验证健康状态
        """
        # 1. 检测驱动版本
        self.driver_version = DriverManager.detect_driver_version(self.vendor)
        
        if not self.driver_version:
            logger.warning("无法检测GPU驱动版本")
            return
        
        # 2. 检查驱动健康状态
        self.driver_health = DriverManager.check_driver_health(
            self.vendor, 
            self.driver_version, 
            self.profile
        )
        
        # 3. 记录健康检查结果
        if self.driver_health['status'] == 'critical':
            logger.error(
                f"GPU驱动健康检查失败: {self.driver_health['message']}"
            )
            for rec in self.driver_health['recommendations']:
                logger.error(f"  建议: {rec}")
        elif self.driver_health['status'] == 'warning':
            logger.warning(
                f"GPU驱动健康检查警告: {self.driver_health['message']}"
            )
            for rec in self.driver_health['recommendations']:
                logger.warning(f"  建议: {rec}")
        else:
            logger.info(
                f"GPU驱动版本: {self.driver_version}, 状态: 正常"
            )
        
        # 4. 获取驱动优化标志
        self.driver_optimization_flags = DriverManager.get_driver_optimization_flags(
            self.vendor,
            self.driver_version,
            self.profile
        )
        
        logger.debug(
            f"驱动优化标志: {self.driver_optimization_flags}"
        )
    
    def get_driver_info(self) -> Dict:
        """
        获取驱动信息
        
        Returns:
            驱动信息字典
        """
        return {
            'version': self.driver_version,
            'health': self.driver_health,
            'optimization_flags': self.driver_optimization_flags
        }
    
    def get_device_info(self) -> Dict:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        return self.device_info.copy()
    
    def cleanup(self):
        """释放GPU资源"""
        # 清理命令队列
        queues_to_cleanup = []
        
        if self.compute_queue:
            queues_to_cleanup.append(("计算队列", self.compute_queue))
        if self.transfer_queue:
            queues_to_cleanup.append(("传输队列", self.transfer_queue))
        if self.queue and self.queue not in [self.compute_queue, self.transfer_queue]:
            queues_to_cleanup.append(("默认队列", self.queue))
        
        for name, q in queues_to_cleanup:
            try:
                q.finish()
            except Exception as e:
                logger.debug(f"{name}清理失败: {e}")
        
        self.queue = None
        self.compute_queue = None
        self.transfer_queue = None
        
        # 清理上下文
        if self.context:
            try:
                # 确保所有命令完成
                if hasattr(self.context, 'finish'):
                    self.context.finish()
            except Exception as e:
                logger.debug(f"GPU上下文完成失败: {e}")
            finally:
                self.context = None
        
        # 显式清理设备引用
        self.device = None
        self.device_info = {}
        self.vendor = None
        self.profile = None
        
        logger.info("GPU资源已释放")
