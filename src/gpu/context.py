"""GPU上下文管理

管理GPU设备上下文、厂商优化器和内核编译。
"""

import logging
from typing import Optional
from .device import GPUDevice, identify_vendor
from .vendors.base import GPUVendorBase
from .vendors.nvidia import NVIDIAGPUVendor
from .vendors.amd import AMDGPUVendor
from .vendors.intel import IntelGPUVendor

logger = logging.getLogger(__name__)


class GPUContext:
    """
    GPU上下文管理器
    
    负责:
    1. 创建厂商特定的优化器
    2. 应用厂商优化策略
    3. 管理OpenCL内核编译
    4. 资源清理
    """
    
    def __init__(self, device: GPUDevice):
        """
        初始化GPU上下文
        
        Args:
            device: 已初始化的GPUDevice实例
        """
        self.device = device
        self.vendor_handler = self._create_vendor_handler()
        self.program = None
        
        logger.info(
            f"GPU上下文已创建: {device.device_info.get('name', 'Unknown')} "
            f"({self.vendor_handler.get_vendor_name()})"
        )
    
    def _create_vendor_handler(self) -> GPUVendorBase:
        """
        根据厂商创建对应的优化处理器
        
        Returns:
            厂商优化器实例
        """
        vendor = self.device.device_info.get('vendor', '')
        name = self.device.device_info.get('name', '')
        
        # 使用共享函数识别厂商
        vendor_type = identify_vendor(name, vendor)
        
        # 根据厂商类型创建处理器
        if vendor_type == 'nvidia':
            return NVIDIAGPUVendor()
        elif vendor_type == 'amd':
            return AMDGPUVendor()
        elif vendor_type == 'intel':
            return IntelGPUVendor()
        else:
            logger.warning(f"未知GPU厂商: {vendor},使用默认优化器")
            return GPUVendorBase()
    
    def apply_optimizations(self):
        """
        应用厂商特定优化
        
        调用厂商优化器的apply_optimizations方法
        """
        if not self.device.profile:
            logger.warning("GPU型号配置未加载,跳过优化")
            return
        
        try:
            self.vendor_handler.apply_optimizations(self.device, self.device.profile)
            logger.info("GPU厂商优化应用成功")
        except Exception as e:
            logger.error(f"应用GPU优化失败: {e}")
    
    def calculate_batch_size(self) -> int:
        """
        计算最优batch_size
        
        Returns:
            推荐的batch_size值
        """
        if not self.device.profile:
            # 未找到配置,使用默认值
            logger.warning("GPU型号配置未加载,使用默认batch_size")
            return 65536
        
        try:
            return self.vendor_handler.calculate_batch_size(
                self.device, 
                self.device.profile
            )
        except Exception as e:
            logger.error(f"计算batch_size失败: {e},使用默认值")
            return 65536
    
    def compile_kernel(self, kernel_source: str):
        """
        编译OpenCL内核
        
        Args:
            kernel_source: OpenCL内核源码
            
        Returns:
            编译后的Program对象
        """
        try:
            import pyopencl as cl
            
            # 应用厂商特定的编译选项
            build_options = self._get_build_options()
            
            # 编译内核
            self.program = cl.Program(
                self.device.context, 
                kernel_source
            ).build(options=build_options)
            
            logger.info("OpenCL内核编译成功")
            return self.program
            
        except Exception as e:
            logger.error(f"OpenCL内核编译失败: {e}")
            raise RuntimeError(f"GPU内核编译失败: {e}")
    
    def _get_build_options(self) -> str:
        """
        获取厂商特定的编译选项
        
        Returns:
            编译选项字符串
        """
        options = []
        
        # 根据厂商添加特定选项
        vendor = self.vendor_handler.get_vendor_name()
        
        if vendor == "NVIDIA":
            # NVIDIA优化选项
            options.append("-cl-fast-relaxed-math")
        
        elif vendor == "AMD":
            # AMD优化选项
            options.append("-cl-std=CL2.0")
        
        elif vendor == "Intel":
            # Intel选项(v2.2.1优化: 添加快速数学选项)
            options.append("-cl-std=CL2.0")
            # v2.2.1: 启用快速数学优化(测试稳定后保留)
            options.append("-cl-fast-relaxed-math")
        
        return " ".join(options)
    
    def get_vendor_handler(self) -> GPUVendorBase:
        """获取厂商优化器"""
        return self.vendor_handler
    
    def cleanup(self):
        """释放资源"""
        if self.program:
            self.program = None
        
        logger.info("GPU上下文已清理")
