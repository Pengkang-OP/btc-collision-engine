# 日志系统使用指南

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **面向**: 开发者

本文档提供BTC碰撞引擎项目日志系统的完整使用指南，包括配置、使用和最佳实践。

## 目录

- [1. 快速开始](#1-快速开始)

- [2. 日志配置](#2-日志配置)

- [3. 基本使用](#3-基本使用)

- [4. 性能监控](#4-性能监控)

- [5. 采样日志](#5-采样日志)

- [6. 高级用法](#6-高级用法)

- [7. 最佳实践](#7-最佳实践)

---

## 1. 快速开始

### 1.1 最简单的使用方式

```python
from src.utils import init_logging, get_configured_logger

# 初始化日志系统
init_logging()

# 获取日志记录器
logger = get_configured_logger(__name__)

# 记录日志
logger.info("程序启动")
logger.debug(f"配置值: {config_value}")
logger.warning("潜在问题")
logger.error("发生错误")

```markdown

## 1.2 在模块中使用

```python
# 在模块顶部创建logger
import logging
logger = logging.getLogger(__name__)

# 在函数中使用
def my_function():
    logger.info("函数被调用")

```python

---

## 2. 日志配置

### 2.1 从config.json加载配置

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/collision.log",
    "max_bytes": 10485760,
    "backup_count": 5,
    "enable_console": true,
    "enable_file": true
  }
}

```markdown

### 2.2 编程方式配置

```python
from src.utils import init_logging

config = {
    "level": "DEBUG",
    "file": "logs/my_app.log",
    "max_bytes": 52428800,  # 50MB
    "backup_count": 10,
    "enable_console": True,
    "enable_file": True
}

init_logging(config)

```markdown

### 2.3 环境特定配置

```python
import os
from src.utils import init_logging

env = os.getenv('APP_ENV', 'production')

if env == 'development':
    init_logging({
        "level": "DEBUG",
        "enable_console": True,
        "enable_file": False
    })
elif env == 'production':
    init_logging({
        "level": "INFO",
        "enable_console": False,
        "enable_file": True
    })

```python

---

## 3. 基本使用

### 3.1 日志级别

```python
import logging
logger = logging.getLogger(__name__)

# DEBUG: 详细调试信息
logger.debug(f"变量值: x={x}, y={y}")

# INFO: 一般运行信息
logger.info(f"引擎启动成功: {engine_type}")

# WARNING: 潜在问题
logger.warning(f"配置项缺失，使用默认值: {config_key}")

# ERROR: 错误事件
logger.error(f"操作失败: {operation} - {error}")

# EXCEPTION: 异常（自动包含堆栈）
try:
    do_something()
except Exception as e:
    logger.exception(f"未知错误: {operation}")

# CRITICAL: 严重错误
logger.critical(f"系统无法继续运行: {reason}")

```markdown

## 3.2 格式化输出

```python
# [OK] 推荐: 惰性格式化
logger.info("用户%s登录，IP=%s", username, ip_address)

# [FAIL] 不推荐: 提前格式化
logger.info(f"用户{username}登录，IP={ip_address}")

```markdown

## 3.3 包含上下文

```python
# [OK] 推荐: 包含关键上下文
logger.error(
    f"GPU批次处理失败 (device={device_index}, "
    f"batch_size={batch_size}): {error}"
)

# [FAIL] 不推荐: 缺少上下文
logger.error(f"处理失败: {error}")

```python

---

## 4. 性能监控

### 4.1 EnhancedPerformanceMonitor（推荐）

```python
from src.utils import EnhancedPerformanceMonitor

# 基本用法
with EnhancedPerformanceMonitor(logger, "GPU内核编译", level="INFO") as pm:
    program = compile_kernel()
    pm.add_metadata('kernel_size', size)
    pm.add_metadata('device', device_name)

# 输出:
# [Performance] GPU内核编译: 215.34ms

```markdown

## 4.2 性能追踪器

```python
from src.utils import get_performance_tracker, log_performance_summary

tracker = get_performance_tracker()

# 获取统计信息
stats = tracker.get_statistics()
print(f"平均耗时: {stats['avg_ms']:.2f}ms")
print(f"P95耗时: {stats['p95_ms']:.2f}ms")

# 获取慢操作
slow_ops = tracker.get_slow_operations(threshold_ms=1000, limit=5)
for op in slow_ops:
    print(f"慢操作: {op.operation} - {op.elapsed_ms:.2f}ms")

# 记录性能摘要
log_performance_summary(logger, tracker)

```markdown

## 4.3 性能监控场景

```python
from src.utils import EnhancedPerformanceMonitor

# 场景1: 初始化性能
with EnhancedPerformanceMonitor(logger, "GPU引擎初始化", level="INFO") as pm:
    init_gpu()
    pm.add_metadata('device', device_name)

# 场景2: 批次处理性能
with EnhancedPerformanceMonitor(logger, "批次处理", level="DEBUG"):
    results = process_batch(data)

# 场景3: 文件I/O性能
with EnhancedPerformanceMonitor(logger, "断点保存", level="INFO"):
    save_checkpoint(data)

```python

---

## 5. 采样日志

### 5.1 基本使用

```python
from src.utils import get_sampled_logger

# 创建采样日志器（每1000条记录1条）
sampled_logger = get_sampled_logger("MyModule.sampled", sample_rate=1000)

# 在高频循环中使用
for i in range(1000000):
    sampled_logger.info(f"进度: {i:,} / 1,000,000")
    # 实际只记录1000条日志

```markdown

## 5.2 采样率选择

```python
from src.utils import get_sampled_logger

# 极高频率（>10000次/秒）
ultra_sampled = get_sampled_logger("ultra", sample_rate=10000)

# 高频率（~1000次/秒）
high_sampled = get_sampled_logger("high", sample_rate=1000)

# 中频率（~100次/秒）
medium_sampled = get_sampled_logger("medium", sample_rate=100)

# 低频率（~10次/秒）
low_sampled = get_sampled_logger("low", sample_rate=10)

```markdown

## 5.3 实际示例

```python
from src.utils import get_sampled_logger

# GPU碰撞引擎中的采样日志
sampled_logger = get_sampled_logger(
    "KeyCollisionEngine.sampled", 
    sample_rate=1000
)

def process_keys():
    for batch in key_batches:
        results = process(batch)
        sampled_logger.info(
            f"批次处理完成: {len(results)} 个密钥, "
            f"速度: {speed:.0f} 次/秒"
        )

```python

---

## 6. 高级用法

### 6.1 线程安全日志

```python
from src.utils import get_configured_logger

# 获取线程安全的日志记录器
logger = get_configured_logger(__name__, thread_safe=True)

# 在多线程环境中安全使用
import threading

def worker():
    logger.info(f"工作线程 {threading.current_thread().name} 启动")

```markdown

## 6.2 彩色格式化器

```python
from src.utils import ColoredFormatter
import logging

# 创建带颜色的格式化器
formatter = ColoredFormatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 应用到处理器
handler = logging.StreamHandler()
handler.setFormatter(formatter)

```markdown

## 6.3 性能监控组合

```python
from src.utils import (
    EnhancedPerformanceMonitor, 
    get_performance_tracker,
    log_performance_summary
)

# 组合使用
tracker = get_performance_tracker()

# 记录多个操作
with EnhancedPerformanceMonitor(logger, "操作1"):
    do_operation1()

with EnhancedPerformanceMonitor(logger, "操作2"):
    do_operation2()

# 最后输出统计
log_performance_summary(logger, tracker)

```markdown

## 6.4 条件日志

```python
import logging
logger = logging.getLogger(__name__)

# 仅在DEBUG级别启用
if logger.isEnabledFor(logging.DEBUG):
    expensive_data = compute_expensive_data()
    logger.debug(f"详细数据: {expensive_data}")

# 避免不必要的计算
logger.debug(f"详细数据: %s", compute_expensive_data())  # 总是执行

```python

---

## 7. 最佳实践

### 7.1 日志初始化

```python
# [OK] 推荐: 在程序入口初始化
from src.utils import init_logging

def main():
    init_logging()  # 最先调用
    # ... 其他代码

# [FAIL] 不推荐: 延迟初始化
def some_function():
    init_logging()  # 可能导致日志丢失

```markdown

## 7.2 日志记录器命名

```python
# [OK] 推荐: 使用模块路径
logger = logging.getLogger(__name__)
# 输出: src.collision.key_collision_engine

# [OK] 推荐: 明确命名
logger = logging.getLogger("GPUMonitor")

# [FAIL] 不推荐: 使用根日志记录器
logger = logging.getLogger()

```markdown

## 7.3 避免敏感信息

```python
# [FAIL] 绝对禁止
logger.debug(f"私钥: {private_key_hex}")
logger.info(f"WIF: {wif}")

# [OK] 推荐
logger.debug(f"地址: {address}")
logger.info(f"地址数量: {len(targets)}")

```markdown

## 7.4 异常处理

```python
# [OK] 推荐: 已知错误
try:
    result = gpu_operation()
except RuntimeError as e:
    logger.error(f"GPU运行时错误: {type(e).__name__}: {e}")

# [OK] 推荐: 未知错误
try:
    result = complex_operation()
except Exception as e:
    logger.exception(f"未知错误: {operation}")

# [FAIL] 不推荐: 吞掉异常
try:
    do_something()
except Exception:
    pass  # 没有日志！

```markdown

## 7.5 性能优化

```python
# [OK] 推荐: 使用采样日志
for i in range(1000000):
    sampled_logger.info(f"进度: {i}")

# [OK] 推荐: 使用时间间隔
last_log = time.time()
for i in range(1000000):
    if time.time() - last_log > 1.0:
        logger.info(f"进度: {i}")
        last_log = time.time()

# [FAIL] 不推荐: 每次都记录
for i in range(1000000):
    logger.info(f"进度: {i}")  # 太慢！

```markdown

## 7.6 资源管理日志

```python
# [OK] 推荐: 完整的生命周期日志
logger.info(f"GPU设备初始化: {device_name}")
logger.debug(f"GPU显存使用: {used_mb:.1f}MB / {total_mb:.1f}MB")
logger.info(f"GPU资源已清理: {device_name}")

# [OK] 推荐: 使用性能监控
with EnhancedPerformanceMonitor(logger, "资源清理"):
    cleanup_resources()

```python

---

## 附录A: 完整示例

### A.1 主程序示例

```python
#!/usr/bin/env python3
"""BTC碰撞引擎主程序"""

import sys
import logging
from src.utils import (
    init_logging, 
    get_configured_logger,
    EnhancedPerformanceMonitor,
    get_performance_tracker,
    log_performance_summary
)
from src.collision import create_collision_engine

logger = get_configured_logger(__name__)

def main():
    """主函数"""
    # 1. 初始化日志
    init_logging()
    logger.info("BTC碰撞引擎启动")
    
    # 2. 加载配置
    with EnhancedPerformanceMonitor(logger, "配置加载", level="INFO"):
        config = load_config()
    
    # 3. 创建引擎
    with EnhancedPerformanceMonitor(logger, "引擎创建", level="INFO") as pm:
        engine = create_collision_engine(
            targets=config['targets'],
            mode=config['mode'],
            config=config
        )
        pm.add_metadata('mode', config['mode'])
    
    # 4. 启动引擎
    logger.info("开始碰撞...")
    engine.start()
    
    # 5. 输出性能统计
    log_performance_summary(logger)
    
    logger.info("程序退出")

if __name__ == '__main__':
    main()

```markdown

### A.2 模块示例

```python
"""GPU碰撞引擎模块"""

import logging
from src.utils import (
    EnhancedPerformanceMonitor,
    get_sampled_logger,
    ExceptionHandler
)

logger = logging.getLogger(__name__)
sampled_logger = get_sampled_logger("GPUCollision.sampled", sample_rate=1000)

class GPUCollisionEngine:
    def __init__(self, targets):
        with EnhancedPerformanceMonitor(logger, "GPU引擎初始化") as pm:
            self._init_gpu()
            pm.add_metadata('targets', len(targets))
    
    def process_batch(self, batch):
        with EnhancedPerformanceMonitor(logger, "批次处理", level="DEBUG"):
            try:
                results = self._gpu_kernel.run(batch)
                sampled_logger.info(
                    f"批次完成: {len(results)} 个结果"
                )
                return results
            except Exception as e:
                ExceptionHandler.handle_gpu_error("批次处理", e)
                return []

```python

---

## 附录B: 常见问题

### Q1: 日志没有输出？

**A**: 检查日志级别配置：

```python
# 检查当前级别
logger = logging.getLogger(__name__)
print(f"日志级别: {logger.level}")

# 确保初始化
from src.utils import init_logging
init_logging()

```markdown

## Q2: 如何禁用文件日志？

**A**: 配置中设置`enable_file=False`：

```python
init_logging({"enable_file": False})

```markdown

### Q3: 如何动态修改日志级别？

**A**: 

```python
import logging

# 修改根日志级别
logging.getLogger().setLevel(logging.DEBUG)

# 修改特定模块级别
logging.getLogger("src.collision").setLevel(logging.DEBUG)

```markdown

## Q4: 采样日志不工作？

**A**: 确保使用同一个采样日志器实例：

```python
# [OK] 正确: 全局实例
sampled_logger = get_sampled_logger("mymodule", sample_rate=1000)

def func1():
    sampled_logger.info("消息1")

def func2():
    sampled_logger.info("消息2")

# [FAIL] 错误: 每次创建新实例
def func():
    sampled_logger = get_sampled_logger("mymodule", sample_rate=1000)
    sampled_logger.info("消息")

```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-20  
**维护者**: BTC碰撞引擎开发团队
