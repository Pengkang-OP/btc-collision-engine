# create_collision_engine 工厂函数使用指南

本文档详细介绍优化后的 `create_collision_engine` 工厂函数的使用方法。

## 目录

- [1. 基本用法](#1-基本用法)
- [2. 使用配置字典](#2-使用配置字典)
- [3. 配置优先级](#3-配置优先级)
- [4. 与ConfigCoordinator集成](#4-与configcoordinator集成)
- [5. 高级模式](#5-高级模式)
- [6. 错误处理](#6-错误处理)
- [7. 完整示例](#7-完整示例)

---

## 1. 基本用法

### 1.1 自动模式（推荐）

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 自动检测GPU可用性
engine = create_collision_engine(targets, mode='auto')

# 检查实际使用的引擎类型
print(f"引擎类型: {type(engine).__name__}")
```

### 1.2 强制GPU模式

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

try:
    # 强制使用GPU
    engine = create_collision_engine(targets, mode='gpu')
    print("✅ GPU引擎创建成功")
except RuntimeError as e:
    print(f"❌ GPU不可用: {e}")
```

### 1.3 强制CPU模式

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 强制使用CPU
engine = create_collision_engine(targets, mode='cpu')
print(f"引擎类型: {type(engine).__name__}")  # KeyCollisionEngine
```

---

## 2. 使用配置字典

### 2.1 基本配置

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 定义配置
config = {
    'gpu': {
        'batch_size': 131072,
        'device_index': 0
    },
    'collision': {
        'max_workers': 4,
        'checkpoint_interval': 60
    }
}

# 使用配置创建引擎
engine = create_collision_engine(targets, mode='auto', config=config)
```

### 2.2 GPU配置项

```python
config = {
    'gpu': {
        'batch_size': 262144,          # 批次大小
        'device_index': 0,             # GPU设备索引（-1=自动选择）
        'memory_usage_ratio': 0.8      # 显存使用比例
    }
}

engine = create_collision_engine(targets, mode='gpu', config=config)
```

### 2.3 碰撞引擎配置项

```python
config = {
    'collision': {
        'max_workers': 8,              # 最大工作线程数
        'checkpoint_interval': 120,    # 断点保存间隔（秒）
        'dedup_max_size': 2000000      # 去重过滤器最大容量
    }
}

engine = create_collision_engine(targets, mode='cpu', config=config)
```

---

## 3. 配置优先级

配置系统遵循以下优先级（从高到低）：

1. **kwargs** - 直接传递的参数（最高优先级）
2. **config** - 配置字典
3. **默认值** - 引擎构造函数的默认值

### 3.1 示例：kwargs覆盖config

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

config = {
    'gpu': {
        'batch_size': 65536,  # config中的值
        'device_index': 0
    }
}

# kwargs中的batch_size会覆盖config中的值
engine = create_collision_engine(
    targets, 
    mode='gpu',
    config=config,
    batch_size=131072  # 使用这个值（65536被覆盖）
)
```

### 3.2 示例：config与kwargs组合

```python
config = {
    'gpu': {
        'batch_size': 65536,      # 被kwargs覆盖
        'device_index': 0         # 使用这个值
    },
    'collision': {
        'max_workers': 4          # 使用这个值
    }
}

engine = create_collision_engine(
    targets,
    mode='auto',
    config=config,
    batch_size=131072  # 只覆盖batch_size
)

# 最终配置：
# - batch_size: 131072 (来自kwargs)
# - device_index: 0 (来自config)
# - max_workers: 4 (来自config)
```

---

## 4. 与ConfigCoordinator集成

### 4.1 从config.json读取配置

```python
from src.config import ConfigCoordinator
from src.collision import create_collision_engine

# 加载配置
coordinator = ConfigCoordinator('config.json')

# 获取统一配置
config = coordinator.get_unified_config()

# 使用配置创建引擎
targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
engine = create_collision_engine(targets, mode='auto', config=config)

print(f"引擎类型: {type(engine).__name__}")
print(f"使用配置: batch_size={config['gpu']['batch_size']}")
```

### 4.2 动态修改配置

```python
from src.config import ConfigCoordinator
from src.collision import create_collision_engine

coordinator = ConfigCoordinator('config.json')

# 修改配置
coordinator.set('gpu.batch_size', 262144)
coordinator.set('collision.max_workers', 8)

# 保存配置
coordinator.save_all()

# 使用更新后的配置创建引擎
config = coordinator.get_unified_config()
engine = create_collision_engine(targets, mode='auto', config=config)
```

### 4.3 多环境配置

```python
from src.config import ConfigCoordinator
from src.collision import create_collision_engine

# 加载不同环境的配置
env = 'dev'  # 或 'prod'
config_file = f'config.{env}.json'

if os.path.exists(config_file):
    coordinator = ConfigCoordinator(config_file)
else:
    coordinator = ConfigCoordinator('config.json')

config = coordinator.get_unified_config()
engine = create_collision_engine(targets, mode='auto', config=config)
```

---

## 5. 高级模式

### 5.1 完整配置示例

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 完整配置
config = {
    'gpu': {
        'batch_size': 262144,
        'device_index': 0,
        'memory_usage_ratio': 0.9
    },
    'collision': {
        'max_workers': 8,
        'checkpoint_interval': 120,
        'dedup_max_size': 5000000
    }
}

# 额外的kwargs
engine = create_collision_engine(
    targets,
    mode='auto',
    config=config,
    on_progress=lambda progress: print(f"进度: {progress}%"),
    on_match=lambda result: print(f"发现匹配: {result}"),
    checkpoint_enabled=True,
    data_logging_enabled=True
)
```

### 5.2 批量创建引擎

```python
from src.collision import create_collision_engine

# 配置列表
configs = [
    {'gpu': {'batch_size': 65536, 'device_index': 0}},
    {'gpu': {'batch_size': 131072, 'device_index': 0}},
    {'gpu': {'batch_size': 262144, 'device_index': 0}},
]

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 批量创建引擎
engines = []
for i, config in enumerate(configs):
    engine = create_collision_engine(targets, mode='gpu', config=config)
    engines.append(engine)
    print(f"引擎{i+1}创建成功")
```

### 5.3 引擎池管理

```python
from src.collision import create_collision_engine

class EnginePool:
    """引擎池管理器"""
    
    def __init__(self, config):
        self.config = config
        self.engines = []
    
    def create_engine(self, targets, mode='auto'):
        """创建引擎并加入池"""
        engine = create_collision_engine(
            targets, 
            mode=mode, 
            config=self.config
        )
        self.engines.append(engine)
        return engine
    
    def get_all_engines(self):
        """获取所有引擎"""
        return self.engines.copy()
    
    def clear(self):
        """清空引擎池"""
        for engine in self.engines:
            if hasattr(engine, 'stop'):
                engine.stop()
        self.engines.clear()

# 使用示例
config = {
    'gpu': {'batch_size': 131072},
    'collision': {'max_workers': 4}
}

pool = EnginePool(config)

# 创建多个引擎
targets_list = [
    {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'},
    {'1BvBMSEYestWZgxZBqQkPQj2Xj3'},
]

targets1, targets2 = targets_list
engine1 = pool.create_engine(targets1, mode='gpu')
engine2 = pool.create_engine(targets2, mode='cpu')

print(f"引擎池大小: {len(pool.get_all_engines())}")
```

---

## 6. 错误处理

### 6.1 GPU不可用

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

try:
    engine = create_collision_engine(targets, mode='gpu')
except RuntimeError as e:
    print(f"GPU创建失败: {e}")
    # 回退到CPU
    engine = create_collision_engine(targets, mode='cpu')
    print("已回退到CPU引擎")
```

### 6.2 配置验证

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 无效的配置
try:
    engine = create_collision_engine(targets, mode='invalid')
except ValueError as e:
    print(f"配置错误: {e}")
    # 输出: 无效的mode参数: invalid，必须是 'auto', 'gpu' 或 'cpu'
```

### 6.3 空目标集合警告

```python
from src.collision import create_collision_engine
import logging

# 启用日志
logging.basicConfig(level=logging.WARNING)

# 空目标集合会触发警告
targets = set()
engine = create_collision_engine(targets, mode='cpu')
# 日志输出: WARNING - 目标地址集合为空，碰撞将无意义
```

### 6.4 完整错误处理示例

```python
from src.collision import create_collision_engine

def safe_create_engine(targets, mode='auto', config=None):
    """安全创建引擎"""
    try:
        # 参数验证
        if not isinstance(targets, set):
            raise TypeError("targets必须是set类型")
        
        if not targets:
            import logging
            logging.warning("目标地址集合为空")
            return None
        
        # 创建引擎
        engine = create_collision_engine(targets, mode=mode, config=config)
        return engine
        
    except ValueError as e:
        print(f"参数错误: {e}")
        return None
    except RuntimeError as e:
        print(f"运行时错误: {e}")
        return None
    except Exception as e:
        print(f"未知错误: {e}")
        return None

# 使用示例
targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
engine = safe_create_engine(targets, mode='auto')
if engine:
    print("✅ 引擎创建成功")
else:
    print("❌ 引擎创建失败")
```

---

## 7. 完整示例

### 7.1 生产环境完整示例

```python
import logging
from pathlib import Path
from src.config import ConfigCoordinator
from src.collision import create_collision_engine

def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 1. 加载配置
    config_file = 'config.json'
    if not Path(config_file).exists():
        logger.error(f"配置文件不存在: {config_file}")
        return
    
    coordinator = ConfigCoordinator(config_file)
    
    # 2. 验证配置
    errors = coordinator.validate_all()
    if errors:
        logger.error(f"配置验证失败: {errors}")
        return
    
    logger.info("配置验证通过")
    
    # 3. 读取目标地址
    targets = load_targets('valid_addresses.txt')
    if not targets:
        logger.error("未加载到目标地址")
        return
    
    logger.info(f"加载 {len(targets)} 个目标地址")
    
    # 4. 创建引擎
    config = coordinator.get_unified_config()
    
    try:
        engine = create_collision_engine(
            targets,
            mode='auto',
            config=config,
            on_progress=lambda p: logger.info(f"进度: {p:.2f}%"),
            on_match=lambda m: logger.warning(f"发现匹配: {m['address']}"),
            on_complete=lambda s: logger.info(f"碰撞完成: {s}")
        )
        
        logger.info(f"引擎类型: {type(engine).__name__}")
        
        # 5. 启动碰撞
        engine.start()
        
    except Exception as e:
        logger.error(f"引擎创建或启动失败: {e}")
        raise

def load_targets(filepath):
    """从文件加载目标地址"""
    targets = set()
    try:
        with open(filepath, 'r') as f:
            for line in f:
                address = line.strip()
                if address:
                    targets.add(address)
    except FileNotFoundError:
        logging.error(f"文件不存在: {filepath}")
    except Exception as e:
        logging.error(f"加载目标地址失败: {e}")
    
    return targets

if __name__ == '__main__':
    main()
```

### 7.2 测试环境示例

```python
from src.collision import create_collision_engine

def test_engine_creation():
    """测试引擎创建"""
    targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    
    # 测试1: 基本创建
    engine1 = create_collision_engine(targets, mode='auto')
    assert engine1 is not None
    print("✅ 测试1通过: 基本创建")
    
    # 测试2: 带配置创建
    config = {
        'gpu': {'batch_size': 65536},
        'collision': {'max_workers': 2}
    }
    engine2 = create_collision_engine(targets, mode='auto', config=config)
    assert engine2 is not None
    print("✅ 测试2通过: 带配置创建")
    
    # 测试3: kwargs覆盖
    engine3 = create_collision_engine(
        targets, 
        mode='cpu', 
        config=config,
        max_workers=4  # 覆盖config中的max_workers
    )
    assert engine3 is not None
    print("✅ 测试3通过: kwargs覆盖")
    
    print("\n✅ 所有测试通过")

if __name__ == '__main__':
    test_engine_creation()
```

### 7.3 命令行工具示例

```python
import argparse
from src.collision import create_collision_engine
from src.config import ConfigCoordinator

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='BTC碰撞引擎')
    
    parser.add_argument('--targets', '-t', required=True, help='目标地址文件')
    parser.add_argument('--mode', '-m', choices=['auto', 'gpu', 'cpu'], 
                       default='auto', help='引擎模式')
    parser.add_argument('--config', '-c', default='config.json', 
                       help='配置文件路径')
    parser.add_argument('--batch-size', type=int, help='批次大小（覆盖配置）')
    parser.add_argument('--max-workers', type=int, help='最大线程数（覆盖配置）')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 加载配置
    coordinator = ConfigCoordinator(args.config)
    config = coordinator.get_unified_config()
    
    # 应用命令行覆盖
    if args.batch_size:
        config['gpu']['batch_size'] = args.batch_size
    if args.max_workers:
        config['collision']['max_workers'] = args.max_workers
    
    # 加载目标
    targets = load_targets(args.targets)
    
    # 创建引擎
    engine = create_collision_engine(
        targets,
        mode=args.mode,
        config=config
    )
    
    print(f"引擎类型: {type(engine).__name__}")
    print(f"批次大小: {config['gpu']['batch_size']}")
    print(f"最大线程: {config['collision']['max_workers']}")
    
    # 启动引擎
    engine.start()

def load_targets(filepath):
    """加载目标地址"""
    targets = set()
    with open(filepath, 'r') as f:
        for line in f:
            address = line.strip()
            if address:
                targets.add(address)
    return targets

if __name__ == '__main__':
    main()
```

---

## 附录A: 参数完整列表

### A.1 create_collision_engine参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `targets` | Set[str] | 必需 | 目标地址集合 |
| `mode` | str | 'auto' | 引擎模式（auto/gpu/cpu） |
| `config` | Dict | None | 配置字典 |
| `**kwargs` | Any | - | 额外参数（传递给引擎） |

### A.2 GPU配置项（config['gpu']）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `batch_size` | int | 65536 | 批次大小 |
| `device_index` | int | -1 | GPU设备索引 |
| `memory_usage_ratio` | float | 0.5 | 显存使用比例 |

### A.3 碰撞引擎配置项（config['collision']）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_workers` | int/None | None | 最大线程数 |
| `checkpoint_interval` | int | 30 | 断点保存间隔（秒） |
| `dedup_max_size` | int | 1000000 | 去重过滤器容量 |

### A.4 常用kwargs参数

| 参数 | 类型 | 适用引擎 | 说明 |
|------|------|----------|------|
| `on_progress` | Callable | CPU | 进度回调 |
| `on_match` | Callable | CPU | 匹配回调 |
| `on_complete` | Callable | CPU | 完成回调 |
| `checkpoint_enabled` | bool | CPU | 启用断点 |
| `data_logging_enabled` | bool | 两者 | 启用数据日志 |
| `use_enhanced_monitoring` | bool | 两者 | 启用增强监控 |

---

## 附录B: 常见问题

### Q1: 何时使用config，何时使用kwargs？

**A**: 
- 使用 `config`：当需要从配置文件读取多个参数时
- 使用 `kwargs`：当只需要覆盖少数几个参数时
- 两者结合：config提供基础配置，kwargs进行微调

### Q2: 如何查看最终使用的配置？

**A**: 创建引擎后，可以访问引擎的配置属性：

```python
engine = create_collision_engine(targets, mode='gpu', config=config)

# GPU引擎
if hasattr(engine, '_batch_size'):
    print(f"batch_size: {engine._batch_size}")
if hasattr(engine, '_device_index'):
    print(f"device_index: {engine._device_index}")

# CPU引擎
if hasattr(engine, 'max_workers'):
    print(f"max_workers: {engine.max_workers}")
```

### Q3: 配置修改后需要重新创建引擎吗？

**A**: 是的，配置只在引擎创建时读取。修改配置后需要重新创建引擎：

```python
# 错误做法
engine = create_collision_engine(targets, config=config)
config['gpu']['batch_size'] = 131072  # 不会影响已创建的引擎

# 正确做法
config['gpu']['batch_size'] = 131072
engine = create_collision_engine(targets, config=config)  # 重新创建
```

---

**文档版本**: v1.0  
**最后更新**: 2026-04-20  
**维护者**: BTC碰撞引擎开发团队
