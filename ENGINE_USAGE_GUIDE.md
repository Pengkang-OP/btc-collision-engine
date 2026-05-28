# BTC碰撞引擎 - 正确使用指南

## 引擎选择

### 1. CPU引擎 (KeyCollisionEngine)

**正确的模块路径**:
```python
from src.collision.key_collision_engine import KeyCollisionEngine
```

**使用示例**:
```python
from src.collision.key_collision_engine import KeyCollisionEngine

# 创建CPU引擎
engine = KeyCollisionEngine(
    targets={'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'},
    checkpoint_enabled=False,
    dedup_enabled=False,
)

# 启动引擎
engine.start()

# 运行一段时间
import time
time.sleep(60)

# 停止引擎
engine.stop()

# 关闭引擎
engine.shutdown()
```

---

### 2. GPU引擎 (GPUFacade)

**正确的模块路径**:
```python
from src.gpu.facade import GPUFacade
```

**使用示例**:
```python
from src.gpu.facade import GPUFacade

# 创建GPU引擎
engine = GPUFacade(
    targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
    config={},
    checkpoint_enabled=False,
    dedup_enabled=False,
)

# 引擎自动启动

# 运行一段时间
import time
time.sleep(60)

# 关闭引擎
engine.shutdown()
```

---

### 3. GPU引擎 (GPUCollisionEngine) - 直接使用

**正确的模块路径**:
```python
from src.collision.gpu.engine import GPUCollisionEngine
```

**使用示例**:
```python
from src.collision.gpu.engine import GPUCollisionEngine

# 创建GPU引擎
engine = GPUCollisionEngine(
    targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
    device_index=-1,  # 自动选择最佳GPU
    batch_size=262144,
    checkpoint_enabled=False,
    dedup_enabled=False,
    data_logging_enabled=False,
)

# 运行一段时间
import time
time.sleep(60)

# 获取统计信息
stats = engine.get_stats()
print(f"检查密钥: {stats.total_checked}")
print(f"速度: {stats.speed} keys/s")

# 关闭引擎
engine.shutdown()
```

---

## 错误的模块路径

### [FAIL] 错误: CPUCollisionEngine

**错误示例**:
```python
# 这些都是错误的！
from src.collision.cpu.engine import CPUCollisionEngine  # [FAIL] 不存在
from src.cpu.collision.engine import CPUCollisionEngine  # [FAIL] 不存在
```

**原因**: 项目中没有 `src/collision/cpu/` 目录，CPU引擎实际上叫 `KeyCollisionEngine`。

---

### [OK] 正确的模块总结

| 引擎类型 | 正确模块路径 | 类名 |
|---------|------------|------|
| CPU引擎 | `src.collision.key_collision_engine` | `KeyCollisionEngine` |
| GPU Facade | `src.gpu.facade` | `GPUFacade` |
| GPU引擎 | `src.collision.gpu.engine` | `GPUCollisionEngine` |
| GPU管理器 | `src.gpu.device_manager` | `GPUDeviceManager` |
| 多GPU引擎 | `src.gpu.multi_gpu_engine` | `MultiGPUCollisionEngine` |

---

## CLI使用

### CPU模式
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

### GPU模式
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --use-gpu
```

### 多GPU模式
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --multi-gpu
```

---

## 引擎内部结构

```
src/
├── collision/
│   ├── key_collision_engine.py  # CPU引擎 (KeyCollisionEngine) [OK]
│   ├── multiprocess_engine.py     # 多进程引擎
│   └── gpu/
│       ├── engine.py              # GPU引擎 (GPUCollisionEngine) [OK]
│       ├── facade.py              # GPU Facade
│       └── ...
└── gpu/
    ├── device_manager.py          # GPU设备管理
    ├── multi_gpu_engine.py        # 多GPU引擎
    └── ...
```

**注意**: 没有 `src/collision/cpu/` 目录！

---

## 常见问题

### Q: 如何选择CPU还是GPU引擎？

**A**: 根据 `--use-gpu` 参数自动选择：
- CLI中添加 `--use-gpu` → GPU引擎
- CLI中不添加 → CPU引擎

### Q: GPUFacade 和 GPUCollisionEngine 有什么区别？

**A**:
- `GPUFacade`: CLI使用的封装层，更易用
- `GPUCollisionEngine`: 底层引擎，功能更完整

### Q: 为什么没有 CPUCollisionEngine？

**A**: 因为CPU引擎被设计为项目的默认引擎，所以直接命名为 `KeyCollisionEngine`（密钥碰撞引擎），而不是 `CPUCollisionEngine`。

---

## 测试代码示例

### 正确测试CPU引擎
```python
from src.collision.key_collision_engine import KeyCollisionEngine

def test_cpu_engine():
    engine = KeyCollisionEngine(
        targets={'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
    )
    engine.start()
    time.sleep(5)
    engine.stop()
    engine.shutdown()
```

### 正确测试GPU引擎
```python
from src.gpu.facade import GPUFacade

def test_gpu_engine():
    engine = GPUFacade(
        targets=['1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'],
        config={},
    )
    time.sleep(5)
    engine.shutdown()
```

---

**文档版本**: 1.0
**更新日期**: 2026-05-26
