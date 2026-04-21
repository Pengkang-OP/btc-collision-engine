# GPU自适应优化系统 - 快速参考

## 🚀 快速开始

### 1. 使用优化系统（自动模式）

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 创建引擎 - 自动启用性能优化
engine = GPUCollisionEngine(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    device_index=0,
    batch_size=None  # None = 自动优化
)

# 启动 - 系统会自动调整参数
engine.start(mode="random")
```

### 2. 查看优化状态

```python
from src.gpu.performance_optimizer import get_gpu_optimizer

optimizer = get_gpu_optimizer()
report = optimizer.get_optimization_report()

print(f"GPU: {report['profile']['device']}")
print(f"Batch Size: {report['profile']['batch_size']:,}")
print(f"平均速度: {report['performance']['avg_speed_keys_per_sec']:,.0f} keys/sec")
print(f"调整次数: {report['performance']['total_adjustments']}")
```

## 📊 厂商默认配置

| GPU厂商 | Batch Size | Work Group | 内存使用率 | 特殊优化 |
|--------|-----------|-----------|-----------|---------|
| **NVIDIA** | 1,048,576 | 256 | 70% | 异步+缓冲池 |
| **AMD** | 524,288 | 256 | 60% | 异步+缓冲池 |
| **Intel** | 262,144 | 128 | 50% | uint32 workaround |

## 🔄 自适应调整规则

### 何时减小 Batch Size？

| 条件 | 阈值 | 动作 |
|-----|------|------|
| 错误率过高 | > 1% | 减小 25% |
| 执行时间过长 | > 1000ms | 减小 25% |
| 显存不足 | < 2GB | 使用最小值 |

### 何时增大 Batch Size？

| 条件 | 阈值 | 动作 |
|-----|------|------|
| 性能良好 | 执行 < 500ms 且 错误 < 0.5% | 增加 8192 |

## 🎯 显存优化参考

| 显存大小 | Batch Size | 内存使用率 | 适用场景 |
|---------|-----------|-----------|---------|
| < 2GB | 1,024 | 30% | 低端GPU/集成显卡 |
| 2-4GB | 32,768 | 40% | 入门级独显 |
| 4-8GB | 65,536-131,072 | 50-60% | 中端独显 |
| 8GB+ | 131,072-2M | 70-80% | 高端独显 |

## 🔧 常见问题

### Q1: 如何知道优化系统是否在工作？

查看日志中的以下信息：
```
GPU性能优化器初始化完成
GPU配置已优化: NVIDIA GeForce RTX 3080, batch_size=2097152, work_group=256, mem_ratio=0.8
自适应优化: batch_size 100000 -> 108192 (performance_good)
```

### Q2: 如何禁用自动优化？

```python
# 使用固定batch_size
engine = GPUCollisionEngine(
    targets={...},
    batch_size=65536  # 固定值，不自动调整
)
```

### Q3: 错误率持续过高怎么办？

1. 检查GPU驱动是否最新
2. 降低 `memory_usage_ratio`（在config.json中）
3. 检查GPU温度和健康状态
4. 考虑使用更小的初始batch_size

### Q4: Intel Arc GPU注意事项

- ✅ 系统会自动启用 `uint32 workaround`
- ✅ 自动禁用异步执行（避免hang）
- ✅ 首次编译可能需要20-30秒（正常）
- ⚠️ 推荐使用 `range_scan` 模式

## 📈 性能监控

### 查看实时性能

优化系统会自动记录以下指标：
- 内核编译时间
- 批次执行时间
- 每秒处理密钥数
- 显存使用量
- 错误计数

### 获取优化建议

```python
report = optimizer.get_optimization_report()
for rec in report['recommendations']:
    print(f"建议: {rec}")
```

示例输出：
```
建议: 检测到4个错误，建议检查GPU驱动和显存使用
建议: NVIDIA GPU可以尝试提高显存使用率至60-70%
建议: Intel GPU建议启用uint32 workaround避免hang bug
```

## 📁 相关文件

| 文件 | 说明 |
|-----|------|
| `src/gpu/performance_optimizer.py` | 核心优化器实现 |
| `src/collision/gpu_collision_engine.py` | 集成点 |
| `tests/test_gpu_performance_optimizer.py` | 单元测试 |
| `GPU_PERFORMANCE_OPTIMIZATION.md` | 完整文档 |
| `demo_gpu_optimizer.py` | 演示脚本 |

## ⚡ 性能指标

- **优化器开销**: < 0.01% 吞吐量影响
- **内存占用**: < 100KB
- **调整频率**: 每10秒一次
- **分析耗时**: < 1ms

## 🎓 最佳实践

1. **首次运行**: 允许系统运行30秒以收集足够的性能数据
2. **监控日志**: 关注自适应调整日志，了解系统决策
3. **查看报告**: 定期调用 `get_optimization_report()` 获取建议
4. **保持驱动最新**: GPU驱动更新可能显著改善性能
5. **合理设置batch_size**: 使用 `None` 让系统自动选择

## 🔍 调试技巧

### 启用详细日志

```python
import logging
logging.getLogger('src.gpu.performance_optimizer').setLevel(logging.DEBUG)
```

### 手动触发调整

```python
optimizer = get_gpu_optimizer()
new_batch, adjustments = optimizer.analyze_and_adjust(
    current_batch_size=100000,
    error_rate=0.01
)
print(f"建议调整: {adjustments}")
```

### 重置优化器

```python
optimizer = get_gpu_optimizer()
optimizer.reset()  # 清除所有历史数据
```

---

**更多信息**: 查看 `GPU_PERFORMANCE_OPTIMIZATION.md` 获取完整文档
