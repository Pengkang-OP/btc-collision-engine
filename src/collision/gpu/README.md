# GPU碰撞引擎重构模块

本目录包含从`GPUCollisionEngine`解耦出来的核心组件。

## 模块结构

```
src/collision/gpu/
├── __init__.py              # 模块入口，延迟导入
├── protocols.py             # 接口协议定义
├── facade.py                # GPU引擎外观层
├── monitoring.py            # 性能监控管道
├── core.py                  # 碰撞核心逻辑
├── vendor_strategy.py       # 厂商优化策略工厂
├── kernel_adapter.py        # GPU内核适配器
└── async_pipeline_adapter.py # 异步执行管道适配器
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
    PerformanceMonitoringPipeline,
    CollisionCore,
    VendorOptimizationFactory,
)

# 1. 创建外观层
facade = GPUEngineFacade(config=config)
facade.initialize(device_index=-1, batch_size=1000000)

# 2. 创建监控管道
monitoring = PerformanceMonitoringPipeline(engine=engine, config=config)
monitoring.start()

# 3. 创建碰撞核心
core = CollisionCore(targets=targets, config=config)
core.start(mode='random')

# 4. 执行批次
result = facade.execute_batch(seed, batch_size)
core.on_batch_complete(result.matches, result.batch_size)
monitoring.record_metrics(
    batch_size=result.batch_size,
    execution_time_ms=result.execution_time_ms
)

# 5. 清理
core.stop()
monitoring.stop()
facade.cleanup()
```

## 实施阶段

- ✅ **Phase 1**: 基础设施准备（当前）
- ⏳ **Phase 2**: 外观层实现
- ⏳ **Phase 3**: 监控管道实现
- ⏳ **Phase 4**: 碰撞核心实现
- ⏳ **Phase 5**: 引擎协调器重构
- ⏳ **Phase 6**: 迁移验证

## 版本

- **版本**: v1.0
- **创建日期**: 2026-04-29
- **状态**: 开发中
