# GPU碰撞引擎重构模块

本目录包含从`GPUCollisionEngine`解耦出来的核心组件。

## 模块结构

```
src/collision/gpu/
├── __init__.py                 # 模块入口，延迟导入
├── protocols.py                # 接口协议定义
├── facade.py                   # GPU引擎外观层（Phase 2 已实现）
├── device_manager_adapter.py   # GPU设备管理器适配器（Phase 2 新增）
├── kernel_adapter.py           # GPU内核适配器（Phase 2 完善）
├── async_pipeline_adapter.py   # 异步执行管道适配器（Phase 2 完善）
├── monitoring.py               # 性能监控管道
├── core.py                     # 碰撞核心逻辑
└── vendor_strategy.py          # 厂商优化策略工厂
```

## 重构目标

- **降低代码复杂度**: 1466行 → <400行 (-73%)
- **减少导入模块**: 49个 → <15个 (-70%)
- **提高可测试性**: Mock层从7+降到1-2
- **保持向后兼容**: API不变

## 使用示例

```python
from src.collision.gpu import (
    GPUEngineFacade,
    DeviceManagerAdapter,
    GPUKernelAdapter,
    AsyncPipelineAdapter,
)

# 1. 创建外观层
facade = GPUEngineFacade(config=config)
facade.initialize(device_index=-1, batch_size=1000000)

# 2. 设置目标地址
facade.set_targets(targets_set)

# 3. 执行批次
result = facade.execute_batch(seed, batch_size)

# 4. 预取下一批
facade.prefetch_next_batch(next_seed, batch_size)

# 5. 清理
facade.cleanup()
```

## 实施阶段

- ✅ **Phase 1**: 基础设施准备（协议定义、模块骨架）
- ✅ **Phase 2**: 外观层实现（设备适配器、内核适配器、异步管道适配器、facade增强）
- ⏳ **Phase 3**: 监控管道实现
- ⏳ **Phase 4**: 碰撞核心实现
- ⏳ **Phase 5**: 引擎协调器重构
- ⏳ **Phase 6**: 迁移验证

## Phase 2 实施详情

### 新增文件

- `device_manager_adapter.py`: 适配 GPUDevice/GPUDeviceDetector/GPUContext 到 IGPUDeviceManager 协议
  - `list_devices()`: 通过 GPUDeviceDetector 枚举设备
  - `select_device()`: 初始化底层 GPUDevice 并返回协议层 GPUDevice
  - `create_context()`: 创建 GPUContext 并应用优化
  - `release_all()`: 按序释放上下文和设备资源

### 增强文件

- `facade.py`: 移除全部4处TODO，新增功能：
  - `set_targets()`: 目标地址设置
  - `prefetch_next_batch()`: 异步预取
  - `flush_pending()`: 收集待处理结果
  - `get_device_info()`: 设备信息查询
  - `get_async_stats()`: 异步统计查询
  - `_apply_targets()`: 内核目标地址应用
  - `_apply_vendor_optimizations()`: 厂商优化集成
- `kernel_adapter.py`: 修正 GPUKernelImpl 构造参数，使用真实编译流程
- `async_pipeline_adapter.py`: 补全 `is_ready()`, `prefetch_next_batch()`, `flush_pending()`, `get_stats()` 方法

## 版本

- **版本**: v2.0
- **创建日期**: 2026-04-29
- **更新日期**: 2026-04-30
- **状态**: Phase 2 已完成
