# 异常处理规范

> **版本**: v1.0 | **创建日期**: 2026-05-27 | **适用范围**: btc-collision-engine 全体 Python 源码

---

## 1. 核心原则

```
捕获具体 → 记录完整 → 尽职传递 → 不静默失败
```

| 原则 | 说明 |
|------|------|
| **捕获具体** | 优先捕获具体异常类型（`ValueError`、`OSError`），而非 `Exception` |
| **记录完整** | 日志包含异常信息 + 堆栈（`exc_info=True`） |
| **尽职传递** | 非降级场景必须 `raise` 或包装后 `raise ... from e` |
| **不静默失败** | 禁止 `except: pass`、`except Exception: logger.error(...)` 后不 raise/return |

---

## 2. 五级异常处理模型

根据异常的影响范围和处理意图，将异常处理分为 5 个等级：

| 等级 | 名称 | 处理方式 | 典型场景 | 日志级别 |
|------|------|----------|----------|----------|
| **L1** | 致命错误 | `logger.error()` + `raise` | 加密初始化、GPU 内核执行 | ERROR |
| **L2** | 降级回退 | `logger.warning()` + return 默认值 | GPU 不可用回退 CPU | WARNING |
| **L3** | 隔离保护 | `logger.exception()` + return 降级值 | 回调执行、日志记录 | EXCEPTION |
| **L4** | 确定性清理 | `suppress()` / `contextlib.suppress` | 临时文件删除、缓存清理 | 无（可信操作） |
| **L5** | 边界包装 | `raise HighLevelError(...) from e` | 适配器层、跨模块调用 | 调用方自决 |

---

### 2.1 L1：致命错误 — 必须传播

**适用场景**：核心功能链路上的错误，导致后续操作不可靠。

```python
# ✅ 正确
try:
    self._init_crypto_backend(config)
except Exception as e:
    logger.error("加密后端初始化失败: %s", e, exc_info=True)
    raise  # 必须传播，让上层处理

# ✅ 包装后传播
try:
    result = low_level_api()
except (ValueError, TypeError) as e:
    raise HighLevelError(f"参数验证失败: {e}") from e

# ❌ 错误：静默吞异常
try:
    self._init_crypto_backend(config)
except Exception as e:
    logger.error("加密后端初始化失败: %s", e)
    # 没有 raise — 后续代码在错误状态下运行
```

**验证清单**：
- [ ] `logger.error()` 包含 `exc_info=True`
- [ ] 异常被 `raise` 或 `raise ... from e` 传递
- [ ] 日志消息包含 操作名 + 异常详情（`%s`, `e`）

---

### 2.2 L2：降级回退 — 记录后返回替代值

**适用场景**：非核心功能失败，可以用降级方案继续执行。

```python
# ✅ 正确：GPU 不可用，回退 CPU
try:
    gpu_result = self._run_on_gpu(batch)
except (RuntimeError, MemoryError) as e:
    logger.warning("GPU执行失败，回退CPU模式: %s", e)
    return self._run_on_cpu(batch)

# ✅ 正确：资源获取失败，返回默认值
try:
    result = get_performance_data()
except Exception as e:
    logger.warning("获取性能数据失败，使用默认值: %s", e)
    return DEFAULT_PERF_DATA

# ❌ 错误：不应降级的关键路径
try:
    self._process_payment(amount)
except Exception as e:
    logger.warning("支付处理失败: %s", e)  # ❌ 支付不能降级
    return False  # ❌ 调用方无法区分"支付失败"和"支付被拒"
```

---

### 2.3 L3：隔离保护 — 记录后继续（不传播）

**适用场景**：回调、日志、监控等外围操作，失败不应影响主流程。

```python
# ✅ 正确：回调隔离
try:
    if self.on_progress:
        self.on_progress(stats)
except Exception as e:
    logger.exception("进度回调执行异常（已隔离）: %s", e)
    # 不 raise — 回调失败不应中断引擎

# ✅ 正确：数据日志隔离
try:
    self.data_logger.log_performance(metrics)
except Exception as e:
    logger.exception("数据日志记录失败（已隔离）: %s", e)
    # 不 raise — 日志失败不应中断搜索

# ❌ 错误：L3 滥用为 L1
try:
    seeds = self._generate_seeds(count)  # 关键操作
except Exception as e:
    logger.exception("生成种子失败（已隔离）: %s", e)  # ❌ 种子是搜索的关键输入
    # raise 缺失 — 后续搜索使用无效种子
```

---

### 2.4 L4：确定性清理 — 使用 `suppress`

**适用场景**：临时文件删除、缓存清理、信号量释放等确定性操作。

```python
# ✅ 正确：使用 contextlib.suppress
from contextlib import suppress

with suppress(OSError):
    pathlib.Path(temp_file).unlink()

with suppress(FileNotFoundError):
    os.remove(log_file)

# ✅ 正确：需要记录的清理
try:
    os.remove(temp_file)
except OSError as cleanup_error:
    logger.debug("清理临时文件失败（可忽略）: %s", cleanup_error)

# ❌ 错误：使用 except: pass
try:
    os.remove(temp_file)
except:
    pass
```

---

### 2.5 L5：边界包装 — 语义转换

**适用场景**：模块边界处需要将底层异常转换为高层语义异常。

```python
# ✅ 正确：适配器层转换
try:
    result = low_level_gpu_api.run(batch)
except OpenCLError as e:
    raise GPUExecutionError(f"GPU批次执行失败: {e}") from e

# ✅ 正确：保持原始异常链
try:
    self._validate_config(config)
except (ValueError, TypeError) as e:
    raise ConfigError(f"GPU配置无效: {e}") from e

# ❌ 错误：丢失原始异常
try:
    self._validate_config(config)
except (ValueError, TypeError) as e:
    raise ConfigError(f"GPU配置无效: {e}")  # 丢失 from
```

---

## 3. 禁止模式

### 3.1 绝对禁止

```python
# ❌ 裸 except
except:
    ...

# ❌ 静默吞异常  
except Exception:
    pass

# ❌ 无变量的 except（无法访问异常信息）
except Exception:
    logger.error("操作失败")
```

### 3.2 条件禁止

```python
# ❌ L1 路径中缺少 raise
try:
    self._init_crypto_backend(config)
except Exception as e:
    logger.error("初始化失败: %s", e, exc_info=True)
    # 缺少 raise — 后续在错误状态下运行

# ❌ L1 路径中使用 warning 级别
try:
    kernel_result = self._execute_kernel(count, ws)
except Exception as e:
    logger.warning("内核执行失败: %s", e)  # 应使用 ERROR + raise
    return []

# ❌ 关键路径使用 f-string 而非 %s 格式化
logger.error(f"操作失败: {e}")  # 应使用 logger.error("操作失败: %s", e)
```

---

## 4. 日志格式规范

### 4.1 消息格式

```python
# ✅ 标准格式
logger.error("操作失败: %s", e, exc_info=True)          # 需要堆栈
logger.warning("操作失败: %s", e)                         # 不需要堆栈
logger.exception("操作失败（已隔离）: %s", e)              # 自动包含堆栈

# ✅ 结构化上下文
logger.error(
    "批次执行失败: batch=%d, device=%s, error=%s",
    batch_id,
    device_name,
    e,
)

# ❌ 禁止 f-string（延迟求值增加开销，且与项目规范不一致）
logger.error(f"操作失败: {e}")
```

### 4.2 消息内容要求

| 要素 | 必选 | 示例 |
|------|------|------|
| 操作名 | ✔ | `"GPU批次执行失败"` |
| 异常详情 | ✔ | `"%s", e` |
| 上下文信息 | 推荐 | `"device=%s, batch=%d"` |
| 操作影响 | 推荐 | `"（已隔离）"`、`"（已降级）"` |

---

## 5. 异常变量命名规范

| 场景 | 变量名 | 说明 |
|------|--------|------|
| 资源清理 | `cleanup_error` | 文件删除、缓存清理 |
| 权限设置 | `perm_error` | 文件权限、icacls |
| 数据解析 | `e` | JSON 解析、类型转换 |
| 降级回退 | `e` | 功能降级、默认值回退 |
| 通用场景 | `e` | 一般错误处理 |

```python
# 资源清理
except OSError as cleanup_error:
    logger.debug("清理临时文件时出错: %s", cleanup_error)

# 通用场景
except RuntimeError as e:
    logger.error("GPU执行失败: %s", e, exc_info=True)
    raise
```

---

## 6. 各模块应用等级对照

| 模块 | 推荐等级 | 说明 |
|------|---------|------|
| 加密后端 (`src/core/`) | L1 | 核心功能，必须失败传播 |
| 碰撞引擎 (`src/collision/`) | L1/L2 | 搜索失败→L1，日志/回调→L3 |
| GPU 内核 (`src/gpu/kernel_impl.py`) | L1 | 内核执行失败必须传播 |
| GPU 工作器 (`src/gpu/worker.py`) | L1 | 工作器异常必须通知调用方 |
| GPU 执行器 (`src/gpu/async_executor/`) | L1/L2 | 执行失败→L1，缓冲区分配→L2 |
| 监控系统 (`src/monitoring/`) | L3 | 监控失败不影响主流程 |
| CLI 界面 (`src/cli/`) | L2/L4 | UI 异常→降级，清理→L4 |
| 配置管理 (`src/config/`) | L1/L5 | 配置错误→L1，边界转换→L5 |
| 工具函数 (`src/utils/`) | L2/L4 | 辅助功能→L2，清理→L4 |
| 测试代码 (`tests/`) | 容忍 | 合理场景可容忍 `except Exception: pass` |

---

## 7. 代码审查清单

提交代码前请检查：

- [ ] 无裸 `except:`（禁止）
- [ ] 无 `except Exception: pass`（禁止）
- [ ] 无 `except Exception:` 不带异常变量（禁止）
- [ ] L1 路径中 `logger.error()` 后有 `raise`（必须）
- [ ] `logger.error()` 在 except 块中包含 `exc_info=True`
- [ ] 日志消息使用 `%s` 风格而非 f-string
- [ ] L4 清理操作优先使用 `contextlib.suppress`
- [ ] L5 包装异常使用 `raise ... from e` 保留链
- [ ] 异常变量名遵循语义化命名规范

---

## 8. 示例对照表

| 场景 | ✅ 正确 | ❌ 错误 |
|------|---------|---------|
| 内核执行失败 | `logger.error + raise` | `logger.warning + return []` |
| 回调隔离 | `logger.exception + 不raise` | `except: pass` |
| 文件清理 | `suppress(OSError)` | `except: pass` |
| 适配器包装 | `raise NewError from e` | `raise NewError` |
| GPU 降级 CPU | `logger.warning + return fallback` | 不记录直接 fallback |
| 配置验证 | `raise ConfigError from e` | `logger.warning + return default` |

---

*参考文件*：

- `docs/standards/development_code_standards.md` — 基础代码规范（第 7 节）
- `docs/archive/EXCEPTION_HANDLING_REVIEW_20260423.md` — 异常审查历史
- `docs/archive/security-related/EXCEPTION_NAMING_CONVENTION.md` — 命名约定
