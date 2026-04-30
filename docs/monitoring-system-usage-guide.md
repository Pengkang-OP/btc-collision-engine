# 监控系统使用指南和最佳实践

> **版本**: v3.3.1 | **最后更新**: 2026-04-28  
> **面向**: 运维/开发者



## 目录

- [📋 目录](#-目录)
- [系统架构概述](#系统架构概述)
  - [架构图](#架构图)
- [核心组件](#核心组件)
  - [1. DataStorage - 数据存储](#1-datastorage---数据存储)
  - [2. DataCollector - 数据采集](#2-datacollector---数据采集)
  - [3. AnomalyDetector - 异常检测](#3-anomalydetector---异常检测)
  - [4. AlertSystem - 告警系统](#4-alertsystem---告警系统)
  - [5. ReportGenerator - 报告生成](#5-reportgenerator---报告生成)
- [使用示例](#使用示例)
  - [示例1: 完整功能（推荐）](#示例1-完整功能推荐)
- [示例2: 独立使用DataStorage](#示例2-独立使用datastorage)
- [示例3: 独立使用AnomalyDetector](#示例3-独立使用anomalydetector)
- [示例4: 独立使用AlertSystem](#示例4-独立使用alertsystem)
- [示例5: 独立使用ReportGenerator](#示例5-独立使用reportgenerator)
- [依赖注入模式](#依赖注入模式)
  - [什么是依赖注入？](#什么是依赖注入)
  - [监控系统的依赖关系](#监控系统的依赖关系)
  - [使用Optional类型提示](#使用optional类型提示)
  - [依赖注入的好处](#依赖注入的好处)
    - [1. 灵活组合](#1-灵活组合)
- [2. 易于测试](#2-易于测试)
    - [3. 降级方案](#3-降级方案)
- [最佳实践](#最佳实践)
  - [1. 始终检查依赖](#1-始终检查依赖)
- [2. 使用try-except保护](#2-使用try-except保护)
- [3. 实现降级方案](#3-实现降级方案)
- [4. 原子写入保证数据完整性](#4-原子写入保证数据完整性)
- [5. 限制数据量防止内存溢出](#5-限制数据量防止内存溢出)
- [6. 使用Optional类型提示](#6-使用optional类型提示)
- [7. 添加详细文档](#7-添加详细文档)
- [常见问题](#常见问题)
  - [Q1: 什么时候应该使用完整功能，什么时候独立使用组件？](#q1-什么时候应该使用完整功能什么时候独立使用组件)
  - [Q2: 为什么不强制要求依赖？](#q2-为什么不强制要求依赖)
  - [Q3: 原子写入有什么作用？](#q3-原子写入有什么作用)
  - [Q4: 如何自定义异常检测阈值？](#q4-如何自定义异常检测阈值)
  - [Q5: 如何清理旧数据？](#q5-如何清理旧数据)
  - [Q6: 监控系统会影响性能吗？](#q6-监控系统会影响性能吗)
  - [Q7: 如何集成到现有的碰撞引擎？](#q7-如何集成到现有的碰撞引擎)
- [附录](#附录)
  - [A. 配置文件示例](#a-配置文件示例)
  - [B. 错误码说明](#b-错误码说明)
  - [C. 性能指标参考](#c-性能指标参考)
**文档版本**: v1.0  
**创建日期**: 2026-04-20  
**适用范围**: monitoring_system.py模块  

---

## 📋 目录

1. [系统架构概述](#系统架构概述)
2. [核心组件](#核心组件)
3. [使用示例](#使用示例)
4. [依赖注入模式](#依赖注入模式)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## 系统架构概述

BTC碰撞引擎监控系统采用**模块化设计**和**依赖注入模式**，提供灵活的监控、异常检测和告警功能。

### 架构图

```python
┌─────────────────────────────────────────────────────────┐
│                  MonitoringSystem                       │
│                  (监控系统主类)                           │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ DataCollector│  │ DataStorage  │  │ Anomaly      │  │
│  │ (数据采集)    │  │ (数据存储)    │  │ Detector     │  │
│  └──────────────┘  └──────────────┘  │ (异常检测)    │  │
│                                      └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │ AlertSystem  │  │ Report       │                    │
│  │ (告警系统)    │  │ Generator    │                    │
│  └──────────────┘  │ (报告生成)    │                    │
│                    └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. DataStorage - 数据存储

**职责**: 安全地存储监控数据，支持原子写入和数据恢复

**特性**:
- ✅ 原子写入（防止数据损坏）
- ✅ JSON损坏自动恢复
- ✅ 数据量限制（历史1000条，错误500条）
- ✅ 线程安全

**文件**:
- `current_data.json` - 当前状态
- `history_data.json` - 历史数据
- `error_log.json` - 错误日志

### 2. DataCollector - 数据采集

**职责**: 从引擎和系统收集性能数据

**采集指标**:
- CPU使用率
- 内存使用量
- 线程数量
- 检测速率
- 已检测总数
- 匹配数

### 3. AnomalyDetector - 异常检测

**职责**: 检测性能异常和引擎状态异常

**检测规则**:
- 速度过低 (< 100/s) 或过高 (> 1,000,000/s)
- CPU使用率过高 (> 90%)
- 内存使用过高 (> 1024 MB)
- 引擎运行但速率为0

### 4. AlertSystem - 告警系统

**职责**: 生成和处理告警信息

**告警级别**:
- `warning` - 性能异常
- `critical` - 引擎异常

### 5. ReportGenerator - 报告生成

**职责**: 生成每日报告和优化建议

**报告内容**:
- 统计摘要（速度、CPU、内存）
- 趋势分析
- 错误汇总
- 优化建议

---

## 使用示例

### 示例1: 完整功能（推荐）

使用所有组件的完整功能：

```python
from src.monitoring.monitoring_system import MonitoringSystem

# 创建监控系统（自动初始化所有组件）
monitoring = MonitoringSystem(
    engine=my_collision_engine,  # 可选：传入引擎实例
    collection_interval=5        # 数据采集间隔（秒）
)

# 启动监控
monitoring.start()

# 引擎运行...
# 监控系统会自动：
# - 每5秒采集一次数据
# - 检测异常并生成告警
# - 每小时生成一次报告

# 停止监控
monitoring.stop()

# 获取当前状态
status = monitoring.get_current_status()
print(f"当前速度: {status['current_data']['performance']['speed']}")

# 生成报告
report = monitoring.generate_report()
print(f"平均速度: {report['summary']['average_speed']}")
```markdown

## 示例2: 独立使用DataStorage

单独使用数据存储功能：

```python
from src.monitoring.monitoring_system import DataStorage, MonitoringData

# 创建数据存储（自定义目录）
storage = DataStorage(storage_dir="my_monitoring_data")

# 创建监控数据
data = MonitoringData()
data.performance["speed"] = 1500.5
data.performance["total_checked"] = 10000
data.engine["is_running"] = True

# 保存数据（原子写入）
storage.save_current_data(data)
storage.save_history_data(data)

# 读取数据
current = storage.get_current_data()
history = storage.get_history_data()
errors = storage.get_error_logs()

# 保存错误记录
storage.save_error({
    "type": "test_error",
    "message": "这是一个测试错误"
})
```markdown

## 示例3: 独立使用AnomalyDetector

单独使用异常检测功能：

```python
from src.monitoring.monitoring_system import (
    AnomalyDetector,
    DataStorage,
    MonitoringData
)

# 方式1: 带storage（会保存异常记录）
storage = DataStorage()
detector = AnomalyDetector(storage=storage)

# 方式2: 不带storage（仅检测，不保存）
detector = AnomalyDetector()

# 创建测试数据
data = MonitoringData()
data.performance["speed"] = 50  # 低于阈值
data.performance["cpu_usage"] = 95  # 超过阈值
data.engine["is_running"] = True

# 检测异常
anomalies = detector.detect_anomalies(data)

for anomaly in anomalies:
    print(f"检测到异常: {anomaly['message']}")
    print(f"  类型: {anomaly['type']}")
    print(f"  指标: {anomaly['metric']}")
    print(f"  值: {anomaly['value']}")
    print(f"  阈值: {anomaly['threshold']}")

# 分析趋势
history_data = storage.get_history_data()
trends = detector.analyze_trends(history_data)
print(f"速度趋势: {trends['speed']['trend']}")
```markdown

## 示例4: 独立使用AlertSystem

单独使用告警系统：

```python
from src.monitoring.monitoring_system import (
    AlertSystem,
    DataStorage
)

# 方式1: 带storage（会保存告警记录）
storage = DataStorage()
alert_system = AlertSystem(storage=storage)

# 方式2: 不带storage（仅打印，不保存）
alert_system = AlertSystem()

# 生成告警
anomaly = {
    "type": "performance",
    "metric": "speed",
    "value": 50,
    "threshold": 100,
    "message": "检测速率过低: 50.00/s"
}

alert_system.generate_alert(anomaly)

# 查看告警历史
history = alert_system.get_alert_history()
print(f"告警数量: {len(history)}")
print(f"最新告警: {history[-1]['message']}")

# 批量处理异常
anomalies = [
    {"type": "performance", "metric": "cpu_usage", "message": "CPU过高"},
    {"type": "engine", "metric": "speed", "message": "速度为0"}
]
alert_system.process_anomalies(anomalies)
```markdown

## 示例5: 独立使用ReportGenerator

单独使用报告生成功能：

```python
from src.monitoring.monitoring_system import (
    ReportGenerator,
    DataStorage,
    AnomalyDetector
)
import json
from datetime import datetime, timedelta

# 方式1: 完整功能（推荐）
storage = DataStorage(storage_dir="my_reports")
detector = AnomalyDetector(storage=storage)
generator = ReportGenerator(storage=storage, detector=detector)

# 方式2: 仅storage（使用简单趋势分析）
generator = ReportGenerator(storage=storage, detector=None)

# 方式3: 无依赖（返回错误信息）
generator = ReportGenerator()
result = generator.generate_daily_report()
print(result)  # {"error": "ReportGenerator: storage未初始化，无法生成报告"}

# 添加测试数据（实际使用时由监控系统自动采集）
today = datetime.now()
test_data = []
for i in range(20):
    timestamp = (today - timedelta(hours=i)).timestamp()
    test_data.append({
        "timestamp": timestamp,
        "performance": {
            "speed": 1000 + i * 10,
            "total_checked": 10000 + i * 100,
            "matches_found": 0,
            "cpu_usage": 50.0,
            "memory_usage": 256.0
        }
    })

# 写入历史数据
history_file = "my_reports/history_data.json"
with open(history_file, 'w') as f:
    json.dump(test_data, f)

# 生成报告
report = generator.generate_daily_report()
print(f"报告日期: {report['date']}")
print(f"平均速度: {report['summary']['average_speed']}")
print(f"趋势: {report['trends']['speed']['trend']}")
print(f"建议: {report['recommendations']}")
```python

---

## 依赖注入模式

### 什么是依赖注入？

依赖注入是一种设计模式，通过将依赖对象作为参数传入，而不是在类内部创建，实现：
- ✅ 降低耦合度
- ✅ 提高可测试性
- ✅ 支持灵活组合

### 监控系统的依赖关系

```
MonitoringSystem
  ├── DataStorage (创建)
  ├── DataCollector (创建)
  ├── AnomalyDetector (注入 DataStorage)
  ├── AlertSystem (注入 DataStorage)
  └── ReportGenerator (注入 DataStorage + AnomalyDetector)
```markdown

### 使用Optional类型提示

```python
from typing import Optional

class AnomalyDetector:
    def __init__(self, storage: Optional['DataStorage'] = None):
        """
        Args:
            storage: 数据存储实例（可选），用于保存异常记录
        """
        self.storage = storage
        # 使用时检查
        if self.storage is not None:
            self.storage.save_error(...)
```markdown

### 依赖注入的好处

#### 1. 灵活组合

```python
# 完整功能
storage = DataStorage()
detector = AnomalyDetector(storage)
alert = AlertSystem(storage)
report = ReportGenerator(storage, detector)

# 仅检测功能
detector = AnomalyDetector()  # 不需要storage

# 仅告警功能
alert = AlertSystem()  # 不需要storage
```markdown

## 2. 易于测试

```python
from unittest.mock import Mock

def test_anomaly_detector():
    # 使用mock storage
    mock_storage = Mock()
    detector = AnomalyDetector(storage=mock_storage)
    
    # 测试检测功能
    detector.detect_anomalies(test_data)
    
    # 验证storage被正确调用
    mock_storage.save_error.assert_called_once()
```markdown

#### 3. 降级方案

```python
class ReportGenerator:
    def generate_daily_report(self):
        if self.detector is not None:
            # 完整功能
            trends = self.detector.analyze_trends(data)
        else:
            # 降级方案
            trends = self._simple_trend_analysis(data)
```python

---

## 最佳实践

### 1. 始终检查依赖

```python
# ✅ 正确做法
def generate_report(self):
    if self.storage is None:
        return {"error": "storage未初始化"}
    
    data = self.storage.get_history_data()

# ❌ 错误做法
def generate_report(self):
    data = self.storage.get_history_data()  # 可能崩溃
```markdown

## 2. 使用try-except保护

```python
# ✅ 正确做法
try:
    history = self.storage.get_history_data()
except Exception as e:
    logger.error(f"读取失败: {e}")
    return {"error": str(e)}

# ❌ 错误做法
history = self.storage.get_history_data()  # 可能抛出异常
```markdown

## 3. 实现降级方案

```python
# ✅ 正确做法
if self.detector is not None:
    trends = self.detector.analyze_trends(data)
else:
    trends = self._simple_trend_analysis(data)  # 降级

# ❌ 错误做法
trends = self.detector.analyze_trends(data)  # detector可能为None
```markdown

## 4. 原子写入保证数据完整性

```python
# ✅ 正确做法
def save_data(self, data):
    temp_file = file_path + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        
        os.replace(temp_file, file_path)  # 原子替换
    except Exception:
        if os.path.exists(temp_file):
            os.remove(temp_file)  # 清理临时文件
        raise
```markdown

## 5. 限制数据量防止内存溢出

```python
# ✅ 正确做法
history.append(new_data)
if len(history) > 1000:
    history = history[-1000:]  # 保留最近1000条

# ❌ 错误做法
history.append(new_data)  # 无限增长
```markdown

## 6. 使用Optional类型提示

```python
# ✅ 正确做法
def __init__(self, storage: Optional['DataStorage'] = None):
    self.storage = storage

# ❌ 错误做法
def __init__(self, storage: DataStorage = None):  # 类型提示不准确
    self.storage = storage
```markdown

## 7. 添加详细文档

```python
class ReportGenerator:
    """报告生成器
    
    使用示例:
        # 完整功能（推荐）
        storage = DataStorage()
        detector = AnomalyDetector(storage)
        generator = ReportGenerator(storage, detector)
        
        # 独立使用（功能受限）
        generator = ReportGenerator()
        generator.storage = custom_storage
    """
```yaml

---

## 常见问题

### Q1: 什么时候应该使用完整功能，什么时候独立使用组件？

**A**: 
- **完整功能**: 生产环境，需要完整监控、告警、报告
- **独立使用**: 
  - 单元测试（Mock依赖）
  - 特殊场景（只需要检测或告警）
  - 自定义组合（使用不同的storage实现）

### Q2: 为什么不强制要求依赖？

**A**: 依赖注入设计为可选的原因：
1. **灵活性**: 允许独立使用各个组件
2. **可测试性**: 便于单元测试时Mock
3. **降级能力**: 部分功能不可用时，其他功能仍可工作

### Q3: 原子写入有什么作用？

**A**: 原子写入防止数据损坏：
1. 先写入临时文件
2. 确保数据完全写入磁盘（fsync）
3. 原子替换原文件（os.replace）
4. 如果写入失败，原文件不受影响

### Q4: 如何自定义异常检测阈值？

**A**: 
```python
detector = AnomalyDetector()
detector.thresholds["speed"]["min"] = 200  # 修改最低速度阈值
detector.thresholds["cpu_usage"]["max"] = 80  # 修改CPU阈值
```markdown

### Q5: 如何清理旧数据？

**A**: 使用DataLogger的清理功能（如果需要更高级的数据管理）：
```python
from src.monitoring.data_logger import DataLogger

logger = DataLogger()
logger.cleanup_old_data(max_age_days=30)  # 清理30天前的数据
```markdown

### Q6: 监控系统会影响性能吗？

**A**: 影响很小：
- 数据采集间隔默认5秒
- 使用后台线程，不阻塞主线程
- 数据采集使用psutil，开销极低
- 建议生产环境保持默认配置

### Q7: 如何集成到现有的碰撞引擎？

**A**: 非常简单：
```python
from src.collision.key_collision_engine import KeyCollisionEngine

# 创建引擎（默认启用监控）
engine = KeyCollisionEngine(
    use_enhanced_monitoring=True  # 默认值
)

# 引擎会自动：
# - 创建MonitoringSystem
# - 启动时自动启动监控
# - 停止时自动停止监控
```python

---

## 附录

### A. 配置文件示例

```json
{
  "monitoring": {
    "enabled": true,
    "collection_interval": 5,
    "storage_dir": "monitoring_data",
    "thresholds": {
      "speed": {"min": 100, "max": 1000000},
      "cpu_usage": {"max": 90},
      "memory_usage": {"max": 1024}
    }
  }
}
```

### B. 错误码说明

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| "storage未初始化" | ReportGenerator未传入storage | 传入storage参数 |
| "读取数据失败" | 文件损坏或权限问题 | 检查文件权限，使用恢复机制 |
| "数据点不足" | 历史数据少于2条 | 等待更多数据采集 |

### C. 性能指标参考

| 指标 | 正常范围 | 警告阈值 | 严重阈值 |
|------|---------|---------|---------|
| 速度 | 100-100,000/s | <100 或 >1M | 0（引擎运行时） |
| CPU使用率 | 20-80% | >80% | >90% |
| 内存使用 | 128-512MB | >512MB | >1024MB |

---

**文档维护**: 随代码更新同步维护  
**反馈渠道**: 提交Issue或Pull Request
