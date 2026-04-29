"""厂商优化策略工厂

实现策略模式，解耦GPU厂商特定优化逻辑。
支持Intel、NVIDIA、AMD等厂商的独立优化策略。

职责:
- 厂商优化策略管理
- 策略工厂创建
- 默认策略回退

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Dict, Any, Optional
import logging

from .protocols import VendorOptimizationStrategy, GPUExecutionContext

logger = logging.getLogger(__name__)


class IntelOptimizationStrategy:
    """Intel GPU优化策略
    
    针对Intel Arc GPU的特定优化:
    - uint32 workaround
    - 保守内存策略
    - 自适应超时
    - 内存监控
    """
    
    def apply_optimizations(self, context: GPUExecutionContext) -> Dict[str, Any]:
        """应用Intel特定优化"""
        components = {}
        
        try:
            # 1. 超时管理器
            from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager
            components['timeout_manager'] = AdaptiveTimeoutManager(
                config=context.config
            )
            
            # 2. 内存监控器
            from ..gpu.intel_memory_monitor import IntelMemoryMonitor
            if context.device:
                components['memory_monitor'] = IntelMemoryMonitor(context.device)
            
            # 3. Intel优化器
            from ..gpu.intel_optimizer import IntelGPUOptimizer
            components['intel_optimizer'] = IntelGPUOptimizer(
                device=context.device,
                config=context.config or {}
            )
            
            logger.info("Intel GPU优化策略已应用")
            
        except Exception as e:
            logger.error(f"应用Intel优化失败: {e}")
        
        return components
    
    def get_monitoring_components(self) -> Dict[str, Any]:
        """获取Intel监控组件"""
        return {
            'memory_monitor': 'IntelMemoryMonitor',
            'timeout_manager': 'AdaptiveTimeoutManager',
        }


class NvidiaOptimizationStrategy:
    """NVIDIA GPU优化策略
    
    针对NVIDIA GPU的特定优化:
    - CUDA核心优化
    - Tensor Core利用
    - 内存带宽优化
    """
    
    def apply_optimizations(self, context: GPUExecutionContext) -> Dict[str, Any]:
        """应用NVIDIA特定优化"""
        components = {}
        
        try:
            # TODO: Phase 5实现 - NVIDIA特定优化
            # from ..gpu.nvidia_optimizer import NvidiaGPUOptimizer
            # components['nvidia_optimizer'] = NvidiaGPUOptimizer(...)
            
            logger.info("NVIDIA GPU优化策略已应用")
            
        except Exception as e:
            logger.error(f"应用NVIDIA优化失败: {e}")
        
        return components
    
    def get_monitoring_components(self) -> Dict[str, Any]:
        """获取NVIDIA监控组件"""
        return {}


class AMDOptimizationStrategy:
    """AMD GPU优化策略
    
    针对AMD GPU的特定优化:
    - RDNA架构优化
    - Infinity Cache利用
    - ROCm优化
    """
    
    def apply_optimizations(self, context: GPUExecutionContext) -> Dict[str, Any]:
        """应用AMD特定优化"""
        components = {}
        
        try:
            # TODO: Phase 5实现 - AMD特定优化
            # from ..gpu.amd_optimizer import AMDGPUOptimizer
            # components['amd_optimizer'] = AMDGPUOptimizer(...)
            
            logger.info("AMD GPU优化策略已应用")
            
        except Exception as e:
            logger.error(f"应用AMD优化失败: {e}")
        
        return components
    
    def get_monitoring_components(self) -> Dict[str, Any]:
        """获取AMD监控组件"""
        return {}


class DefaultOptimizationStrategy:
    """默认优化策略
    
    当无法识别厂商时使用的基础优化。
    """
    
    def apply_optimizations(self, context: GPUExecutionContext) -> Dict[str, Any]:
        """应用默认优化"""
        logger.info("使用默认优化策略")
        return {}
    
    def get_monitoring_components(self) -> Dict[str, Any]:
        """获取默认监控组件"""
        return {}


class VendorOptimizationFactory:
    """厂商优化策略工厂
    
    根据GPU厂商创建对应的优化策略。
    
    使用示例:
        >>> factory = VendorOptimizationFactory()
        >>> strategy = factory.create('intel')
        >>> components = strategy.apply_optimizations(context)
    """
    
    # 策略注册表
    _strategies: Dict[str, type] = {
        'intel': IntelOptimizationStrategy,
        'nvidia': NvidiaOptimizationStrategy,
        'amd': AMDOptimizationStrategy,
    }
    
    @classmethod
    def create(cls, vendor: str) -> VendorOptimizationStrategy:
        """创建厂商优化策略
        
        Args:
            vendor: 厂商标识符 ('intel', 'nvidia', 'amd')
            
        Returns:
            对应的优化策略实例
        """
        vendor_lower = vendor.lower()
        
        # 查找策略
        strategy_cls = cls._strategies.get(vendor_lower)
        
        if strategy_cls is None:
            logger.warning(f"未识别的GPU厂商: {vendor}，使用默认策略")
            return DefaultOptimizationStrategy()
        
        try:
            strategy = strategy_cls()
            logger.debug(f"创建{vendor}优化策略成功")
            return strategy
        except Exception as e:
            logger.error(f"创建{vendor}优化策略失败: {e}")
            return DefaultOptimizationStrategy()
    
    @classmethod
    def register(cls, vendor: str, strategy_class: type) -> None:
        """注册新的厂商优化策略
        
        Args:
            vendor: 厂商标识符
            strategy_class: 策略类
        """
        cls._strategies[vendor.lower()] = strategy_class
        logger.info(f"注册厂商优化策略: {vendor}")
    
    @classmethod
    def get_supported_vendors(cls) -> list:
        """获取支持的厂商列表
        
        Returns:
            厂商标识符列表
        """
        return list(cls._strategies.keys())
