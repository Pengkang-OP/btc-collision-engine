---
name: task-4-type-ignore-cleanup
overview: "清理 src/ 中 # type: ignore 注释，从 28 个文件 86 处降至 ≤ 10 个文件"
todos:
  - id: phase1-fix-non-gpu-modules
    content: "修复非 GPU 模块的类型错误（9 个文件，32 处）：逐一修复 `utils/timeout.py`、`utils/error_recovery.py`、`collision/key_collision_engine.py`、`web/dashboard.py` 等的 `# type: ignore`"
    status: completed
  - id: phase2-create-pyopencl-stubs
    content: 为 pyopencl 创建 minimal `.pyi` stub 文件：创建 `src/gpu/pyopencl_stubs/pyopencl/` 目录结构，定义 `Context`、`CommandQueue`、`Buffer`、`Program`、`Kernel` 等核心类型的 stub
    status: completed
    dependencies:
      - phase1-fix-non-gpu-modules
  - id: phase3-configure-mypy
    content: "配置 mypy 忽略残留的 `# type: ignore`：在 `pyproject.toml` 中设置 `ignore_missing_imports = true`，并配置 `mypy_path` 指向 stub 目录"
    status: completed
    dependencies:
      - phase2-create-pyopencl-stubs
  - id: phase4-verify-and-cleanup
    content: "验证并清理：运行 `mypy src/` 检查类型错误，移除已修复的 `# type: ignore` 注释，更新重构清单中的执行进度"
    status: completed
    dependencies:
      - phase3-configure-mypy
---

## 用户需求

按照重构清单顺序逐一执行重构任务。当前已完成任务 1-3，需要执行**任务 4（# type: ignore 清理）**。

## 任务 4 分析摘要

### 当前状态

- **28 个文件**存在 `# type: ignore`，共 **86 处**
- 目标：降至 **≤ 10 个文件**

### 文件分布

| 类别 | 文件数 | 处数 | 主要原因 |
| --- | --- | --- | --- |
| GPU (pyopencl) | 18 | 53 | pyopencl 缺少 stub 文件 |
| 其他模块 | 9 | 32 | 类型注解不匹配 |
| Crypto | 1 | 1 | 可修复 |


### 错误码分布（前 5 位）

| 错误码 | 数量 | 处理策略 |
| --- | --- | --- |
| `[attr-defined]` | 20 | 创建 pyopencl `.pyi` stub |
| `[assignment]` | 11 | 修复类型注解 |
| `[return-value]` | 10 | 修复返回值类型 |
| `[arg-type]` | 10 | 修复参数类型 |
| `[import-not-found]` | 5 | 安装对应 stub 包或创建 stub |


## 执行策略

1. **阶段 1** - 修复非 GPU 模块（9 个文件，32 处），包括 `utils/timeout.py`、`utils/error_recovery.py`、`collision/key_collision_engine.py`、`web/dashboard.py` 等
2. **阶段 2** - 为 pyopencl 创建 minimal `.pyi` stub 文件（覆盖常用类型：`cl.Context`、`cl.CommandQueue`、`cl.Buffer`、`cl.Program`、`cl.Kernel`、`cl.enqueue_copy` 等）
3. **阶段 3** - 对于无法修复的（如 Flask 可选依赖），在 `pyproject.toml` 中集中配置 `ignore_missing_imports = true`

## 技术栈

- Python 3.9+
- mypy（静态类型检查）
- pyopencl（GPU 计算框架，需创建 stub）

## 实施方案

### 阶段 1：修复非 GPU 模块（9 个文件，32 处）

#### 1.1 `src/utils/timeout.py`（6 处 `[attr-defined]`）

- **问题**：`signal.setitimer`、`signal.SIGALRM` 等属性在 `signal` 模块的类型注解中未定义（Windows 不支持）
- **修复**：将 `# type: ignore[attr-defined]` 替换为正确的类型注解，或为 `signal` 模块添加 conditional import 的类型保护

#### 1.2 `src/utils/error_recovery.py`（6 处）

- **问题**：`raise last_exception` 的 `[misc]` 和 `[return-value]` 类型不匹配
- **修复**：修正函数返回类型注解

#### 1.3 `src/collision/key_collision_engine.py`（7 处）

- **问题**：`[return-value]` 和 `[assignment]` 类型不匹配
- **修复**：修正函数签名和变量类型注解

#### 1.4 `src/web/dashboard.py`（6 处 `[no-redef]`）

- **问题**：`Flask`、`jsonify` 等 Flask 可选依赖的类型注解
- **处理**：Flask 是可选依赖，保留 `# type: ignore[no-redef]`，但在 `pyproject.toml` 中统一配置

#### 1.5 其他文件（共 7 处）

- `src/automation/auto_test.py`：`[attr-defined]` → 修复 `CryptoBackend` 类型
- `src/collision/targets/cache.py`、`matcher.py`：`[import-untyped]` → 安装 `types-cachetools` 或创建 stub
- `src/core/precomputed_table.py`：修复类型注解

---

### 阶段 2：为 pyopencl 创建 minimal `.pyi` stub

#### 2.1 创建 stub 目录结构

```
src/gpu/pyopencl_stubs/pyopencl/
├── __init__.pyi
├── _cl.pyi
├── array.pyi
├── buffer.pyi
├── context.pyi
├── device.pyi
├── program.pyi
└── queue.pyi
```

#### 2.2 核心类型 stub 内容（覆盖 20 处 `[attr-defined]`）

**`__init__.pyi`**：

```python
from ._cl import *
from .buffer import Buffer
from .context import Context
from .queue import CommandQueue
from .program import Program, Kernel
```

**`_cl.pyi`**（核心类型）：

```python
from typing import Any, Optional

class Device:
    name: str
    vendor: str
    global_mem_size: int
    local_mem_size: int
    max_compute_units: int
    max_work_group_size: int
    platform: Any

class Platform:
    name: str

class Context:
    def __init__(self, devices: list[Device]) -> None: ...

class CommandQueue:
    def __init__(self, context: Context, device: Optional[Device] = ..., properties: int = ...) -> None: ...
    def finish(self) -> None: ...

class Buffer:
    def __init__(self, context: Context, flags: int, size: int, hostbuf: Any = ...) -> None: ...
    def release(self) -> None: ...

def enqueue_copy(queue: CommandQueue, dest: Buffer, src: Any, size: Optional[int] = ...) -> None: ...
def enqueue_fill_buffer(...) -> None: ...
def enqueue_nd_range_kernel(...) -> None: ...

# 常量
mem_flags: Any
command_queue_properties: Any
```

#### 2.3 配置 mypy 使用 stub

在 `pyproject.toml` 的 `[tool.mypy]` 中添加：

```
[tool.mypy]
ignore_missing_imports = true
mypy_path = ["src/gpu/pyopencl_stubs"]
```

---

### 阶段 3：配置 mypy 忽略残留的 `# type: ignore`

在 `pyproject.toml` 中配置：

```
[tool.mypy]
ignore_missing_imports = true  # 处理 Flask 等可选依赖
```

---

## 验收标准

| 指标 | 当前值 | 目标值 |
| --- | --- | --- |
| 带 `# type: ignore` 的文件数 | 28 | ≤ 10 |
| `# type: ignore` 总处数 | 86 | ≤ 20 |


## 预计工作量

- 阶段 1（非 GPU 模块）：2-3 小时
- 阶段 2（pyopencl stub）：3-4 小时
- 阶段 3（mypy 配置）：30 分钟
- **总计：约 6-8 小时**

## Agent Extensions

### SubAgent

- **code-explorer**
- 用途：探索 `src/` 中所有带 `# type: ignore` 的文件，分析类型错误的具体原因
- 预期结果：生成每个文件的类型错误修复方案

### Skill

- **code-review-and-quality**
- 用途：在修复完成后，进行代码质量审查，确保所有类型注解正确且无新引入的错误
- 预期结果：通过 mypy 类型检查，无新增 `# type: ignore`