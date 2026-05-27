"""GPU碰撞引擎接口协议定义.

定义所有组件的接口协议，遵循依赖倒置原则(DIP)。
所有实现类都应该实现这些接口。

版本: v4.2.2 Phase 6.1
创建日期: 2026-04-29
更新日期: 2026-05-23

使用说明:
- Phase 6: 定义了核心协议接口
- Phase 6.1: GPUCollisionEngine开始支持通过参数注入实现这些协议的具体类
- 推荐实现这些接口以获得更好的可测试性和灵活性

当前支持注入的组件:
- IGPUDeviceManager: 通过 device_manager_class 参数注入
- ISearchModeCoordinator: 通过 search_coordinator_class 参数注入（未来支持）
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

# ========== GPU类型定义 ==========


class GPUDeviceInfo(TypedDict, total=False):
    """GPU设备信息."""

    device_id: int
    vendor: str
    name: str
    memory_total: int  # 字节
    memory_free: int  # 字节
    compute_units: int
    clock_frequency: int  # MHz
    platform: str  # 'OpenCL', 'CUDA', etc.


class GPUDevice:
    """GPU设备实例（轻量级封装）."""

    def __init__(
        self,
        device_id: int = -1,
        vendor: str = "unknown",
        name: str = "",
        memory_total: int = 0,
        device_obj: Any = None,
    ) -> None:
        self.device_id = device_id
        self.vendor = vendor
        self.name = name
        self.memory_total = memory_total
        self.device_obj = device_obj  # 底层GPU对象（cl.Device等）

    def to_dict(self) -> GPUDeviceInfo:
        return {
            "device_id": self.device_id,
            "vendor": self.vendor,
            "name": self.name,
            "memory_total": self.memory_total,
        }


class GPUContext:
    """GPU上下文封装."""

    def __init__(self, context_obj: Any = None, device: GPUDevice | None = None) -> None:
        self.context_obj = context_obj  # 底层上下文对象（cl.Context等）
        self.device = device


class GPUKernel:
    """GPU内核封装."""

    def __init__(
        self,
        kernel_obj: Any = None,
        name: str = "",
        context: GPUContext | None = None,
    ) -> None:
        self.kernel_obj = kernel_obj  # 底层内核对象（cl.Kernel等）
        self.name = name
        self.context = context


class MatchResult(TypedDict, total=False):
    """匹配结果."""

    address: str
    private_key: str
    public_key: str
    hash160: str
    index: int
    seed: str
    private_key_hash: str


class IGPUDeviceManager(Protocol):
    """GPU设备管理器接口."""

    def list_devices(self) -> list[GPUDevice]:
        """列出所有可用GPU设备.

        Returns:
            GPU设备列表

        """
        ...

    def select_device(self, device_index: int = -1) -> GPUDevice:
        """选择GPU设备.

        Args:
            device_index: 设备索引，-1表示自动选择

        Returns:
            GPU设备实例

        """
        ...

    def create_context(self, device: GPUDevice) -> GPUContext:
        """创建GPU上下文.

        Args:
            device: GPU设备实例

        Returns:
            GPU上下文实例

        """
        ...

    def release_all(self) -> None:
        """释放所有GPU资源."""
        ...


class IKernelExecutor(Protocol):
    """GPU内核执行器接口."""

    def compile_kernel(self, device: GPUDevice, context: GPUContext) -> GPUKernel:
        """编译GPU内核.

        Args:
            device: GPU设备
            context: GPU上下文

        Returns:
            GPU内核实例

        """
        ...

    def execute_batch(
        self,
        kernel: GPUKernel,
        seed: bytes,
        batch_size: int,
        stop_event: Any = None,
    ) -> tuple[list[MatchResult], float]:
        """执行单个批次.

        Args:
            kernel: GPU内核
            seed: 32字节随机种子
            batch_size: 批次大小
            stop_event: 停止事件

        Returns:
            (匹配结果列表, 执行时间ms)

        """
        ...


class IAsyncExecutionPipeline(Protocol):
    """异步执行管道接口."""

    def initialize(self, kernel: GPUKernel, batch_size: int) -> None:
        """初始化异步管道.

        Args:
            kernel: GPU内核
            batch_size: 批次大小

        """
        ...

    def is_ready(self) -> bool:
        """检查管道是否就绪.

        Returns:
            是否就绪

        """
        ...

    def run_batch(self, seed: bytes, batch_size: int) -> tuple[list[MatchResult], float]:
        """运行单个批次.

        Args:
            seed: 随机种子
            batch_size: 批次大小

        Returns:
            (匹配结果列表, 执行时间ms)

        """
        ...

    def cleanup(self) -> None:
        """清理异步管道资源."""
        ...


class IMonitoringPipeline(Protocol):
    """监控管道接口."""

    def start(self) -> None:
        """启动所有监控器."""
        ...

    def stop(self) -> None:
        """停止所有监控器."""
        ...

    def record_metrics(self, batch_size: int, execution_time_ms: float, **metrics: Any) -> None:
        """记录性能指标.

        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间(毫秒)
            **metrics: 其他指标

        """
        ...

    def flush(self) -> None:
        """刷写所有缓冲数据."""
        ...


class ICollisionCore(Protocol):
    """碰撞核心接口."""

    def start(self, mode: str = "random", **kwargs) -> None:
        """启动碰撞.

        Args:
            mode: 碰撞模式 (random/range/brute_force)
            **kwargs: 其他参数

        """
        ...

    def stop(self) -> None:
        """停止碰撞."""
        ...

    def pause(self) -> None:
        """暂停碰撞."""
        ...

    def resume(self) -> None:
        """恢复碰撞."""
        ...

    def reset(self) -> None:
        """重置统计."""
        ...

    def on_batch_complete(self, matches: list[MatchResult], batch_size: int) -> None:
        """批次完成回调.

        Args:
            matches: 匹配结果列表
            batch_size: 批次大小

        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """获取碰撞统计.

        Returns:
            统计信息字典

        """
        ...


@dataclass
class GPUExecutionContext:
    """GPU执行上下文.

    包含GPU执行所需的所有资源和配置。

    v4.2.1 新增: engine 字段，用于传递 GPU 引擎实例给厂商优化器，
    使 benchmark_suite / auto_tuner / performance_reporter 等 P2 组件能够初始化。
    """

    device: GPUDevice | None = None
    context: GPUContext | None = None
    kernel: GPUKernel | None = None
    batch_size: int = 1_000_000
    vendor: str = "unknown"
    config: dict[str, Any] | None = None
    initialized_at: float = 0.0  # 初始化时间戳
    engine: Any | None = None  # v4.2.1: GPU 引擎实例引用（用于 P2 组件初始化）


@dataclass
class CollisionResult:
    """碰撞结果.

    单次批次执行的完整结果。
    """

    matches: list[MatchResult] = field(default_factory=list)
    execution_time_ms: float = 0.0
    batch_size: int = 0
    total_checked: int = 0
    gpu_errors: int = 0
    keys_per_second: float = 0.0  # 性能指标
    device_id: int = -1  # 多GPU追踪
    timestamp: float = 0.0  # 时间戳
    seed: bytes | None = None  # 可追溯性

    def __post_init__(self) -> None:
        """计算派生字段."""
        if self.execution_time_ms > 0 and self.batch_size > 0:
            self.keys_per_second = self.batch_size / (self.execution_time_ms / 1000.0)
        if self.timestamp == 0.0:
            import time

            self.timestamp = time.time()


class VendorOptimizationStrategy(Protocol):
    """厂商优化策略接口."""

    def apply_optimizations(self, context: GPUExecutionContext) -> dict[str, Any]:
        """应用厂商特定优化.

        Args:
            context: GPU执行上下文

        Returns:
            优化后的组件字典

        """
        ...

    def get_monitoring_components(self) -> dict[str, Any]:
        """获取厂商特定监控组件.

        Returns:
            监控组件字典

        """
        ...
