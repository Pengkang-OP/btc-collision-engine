# 数据日志系统使用指南

> **版本**: v3.5.1 | **最后更新**: 2026-05-01
> **面向**: 运维/开发者

## 目录

- [1. 系统概述](#1-系统概述)
- [2. 数据存储结构](#2-数据存储结构)
- [3. 核心文件说明](#3-核心文件说明)
- [4. 使用方法](#4-使用方法)
- [5. 数据归档策略](#5-数据归档策略)
- [6. 配置选项](#6-配置选项)
- [7. 编程接口](#7-编程接口)
- [8. 故障排查](#8-故障排查)

## 1. 系统概述

数据日志系统 (`DataLogger`) 是BTC碰撞引擎的持久化数据记录组件，负责记录引擎运行期间的所有性能指标、系统状态、错误信息和匹配结果。数据统一存储在 `data_logs/` 目录下。

### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `DataLogger` | `src/monitoring/data_logger.py` | 核心日志记录器 |
| `LogProcessor` | `src/logging/log_processor.py` | 日志格式化与脱敏 |
| `SensitiveDataFilter` | `src/logging/log_processor.py` | 敏感数据(私钥/地址)过滤 |
| `DataCleaner` | `src/utils/data_cleanup.py` | 数据清理与轮转 |
| `PerformanceMonitor` | `src/utils/logger.py` | 性能监控器 |

### 敏感数据保护

系统内置 `SensitiveDataFilter` 自动脱敏以下敏感信息：

- 64位十六进制私钥 → `***REDACTED***`
- P2PKH 地址 (1开头) → `[P2PKH_ADDRESS]`
- P2SH 地址 (3开头) → `[P2SH_ADDRESS]`
- Bech32 地址 (bc1开头) → `[BECH32_ADDRESS]`
- Bech32m 地址 (bc1p开头) → `[BECH32M_ADDRESS]`

## 2. 数据存储结构

```
data_logs/
├── current_data.json       # 当前运行数据（实时更新）
├── history_data.json       # 历史性能数据（最多1000条）
├── error_log.json          # 错误日志（最多500条）
├── performance.log         # CSV格式性能日志
├── alert_history.json      # 告警历史记录
├── collision_checkpoint.json # 断点续传数据
├── report_daily_*.json     # 每日自动生成报告
└── archive/                # 归档目录（>7天的旧文件）
    ├── report_daily_*.json
    └── performance_log_*.log
```

## 3. 核心文件说明

### 3.1 current_data.json

实时更新的当前运行快照：

```json
{
  "saved_at": "2026-05-01T12:00:00",
  "uptime": 3600.5,
  "performance": {
    "timestamp": 1776500000.0,
    "speed": 500000.0,
    "total_checked": 1000000000,
    "matches_found": 3,
    "cpu_usage": 65.5,
    "memory_usage": 512.0,
    "thread_count": 8,
    "avg_speed": 498000.0
  },
  "system": {
    "os": "nt",
    "python_version": "3.12.3",
    "pid": 12345,
    "uptime": 3600.5
  },
  "engine": {
    "mode": "random",
    "target_count": 10,
    "is_running": true,
    "current_position": 500000000
  }
}
```

### 3.2 history_data.json

历史性能数据数组（FIFO队列，最多1000条），每条记录格式同 `performance` 字段。

### 3.3 error_log.json

结构化错误记录数组（FIFO队列，最多500条）：

```json
{
  "timestamp": 1776500000.0,
  "datetime": "2026-05-01T12:00:00",
  "type": "gpu_buffer_resize_failed",
  "message": "GPU缓冲区调整失败: CUDA out of memory",
  "exception_type": "MemoryError",
  "exception_message": "CUDA out of memory",
  "context": {"batch_size": 1048576, "gpu_memory_mb": 8192}
}
```

### 3.4 performance.log

CSV格式持续追加的性能日志，格式为：

```
timestamp,speed,total_checked,matches_found,cpu_usage,memory_usage,thread_count
```

## 4. 使用方法

### 4.1 通过引擎启用日志

```python
from src.collision.gpu.engine import GPUCollisionEngine

engine = GPUCollisionEngine(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    data_logging_enabled=True,      # 启用数据日志
    data_logging_interval=5,        # 数据记录间隔(秒)
    use_async_logging=True,         # 启用异步日志
    async_log_file="logs/gpu_async.log",
)
```

### 4.2 独立使用 DataLogger

```python
from src.monitoring.data_logger import DataLogger

# 初始化
logger = DataLogger(storage_dir="data_logs")

# 记录性能数据
logger.record_performance_data(
    speed=500000.0,
    total_checked=1000000,
    matches_found=2,
    cpu_usage=65.5,
    memory_usage=512.0,
    thread_count=8,
)

# 记录系统数据
logger.record_system_data()

# 记录引擎状态
logger.record_engine_data(
    mode="random",
    target_count=10,
    is_running=True,
    current_position=500000,
)

# 记录错误
logger.record_error(
    error_type="gpu_timeout",
    message="GPU批次执行超时",
    exception=timeout_error,
    context={"batch_size": 1000000},
)

# 生成每日报告
report = logger.generate_report(report_type="daily")

# 停止并刷写缓冲
logger.stop()
```

### 4.3 查看统计信息

```python
stats = logger.get_statistics()
print(f"总检测: {stats['total_checks']}")
print(f"匹配数: {stats['matches_found']}")
print(f"平均速度: {stats['avg_speed']:.2f}/s")
print(f"最大速度: {stats['max_speed']:.2f}/s")
print(f"运行时间: {stats['uptime']:.0f}s")
```

## 5. 数据归档策略

### 5.1 自动清理

系统默认启用自动清理机制：

- **保留期**：7天（可通过 `config.json` 配置）
- **执行频率**：每24小时
- **归档目标**：`data_logs/archive/`
- **处理文件**：`report_daily_*.json`, `report_*.json`

### 5.2 手动清理

```bash
# 清理30天前的数据
python -c "
from src.utils.data_cleanup import DataCleaner
dc = DataCleaner(project_root='.')
dc.clean_all()
"

# 轮转 performance.log（超过10MB时）
python -c "
from src.utils.data_cleanup import DataCleaner
dc = DataCleaner(project_root='.')
dc.rotate_performance_log()
"
```

### 5.3 配置自动清理

在 `config.json` 中：

```json
{
  "monitoring": {
    "auto_cleanup": {
      "enabled": true,
      "max_age_days": 7
    }
  }
}
```

## 6. 配置选项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `data_logging_enabled` | `True` | 是否启用数据日志 |
| `data_logging_interval` | `5` | 数据采集间隔(秒) |
| `monitoring.auto_cleanup.enabled` | `True` | 自动清理开关 |
| `monitoring.auto_cleanup.max_age_days` | `7` | 归档保留天数 |

## 7. 编程接口

### DataLogger 主要方法

| 方法 | 说明 |
|------|------|
| `record_performance_data(speed, ...)` | 记录性能指标 |
| `record_system_data(...)` | 记录系统信息 |
| `record_engine_data(...)` | 记录引擎状态 |
| `record_error(error_type, message, ...)` | 记录错误信息 |
| `save_current_data()` | 持久化当前数据 |
| `save_history_data()` | 追加历史数据 |
| `generate_report(report_type)` | 生成日/周/月报告 |
| `get_statistics()` | 获取统计摘要 |
| `get_current_data()` | 获取当前数据快照 |
| `cleanup_old_data(max_age_days)` | 清理过期数据 |
| `flush()` | 刷写缓冲区到磁盘 |
| `stop()` | 安全停止日志记录器 |

### 原子写入保障

所有JSON文件写入均采用"临时文件+原子重命名"策略，确保：

- 写入中断不会损坏现有数据
- 并发安全（`threading.Lock` 保护）
- 磁盘同步（`os.fsync`）

### 数据恢复

`history_data.json` 损坏时自动触发恢复机制，使用括号匹配算法从损坏JSON中提取完整记录。

## 8. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 数据未写入 | 缓冲区未刷写 | 调用 `logger.flush()` 或 `logger.stop()` |
| JSON文件损坏 | 写入过程中断 | 系统自动恢复，无需手动干预 |
| 磁盘空间不足 | 历史数据过多 | 减小 `max_age_days` 或手动清理 |
| performance.log过大 | 长时间运行 | 使用 `DataCleaner.rotate_performance_log()` |
| 临时文件残留 | 写入失败未清理 | 删除 `data_logs/.history_data_*.tmp` |
