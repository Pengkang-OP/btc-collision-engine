# BTC碰撞引擎 - 架构优化修复方案

**问题来源**: 模块集成度分析报告 (MODULE_INTEGRATION_ANALYSIS_v3.1.1.md)  
**创建日期**: 2026-04-24  
**优先级**: P1 (高优先级)  
**预计工时**: 6.5小时

---

## 📋 问题清单

| 编号 | 问题 | 严重度 | 影响范围 | 预计工时 |
|------|------|--------|---------|---------|
| **P1-1** | DataLogger与碰撞引擎直接耦合 | 高 | collision/ + monitoring/ | 4小时 |
| **P1-2** | 回调函数类型提示不统一 | 中 | collision/*.py | 2小时 |
| **P1-3** | 部分组件可引入依赖注入 | 低 | 多个模块 | 0.5小时 |

---

## 🔧 修复方案 P1-1: DataLogger解耦

### 问题分析

**当前架构 (紧耦合)**:

```python
# src/collision/key_collision_engine.py
class KeyCollisionEngine(BaseCollisionEngine):
    def __init__(self, ..., data_logging_enabled: bool = True, ...):
        # 问题1: 引擎内部直接实例化DataLogger
        if data_logging_enabled:
            if use_enhanced_monitoring:
                self.enhanced_monitoring = EnhancedMonitoringSystem(
                    engine=self,  # 问题2: 直接传递self，形成循环依赖
                    ...
                )
                self.data_logger = self.enhanced_monitoring.data_logger
            else:
                self.data_logger = DataLogger()  # 问题3: 硬编码创建
```

**问题**:

1. ❌ 引擎直接依赖DataLogger实现，无法替换为Mock
2. ❌ EnhancedMonitoringSystem需要engine引用，形成循环依赖
3. ❌ 单元测试时必须启动完整的监控系统
4. ❌ 违反依赖倒置原则 (DIP)

---

### 解决方案: 事件总线架构

#### 方案设计

```
┌─────────────────────────────────────────────┐
│          碰撞引擎 (CollisionEngine)          │
│                                             │
│  发布事件:                                   │
│  - EngineProgressEvent                      │
│  - EngineMatchEvent                         │
│  - EngineErrorEvent                         │
│  - EngineCompleteEvent                      │
└──────────────┬──────────────────────────────┘
               │
               │ 发布/订阅
               ▼
┌─────────────────────────────────────────────┐
│          事件总线 (EventBus)                 │
│                                             │
│  - subscribe(event_type, handler)           │
│  - publish(event)                           │
│  - unsubscribe(event_type, handler)         │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐
│Data- │  │Alert │  │Custom│
│Logger│  │System│  │Handler│
│(订阅)│  │(订阅)│  │(订阅)│
└──────┘  └──────┘  └──────┘
```

#### 实现代码

**步骤1: 创建事件定义模块**

```python
# src/collision/events.py
"""碰撞引擎事件定义"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum
from datetime import datetime

class EventType(Enum):
    """事件类型枚举"""
    ENGINE_PROGRESS = "engine.progress"
    ENGINE_MATCH = "engine.match"
    ENGINE_ERROR = "engine.error"
    ENGINE_COMPLETE = "engine.complete"
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"

@dataclass
class CollisionEvent:
    """碰撞事件基类"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "collision_engine"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EngineProgressEvent(CollisionEvent):
    """引擎进度事件"""
    total_checked: int = 0
    speed: float = 0.0
    matches_found: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    def __post_init__(self):
        self.event_type = EventType.ENGINE_PROGRESS

@dataclass
class EngineMatchEvent(CollisionEvent):
    """引擎匹配事件"""
    private_key: bytes = b""
    address: str = ""
    wif: str = ""
    target_address: str = ""
    
    def __post_init__(self):
        self.event_type = EventType.ENGINE_MATCH

@dataclass
class EngineErrorEvent(CollisionEvent):
    """引擎错误事件"""
    error_type: str = ""
    error_message: str = ""
    exception: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.event_type = EventType.ENGINE_ERROR

@dataclass
class EngineCompleteEvent(CollisionEvent):
    """引擎完成事件"""
    total_checked: int = 0
    matches_found: int = 0
    elapsed_time: float = 0.0
    avg_speed: float = 0.0
    
    def __post_init__(self):
        self.event_type = EventType.ENGINE_COMPLETE
```

---

**步骤2: 创建事件总线**

```python
# src/collision/event_bus.py
"""事件总线实现 - 发布/订阅模式"""
import threading
from typing import Callable, Dict, List, Any
from collections import defaultdict
import logging

from .events import CollisionEvent, EventType

logger = logging.getLogger(__name__)

class EventBus:
    """
    事件总线 - 解耦组件通信
    
    使用示例:
        >>> bus = EventBus()
        >>> 
        >>> # 订阅事件
        >>> bus.subscribe(EventType.ENGINE_PROGRESS, handle_progress)
        >>> bus.subscribe(EventType.ENGINE_MATCH, handle_match)
        >>> 
        >>> # 发布事件
        >>> bus.publish(EngineProgressEvent(total_checked=1000, speed=500000))
        >>> 
        >>> # 取消订阅
        >>> bus.unsubscribe(EventType.ENGINE_PROGRESS, handle_progress)
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._error_handler: Optional[Callable] = None
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数，签名为 handler(event: CollisionEvent) -> None
        """
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(f"订阅事件: {event_type.value}, 处理器: {handler.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"取消订阅: {event_type.value}, 处理器: {handler.__name__}")
    
    def publish(self, event: CollisionEvent) -> None:
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        with self._lock:
            handlers = self._subscribers.get(event.event_type, []).copy()
        
        # 在锁外执行处理器，避免死锁
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理器异常: {handler.__name__}, 错误: {e}")
                if self._error_handler:
                    self._error_handler(event, e)
    
    def set_error_handler(self, handler: Callable) -> None:
        """
        设置全局错误处理器
        
        Args:
            handler: 错误处理函数，签名为 handler(event, exception) -> None
        """
        self._error_handler = handler
    
    def clear(self) -> None:
        """清空所有订阅"""
        with self._lock:
            self._subscribers.clear()
    
    @property
    def subscriber_count(self) -> int:
        """获取订阅者总数"""
        with self._lock:
            return sum(len(handlers) for handlers in self._subscribers.values())

# 全局事件总线实例 (可选使用)
_global_event_bus: EventBus = None

def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus

def reset_event_bus() -> None:
    """重置全局事件总线 (主要用于测试)"""
    global _global_event_bus
    _global_event_bus = None
```

---

**步骤3: 创建事件适配器**

```python
# src/monitoring/event_adapters.py
"""监控系统事件适配器 - 将事件转换为监控调用"""
import logging
from typing import Optional

from src.collision.events import (
    CollisionEvent,
    EngineProgressEvent,
    EngineMatchEvent,
    EngineErrorEvent,
    EngineCompleteEvent,
    EventType
)
from src.monitoring.data_logger import DataLogger
from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem

logger = logging.getLogger(__name__)

class DataLoggerAdapter:
    """
    DataLogger事件适配器
    
    订阅引擎事件并自动记录到数据日志
    """
    
    def __init__(self, data_logger: Optional[DataLogger] = None):
        self.data_logger = data_logger or DataLogger()
    
    def handle_progress(self, event: EngineProgressEvent) -> None:
        """处理进度事件"""
        if self.data_logger:
            self.data_logger.record_performance_data(
                speed=event.speed,
                total_checked=event.total_checked,
                matches_found=event.matches_found,
                cpu_usage=event.cpu_usage,
                memory_usage=event.memory_usage
            )
    
    def handle_match(self, event: EngineMatchEvent) -> None:
        """处理匹配事件"""
        if self.data_logger:
            self.data_logger.record_match(
                private_key=event.private_key,
                address=event.address,
                wif=event.wif,
                target_address=event.target_address
            )
    
    def handle_error(self, event: EngineErrorEvent) -> None:
        """处理错误事件"""
        if self.data_logger:
            self.data_logger.record_error(
                error_type=event.error_type,
                message=event.error_message,
                exception=event.exception,
                context=event.context
            )
    
    def handle_complete(self, event: EngineCompleteEvent) -> None:
        """处理完成事件"""
        if self.data_logger:
            self.data_logger.save_current_data()

class EnhancedMonitoringAdapter:
    """
    EnhancedMonitoringSystem事件适配器
    
    订阅引擎事件并触发增强监控
    """
    
    def __init__(self, monitoring_system: EnhancedMonitoringSystem):
        self.monitoring_system = monitoring_system
    
    def handle_progress(self, event: EngineProgressEvent) -> None:
        """处理进度事件"""
        # 增强监控已通过独立线程运行，这里只传递关键数据
        pass  # EnhancedMonitoringSystem自行采集数据
    
    def handle_error(self, event: EngineErrorEvent) -> None:
        """处理错误事件"""
        if self.monitoring_system:
            self.monitoring_system.handle_error(
                error=event.exception or Exception(event.error_message),
                context=event.context
            )
```

---

**步骤4: 重构碰撞引擎**

```python
# src/collision/key_collision_engine.py (重构后)
"""比特币私钥对撞引擎 - 事件驱动版本"""
import os
import time
import threading
import secrets
from typing import Set, Optional, Callable, Dict, Any

from ..core.address_generator import P2PKHAddressGenerator
from ..core.crypto_backend import crypto_manager
from .collision_stats import CollisionStats
from .checkpoint_manager import CheckpointManager
from .deduplication_filter import DeduplicationFilter
from .base_engine import BaseCollisionEngine
from .event_bus import EventBus, get_event_bus
from .events import (
    EngineProgressEvent,
    EngineMatchEvent,
    EngineErrorEvent,
    EngineCompleteEvent
)
from ..utils import init_logging, get_configured_logger

logger = get_configured_logger("KeyCollisionEngine")

class KeyCollisionEngine(BaseCollisionEngine):
    """比特币私钥对撞引擎 (CPU实现) - 事件驱动版本"""

    def __init__(self, targets: Set[str],
                 on_progress: Optional[Callable] = None,
                 on_match: Optional[Callable[[bytes, str, str], None]] = None,
                 on_complete: Optional[Callable] = None,
                 checkpoint_enabled: bool = False,
                 dedup_enabled: bool = False,
                 dedup_max_size: int = 1_000_000,
                 checkpoint_interval: int = 30,
                 max_workers: Optional[int] = None,
                 # 新增: 事件总线支持
                 event_bus: Optional[EventBus] = None,
                 # 保留向后兼容
                 data_logging_enabled: bool = True,
                 data_logging_interval: int = 5,
                 use_enhanced_monitoring: bool = True):
        """
        初始化碰撞引擎
        
        Args:
            targets: 目标地址集合
            on_progress: 进度回调 (向后兼容)
            on_match: 匹配回调 (向后兼容)
            on_complete: 完成回调 (向后兼容)
            event_bus: 事件总线 (新方式，推荐)
            data_logging_enabled: 是否启用数据日志 (向后兼容)
            use_enhanced_monitoring: 是否使用增强监控 (向后兼容)
        """
        super().__init__()
        
        self.targets = targets
        self.stats = CollisionStats()
        self.event_bus = event_bus or EventBus()
        
        # 初始化回调 (向后兼容)
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
        
        # 初始化支撑系统
        self.checkpoint_manager = CheckpointManager(
            enabled=checkpoint_enabled,
            interval=checkpoint_interval
        ) if checkpoint_enabled else None
        
        self.dedup_filter = DeduplicationFilter(
            enabled=dedup_enabled,
            max_size=dedup_max_size
        ) if dedup_enabled else None
        
        # 向后兼容: 自动订阅事件
        if data_logging_enabled:
            self._setup_legacy_monitoring(use_enhanced_monitoring)
        
        logger.info(f"碰撞引擎初始化完成 (事件驱动模式)")
    
    def _setup_legacy_monitoring(self, use_enhanced_monitoring: bool) -> None:
        """设置向后兼容的监控系统"""
        from src.monitoring.event_adapters import DataLoggerAdapter, EnhancedMonitoringAdapter
        from src.monitoring.data_logger import DataLogger
        from src.monitoring.enhanced_monitoring import EnhancedMonitoringSystem
        
        adapter = DataLoggerAdapter()
        
        # 订阅事件
        self.event_bus.subscribe(EventType.ENGINE_PROGRESS, adapter.handle_progress)
        self.event_bus.subscribe(EventType.ENGINE_MATCH, adapter.handle_match)
        self.event_bus.subscribe(EventType.ENGINE_ERROR, adapter.handle_error)
        self.event_bus.subscribe(EventType.ENGINE_COMPLETE, adapter.handle_complete)
        
        self.data_logger = adapter.data_logger
        logger.info("数据日志系统已启用 (事件驱动)")
    
    def _emit_progress(self) -> None:
        """发布进度事件"""
        event = EngineProgressEvent(
            total_checked=self.stats.total_checked,
            speed=self.stats.speed,
            matches_found=self.stats.matches_found,
            cpu_usage=self.stats.cpu_usage,
            memory_usage=self.stats.memory_usage
        )
        self.event_bus.publish(event)
        
        # 向后兼容: 调用旧回调
        if self.on_progress:
            self.on_progress(self.stats)
    
    def _emit_match(self, private_key: bytes, address: str, wif: str) -> None:
        """发布匹配事件"""
        event = EngineMatchEvent(
            private_key=private_key,
            address=address,
            wif=wif
        )
        self.event_bus.publish(event)
        
        # 向后兼容: 调用旧回调
        if self.on_match:
            self.on_match(private_key, address, wif)
    
    def _emit_error(self, error_type: str, message: str, exception: Exception = None) -> None:
        """发布错误事件"""
        event = EngineErrorEvent(
            error_type=error_type,
            error_message=message,
            exception=exception
        )
        self.event_bus.publish(event)
    
    def _emit_complete(self) -> None:
        """发布完成事件"""
        event = EngineCompleteEvent(
            total_checked=self.stats.total_checked,
            matches_found=self.stats.matches_found,
            elapsed_time=self.stats.elapsed_time,
            avg_speed=self.stats.avg_speed
        )
        self.event_bus.publish(event)
        
        # 向后兼容: 调用旧回调
        if self.on_complete:
            self.on_complete(self.stats)
```

---

### 优势对比

| 维度 | 当前架构 (紧耦合) | 新架构 (事件驱动) |
|------|------------------|------------------|
| **可测试性** | ❌ 需要完整监控系统 | ✅ 可Mock EventBus |
| **可扩展性** | ❌ 修改引擎代码 | ✅ 添加订阅者即可 |
| **解耦度** | ❌ 引擎直接依赖DataLogger | ✅ 通过事件总线 |
| **向后兼容** | - | ✅ 保留旧回调 |
| **性能** | - | ✅ 异步事件处理 |
| **代码复杂度** | 中 | 中+ (增加事件层) |

---

## 🔧 修复方案 P1-2: 回调函数类型提示统一

### 问题分析

**当前状态 (不统一)**:

```python
# CPU引擎 - 有类型提示
def __init__(self, targets: Set[str],
             on_progress: Optional[Callable[[Any], None]] = None,
             on_match: Optional[Callable[[bytes, str, str], None]] = None,
             on_complete: Optional[Callable[[Any], None]] = None):

# GPU引擎 - 无类型提示
def __init__(self, targets: Set[str],
             on_progress: Optional[Callable] = None,  # ❌ 缺少参数类型
             on_match: Optional[Callable] = None,     # ❌ 缺少参数类型
             on_complete: Optional[Callable] = None): # ❌ 缺少参数类型
```

---

### 解决方案: 类型别名 + 统一签名

**步骤1: 定义类型别名**

```python
# src/collision/types.py
"""碰撞引擎类型定义"""
from typing import Callable, Optional, Any
from .collision_stats import CollisionStats

# 回调函数类型别名
ProgressCallback = Callable[[CollisionStats], None]
"""进度回调函数类型: (stats: CollisionStats) -> None"""

MatchCallback = Callable[[bytes, str, str], None]
"""匹配回调函数类型: (private_key: bytes, address: str, wif: str) -> None"""

CompleteCallback = Callable[[CollisionStats], None]
"""完成回调函数类型: (stats: CollisionStats) -> None"""

ErrorCallback = Callable[[str, str, Optional[Exception]], None]
"""错误回调函数类型: (error_type: str, message: str, exception: Optional[Exception]) -> None"""
```

---

**步骤2: 更新CPU引擎**

```python
# src/collision/key_collision_engine.py
from .types import ProgressCallback, MatchCallback, CompleteCallback

class KeyCollisionEngine(BaseCollisionEngine):
    def __init__(self, targets: Set[str],
                 on_progress: Optional[ProgressCallback] = None,  # ✅ 统一
                 on_match: Optional[MatchCallback] = None,        # ✅ 统一
                 on_complete: Optional[CompleteCallback] = None,  # ✅ 统一
                 ...):
```

---

**步骤3: 更新GPU引擎**

```python
# src/collision/gpu_collision_engine.py
from .types import ProgressCallback, MatchCallback, CompleteCallback

class GPUCollisionEngine(BaseCollisionEngine):
    def __init__(self, targets: Set[str],
                 device_index: int = 1,
                 batch_size: int = None,
                 on_progress: Optional[ProgressCallback] = None,  # ✅ 统一
                 on_match: Optional[MatchCallback] = None,        # ✅ 统一
                 on_complete: Optional[CompleteCallback] = None,  # ✅ 统一
                 ...):
```

---

**步骤4: 更新基类**

```python
# src/collision/base_engine.py
from .types import ProgressCallback, MatchCallback, CompleteCallback

class BaseCollisionEngine:
    """碰撞引擎抽象基类"""
    
    def __init__(self,
                 on_progress: Optional[ProgressCallback] = None,
                 on_match: Optional[MatchCallback] = None,
                 on_complete: Optional[CompleteCallback] = None):
        self.on_progress = on_progress
        self.on_match = on_match
        self.on_complete = on_complete
```

---

### 优势

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| **类型安全** | ❌ GPU引擎无类型检查 | ✅ 全部类型检查 |
| **IDE提示** | ❌ 参数不明确 | ✅ 完整参数提示 |
| **一致性** | ❌ CPU/GPU不一致 | ✅ 完全一致 |
| **文档生成** | ❌ 无法自动生成 | ✅ 可自动生成 |

---

## 🔧 修复方案 P1-3: 引入依赖注入

### 问题分析

**当前状态 (部分硬编码)**:

```python
# 问题: 引擎内部直接创建依赖
class KeyCollisionEngine:
    def __init__(self):
        self.checkpoint_manager = CheckpointManager(...)  # 硬编码
        self.dedup_filter = DeduplicationFilter(...)      # 硬编码
        self.stats = CollisionStats()                     # 硬编码
```

---

### 解决方案: 构造函数注入

**改进版本**:

```python
# src/collision/key_collision_engine.py
class KeyCollisionEngine(BaseCollisionEngine):
    def __init__(self, 
                 targets: Set[str],
                 # 核心依赖 (必须)
                 crypto_backend=None,
                 
                 # 可选依赖 (提供默认值)
                 checkpoint_manager: Optional[CheckpointManager] = None,
                 dedup_filter: Optional[DeduplicationFilter] = None,
                 stats: Optional[CollisionStats] = None,
                 event_bus: Optional[EventBus] = None,
                 
                 # 配置参数
                 checkpoint_enabled: bool = False,
                 dedup_enabled: bool = False,
                 ...):
        """
        初始化碰撞引擎 (依赖注入版本)
        
        Args:
            targets: 目标地址集合
            crypto_backend: 加密后端 (默认使用全局管理器)
            checkpoint_manager: 断点管理器 (默认自动创建)
            dedup_filter: 去重过滤器 (默认自动创建)
            stats: 碰撞统计 (默认自动创建)
            event_bus: 事件总线 (默认自动创建)
        """
        super().__init__()
        
        self.targets = targets
        
        # 依赖注入: 使用传入或创建默认
        self.crypto_backend = crypto_backend or crypto_manager
        self.stats = stats or CollisionStats()
        self.event_bus = event_bus or EventBus()
        
        # 条件创建
        self.checkpoint_manager = checkpoint_manager or (
            CheckpointManager(enabled=checkpoint_enabled) if checkpoint_enabled else None
        )
        
        self.dedup_filter = dedup_filter or (
            DeduplicationFilter(enabled=dedup_enabled) if dedup_enabled else None
        )
```

---

### 单元测试示例

```python
# tests/test_key_collision_engine.py
import pytest
from unittest.mock import Mock, MagicMock
from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.event_bus import EventBus
from src.collision.collision_stats import CollisionStats

class TestKeyCollisionEngine:
    """碰撞引擎单元测试 - 依赖注入版本"""
    
    def setup_method(self):
        """每个测试前准备"""
        self.targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        
        # Mock依赖
        self.mock_event_bus = Mock(spec=EventBus)
        self.mock_stats = Mock(spec=CollisionStats)
        self.mock_checkpoint = Mock()
        self.mock_dedup = Mock()
    
    def test_engine_with_injected_dependencies(self):
        """测试注入依赖的引擎"""
        # 注入Mock依赖
        engine = KeyCollisionEngine(
            targets=self.targets,
            event_bus=self.mock_event_bus,
            stats=self.mock_stats,
            checkpoint_manager=self.mock_checkpoint,
            dedup_filter=self.mock_dedup
        )
        
        # 验证使用注入的依赖
        assert engine.event_bus is self.mock_event_bus
        assert engine.stats is self.mock_stats
        assert engine.checkpoint_manager is self.mock_checkpoint
        assert engine.dedup_filter is self.mock_dedup
    
    def test_engine_creates_default_dependencies(self):
        """测试默认创建依赖"""
        engine = KeyCollisionEngine(targets=self.targets)
        
        # 验证自动创建
        assert engine.event_bus is not None
        assert engine.stats is not None
        assert isinstance(engine.event_bus, EventBus)
        assert isinstance(engine.stats, CollisionStats)
    
    def test_engine_publishes_progress_event(self):
        """测试引擎发布进度事件"""
        engine = KeyCollisionEngine(
            targets=self.targets,
            event_bus=self.mock_event_bus
        )
        
        # 触发进度更新
        engine._emit_progress()
        
        # 验证事件发布
        self.mock_event_bus.publish.assert_called_once()
        event = self.mock_event_bus.publish.call_args[0][0]
        assert event.event_type.value == "engine.progress"
```

---

## 📊 实施计划

### 阶段1: 事件总线 (4小时)

| 任务 | 文件 | 工时 |
|------|------|------|
| 创建事件定义 | `src/collision/events.py` | 1小时 |
| 创建事件总线 | `src/collision/event_bus.py` | 1小时 |
| 创建事件适配器 | `src/monitoring/event_adapters.py` | 1小时 |
| 重构碰撞引擎 | `src/collision/key_collision_engine.py` | 0.5小时 |
| 重构GPU引擎 | `src/collision/gpu_collision_engine.py` | 0.5小时 |

### 阶段2: 类型提示统一 (2小时)

| 任务 | 文件 | 工时 |
|------|------|------|
| 定义类型别名 | `src/collision/types.py` | 0.5小时 |
| 更新CPU引擎 | `src/collision/key_collision_engine.py` | 0.5小时 |
| 更新GPU引擎 | `src/collision/gpu_collision_engine.py` | 0.5小时 |
| 更新基类 | `src/collision/base_engine.py` | 0.5小时 |

### 阶段3: 依赖注入 (0.5小时)

| 任务 | 文件 | 工时 |
|------|------|------|
| 更新构造函数 | `src/collision/key_collision_engine.py` | 0.25小时 |
| 编写单元测试 | `tests/test_engine_di.py` | 0.25小时 |

---

## ✅ 验收标准

### P1-1: DataLogger解耦

- [ ] 碰撞引擎不直接实例化DataLogger
- [ ] 通过EventBus发布事件
- [ ] DataLogger通过适配器订阅事件
- [ ] 向后兼容: 旧回调仍可用
- [ ] 单元测试可Mock EventBus
- [ ] 无性能退化 (< 5%开销)

### P1-2: 类型提示统一

- [ ] CPU和GPU引擎回调签名一致
- [ ] 所有回调使用类型别名
- [ ] IDE类型检查通过
- [ ] mypy类型检查通过

### P1-3: 依赖注入

- [ ] 核心组件可通过构造函数注入
- [ ] 提供合理的默认值
- [ ] 单元测试可注入Mock
- [ ] 向后兼容: 不传参时自动创建

---

## 🎯 预期收益

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| **可测试性** | 6/10 | 9/10 | +50% |
| **解耦度** | 7/10 | 9/10 | +29% |
| **代码质量** | 8/10 | 9/10 | +13% |
| **可维护性** | 8/10 | 9.5/10 | +19% |

---

## 📝 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 性能退化 | 低 | 中 | 事件总线优化，异步处理 |
| 向后不兼容 | 低 | 高 | 保留旧回调接口 |
| 复杂度增加 | 中 | 中 | 详细文档和示例 |
| 测试覆盖不足 | 中 | 高 | 编写完整单元测试 |

---

**创建人员**: AI架构师  
**审核状态**: 待审核  
**计划实施**: v3.2.0
