"""GPU上下文管理

管理GPU设备上下文、厂商优化器和内核编译。
"""

import hashlib
import logging
from typing import Dict, Any

# P3-5: 统一日志获取
from ..utils import init_logging, get_configured_logger

from .device import GPUDevice, identify_vendor
from .vendors.base import GPUVendorBase
from .vendors.nvidia import NVIDIAGPUVendor
from .vendors.amd import AMDGPUVendor
from .vendors.intel import IntelGPUVendor

logger = get_configured_logger("GPUContext")


# 厂商编译选项配置
# 注意: 加密/哈希运算（椭圆曲线、SHA256、RIPEMD160）不使用 -cl-fast-relaxed-math，
# 快速数学优化会破坏加密精度，仅 NVIDIA 在验证稳定的情况下保留。
VENDOR_BUILD_OPTIONS = {
    'nvidia': {
        'options': ['-cl-fast-relaxed-math'],  # NVIDIA: 快速数学经测试可接受
        'cl_version': None,  # NVIDIA默认CL1.2即可
        'description': 'NVIDIA优化：启用快速数学加速（需确认精度可接受）'
    },
    'amd': {
        'options': ['-cl-std=CL2.0'],  # AMD: 不用fast-math（精度风险）
        'cl_version': 'CL2.0',
        'description': 'AMD优化：CL2.0标准，精度优先'
    },
    'intel': {
        'options': ['-cl-std=CL2.0'],  # Intel: 不用fast-math（已知精度问题）
        'cl_version': 'CL2.0',
        'intel_workarounds': True,
        'description': 'Intel优化：CL2.0标准，启用workarounds，移除快速数学'
    }
}


class GPUContext:
    """
    GPU上下文管理器
    
    负责:
    1. 创建厂商特定的优化器
    2. 应用厂商优化策略
    3. 管理OpenCL内核编译
    4. 资源清理
    """
    
    def __init__(self, device: GPUDevice) -> None:
        """
        初始化GPU上下文
        
        Args:
            device: 已初始化的GPUDevice实例
        """
        self.device = device
        self.vendor_handler = self._create_vendor_handler()
        self.program = None
        
        # 内核编译缓存: source_hash -> compiled_program
        # OpenCL Program 不能跨 context 共享，每个 context 独立编译。
        # 但对于同厂商同源码的多次编译请求，使用源码哈希避免重复编译。
        self._kernel_cache: Dict[str, Any] = {}
        
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
    
    def apply_optimizations(self) -> None:
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
    
    def compile_kernel(self, kernel_source: str) -> Any:
        """
        编译OpenCL内核（自动使用内核缓存）
        
        Args:
            kernel_source: OpenCL内核源码
            
        Returns:
            编译后的Program对象
        """
        return self._get_or_compile_kernel(kernel_source)
    
    def _get_or_compile_kernel(self, kernel_source: str):
        """
        获取或编译OpenCL内核（内核缓存）
        
        OpenCL Program 不能跨 context 共享，但同一 context 内相同源码可以复用。
        缓存策略: 以 (source_hash + build_options) 为键，避免同一 context 内
        重复编译相同源码的内核。
        
        Args:
            kernel_source: OpenCL内核源码
            
        Returns:
            编译后的Program对象
        """
        build_options = self._get_build_options()
        
        # 计算缓存键: 源码哈希 + 编译选项
        source_hash = hashlib.md5(kernel_source.encode('utf-8'), usedforsecurity=False).hexdigest()[:16]
        cache_key = f"{source_hash}_{build_options.replace(' ', '_')}"
        
        # 检查缓存
        if cache_key in self._kernel_cache:
            logger.info(
                f"复用已编译内核 [厂商={self.vendor_handler.get_vendor_name()}, "
                f"source_hash={source_hash}]"
            )
            self.program = self._kernel_cache[cache_key]
            return self.program
        
        try:
            import pyopencl as cl
            
            logger.info(
                f"编译新内核 [厂商={self.vendor_handler.get_vendor_name()}, "
                f"options='{build_options}', source_hash={source_hash}]"
            )
            
            # 编译内核
            self.program = cl.Program(
                self.device.context, 
                kernel_source
            ).build(options=build_options)
            
            # 存入缓存
            self._kernel_cache[cache_key] = self.program
            logger.info(
                f"OpenCL内核编译成功，已存入缓存 (key={cache_key})"
            )
            return self.program
            
        except Exception as e:
            logger.error(f"OpenCL内核编译失败: {e}")
            raise RuntimeError(f"GPU内核编译失败: {e}")
    
    def _get_build_options(self) -> str:
        """
        获取厂商特定的编译选项
        
        使用 VENDOR_BUILD_OPTIONS 配置表，按厂商返回精细化编译选项。
        
        AMD/Intel 不使用 -cl-fast-relaxed-math：
          加密哈希运算（椭圆曲线、SHA256/RIPEMD160）需要严格数学精度，
          快速数学优化会导致运算结果错误。
        
        Returns:
            编译选项字符串
        """
        vendor_name = self.vendor_handler.get_vendor_name().lower()
        
        # 从配置表获取编译选项
        vendor_cfg = VENDOR_BUILD_OPTIONS.get(vendor_name)
        if vendor_cfg is not None:
            options = vendor_cfg['options'][:]
            logger.debug(
                f"使用厂商编译配置 [{vendor_name}]: {' '.join(options)} "
                f"— {vendor_cfg['description']}"
            )
            return " ".join(options)
        
        # 未知厂商：使用保守默认选项（不启用快速数学）
        logger.warning(
            f"未知GPU厂商 '{vendor_name}'，使用默认编译选项（无快速数学）"
        )
        return ""
    
    def get_vendor_handler(self) -> GPUVendorBase:
        """获取厂商优化器"""
        return self.vendor_handler
    
    def cleanup(self) -> None:
        """释放资源（尽力而为）"""
        # 先清理内核缓存，再清理 program
        try:
            if hasattr(self, '_kernel_cache') and self._kernel_cache:
                self._kernel_cache.clear()
                logger.debug("GPU内核缓存已清理")
        except Exception as e:
            logger.warning(f"清理GPU内核缓存失败: {e}")
        
        try:
            if self.program:
                self.program = None
        except Exception as e:
            logger.debug(f"清理GPU program引用失败（可忽略）: {e}")
        
        logger.info("GPU上下文已清理")
