# GPU引擎异步日志使用示例

**版本**: v2.2.1  
**更新日期**: 2026-04-23  

---

## 快速开始

### 1. 基本使用

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 启用异步日志（推荐用于生产环境）
engine = GPUCollisionEngine(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    device_index=1,
    batch_size=65536,
    use_async_logging=True,  # 启用异步日志
    async_log_file="logs/gpu_async.log",
    async_log_max_bytes=10*1024*1024,  # 10MB
    async_log_backup_count=5
)

try:
    engine.run()
finally:
    engine.cleanup()  # 自动关闭异步日志
```

### 2. 通过配置文件使用

**config.json**:

```json
{
  "gpu": {
    "use_gpu": true,
    "device_index": 1,
    "batch_size": 65536,
    "logging": {
      "use_async": true,
      "async_log_file": "logs/gpu_async.log",
      "async_max_bytes": 10485760,
      "async_backup_count": 5,
      "async_queue_size": 10000
    }
  }
}
```

**加载配置**:

```python
import json
from src.collision.gpu_collision_engine import GPUCollisionEngine

with open('config.json', 'r') as f:
    config = json.load(f)

gpu_config = config.get('gpu', {})
log_config = gpu_config.get('logging', {})

engine = GPUCollisionEngine(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    device_index=gpu_config.get('device_index', 1),
    batch_size=gpu_config.get('batch_size', 65536),
    use_async_logging=log_config.get('use_async', False),
    async_log_file=log_config.get('async_log_file', 'logs/gpu_async.log'),
    async_log_max_bytes=log_config.get('async_max_bytes', 10*1024*1024),
    async_log_backup_count=log_config.get('async_backup_count', 5)
)
```

---

## 性能监控

### 检查异步日志状态

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine

engine = GPUCollisionEngine(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    use_async_logging=True
)

# 运行一段时间后检查状态
if engine._async_log_handler:
    stats = engine._async_log_handler.get_stats()
    print(f"异步日志状态:")
    print(f"  队列大小: {stats['queue_size']}")
    print(f"  丢弃数量: {stats['dropped_count']}")
    print(f"  运行状态: {'正常' if stats['is_running'] else '已停止'}")
    
    # 告警检查
    if stats['queue_size'] > 5000:
        print("⚠️ 警告: 异步日志队列积压严重")
    if stats['dropped_count'] > 100:
        print("❌ 错误: 异步日志丢弃过多")
```

---

## 高级配置

### 1. 自定义队列大小

```python
# 高吞吐量场景（GPU batch_size > 100000）
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True,
    async_log_file="logs/gpu_high_throughput.log",
    # 增加队列大小以应对高频日志
    # 注意：这会增加内存占用（每10000条约5MB）
)

# 手动修改队列大小（如果需要）
if engine._async_log_handler:
    engine._async_log_handler._async_logger._queue.maxsize = 50000
```

### 2. 日志轮转策略

```python
# 大日志文件（适合长时间运行）
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True,
    async_log_file="logs/gpu_long_running.log",
    async_log_max_bytes=50*1024*1024,  # 50MB
    async_log_backup_count=10  # 保留10个备份
)
```

### 3. 调试模式

```python
# 启用详细调试日志
import logging
from src.collision.gpu_collision_engine import GPUCollisionEngine, logger

engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True
)

# 设置logger级别为DEBUG
logger.setLevel(logging.DEBUG)

# 现在会记录所有调试信息到异步日志
```

---

## 故障排除

### Q1: 异步日志未启用？

**检查步骤**:

```python
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True
)

# 1. 检查是否正确初始化
if engine._async_log_handler is None:
    print("异步日志未初始化")
    
    # 2. 检查AsyncFileHandler是否可用
    from src.collision.gpu_collision_engine import ASYNC_LOG_AVAILABLE
    if not ASYNC_LOG_AVAILABLE:
        print("错误: AsyncFileHandler导入失败")
        print("请确保 src/utils/logger.py 包含 AsyncFileHandler 类")
```

**解决方案**:

```bash
# 检查logger.py是否包含AsyncFileHandler
grep -n "class AsyncFileHandler" src/utils/logger.py

# 如果没有，运行核心模块修复
python tests/verify_threadsafe_replacement.py
```

### Q2: 日志丢弃过多？

**症状**: `dropped_count > 100`

**原因**: 日志产生速度超过写入速度

**解决方案**:

```python
# 方案1: 增加队列大小
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True
)
if engine._async_log_handler:
    engine._async_log_handler._async_logger._queue.maxsize = 50000

# 方案2: 降低日志级别
import logging
logger.setLevel(logging.WARNING)  # 只记录WARNING及以上

# 方案3: 使用采样日志（在高频循环中）
from src.utils.logger import SampledLogger
sampled_logger = SampledLogger(logger, sample_rate=100)
```

### Q3: 程序退出时日志丢失？

**原因**: 未调用 `cleanup()`

**解决方案**:

```python
# ✅ 正确做法
try:
    engine.run()
finally:
    engine.cleanup()  # 这会等待队列清空再关闭

# ❌ 错误做法
engine.run()
# 忘记调用cleanup()，队列中的日志会丢失
```

---

## 性能基准

### 测试结果（2026-04-23）

| 场景 | 同步日志 | 异步日志 | 提升 |
|------|---------|---------|------|
| 单batch（10条日志） | ~5ms | ~1ms | **80%** |
| 1000 batches | ~5s | ~1s | **80%** |
| GPU引擎预期 | 基线 | +10-15% | **显著** |

### 内存占用

| 配置 | 内存占用 |
|------|---------|
| 默认队列（10000） | ~5MB |
| 大队列（50000） | ~25MB |
| 超大队列（100000） | ~50MB |

---

## 最佳实践

### 1. 生产环境配置

```python
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True,
    async_log_file="logs/gpu_production.log",
    async_log_max_bytes=20*1024*1024,  # 20MB
    async_log_backup_count=10,
    use_enhanced_monitoring=True
)
```

### 2. 开发环境配置

```python
# 开发环境不需要异步日志（方便调试）
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=False  # 使用同步日志
)
```

### 3. 长时间运行任务

```python
# 使用大日志文件 + 多备份
engine = GPUCollisionEngine(
    targets=targets,
    use_async_logging=True,
    async_log_file="logs/gpu_long_term.log",
    async_log_max_bytes=50*1024*1024,  # 50MB
    async_log_backup_count=20  # 保留20个备份（1GB）
)

# 定期检查日志状态
import time
while engine._running:
    time.sleep(60)  # 每分钟检查一次
    if engine._async_log_handler:
        stats = engine._async_log_handler.get_stats()
        if stats['dropped_count'] > 1000:
            logger.warning("日志丢弃过多，考虑增加队列大小")
```

---

## 降级策略

如果异步日志出现问题，可以自动降级到同步日志：

```python
def check_async_log_health(engine):
    """检查异步日志健康状态，必要时降级"""
    if not engine._async_log_handler:
        return
    
    stats = engine._async_log_handler.get_stats()
    
    # 如果丢弃率超过阈值，降级到同步
    if stats['dropped_count'] > 1000:
        logger.warning("异步日志丢弃过多，降级到同步日志")
        
        try:
            engine._async_log_handler.close()
            logger.removeHandler(engine._async_log_handler)
            engine._async_log_handler = None
            logger.info("已降级到同步日志")
        except Exception as e:
            logger.error(f"降级失败: {e}")
```

---

## 相关文档

- [GPU异步日志集成指南](file:///f:/Qoder/btc-collision-engine/docs/GPU_ASYNC_LOGGING_INTEGRATION_GUIDE.md)
- [核心模块修复报告](file:///f:/Qoder/btc-collision-engine/docs/CORE_MODULES_FIX_REPORT_20260423.md)
- [四步任务完成总结](file:///f:/Qoder/btc-collision-engine/docs/FOUR_TASKS_COMPLETION_SUMMARY.md)

---

**文档版本**: 1.0  
**维护人员**: BTC Collision Team  
**最后更新**: 2026-04-23
