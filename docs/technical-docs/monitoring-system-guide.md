# 监控系统使用指南

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **面向**: 运维/开发者

## 目录

- [1. 系统概述](#1-系统概述)

- [2. 系统架构](#2-系统架构)

  - [2.1 数据采集器 (DataCollector)](#21-数据采集器-datacollector)

  - [2.2 数据存储 (DataStorage)](#22-数据存储-datastorage)

  - [2.3 异常检测 (AnomalyDetector)](#23-异常检测-anomalydetector)

  - [2.4 告警系统 (AlertSystem)](#24-告警系统-alertsystem)

  - [2.5 报告生成器 (ReportGenerator)](#25-报告生成器-reportgenerator)

- [3. 数据采集指标](#3-数据采集指标)

  - [3.1 性能指标](#31-性能指标)

  - [3.2 系统指标](#32-系统指标)

  - [3.3 引擎指标](#33-引擎指标)

- [4. 异常检测与告警](#4-异常检测与告警)

  - [4.1 异常检测规则](#41-异常检测规则)

  - [4.2 告警级别](#42-告警级别)

  - [4.3 告警通知方式](#43-告警通知方式)

- [5. 报告生成](#5-报告生成)

  - [5.1 每日报告](#51-每日报告)

  - [5.2 报告存储位置](#52-报告存储位置)

- [6. 配置选项](#6-配置选项)

  - [6.1 监控系统配置](#61-监控系统配置)

  - [6.2 异常检测阈值配置](#62-异常检测阈值配置)

- [7. 使用方法](#7-使用方法)

  - [7.1 启用监控系统](#71-启用监控系统)

- [7.2 查看监控状态](#72-查看监控状态)

  - [7.3 生成报告](#73-生成报告)

- [8. 数据存储结构](#8-数据存储结构)

  - [8.1 监控数据目录](#81-监控数据目录)

  - [8.2 数据格式](#82-数据格式)

- [9. 最佳实践](#9-最佳实践)

  - [9.1 性能优化](#91-性能优化)

  - [9.2 故障排查](#92-故障排查)

  - [9.3 系统维护](#93-系统维护)

- [10. 故障排除](#10-故障排除)

  - [10.1 常见问题](#101-常见问题)

  - [10.2 日志查看](#102-日志查看)

- [11. GPU监控（新增）](#11-gpu监控新增)

  - [11.1 GPU监控模块](#111-gpu监控模块)

  - [11.2 使用方法](#112-使用方法)

- [11.3 依赖要求](#113-依赖要求)

- [12. 数据自动清理（新增）](#12-数据自动清理新增)

  - [12.1 清理工具](#121-清理工具)

- [12.2 配置自动清理](#122-配置自动清理)

- [13. 总结](#13-总结)
## 1. 系统概述

监控系统是比特币私钥对撞引擎的实时监控和数据分析工具，旨在帮助用户评估引擎的运行状态、性能表现和潜在问题。该系统提供全面的数据采集、分析和告警功能，确保引擎持续稳定运行。

## 2. 系统架构

监控系统由以下核心组件组成：

### 2.1 数据采集器 (DataCollector)

- 收集引擎性能指标（检测速率、已检测数量、匹配数量）

- 收集系统资源使用情况（CPU、内存、线程数）

- 收集引擎运行状态（模式、目标数量、运行状态）

### 2.2 数据存储 (DataStorage)

- 保存当前运行数据

- 存储历史数据（最多1000条）

- 记录错误日志（最多500条）

- 生成每日报告

### 2.3 异常检测 (AnomalyDetector)

- 检测性能异常（速率过低/过高）

- 检测系统资源异常（CPU/内存使用过高）

- 检测引擎状态异常

- 分析数据趋势

### 2.4 告警系统 (AlertSystem)

- 生成实时告警

- 记录告警历史

- 分级告警（警告/严重）

### 2.5 报告生成器 (ReportGenerator)

- 生成每日运行报告

- 分析性能趋势

- 提供优化建议

## 3. 数据采集指标

监控系统采集的关键指标包括：

### 3.1 性能指标

- **检测速率**：每秒检测的私钥数量

- **已检测总数**：累计检测的私钥数量

- **匹配数量**：找到的匹配私钥数量

- **CPU使用率**：系统CPU使用百分比

- **内存使用率**：系统内存使用量（MB）

- **线程数**：当前运行的线程数量

### 3.2 系统指标

- **操作系统**：运行环境

- **Python版本**：使用的Python版本

- **进程ID**：引擎进程ID

- **运行时间**：系统运行时间（秒）

### 3.3 引擎指标

- **运行模式**：当前使用的对撞模式（随机/范围/暴力）

- **目标数量**：设置的目标地址数量

- **运行状态**：引擎是否正在运行

- **当前位置**：当前处理的私钥位置

## 4. 异常检测与告警

### 4.1 异常检测规则

| 指标 | 正常范围 | 异常判定 |
|------|----------|----------|
| 检测速率 | 100-1,000,000/s | < 100/s 或 > 1,000,000/s |
| CPU使用率 | 0-90% | > 90% |
| 内存使用率 | 0-1024MB | > 1024MB |
| 引擎状态 | 运行中 | 运行中但速率为0 |

### 4.2 告警级别

- **警告**：性能异常，可能影响系统效率

- **严重**：引擎状态异常，可能导致系统故障

### 4.3 告警通知方式

- 控制台实时显示

- 日志文件记录

- 告警历史存储

## 5. 报告生成

### 5.1 每日报告

- 生成时间：每天00:00

- 内容包括：

  - 当日统计数据（检测数量、匹配数量）

  - 平均性能指标（速率、CPU、内存）

  - 性能趋势分析

  - 错误记录

  - 优化建议

### 5.2 报告存储位置

```python
monitoring_data/report_YYYY-MM-DD.json

```

## 6. 配置选项

### 6.1 监控系统配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| collection_interval | 5秒 | 数据采集间隔 |
| storage_dir | "monitoring_data" | 数据存储目录 |
| history_max_size | 1000 | 历史数据最大条数 |
| error_max_size | 500 | 错误日志最大条数 |

### 6.2 异常检测阈值配置

在 `AnomalyDetector` 类中可调整以下阈值：

```python
self.thresholds = {
    "speed": {
        "min": 100,  # 最低检测速率
        "max": 1000000  # 最高检测速率
    },
    "cpu_usage": {
        "max": 90  # CPU使用率上限
    },
    "memory_usage": {
        "max": 1024  # 内存使用上限（MB）
    }
}

```markdown

## 7. 使用方法

### 7.1 启用监控系统

监控系统默认在引擎启动时自动启用。可以通过以下方式控制：

```python
# 启用监控系统（默认）
engine = KeyCollisionEngine(
    targets=targets,
    on_progress=on_progress,
    on_match=on_match,
    monitoring_enabled=True
)

# 禁用监控系统
engine = KeyCollisionEngine(
    targets=targets,
    on_progress=on_progress,
    on_match=on_match,
    monitoring_enabled=False
)

```markdown

## 7.2 查看监控状态

```python
if engine.monitoring_system:
    status = engine.monitoring_system.get_current_status()
    print(f"当前状态: {status}")

```markdown

### 7.3 生成报告

```python
if engine.monitoring_system:
    report = engine.monitoring_system.generate_report()
    print(f"报告: {report}")

```markdown

## 8. 数据存储结构

### 8.1 监控数据目录

```
monitoring_data/
├── current_data.json     # 当前运行数据
├── history_data.json     # 历史数据
├── error_log.json        # 错误日志
└── report_YYYY-MM-DD.json # 每日报告

```markdown

### 8.2 数据格式

**current_data.json**:

```json
{
  "timestamp": 1776512338.9676704,
  "performance": {
    "speed": 11956.79,
    "total_checked": 62000,
    "matches_found": 1,
    "cpu_usage": 108.8,
    "memory_usage": 51.66,
    "thread_count": 21
  },
  "system": {
    "os": "nt",
    "python_version": "3.14.3",
    "pid": 21404,
    "uptime": 5.32
  },
  "engine": {
    "mode": "brute_force",
    "target_count": 1,
    "is_running": true,
    "current_position": 62622
  },
  "errors": []
}

```markdown

## 9. 最佳实践

### 9.1 性能优化

- **合理设置采集间隔**：根据系统性能调整 `collection_interval`，避免过于频繁的采集影响性能

- **监控数据管理**：定期清理历史数据，保持存储目录大小合理

- **阈值调整**：根据实际硬件性能调整异常检测阈值

### 9.2 故障排查

- **查看错误日志**：分析 `error_log.json` 了解系统错误

- **分析性能趋势**：通过历史数据和报告分析性能变化

- **检查告警历史**：了解系统曾经出现的异常情况

### 9.3 系统维护

- **定期备份**：定期备份监控数据和报告

- **更新依赖**：保持 psutil 等依赖库的最新版本

- **监控系统本身**：确保监控系统自身的稳定运行

## 10. 故障排除

### 10.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 监控系统未启动 | psutil 未安装 | 运行 `pip install psutil` |
| 数据采集失败 | 权限不足 | 以管理员权限运行程序 |
| 告警过多 | 阈值设置不合理 | 调整异常检测阈值 |
| 内存使用过高 | 历史数据过多 | 清理历史数据文件 |

### 10.2 日志查看

监控系统的日志输出到控制台和系统日志文件，可通过以下方式查看：

```bash
# 查看最近的监控日志
grep "MonitoringSystem" logs/collision.log

```markdown

## 11. GPU监控（新增）

### 11.1 GPU监控模块

监控系统现在支持GPU指标监控，包括：

- GPU基本信息（名称、厂商、计算单元）

- 显存总量和使用量

- GPU可用性检查

### 11.2 使用方法

```python
from src.monitoring.gpu_monitor import get_gpu_monitor

# 获取GPU监控器
monitor = get_gpu_monitor()

# 获取GPU信息
gpu_info = monitor.get_gpu_info()
print(f"GPU: {gpu_info['gpus'][0]['name']}")
print(f"显存: {gpu_info['gpus'][0]['global_memory_mb']} MB")

# 获取GPU指标
gpu_metrics = monitor.get_gpu_metrics()
print(f"显存使用: {gpu_metrics['memory_used_mb']} MB")
print(f"显存使用率: {gpu_metrics['memory_usage_percent']}%")

```markdown

## 11.3 依赖要求

GPU监控需要安装PyOpenCL：

```bash
pip install pyopencl

```python

如果PyOpenCL不可用，GPU监控会自动禁用，不影响其他功能。

## 12. 数据自动清理（新增）

### 12.1 清理工具

提供自动清理工具防止监控数据占用过多磁盘空间：

```bash
# 查看清理建议
python tools/cleanup_monitoring_data.py --recommend

# 试运行（不删除文件）
python tools/cleanup_monitoring_data.py --max-age 30 --dry-run

# 实际清理（删除30天前的文件）
python tools/cleanup_monitoring_data.py --max-age 30

```markdown

## 12.2 配置自动清理

在`config.json`中启用自动清理：

```json
{
  "monitoring": {
    "auto_cleanup": {
      "enabled": true,
      "max_age_days": 30
    }
  }
}

```

## 13. 总结

监控系统为比特币私钥对撞引擎提供了全面的实时监控和数据分析能力，帮助用户：

- 实时了解引擎运行状态和性能表现

- 及时发现和处理异常情况

- 分析性能趋势，优化系统配置

- 生成详细的运行报告，支持决策制定

通过合理配置和使用监控系统，可以显著提高引擎的稳定性和效率，确保系统持续可靠运行。
