"""GPU内核协议定义.

定义GPU内核的标准接口，用于依赖注入和测试Mock（P1-2修复）。
解耦GPU引擎和具体内核实现。

创建日期: 2026-04-22
"""

from typing import Any, Protocol, cast, runtime_checkable

__all__ = ["GPUKernelFactory", "GPUKernelProtocol"]


@runtime_checkable
class GPUKernelProtocol(Protocol):
    """GPU内核接口.

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

    def run_batch(self, seed: bytes, num_keys: int) -> list[dict[str, int]]:
        """执行一批密钥碰撞计算（PRNG模式）.

        v4.2.1 PRNG改造：CPU仅传递32字节随机种子，GPU内核自行生成
        每个工作单元的私钥（key = seed XOR gid），大幅减少PCIe传输量。

        Args:
            seed: 32字节随机种子（替代原 private_keys 大缓冲区）
            num_keys: 本批次生成的私钥数量

        Returns:
            匹配结果列表，每个元素包含:
                - key_index: 匹配的私钥索引
                - target_index: 匹配的目标地址索引

        Raises:
            RuntimeError: GPU执行失败
            ValueError: 参数无效（seed长度不足32字节，或num_keys <= 0）

        """
        ...

    def set_targets(
        self,
        target_hash160s: bytes,
        num_targets: int,
        check_uncompressed: int = 0,
    ) -> None:
        """设置目标地址Hash160.

        只需在初始化时设置一次，后续批次自动复用。

        Args:
            target_hash160s: 目标Hash160字节串（每个20字节）
            num_targets: 目标地址数量
            check_uncompressed: 是否同时检查非压缩格式 (0=仅压缩, 1=双格式)

        Raises:
            RuntimeError: GPU内存分配失败
            ValueError: 目标数据无效

        """
        ...

    def cleanup(self) -> None:
        """清理GPU资源.

        释放所有GPU内存缓冲区，重置内核状态。
        应在引擎停止时调用。

        Raises:
            RuntimeError: 资源清理失败

        """
        ...

    @property
    def max_batch_size(self) -> int:
        """最大批次大小.

        GPU内核能够处理的最大私钥数量。
        基于GPU显存大小自动计算。

        Returns:
            最大批次大小（正整数）

        """
        ...

    @property
    def device(self) -> Any:
        """GPU设备对象.

        Returns:
            GPUDevice实例

        """
        ...

    @property
    def program(self) -> Any:
        """已编译的OpenCL程序.

        Returns:
            pyopencl.Program实例

        """
        ...


class GPUKernelFactory:
    """GPU内核工厂.

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
    _kernel_class: type[GPUKernelProtocol] | None = None

    @classmethod
    def register(cls, kernel_class: type[GPUKernelProtocol]) -> None:
        """注册内核类.

        Args:
            kernel_class: GPU内核实现类（必须实现GPUKernelProtocol接口）

        Example:
            >>> from src.gpu.kernel import GPUKernel
            >>> GPUKernelFactory.register(GPUKernel)

        """
        cls._kernel_class = kernel_class

    @classmethod
    def create(
        cls,
        device: Any,
        max_batch_size: int | None = None,
        program: Any = None,
    ) -> GPUKernelProtocol:
        """创建GPU内核实例.

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
        if cls._kernel_class is None:  # mypy: narrow from None check above
            raise RuntimeError("GPUKernelFactory.create(): cls._kernel_class is None after check")
        return cls._kernel_class(  # type: ignore[call-arg]
            device,
            max_batch_size=max_batch_size,
            program=program,
        )

    @classmethod
    def reset(cls) -> None:
        """重置工厂（用于测试）."""
        cls._kernel_class = cast("type[GPUKernelProtocol] | None", None)
