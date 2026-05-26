# BTC Collision Engine - 架构分离设计方案

**版本**: v4.5.1

## 1. 概述

### 1.1 目标

将BTC碰撞引擎的引导界面与日志界面进行分离设计，实现：

- **引导界面模块**：专注于用户交互与流程引导

- **日志处理模块**：专注于日志的收集、处理与存储功能

- **模块独立运行**：两个模块可独立运行，同时保持必要的数据交互

### 1.2 设计原则

- **高内聚低耦合**：每个模块职责单一，模块间依赖最小化

- **接口清晰**：定义明确的模块间接口和数据传递方式

- **独立运行**：支持模块独立测试和运行

- **向后兼容**：不影响现有功能和使用方式

---

## 2. 当前架构分析

### 2.1 现有模块结构

```text
f:\Qoder\btc-collision-engine\
├── start.bat                      # 启动脚本
├── key_collision_cli.py           # CLI入口
├── src/
│   ├── cli/
│   │   ├── main.py               # CLI主逻辑
│   │   ├── commands.py           # 命令处理(含快速引导)
│   │   ├── output.py             # 输出管理
│   │   └── ...
│   ├── monitoring/
│   │   ├── data_logger.py        # 数据日志记录
│   │   ├── monitoring_system.py  # 监控系统
│   │   └── ...
│   └── utils/
│       ├── logger.py              # 日志工具
│       └── first_run_wizard.py    # 首次运行向导

```

### 2.2 问题

- **引导逻辑与日志逻辑混杂**：`_cmd_quick_start`等函数包含大量用户交互代码

- **日志处理分散**：data_logger、logger等分散在不同目录

- **start.bat职责过多**：处理启动选择、命令分发、环境检查等

---

## 3. 目标架构

### 3.1 分离后的目录结构

```text
f:\Qoder\btc-collision-engine\
├── start.bat                      # 启动脚本(简化版)
├── key_collision_cli.py           # CLI入口
├── src/
│   ├── wizard/                   # [新建] 引导界面模块
│   │   ├── __init__.py
│   │   ├── wizard_engine.py      # 向导引擎
│   │   ├── target_selector.py    # 目标选择器
│   │   ├── mode_selector.py      # 模式选择器
│   │   ├── option_selector.py    # 选项选择器
│   │   ├── gpu_selector.py       # GPU选择器
│   │   └── config_builder.py     # 配置构建器
│   ├── logging/                   # [新建] 日志处理模块
│   │   ├── __init__.py
│   │   ├── log_manager.py        # 日志管理器
│   │   ├── log_collector.py      # 日志收集器
│   │   ├── log_processor.py      # 日志处理器
│   │   ├── log_storage.py        # 日志存储器
│   │   └── log_query.py          # 日志查询器
│   ├── cli/
│   │   ├── main.py               # CLI主逻辑(精简版)
│   │   ├── commands.py           # 命令处理(精简版)
│   │   └── ...
│   ├── monitoring/
│   │   ├── data_logger.py        # 数据日志记录(重构)
│   │   └── ...
│   └── utils/
│       └── logger.py              # 日志工具(重构)

```

### 3.2 模块职责划分

#### 引导界面模块 (src/wizard/)

| 文件 | 职责 |
|------|------|
| wizard_engine.py | 向导引擎，协调各选择器工作 |
| target_selector.py | 目标地址选择 |
| mode_selector.py | 碰撞模式选择 |
| option_selector.py | 功能选项选择 |
| gpu_selector.py | GPU设备选择 |
| config_builder.py | 构建最终配置 |

#### 日志处理模块 (src/log_engine/)

| 文件 | 职责 |
|------|------|
| log_manager.py | 日志管理器，对外统一接口 |
| log_collector.py | 收集日志数据 |
| log_processor.py | 处理和格式化日志 |
| log_storage.py | 存储日志到文件 |
| log_query.py | 查询和检索日志 |

---

## 4. 模块间接口定义

### 4.1 引导模块 → 日志模块接口

```python
# src/wizard/interfaces.py
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class WizardResult:
    """引导结果数据结构"""
    success: bool
    targets: list[str]
    mode: str
    checkpoint: bool
    dedup: bool
    duration: int
    gpu_indices: list[int]
    config: Dict[str, Any]
    command: list[str]

@dataclass
class LogConfig:
    """日志配置"""
    log_level: str = "INFO"
    log_file: Optional[str] = None
    console_output: bool = True
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

```

### 4.2 消息队列接口

```python
# src/wizard/message_queue.py
import queue
import threading
from typing import Optional, Dict, Any

class WizardLogQueue:
    """引导模块到日志模块的消息队列"""

    def __init__(self, maxsize: int = 1000):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._enabled = True

    def send(self, event_type: str, data: Dict[str, Any], priority: int = 5) -> bool:
        """发送事件到日志模块"""
        if not self._enabled:
            return False
        try:
            message = {
                'type': event_type,
                'data': data,
                'priority': priority,
                'timestamp': time.time()
            }
            self._queue.put_nowait(message)
            return True
        except queue.Full:
            return False

    def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """从队列接收消息"""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

```

### 4.3 事件定义

```python
# src/wizard/events.py
from enum import Enum

class WizardEvent(Enum):
    """引导事件类型"""
    WIZARD_START = "wizard_start"
    TARGET_SELECTED = "target_selected"
    MODE_SELECTED = "mode_selected"
    OPTIONS_SELECTED = "options_selected"
    GPU_SELECTED = "gpu_selected"
    WIZARD_COMPLETE = "wizard_complete"
    WIZARD_CANCELLED = "wizard_cancelled"
    WIZARD_ERROR = "wizard_error"

class LogEvent(Enum):
    """日志事件类型"""
    ENGINE_START = "engine_start"
    ENGINE_STOP = "engine_stop"
    ENGINE_ERROR = "engine_error"
    GPU_DETECTED = "gpu_detected"
    PERFORMANCE_UPDATE = "performance_update"
    MATCH_FOUND = "match_found"

```

---

## 5. 数据传递方式

### 5.1 三种数据传递模式

#### 模式1：直接调用（紧耦合）

```python
# 用于同一进程内的数据传递
from src.wizard import WizardEngine
from src.log_engine import LogManager

# 创建实例
wizard = WizardEngine()
log_manager = LogManager()

# 直接传递结果
result = wizard.run()
log_manager.log_wizard_result(result)

```

#### 模式2：消息队列（中等耦合）

```python
# 用于跨线程或进程的数据传递
from src.wizard.message_queue import WizardLogQueue

queue = WizardLogQueue()

# 引导线程发送
queue.send(WizardEvent.WIZARD_COMPLETE, {'config': {...}})

# 日志线程接收
message = queue.receive(timeout=5.0)
if message:
    log_manager.process(message)

```

#### 模式3：文件传递（松耦合）

```python
# 用于独立进程间的数据传递
import json
import tempfile

# 引导进程写入配置
config_file = tempfile.mktemp(suffix='.json')
with open(config_file, 'w') as f:
    json.dump(config, f)

# 日志进程读取配置
with open(config_file, 'r') as f:
    config = json.load(f)

```

### 5.2 推荐的传递方式

| 场景 | 推荐方式 | 原因 |
|------|----------|------|
| 同一进程内 | 直接调用 | 性能最好，实现简单 |
| 多线程环境 | 消息队列 | 线程安全，异步处理 |
| 独立进程 | 文件传递 | 完全解耦，可独立运行 |

---

## 6. start.bat 改造方案

### 6.1 改造后的start.bat结构

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM BTC Collision Engine - 启动脚本 (分离版)

REM ---- 加载配置 ----
call :load_config

REM ---- 处理工具命令 ----
if defined TOOL_CMD (
    goto :handle_tool_cmd
)

REM ---- 显示启动选择菜单 ----
call :show_start_menu

REM ---- 执行选择 ----
call :execute_selection

exit /b %EXIT_CODE%

:load_config
REM 加载配置文件
set "CONFIG_FILE=config.json"
set "WIZARD_MODULE=src.wizard.wizard_engine"
set "LOGGING_MODULE=src.log_engine.log_manager"
set "WIZARD_LOG_FILE=logs\wizard.log"
set "ENGINE_LOG_FILE=logs\collision.log"
goto :eof

:show_start_menu
REM 显示启动选择菜单
echo.
echo ========================================
echo   BTC Collision Engine - 启动选择
echo ========================================
echo.
echo   1. 交互式向导 (推荐新手)
echo   2. 快速模式 (使用 targets.txt)
echo   3. Interactive Menu
echo   0. 取消启动
echo.
set /p CHOICE=请输入选项 (0-3, 默认 1):
if "!CHOICE!"=="" set "CHOICE=1"
goto :eof

:handle_tool_cmd
REM 处理工具命令
python key_collision_cli.py %*
exit /b %errorlevel%

:execute_selection
if "!CHOICE!"=="1" (
    python -m src.wizard.wizard_engine
) else if "!CHOICE!"=="2" (
    python key_collision_cli.py --quick-run
) else if "!CHOICE!"=="3" (
    python key_collision_cli.py --menu
) else if "!CHOICE!"=="0" (
    echo 取消启动。
    exit /b 0
)
goto :eof

```

### 6.2 启动模式对应关系

| 模式 | 命令 | 说明 |
|------|------|------|
| 交互式向导 | `python -m src.wizard.wizard_engine` | 仅运行引导模块 |
| 快速模式 | `python key_collision_cli.py --quick-run` | 使用默认配置启动引擎 |
| 日志模式 | `python -m src.log_engine.log_manager --watch` | 仅运行日志监控 |

---

## 7. 实现步骤

### 阶段1：创建引导模块

1. 创建 `src/wizard/__init__.py`

2. 实现 `wizard_engine.py` - 向导引擎

3. 实现 `target_selector.py` - 目标选择器

4. 实现 `mode_selector.py` - 模式选择器

5. 实现 `option_selector.py` - 选项选择器

6. 实现 `gpu_selector.py` - GPU选择器

7. 实现 `config_builder.py` - 配置构建器

8. 创建接口定义文件

### 阶段2：创建日志模块

1. 创建 `src/log_engine/__init__.py`

2. 实现 `log_manager.py` - 日志管理器

3. 实现 `log_collector.py` - 日志收集器

4. 实现 `log_processor.py` - 日志处理器

5. 实现 `log_storage.py` - 日志存储器

6. 实现 `log_query.py` - 日志查询器

7. 整合现有日志功能

### 阶段3：修改start.bat

1. 简化start.bat代码

2. 添加新的启动选项

3. 支持独立运行各模块

### 阶段4：测试和优化

1. 测试各模块独立运行

2. 测试模块间数据交互

3. 性能优化和错误处理

---

## 8. 接口兼容性保证

### 8.1 向后兼容

- 原有的 `key_collision_cli.py` 保持不变

- 原有的命令行参数保持不变

- start.bat 的使用方式保持不变

### 8.2 新增接口

- 提供 Python API 供其他模块调用

- 提供命令行接口供独立运行

- 提供配置文件接口供数据传递

### 8.3 文档

- 为每个模块编写使用文档

- 提供接口调用示例

- 提供故障排查指南

---

## 9. 总结

本方案通过以下方式实现引导界面与日志界面的分离：

1. **模块化设计**：创建独立的 `src/wizard/` 和 `src/log_engine/` 目录

2. **清晰接口**：定义明确的数据结构和消息传递方式

3. **灵活部署**：支持独立运行和组合运行

4. **向后兼容**：不影响现有功能和使用方式

通过实施本方案，可以实现：

- 引导界面专注于用户交互，提升用户体验

- 日志处理独立进行，提高系统整体性能

- 模块独立测试，降低维护成本

- 灵活的部署方式，适应不同场景需求
