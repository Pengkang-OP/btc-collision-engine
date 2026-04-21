"""GPU内核协议定义

定义GPU内核的标准接口，用于依赖注入和测试Mock（P1-2修复）。
解耦GPU引擎和具体内核实现。

创建日期: 2026-04-22
"""
from typing import Protocol, List, Dict, Any, Type, runtime_checkable
from abc import abstractmethod


@runtime_checkable
class GPUKernelProtocol(Protocol):
    """GPU内核接口
    
    所有GPU内核实现必须遵循此接口。
    用于解耦GPU引擎和具体内核实现，支持：
    1. 依赖注入
    2. 单元测试Mock
    3. 多内核实现（OpenCL, CUDA, etc.）
    
    使用示例:
        >>> from src.gpu.kernel_protocol import GPUKernelProtocol
        >>> from src.gpu.kernel import GPUKernel
        >>> 
        >>> # 使用接口类型标注
        >>> kernel: GPUKernelProtocol = GPUKernel(device, max_batch_size=65536)
        >>> 
        >>> # 运行时检查
        >>> isinstance(kernel, GPUKernelProtocol)
        True
    """
    
    @abstractmethod
    def run_batch(self, private_keys: bytes, num_keys: int) -> List[Dict[str, int]]:
        """执行一批私钥计算
        
        Args:
            private_keys: 私钥字节串（每个私钥32字节）
            num_keys: 私钥数量
            
        Returns:
            匹配结果列表，每个元素包含:
                - key_index: 匹配的私钥索引
                - target_index: 匹配的目标地址索引
                
        Raises:
            RuntimeError: GPU执行失败
            ValueError: 参数无效
        """
        ...
    
    @abstractmethod
    def set_targets(self, target_hash160s: bytes, num_targets: int) -> None:
        """设置目标地址Hash160
        
        只需在初始化时设置一次，后续批次自动复用。
        
        Args:
            target_hash160s: 目标Hash160字节串（每个20字节）
            num_targets: 目标地址数量
            
        Raises:
            RuntimeError: GPU内存分配失败
            ValueError: 目标数据无效
        """
        ...
    
    @abstractmethod
    def cleanup(self) -> None:
        """清理GPU资源
        
        释放所有GPU内存缓冲区，重置内核状态。
        应在引擎停止时调用。
        
        Raises:
            RuntimeError: 资源清理失败
        """
        ...
    
    @property
    @abstractmethod
    def max_batch_size(self) -> int:
        """最大批次大小
        
        GPU内核能够处理的最大私钥数量。
        基于GPU显存大小自动计算。
        
        Returns:
            最大批次大小（正整数）
        """
        ...
    
    @property
    @abstractmethod
    def device(self) -> Any:
        """GPU设备对象
        
        Returns:
            GPUDevice实例
        """
        ...
    
    @property
    @abstractmethod
    def program(self) -> Any:
        """已编译的OpenCL程序
        
        Returns:
            pyopencl.Program实例
        """
        ...


class GPUKernelFactory:
    """GPU内核工厂
    
    用于创建GPU内核实例，支持依赖注入。
    
    使用示例:
        >>> from src.gpu.kernel_protocol import GPUKernelFactory
        >>> from src.gpu.kernel import GPUKernel
        >>> 
        >>> # 注册默认工厂
        >>> GPUKernelFactory.register(GPUKernel)
        >>> 
        >>> # 创建内核
        >>> kernel = GPUKernelFactory.create(device, max_batch_size=65536)
    """
    
    # P3优化：添加类型提示
    _kernel_class: Type[GPUKernelProtocol] = None  # type: ignore
    
    @classmethod
    def register(cls, kernel_class: Type[GPUKernelProtocol]) -> None:
        """注册内核类
        
        Args:
            kernel_class: GPU内核实现类（必须实现GPUKernelProtocol接口）
            
        Example:
            >>> from src.gpu.kernel import GPUKernel
            >>> GPUKernelFactory.register(GPUKernel)
        """
        cls._kernel_class = kernel_class
    
    @classmethod
    def create(cls, device, max_batch_size: int = None, program=None) -> GPUKernelProtocol:
        """创建GPU内核实例
        
        Args:
            device: GPUDevice实例
            max_batch_size: 最大批次大小（可选）
            program: 已编译的OpenCL程序（可选）
            
        Returns:
            GPUKernelProtocol实例
            
        Raises:
            ValueError: 未注册内核类
        """
        if cls._kernel_class is None:
            raise ValueError("未注册GPU内核类，请先调用 GPUKernelFactory.register()")
        
        return cls._kernel_class(device, max_batch_size=max_batch_size, program=program)
    
    @classmethod
    def reset(cls):
        """重置工厂（用于测试）"""
        cls._kernel_class = None
