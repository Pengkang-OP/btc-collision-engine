# 日志记录标准规范

本文档定义BTC碰撞引擎项目的统一日志记录标准，包括日志格式、级别使用规范、性能监控和采样策略。

## 目录

- [1. 日志格式标准](#1-日志格式标准)
- [2. 日志级别使用规范](#2-日志级别使用规范)
- [3. 性能监控日志](#3-性能监控日志)
- [4. 采样日志策略](#4-采样日志策略)
- [5. 日志命名规范](#5-日志命名规范)
- [6. 最佳实践](#6-最佳实践)
- [7. 错误示例](#7-错误示例)

---

## 1. 日志格式标准

### 1.1 标准格式

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**示例输出**:
```
2026-04-20 23:10:15,234 - src.collision.key_collision_engine - INFO - GPU引擎初始化成功: RTX 3080
```

### 1.2 字段说明

| 字段 | 格式 | 说明 | 示例 |
|------|------|------|------|
| `asctime` | `YYYY-MM-DD HH:MM:SS,mmm` | 时间戳（含毫秒） | `2026-04-20 23:10:15,234` |
| `name` | 模块路径 | 日志记录器名称 | `src.collision.key_collision_engine` |
| `levelname` | 大写 | 日志级别 | `INFO`, `ERROR`, `WARNING` |
| `message` | 自定义 | 日志消息 | `GPU引擎初始化成功` |

### 1.3 控制台彩色输出

| 级别 | 颜色 | ANSI代码 |
|------|------|----------|
| DEBUG | 青色 | `\033[36m` |
| INFO | 绿色 | `\033[32m` |
| WARNING | 黄色 | `\033[33m` |
| ERROR | 红色 | `\033[31m` |
| CRITICAL | 紫色 | `\033[35m` |

### 1.4 文件日志格式

文件日志不使用颜色代码，保持纯文本格式：

```
2026-04-20 23:10:15,234 - src.collision.key_collision_engine - INFO - GPU引擎初始化成功: RTX 3080
```

---

## 2. 日志级别使用规范

### 2.1 DEBUG级别

**用途**: 详细的调试信息，仅在开发时启用

**使用场景**:
- ✅ 函数入口/出口追踪
- ✅ 变量值和状态变化
- ✅ 算法中间结果
- ✅ 配置加载细节

**示例**:
```python
logger.debug(f"加载配置文件: {config_file}")
logger.debug(f"batch_size={batch_size}, device_index={device_index}")
logger.debug(f"工作线程 {worker_id}: 开始处理批次 {batch_number}")
```

**注意事项**:
- ❌ 不要记录敏感信息（私钥、密码）
- ❌ 不要在生产环境默认启用
- ✅ 使用惰性格式化: `logger.debug("值=%s", value)`

### 2.2 INFO级别

**用途**: 一般运行信息，记录重要事件和状态变化

**使用场景**:
- ✅ 引擎初始化完成
- ✅ 配置加载成功
- ✅ 阶段性进度（每30秒或每100万次）
- ✅ 资源创建/销毁
- ✅ 模式切换

**示例**:
```python
logger.info(f"GPU引擎初始化成功: {device_name} (厂商: {vendor}, batch_size: {self.batch_size})")
logger.info(f"配置加载成功: {config_file}")
logger.info(f"碰撞引擎已启动，模式: {mode}")
logger.info(f"断点已保存: position={position}, checked={total_checked}")
```

**注意事项**:
- ✅ 包含关键上下文信息
- ✅ 使用人类可读的格式
- ✅ 记录重要操作的结果

### 2.3 WARNING级别

**用途**: 潜在问题，但不影响正常运行

**使用场景**:
- ✅ 配置项缺失（使用默认值）
- ✅ 性能降级
- ✅ 资源使用率高（>80%）
- ✅ 降级操作（fallback）
- ✅ 可恢复的错误

**示例**:
```python
logger.warning(f"GPU型号配置未找到，使用默认配置: {device_name}")
logger.warning(f"显存使用率过高: {usage:.1f}% > 80%")
logger.warning(f"目标地址格式无效 [{address}]: {error}")
logger.warning(f"批次处理失败（资源不足），跳过当前批次")
```

**注意事项**:
- ✅ 说明问题的影响
- ✅ 提供可能的解决方案
- ✅ 包含足够的上下文

### 2.4 ERROR级别

**用途**: 错误事件，影响功能但系统可继续运行

**使用场景**:
- ✅ 功能模块失败
- ✅ 资源分配失败
- ✅ 数据验证失败
- ✅ 外部服务不可用
- ✅ 不可恢复的批次错误

**示例**:
```python
logger.error(f"GPU初始化失败: {error}")
logger.error(f"OpenCL内核编译失败: {type(e).__name__}: {e}")
logger.error(f"文件不存在({operation}): {filepath}")
logger.error(f"配置验证失败: {errors}")
```

**注意事项**:
- ✅ 包含异常类型和消息
- ✅ 说明失败的操作
- ✅ 提供足够的调试信息
- ❌ 不要使用`logger.exception()`除非需要堆栈跟踪

### 2.5 EXCEPTION级别

**用途**: 记录异常及其完整堆栈跟踪

**使用场景**:
- ✅ 未知错误（捕获所有异常）
- ✅ 需要堆栈跟踪调试的错误
- ✅ 系统级错误

**示例**:
```python
try:
    result = complex_operation()
except Exception as e:
    logger.exception(f"未知错误发生: {operation_name}")
    # 自动包含完整堆栈跟踪
```

**注意事项**:
- ✅ 仅在`except`块中使用
- ✅ 自动包含`exc_info=True`
- ❌ 不要用于已知错误类型

### 2.6 CRITICAL级别

**用途**: 严重错误，系统可能无法继续运行

**使用场景**:
- ✅ 关键资源完全不可用
- ✅ 数据损坏
- ✅ 系统即将崩溃

**示例**:
```python
logger.critical(f"所有GPU设备不可用，无法继续执行")
logger.critical(f"配置文件损坏，无法加载: {config_file}")
```

---

## 3. 性能监控日志

### 3.1 PerformanceMonitor使用

**位置**: `src/utils/logger.py`

**基本用法**:
```python
from src.utils.logger import PerformanceMonitor

with PerformanceMonitor(logger, "GPU内核编译", level="INFO"):
    program = cl.Program(context, kernel_source).build()
```

**输出示例**:
```
2026-04-20 23:10:15,234 - src.collision.gpu_collision_engine - INFO - [Performance] GPU内核编译: 215.34ms
```

### 3.2 性能监控场景

| 操作 | 级别 | 说明 |
|------|------|------|
| 设备初始化 | INFO | GPU/CPU设备检测 |
| 内核编译 | INFO | OpenCL内核编译 |
| 配置加载 | DEBUG | 配置文件读取 |
| 批次处理 | DEBUG | 单个批次处理时间 |
| 断点保存 | INFO | 断点写入磁盘 |
| 数据日志 | DEBUG | 监控数据写入 |

### 3.3 自定义性能监控

```python
from src.utils.logger import PerformanceMonitor
import time

# 方式1: 上下文管理器（推荐）
with PerformanceMonitor(logger, "批量地址转换") as pm:
    addresses = convert_batch(keys)
    if pm.elapsed_ms > 100:  # 超过100ms警告
        logger.warning(f"批量地址转换耗时: {pm.elapsed_ms:.2f}ms")

# 方式2: 手动控制
pm = PerformanceMonitor(logger, "复杂计算")
pm.__enter__()
try:
    result = compute()
finally:
    pm.__exit__(None, None, None)
```

### 3.4 性能日志格式

```
[Performance] {operation_name}: {elapsed_ms:.2f}ms
[Performance] {operation_name}: FAILED after {elapsed_ms:.2f}ms - {error}
```

---

## 4. 采样日志策略

### 4.1 SampledLogger使用

**位置**: `src/utils/logger.py`

**基本用法**:
```python
from src.utils.logger import get_sampled_logger

# 创建采样日志器（每1000条记录1条）
sampled_logger = get_sampled_logger("KeyCollisionEngine.sampled", sample_rate=1000)

# 在高频循环中使用
for i in range(1000000):
    sampled_logger.info(f"进度: {i:,} 已检查, {speed:,.0f} 次/秒")
    # 实际只记录1000条日志
```

**输出示例**:
```
2026-04-20 23:10:15,234 - KeyCollisionEngine.sampled - INFO - [Sampled 1/1000] 进度: 1,000,000 已检查, 1,200,000 次/秒
```

### 4.2 采样率推荐

| 场景 | 频率 | 推荐采样率 | 说明 |
|------|------|-----------|------|
| 批次处理 | ~1000次/秒 | 1000 | 每秒记录1次 |
| 进度更新 | ~100次/秒 | 100 | 每秒记录1次 |
| 工作线程日志 | ~10次/秒 | 10 | 每秒记录1次 |
| GPU内核执行 | ~10000次/秒 | 10000 | 每秒记录1次 |

### 4.3 采样日志实现

```python
class SampledLogger:
    """采样日志记录器（用于高频操作）"""
    
    def __init__(self, logger: logging.Logger, sample_rate: int = 100):
        self.logger = logger
        self.sample_rate = sample_rate
        self._counter = 0
        self._lock = threading.Lock()
    
    def info(self, msg: str, *args, **kwargs):
        with self._lock:
            self._counter += 1
            if self._counter % self.sample_rate == 0:
                self.logger.info(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)
```

### 4.4 采样日志优势

- ✅ **减少I/O开销**: 降低日志写入频率99.9%
- ✅ **保持性能**: 不影响高频操作的性能
- ✅ **保留信息**: 仍然可以追踪趋势
- ✅ **线程安全**: 使用锁保护计数器

---

## 5. 日志命名规范

### 5.1 日志记录器命名

**格式**: `src.{module}.{submodule}`

**示例**:
```python
# 碰撞引擎
logger = logging.getLogger("src.collision.key_collision_engine")
logger = logging.getLogger("src.collision.gpu_collision_engine")

# GPU模块
logger = logging.getLogger("src.gpu.device")
logger = logging.getLogger("src.gpu.context")
logger = logging.getLogger("src.gpu.driver_manager")

# 配置模块
logger = logging.getLogger("src.config.config_manager")
logger = logging.getLogger("src.config.crypto_config")

# 监控模块
logger = logging.getLogger("src.monitoring.data_logger")
logger = logging.getLogger("src.monitoring.enhanced_monitoring")
```

### 5.2 特殊日志记录器

```python
# 采样日志
sampled_logger = get_sampled_logger("KeyCollisionEngine.sampled", sample_rate=1000)

# GPU监控
gpu_monitor_logger = logging.getLogger("GPUMonitor")

# 性能监控（使用PerformanceMonitor，不单独命名）
```

### 5.3 命名原则

- ✅ 使用模块路径作为名称
- ✅ 使用点号分隔层级
- ✅ 全部小写，下划线分隔
- ❌ 不要使用中文
- ❌ 不要使用缩写（除非是通用缩写如GPU、CPU）

---

## 6. 最佳实践

### 6.1 日志初始化

```python
from src.utils.logging_config import init_logging, get_configured_logger

# 在程序入口初始化
init_logging()

# 在模块中获取日志记录器
logger = get_configured_logger(__name__)
```

### 6.2 使用惰性格式化

```python
# ✅ 推荐: 惰性格式化
logger.info("GPU初始化成功: %s (batch_size: %d)", device_name, batch_size)

# ❌ 不推荐: 提前格式化（即使日志级别不匹配也会执行）
logger.info(f"GPU初始化成功: {device_name} (batch_size: {batch_size})")
```

### 6.3 包含关键上下文

```python
# ✅ 推荐: 包含上下文
logger.error(f"GPU批次处理失败 (device={device_index}, batch_size={batch_size}): {error}")

# ❌ 不推荐: 缺少上下文
logger.error(f"GPU处理失败: {error}")
```

### 6.4 避免敏感信息

```python
# ❌ 绝对禁止: 记录私钥
logger.debug(f"私钥: {private_key_hex}")

# ✅ 推荐: 记录地址或哈希
logger.debug(f"生成地址: {address}")
logger.debug(f"地址哈希: {hash160.hex()}")
```

### 6.5 异常处理日志

```python
try:
    result = gpu_kernel.run_batch(keys, batch_size)
except RuntimeError as e:
    # 已知错误类型，记录简要信息
    logger.error(f"GPU运行时错误: {type(e).__name__}: {e}")
except Exception as e:
    # 未知错误，记录完整堆栈
    logger.exception(f"GPU未知错误: {operation}")
```

### 6.6 进度日志优化

```python
# ✅ 推荐: 使用采样日志
sampled_logger.info(f"进度: {count:,} 已检查, {speed:,.0f} 次/秒")

# ✅ 推荐: 使用时间间隔
if time.time() - last_log_time > 1.0:  # 每秒记录一次
    logger.info(f"进度: {count:,} 已检查, {speed:,.0f} 次/秒")
    last_log_time = time.time()

# ❌ 不推荐: 每次都记录
logger.info(f"进度: {count:,}")  # 太快！
```

### 6.7 资源管理日志

```python
# 资源创建
logger.info(f"GPU设备初始化: {device_name}")

# 资源使用
logger.debug(f"GPU显存使用: {used_mb:.1f}MB / {total_mb:.1f}MB ({usage:.1f}%)")

# 资源释放
logger.info(f"GPU资源已清理: {device_name}")
```

---

## 7. 错误示例

### 7.1 日志格式错误

```python
# ❌ 错误: 缺少模块名称
logger = logging.getLogger()  # 使用根日志记录器

# ✅ 正确: 使用模块名称
logger = logging.getLogger(__name__)
```

### 7.2 日志级别滥用

```python
# ❌ 错误: 使用INFO记录调试信息
logger.info(f"变量值: x={x}, y={y}, z={z}")

# ✅ 正确: 使用DEBUG
logger.debug(f"变量值: x={x}, y={y}, z={z}")

# ❌ 错误: 使用WARNING记录正常信息
logger.warning("引擎启动成功")

# ✅ 正确: 使用INFO
logger.info("引擎启动成功")
```

### 7.3 敏感信息泄露

```python
# ❌ 绝对禁止
logger.debug(f"私钥: {private_key}")
logger.info(f"WIF: {wif}")
logger.error(f"密钥材料: {key_material.hex()}")

# ✅ 正确
logger.debug(f"地址: {address}")
logger.info(f"地址数量: {len(targets)}")
logger.error(f"地址格式无效: {invalid_address}")
```

### 7.4 性能问题

```python
# ❌ 错误: 高频操作不使用采样
for i in range(1000000):
    logger.info(f"处理: {i}")  # 写入100万次日志！

# ✅ 正确: 使用采样日志
for i in range(1000000):
    sampled_logger.info(f"处理: {i}")  # 只写入1000次日志

# ❌ 错误: 提前格式化字符串
logger.debug(f"复杂计算结果: {expensive_function()}")

# ✅ 正确: 惰性格式化
logger.debug("复杂计算结果: %s", expensive_function())
```

### 7.5 异常处理不当

```python
# ❌ 错误: 使用logger.info记录异常
try:
    do_something()
except Exception as e:
    logger.info(f"错误: {e}")  # 缺少堆栈跟踪

# ✅ 正确: 使用logger.exception
try:
    do_something()
except Exception as e:
    logger.exception(f"操作失败: {operation_name}")

# ❌ 错误: 吞掉异常不记录
try:
    do_something()
except Exception:
    pass  # 没有任何日志！

# ✅ 正确: 至少记录ERROR
try:
    do_something()
except Exception as e:
    logger.error(f"操作失败: {e}")
    raise
```

---

## 附录A: 日志配置示例

### A.1 config.json配置

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/collision.log",
    "max_bytes": 10485760,
    "backup_count": 5,
    "enable_console": true,
    "enable_file": true,
    "rotation_type": "size",
    "rotation_when": "midnight",
    "rotation_interval": 1,
    "compress_backups": false
  }
}
```

### A.2 开发环境配置

```json
{
  "logging": {
    "level": "DEBUG",
    "enable_console": true,
    "enable_file": true
  }
}
```

### A.3 生产环境配置

```json
{
  "logging": {
    "level": "INFO",
    "enable_console": false,
    "enable_file": true,
    "max_bytes": 52428800,
    "backup_count": 10
  }
}
```

---

## 附录B: 日志级别选择流程图

```
开始
  ↓
需要记录堆栈跟踪？
  ├─ 是 → logger.exception()
  └─ 否 ↓
系统是否无法继续运行？
  ├─ 是 → logger.critical()
  └─ 否 ↓
操作是否失败但可继续？
  ├─ 是 → logger.error()
  └─ 否 ↓
是否有潜在问题？
  ├─ 是 → logger.warning()
  └─ 否 ↓
是否是重要事件？
  ├─ 是 → logger.info()
  └─ 否 ↓
是否是调试信息？
  ├─ 是 → logger.debug()
  └─ 否 → 不需要记录
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-20  
**维护者**: BTC碰撞引擎开发团队
