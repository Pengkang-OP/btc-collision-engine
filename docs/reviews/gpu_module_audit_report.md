# GPU 模块六维度审核报告

**审核对象**: `src/gpu/` (85 个文件)
**审核阶段**: Phase 3
**审核工具**: code-review-and-quality (五轴框架) + 手动六维度扩展
**审核日期**: 2026-05-28
**模块评分**: **78/100** [WARN] (良好但有改进空间)

---

## 一、模块概况

### 1.1 规模和结构

| 指标 | 数值 |
|------|------|
| 文件总数 | 85 |
| 总代码行数 | ~15,000+ |
| `__all__` 定义 | 4 处 (根 __init__.py / async_executor / search_modes / vendors) |
| `# type: ignore` | 6 处 (5 文件) |
| `Any` 类型 | 51 处 (31 在 pyopencl_stubs, 20 在实际代码) |
| `# nosec` | 7 处 (全部在 driver_manager.py, B603) |
| 裸 `pass` | 6 处 |
| `try:` 块 | 29+ |

### 1.2 子模块组织

```
src/gpu/
├── __init__.py                 # 38 个符号的 __all__ 导出
├── _kernel_source.py           # 55KB OpenCL C 内核源码
├── kernel_impl.py              # 53KB OpenCL 内核 Python 实现
├── kernel_protocol.py          # GPUKernelProtocol 协议
├── kernel.py                   # 内核源码加载
├── multi_gpu_engine.py         # 50KB 多 GPU 协调
├── multi_format_multi_gpu_engine.py # 多格式多 GPU
├── device.py                   # 35KB GPU 设备检测
├── device_manager.py           # 35KB 设备管理器
├── memory_pool.py              # 36KB GPU 内存池
├── driver_manager.py           # 26KB 驱动管理
├── performance_optimizer.py    # 26KB 性能优化器
├── amd_optimizer.py            # 36KB AMD 优化
├── nvidia_optimizer.py         # 26KB NVIDIA 优化
├── intel_optimizer.py          # Intel 优化
├── auto_config.py              # 自动配置
├── load_balancer.py            # 负载均衡
├── scorer.py                   # 统一评分器
├── gpu_recovery_manager.py     # 异常恢复
├── facade.py                   # 外观模式封装
├── context.py                  # 上下文管理
├── vendors/                    # Strategy 模式
│   ├── base.py                 # 抽象基类
│   ├── nvidia.py               # NVIDIA 实现
│   ├── amd.py                  # AMD 实现
│   └── intel.py                # Intel 实现
├── search_modes/               # 搜索模式
│   ├── base_search.py          # 基础搜索逻辑
│   └── random_search.py        # 随机搜索实现
└── ... (其余 ~60+ 辅助文件)
```

---

## 二、规范审核（Specification）

### 2.1 ruff 规则合规性

**问题 S1 - 导入组织不一致 (I 规则)**
- **严重性**: Minor | **文件**: 多个文件
- 部分文件使用 `from ..utils import get_configured_logger` 统一日志导入，部分使用 `from src.utils import get_configured_logger`
- 建议统一为 `from ..utils import get_configured_logger`（相对导入，与模块内部一致）

**问题 S2 - `# noqa: F401` 残留**
- **严重性**: Info | **文件**: `context.py:9`
- `from typing import Any, Optional, cast  # noqa: F401` — `Optional` 和 `cast` 实际未使用
- 建议移除未使用的导入项

**问题 S3 - `# nosec B603` 合理性验证**
- **严重性**: Info | **文件**: `driver_manager.py` (7 处)
- 所有 `subprocess.run()` 使用列表参数 (`shell=False`)，B603 豁免合理
- 但无中心化安全调用封装，7 处分散豁免增加维护成本
- 建议提取 `_safe_run_subprocess(cmd: list[str])` 辅助函数，集中 B603 豁免

**问题 S4 - `__all__` 缺失**
- **严重性**: Major | **文件**: ~81 个文件
- 根 `__init__.py` 定义了 38 个符号的 `__all__`，但其余 81 个独立模块均缺失
- 内部模块可接受，但 `kernel_impl.py`、`facade.py`、`multi_gpu_engine.py` 等可被外部导入的文件应定义 `__all__`
- 建议：为所有可独立导入的公共模块添加 `__all__`

### 2.2 Docstring 合规性

**问题 S5 - vendor_strategy.py docstring 不完整**
- **严重性**: Minor | **文件**: `vendors/intel.py` (? 需确认)
- 部分策略子类的 `apply_optimizations()` 方法 docstrings 缺少 Args/Returns 部分
- 建议补充完整 Google-style docstring

### 2.3 命名规范

命名规范整体良好：
- 类名：PascalCase（`GPUVendorBase`, `GPUMemoryPool`, `RandomSearchMode`）
- 方法/变量：snake_case
- 常量：UPPER_CASE（模块级常量采用 `_` 前缀标识模块作用域）
- 私有属性：`_` 前缀一致

---

## 三、质量审核（Quality）

### 3.1 文件大小分析

| 文件 | 大小 | 评分 | 建议 |
|------|------|------|------|
| `_kernel_source.py` | 55KB | [WARN] 合理 | OpenCL C 源码嵌入，内容不可分割 |
| `kernel_impl.py` | 53KB | [FAIL] 偏大 | `GPUKernel` 类 ~400 行，含编译/执行/Buffer/验证逻辑，建议拆分 |
| `multi_gpu_engine.py` | 50KB | [FAIL] 偏大 | 多 GPU 协调逻辑复杂，建议拆分 worker 管理/任务分配 |
| `memory_pool.py` | 36KB | [WARN] 合理 | 含 LRU 池 + 预分配 + 监控，逻辑紧凑 |
| `amd_optimizer.py` | 36KB | [WARN] 合理 | 架构检测逻辑复杂，需要详细代码 |
| `device_manager.py` | 35KB | [WARN] 合理 | 设备管理职责集中 |
| `device.py` | 35KB | [WARN] 合理 | 设备检测 + 厂商识别 |
| `performance_optimizer.py` | 26KB | [OK] 合理 | - |
| `driver_manager.py` | 26KB | [OK] 合理 | - |
| `nvidia_optimizer.py` | 26KB | [OK] 合理 | - |

### 3.2 复杂度分析

**问题 Q1 - `multi_gpu_engine.py` 职责过重**
- **严重性**: Major | **文件**: `multi_gpu_engine.py`
- `MultiGPUCollisionEngine` 同时管理：GPU 设备初始化、任务分割、负载均衡、错误恢复、匹配处理
- 单一职责原则未完全贯彻
- 建议：将 worker 管理提取到独立模块（已有 `worker.py`，但集成度不够）

**问题 Q2 - `kernel_impl.compile_kernel_with_retry()` 复杂度**
- **严重性**: Minor | **文件**: `kernel_impl.py`
- 内核编译重试逻辑含 4 种降级策略 + 指数退避，`if-elif` 链较长
- 建议：使用策略模式或字典映射简化

**问题 Q3 - 循环内条件分支**
- **严重性**: Info | **文件**: `search_modes/random_search.py`
- 主循环 `_execute_sync()/_execute_async()` 含多层 if-else 和异常处理，长方法 ~200+ 行
- 已在 `_process_batch_matches()` 等辅助方法中部分减轻，但仍可进一步拆分

### 3.3 重复代码

**问题 Q4 - pyopencl 可用性检查重复**
- **严重性**: Minor | **文件**: `device.py`, `kernel_impl.py` 等
- 模式：
  ```python
  from ._availability import PYOPENCL_AVAILABLE
  if PYOPENCL_AVAILABLE:
      import pyopencl as cl
  else:
      cl = None  # type: ignore[assignment]
  ```
- 此模式在至少 6 个文件中重复
- 建议：创建统一 `pyopencl_import()` 辅助函数，集中管理

**问题 Q5 - 裸 pass 语句验证**
- **严重性**: Minor
- 6 处 `except: pass`，分析结论：

| 位置 | 类型 | 评价 |
|------|------|------|
| `device.py:60-61` | `except ValueError: pass` | [WARN] 版本解析失败静默忽略，至少应 warning 日志 |
| `driver_manager.py:286-287` | `except (OSError, ...): pass` | [OK] 驱动检测方法回退，可接受 |
| `driver_manager.py:396-397` | 同上 | [OK] 同上 |
| `kernel_impl.py:713-714` | `except OSError: pass` | [FAIL] 清理操作失败应记录日志 |
| `kernel.py:240-241` | `except OSError: pass` | [WARN] 文件加载失败回退嵌入源码，可接受 |
| `multi_gpu_engine.py:482-486` | `except (OSError, ...): pass` (x2) | [FAIL] 多处错误静默忽略 |

### 3.4 设计模式使用

| 模式 | 使用位置 | 评价 |
|------|----------|------|
| **Strategy** | `vendors/base.py` → nvidia/amd/intel | [OK] 正确使用，基类 `calculate_batch_size()` 已将共用逻辑提至基类 |
| **Facade** | `facade.py` | [OK] 合理封装 GPU 子系统复杂度 |
| **Protocol** | `_engine_protocol.py` | [OK] 消除反向依赖 (ROADMAP #13) |
| **Adapter** | `collision/gpu/` 目录 | [OK] 适配 GPU 接口到碰撞引擎 |
| **Singleton** | `scorer.py`, `auto_config.py` | [OK] `get_*()` 函数实现单例模式 |
| **LRU Pool** | `memory_pool.py` | [OK] `OrderedDict` 重构后的 LRU 实现 |
| **Observer** | 事件总线引用 | [OK] 解耦搜索模式和引擎状态通知 |

---

## 四、合理审核（Reasonableness）

### 4.1 架构决策评估

**问题 R1 - 厂商 Strategy + 优化器分离架构**
- **决策**: 合理的双重隔离策略
  - `vendors/base.py` → 通用 batch_size 计算、错误处理统一
  - `amd_optimizer.py`/`nvidia_optimizer.py` → 驱动检测 + 架构代识别
  - `intel_optimizer.py` → Intel Arc 特有 workarounds
- **评价**: [OK] 合理 — Strategy 模式 + 独立优化器文件，职责清晰

**问题 R2 - OpenCL 内核编译策略**
- **决策**: 4 种降级编译策略
  1. 标准 CL2.0
  2. 降级 CL1.2
  3. Intel Arc workaround
  4. 最小功能集
- **评价**: [OK] 合理 — 兼容多厂商硬件差异

**问题 R3 - 搜索模式策略分离**
- **决策**: `BaseSearchMode` → `RandomSearchMode` 继承体系
- **评价**: [OK] 合理 — 为未来添加顺序搜索、模式匹配搜索等模式预留扩展点
- **改进建议**: `BaseSearchMode` 已从 `GPUCollisionEngine._execute_batch_loop` 迁移了大量逻辑，但仍需通过 `self.engine` 访问引擎状态，耦合度仍较高

**问题 R4 - 统一 GPU 评分**
- **决策**: `GPUDeviceScorer` 集中评分公式，消除 selector/load_balancer/device 三处不一致
- **评价**: [OK] 合理 — Task 11 改进，有效解决评分不一致问题

### 4.2 安全约束

**问题 R5 - OpenCL 编译选项安全策略**
- **严重性**: Info (正向发现)
- **文件**: `context.py:24-47`
- 所有厂商统一使用 `-cl-std=CL2.0`，严格禁用 `-cl-fast-relaxed-math`
- 代码注释明确说明：`secp256k1/SHA256/RIPEMD160 精度要求`
- **评价**: [OK] 完全正确 — 加密运算必须禁用 fast-math

**问题 R6 - Intel Arc uint32 workaround**
- **严重性**: Info (正向发现)
- **文件**: `vendors/intel.py`
- 避免 `global char*` 导致的驱动级 hang bug，使用 `uint32*` 替代 `uchar*` 缓冲区
- 环境变量优化：`OCL_QUEUE_THREAD_TRACE=0`、`IGDRCL_DEBUG_LEVEL=0` 等
- **评价**: [OK] 合理的厂商特定解决

### 4.3 依赖管理

**问题 R7 - numpy 强依赖**
- **严重性**: Minor | **文件**: `kernel_impl.py`
- `import numpy as np` 用于内存视图操作和类型转换
- 非 GPU 场景无需 numpy，但此模块专为 GPU 设计，依赖合理
- **评价**: [WARN] 合理但有优化空间（可考虑 `memoryview` + `struct` 替代部分场景）

---

## 五、逻辑审核（Logic）

### 5.1 核心逻辑路径

**问题 L1 - GPU 不可用时的运行时行为**
- **严重性**: Critical | **文件**: `device.py`, `kernel_impl.py`
- 当 `PYOPENCL_AVAILABLE = False` 时，`cl = None`
- `kernel_impl.py:28`: `cl = None  # type: ignore[assignment]`
- **没有防护代码**阻止后续 `cl.xxx` 调用，运行时将抛出 `AttributeError: 'NoneType' object has no attribute...`
- 依赖调用方在调用 GPU 前检查 `PYOPENCL_AVAILABLE`
- **建议**: 在 `GPUKernel.__init__()` 中主动检查并抛出明确的 `GPUNotAvailableError`

**问题 L2 - 内存池竞争条件**
- **严重性**: Minor | **文件**: `memory_pool.py`
- LRU 池使用 `threading.Lock` 保护，在多线程同时分配/释放时正确
- 但在 `GPU auto_tune` 场景中，多个引擎实例可能共享同一 pool 引用
- 建议确认 `auto_tune()` 的线程安全性

**问题 L3 - `device.py` 版本解析异常处理**
- **严重性**: Minor | **文件**: `device.py:60-61`
- ```python
  except ValueError:
      pass
  ```
- `_parse_opencl_version()` 版本字符串解析失败时静默忽略，返回 `OPENCL_VERSION_UNKNOWN`
- 建议添加 `logger.debug()` 记录

**问题 L4 - `multi_gpu_engine.py` 错误处理**
- **严重性**: Major | **文件**: `multi_gpu_engine.py:482-486`
- ```python
  except (OSError, ValueError, IndexError):
      pass
  ...
  except (OSError, RuntimeError):
      pass
  ```
- 两处广泛的 bare except 完全静默忽略错误，可能导致 GPU 设备状态不一致但引擎继续运行
- **建议**: 至少记录 warning 日志，系统恢复时机应发布 GpuFailureEvent

### 5.2 竞态条件分析

**问题 L5 - 锁顺序约定**
- **严重性**: Minor
- **文件**: `multi_gpu_engine.py`
- 定义了锁获取顺序约定 (`_state_lock → _workers_lock → _matches_lock`)
- 但该约定为文档注释形式，无运行时验证
- 建议：考虑在 debug 模式添加 `threading._threads_check()` 或自定义 Lock 装饰器验证顺序

### 5.3 检查点与恢复

**问题 L6 - `gpu_recovery_manager.py` 恢复逻辑**
- **严重性**: Minor | **文件**: `gpu_recovery_manager.py`
- `handle_gpu_failure()` 调用 `redistribute_callback` 重新分配负载
- 但回调接口为 `Callable`，无返回值类型约束，`None` 返回时静默继续
- 建议添加回调返回值类型签名并验证

### 5.4 边缘条件

**问题 L7 - 空设备列表**
- **严重性**: Minor | **文件**: `load_balancer.py:84-85`
- ```python
  if not devices:
      raise ValueError("设备列表不能为空")
  ```
- [OK] 正确处理空输入

**问题 L8 - GPU 设备索引越界**
- **严重性**: Minor | **文件**: `search_modes/base_search.py:82-88`
- ```python
  if target_idx >= len(target_list):
      logger.warning("目标索引越界: %d >= %d，跳过匹配", ...)
      continue
  ```
- [OK] 正确处理匹配索引越界

---

## 六、数据类型审核（Data Type Review）

### 6.1 `# type: ignore` 验证

| 位置 | 原因 | 合理性 |
|------|------|--------|
| `device.py:22` | `cl = None` 当 pyopencl 不可用时类型不匹配 | [OK] 必要，无法避免 |
| `kernel_impl.py:28` | 同上 | [OK] 必要 |
| `device_manager.py:573` | `cast("Any", ...)` 用于 OpenCL 对象 | [OK] 必要 |
| `gpu_recovery_manager.py:707` | 设置 `_health_check_executor = None` | [OK] 必要 |
| `search_modes/random_search.py:484` | `_handle_batch_error` override 签名不同 | [OK] 必要 (Liskov) |
| `executor_types.py` (引用提及) | 已在 v5.2.4 消除 | [OK] 已修复 |

**结论**: 6 处 `# type: ignore` 均合理，无需移除。

### 6.2 `Any` 类型审核

**51 处 Any 分布**：
- 31 处：`pyopencl_stubs/` — OpenCL 类型桩，合理
- 10 处：`memory_pool.py` — 缓冲区类型存储，合理
- 5 处：`load_balancer.py` — 异构字典 `dict[str, Any]`
- 3 处：`driver_manager.py` — 驱动检测返回值
- 2 处：`device.py` — 设备属性字典

**问题 T1 - `load_balancer.py` Any 过度使用**
- **严重性**: Minor | **文件**: `load_balancer.py`
- `_performance_stats: dict[int, dict[str, Any]]` 和 `_load_history: dict[int, list[dict[str, Any]]]`
- 异构字典应有明确的 `TypedDict` 或 `@dataclass`
- 建议：为性能统计定义 `PerformanceStats(TypedDict)`

### 6.3 类型注解覆盖度

**问题 T2 - `GPUVendorBase` 类型缺失**
- **严重性**: Minor | **文件**: `vendors/base.py`
- `calculate_batch_size(self, device: Any, profile: dict[str, Any])` 中的 `Any` 参数
- `device: Any` 应改为 `device: GPUDevice`（该类已定义在 `device.py`）
- 依赖方向：vendors/ 引用 device.py 是同级目录引用，合理

**问题 T3 - `facade.py` 缺少返回类型**
- **严重性**: Minor | **文件**: `facade.py`
- `is_available()` → 缺少 `-> bool`
- `initialize(...)` → 缺少 `-> None`
- `start_collision(targets, mode="random")` → 参数缺少类型注解

---

## 七、数据正确性审核（Data Correctness Review）

### 7.1 密码学操作正确性

**问题 D1 - OpenCL 内核中的密码学运算**
- **严重性**: Info
- **文件**: `_kernel_source.py`
- secp256k1 曲线运算使用标准的 Montgomery 域表示
- SHA-256 / RIPEMD-160 实现位于 OpenCL C 代码中
- 编译选项确保 `-cl-std=CL2.0`（无 fast-math），保证精度
- 2*G 自检验证在 `kernel_impl.py` 中: `verify_kernel_with_2g()`
- **评价**: [OK] 整体设计正确

**问题 D2 - 私钥数据传输安全**
- **严重性**: Major
- **文件**: `kernel_impl.py`, `search_modes/random_search.py`
- PRNG 模式（v4.2.1）：CPU 仅生成 32 字节种子，GPU 计算 `key = seed + gid`
- 种子通过 OpenCL Buffer 传输到 GPU
- **问题**: GPU 内存中的私钥数据在释放后未显式清除（OpenCL 不保证 `clReleaseMemObject` 后数据被覆盖）
- **建议**: 在释放 buffer 前使用自定义 kernel 或 `clEnqueueFillBuffer` 覆盖敏感数据

### 7.2 输入验证

**问题 D3 - `auto_config.py` 输入验证**
- **严重性**: Minor | **文件**: `auto_config.py:92-100`
- `_get_memory_gb()` 验证 `device` 是否为 dict 及 `memory_gb` 是否为有效数值
- [OK] 正确的输入验证

**问题 D4 - `vendors/base.py` 缺乏 device 参数验证**
- **严重性**: Minor | **文件**: `vendors/base.py:75`
- ```python
  global_mem = device.device_info.get("global_mem_size", 0)
  ```
- 假定 `device` 有 `device_info` 属性，但 type hint 为 `Any`，无运行时验证
- **建议**: 添加 `hasattr(device, "device_info")` 检查或使用 Protocol

### 7.3 配置数据校验

**问题 D5 - 环境变量解析**
- **严重性**: Minor | **文件**: `kernel_impl.py`
- `ENV_WORK_GROUP_SIZE` / `ENV_LOCAL_MEM_THRESHOLD` 通过 `os.environ.get()` 读取
- 无数值验证，非法字符串会导致 `ValueError`
- **建议**: 添加 try/except 和数值范围验证

### 7.4 时序侧信道风险

**问题 D6 - GPU Kernel 执行时间侧信道**
- **严重性**: Info
- GPU 内核执行时间为批量操作，非条件分支，时序变化在数百微秒级
- 批处理模式下时序信息难以被利用
- **评价**: [OK] 风险极低

---

## 八、修复建议汇总

### Critical（严重 — 必须修复）

| ID | 文件 | 行号 | 问题 | 建议 |
|----|------|------|------|------|
| **C1** | `device.py` / `kernel_impl.py` | 22/28 | `cl = None` 时无运行时检查，后续调用会崩溃 | 在 `GPUKernel.__init__()` 中添加显式守卫 |

### Major（重要 — 建议修复）

| ID | 文件 | 行号 | 问题 | 建议 |
|----|------|------|------|------|
| **M1** | `multi_gpu_engine.py` | 482-486 | bare except 静默忽略错误 | 添加 logger.warning() |
| **M2** | `kernel_impl.py` | 713-714 | OSError 清理失败静默忽略 | 添加 logger.debug() |
| **M3** | GPU 模块 | ~81 文件 | `__all__` 缺失 | 为公共模块补充 `__all__` |
| **M4** | `facade.py` | 全局 | 缺少返回类型注解 | 补充 `-> bool`, `-> None` 等 |
| **M5** | `devices.py`/`kernel_impl.py` 等 | 多处 | `cl = None / type: ignore[assignment]` 重复 6 次 | 提取统一导入辅助函数 |
| **M6** | 所有 kernel Buffer | 释放时 | 私钥数据在 GPU 内存中未清除 | 使用 `clEnqueueFillBuffer` 覆盖 |

### Minor（次要 — 建议改进）

| ID | 文件 | 行号 | 问题 | 建议 |
|----|------|------|------|------|
| **N1** | `device.py` | 60-61 | 版本解析静默 pass | 添加 logger.debug() |
| **N2** | `load_balancer.py` | 97-100 | `dict[str, Any]` 多次使用 | 替换为 `TypedDict` |
| **N3** | `vendors/base.py` | 75 | `device: Any` 参数 | 改为 `device: GPUDevice` |
| **N4** | `context.py` | 9 | `# noqa: F401` 残留 | 清理未使用的导入 |
| **N5** | `kernel_impl.py` | 多个 | 数值环境变量无验证 | 添加 try/except + 范围检查 |
| **N6** | `driver_manager.py` | 7 处 | `# nosec B603` 分散 | 集中到 `_safe_run_subprocess()` 辅助函数 |
| **N7** | `search_modes/base_search.py` | 54-100 | `_process_batch_matches()` 可再拆分 | 将 WIF 编码/事件发布拆分 |

### Info（信息 — 记录参考）

| ID | 文件 | 问题 | 备注 |
|----|------|------|------|
| **I1** | `context.py:24-47` | OpenCL 编译选项安全约束 | [OK] 正确实现，文档记录清晰 |
| **I2** | `vendors/intel.py` | Intel Arc uint32 workaround | [OK] 合理的厂商特定解决 |
| **I3** | `gpu_recovery_manager.py` | 恢复管理器架构 | [OK] 设计良好，接口清晰 |
| **I4** | `scorer.py` | 统一 GPU 评分 | [OK] 消除了多处理评分不一致 |
| **I5** | `multi_gpu_engine.py` | 锁顺序约定（文档注释） | [OK] 良好实践，可考虑运行时验证 |

---

## 九、总体评分

| 审核维度 | 评分 | 关键关注点 |
|----------|------|-----------|
| **规范审核** | 75/100 | `__all__` 缺失严重，导入组织不一致 |
| **质量审核** | 72/100 | 3 个 35KB+ 文件需关注，裸 pass 多处不合理 |
| **合理审核** | 82/100 | 架构决策合理，Strategy/Protocol/Facade 模式使用正确 |
| **逻辑审核** | 70/100 | 多处 bare except 静默忽略，GPU 不可用缺少守卫 |
| **类型审核** | 80/100 | 6 处 type:ignore 均合理，Any 使用主要集中在 pyopencl_stubs |
| **数据正确性** | 85/100 | 密码学操作正确，需关注 GPU 内存私钥清除 |
| **综合评分** | **78/100** [WARN] | |

**对比其他模块**:
- collision/: 75/100
- core/: 82/100
- **gpu/: 78/100** [WARN]

### 主要优势
1. [OK] Strategy 模式厂商架构清晰，可扩展性好
2. [OK] Protocol 接口解耦 (ROADMAP #13 完成)
3. [OK] OpenCL 编译选项安全约束严格 (CL2.0, no fast-math)
4. [OK] GPU 内存池 LRU 重构后的高性能设计
5. [OK] 多 GPU 协调的锁顺序约定

### 主要风险
1. [FAIL] 多处 bare except 静默忽略错误 (M1, M2)
2. [FAIL] GPU 不可用时无运行时守卫 (C1)
3. [WARN] GPU 内存中私钥数据未显式清除 (M6)
4. [WARN] 批量 PRNG 种子模式下 seed_utils 的端序处理一致性问题需在 kernel source 中验证
5. [WARN] 3 个 50KB+ 文件在持续迭代中需关注

---

*本报告由 code-review-and-quality 技能框架驱动，经人工逐文件审查完成。修复优先级：Critical > Major > Minor > Info。*
