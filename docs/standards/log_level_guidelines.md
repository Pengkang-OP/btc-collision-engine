# BTC碰撞引擎 - 日志级别使用规范

**版本**: v4.2.2
**日期**: 2026-04-24
**状态**: [OK] 已实施

---

## 1. 日志级别定义

### 1.1 级别分类

| 级别 | 使用场景 | 示例 | 响应要求 |
|------|---------|------|---------|
| **CRITICAL** | 系统级致命错误，无法继续运行 | GPU驱动丢失、内存耗尽 | 立即停止并告警 |
| **ERROR** | 功能级错误，当前操作失败但系统可继续 | GPU初始化失败、内核编译失败 | 需要人工介入 |
| **WARNING** | 可恢复的异常或性能问题 | 显存使用率过高、批次执行缓慢 | 建议关注 |
| **INFO** | 重要事件和状态变更 | 引擎启动、配置加载完成 | 用于审计 |
| **DEBUG** | 详细的调试信息 | 缓冲区分配、配置读取 | 开发调试 |

---

## 2. 异常处理日志规范

### 2.1 关键错误 (ERROR)

**使用场景**:

- 功能无法继续执行

- 数据可能丢失或损坏

- 需要人工介入

**示例**:

```python
try:
    self._init_gpu()
except RuntimeError as e:
    logger.error(f"GPU初始化失败: {e}")
    raise  # 必须抛出，调用方需要处理

```

**禁止**:

```python
# [FAIL] 错误：吞掉异常
try:
    self._init_gpu()
except Exception as e:
    logger.error(f"失败: {e}")
    pass  # 不应该静默失败

```

---

### 2.2 可恢复错误 (WARNING)

**使用场景**:

- 功能降级但可继续

- 性能问题但不影响正确性

- 自动重试后成功

**示例**:

```python
try:
    self._compile_kernel()
except CompilationError as e:
    logger.warning(
        f"内核编译失败，使用缓存版本: {e}\n"
        f"  性能可能下降10-20%"
    )
    self._use_cached_kernel()

```

---

### 2.3 异常堆栈 (exception)

**使用场景**:

- 未知异常需要完整堆栈

- 仅用于DEBUG模式

- 生产环境使用ERROR+简化消息

**示例**:

```python
try:
    result = complex_calculation()
except Exception as e:
    if logger.isEnabledFor(logging.DEBUG):
        logger.exception(f"复杂计算失败: {e}")  # 包含堆栈
    else:
        logger.error(f"复杂计算失败: {type(e).__name__}: {e}")  # 简化

```

---

## 3. 性能相关日志规范

### 3.1 性能警告阈值

| 指标 | WARNING阈值 | ERROR阈值 |
|------|------------|----------|
| GPU批次执行时间 | > 1000ms | > 5000ms |
| 显存使用率 | > 85% | > 95% |
| CPU-GPU传输时间 | > 500ms | > 2000ms |
| 内核编译时间 | > 30s | > 120s |

**示例**:

```python
execution_time_ms = (time.time() - start_time) * 1000

if execution_time_ms > 5000:
    logger.error(
        f"GPU批次执行时间过长: {execution_time_ms:.0f}ms\n"
        f"  建议: 检查GPU负载或降低batch_size"
    )
elif execution_time_ms > 1000:
    logger.warning(
        f"GPU批次执行缓慢: {execution_time_ms:.0f}ms\n"
        f"  建议: 启用异步执行模式"
    )

```

---

## 4. 配置相关日志规范

### 4.1 配置读取

**INFO**: 成功读取配置

```python
logger.info(f"[OK] 从配置文件读取异步设置: {enable_async}")

```

**WARNING**: 配置值无效，使用默认值

```python
logger.warning(
    f"配置值无效: batch_size={value}，使用默认值1024\n"
    f"  有效范围: 1024-16777216"
)

```

**ERROR**: 配置文件损坏

```python
logger.error(
    f"配置文件损坏: {config_file}\n"
    f"  错误: {e}\n"
    f"  建议: 从备份恢复或使用默认配置"
)

```

---

## 5. 资源管理日志规范

### 5.1 GPU内存

**DEBUG**: 正常分配/释放

```python
logger.debug(f"GPU Buffer追踪: 分配 _keys_buf (32.0 MB)")
logger.debug(f"GPU Buffer追踪: 释放 _keys_buf")

```

**WARNING**: 可能的内存泄漏

```python
logger.warning(
    f"检测到{len(leaked)}个可能的GPU Buffer泄漏: {', '.join(leaked)}\n"
    f"  建议: 检查是否正确释放缓冲区"
)

```

**ERROR**: 内存分配失败

```python
logger.error(
    f"GPU内存分配失败: 请求{size/1024/1024:.1f}MB，可用{available/1024/1024:.1f}MB\n"
    f"  建议: 降低batch_size或关闭其他GPU应用"
)

```

---

## 6. 回调函数日志规范

### 6.1 回调执行

**INFO**: 回调注册

```python
logger.info(f"进度回调已注册: {callback.__name__}")

```

**WARNING**: 回调执行缓慢

```python
logger.warning(
    f"回调执行缓慢: {callback.__name__} ({execution_time_ms:.0f}ms)\n"
    f"  建议: 优化回调函数或减少调用频率"
)

```

**ERROR**: 回调失败

```python
logger.error(
    f"回调执行失败: {callback.__name__}\n"
    f"  错误: {type(e).__name__}: {e}\n"
    f"  影响: 进度更新将跳过，不影响核心功能"
)

```

---

## 7. 常见错误模式

### 7.1 [OK] 正确模式

```python
# 模式1: 关键操作失败 - ERROR + 抛出
try:
    result = critical_operation()
except Exception as e:
    logger.error(f"关键操作失败: {e}")
    raise

# 模式2: 可降级操作 - WARNING + 降级
try:
    result = optional_optimization()
except Exception as e:
    logger.warning(f"优化失败，使用默认实现: {e}")
    result = default_implementation()

# 模式3: 调试信息 - DEBUG
logger.debug(f"缓冲区分配: {name} ({size/1024:.1f} KB)")

```

### 7.2 [FAIL] 错误模式

```python
# 错误1: 静默失败
try:
    do_something()
except:
    pass  # 绝对禁止

# 错误2: 级别不当
try:
    optional_feature()
except Exception as e:
    logger.error(f"失败: {e}")  # 应该是WARNING

# 错误3: 信息不足
logger.error("操作失败")  # 缺少上下文和错误详情

```

---

## 8. 国际化支持

### 8.1 语言规范

**当前**: 中文（主要）+ 英文（错误码）

**示例**:

```python
logger.error(
    f"GPU初始化失败 [GPU_INIT_FAILED]\n"
    f"  错误: {e}\n"
    f"  建议: 检查GPU驱动和OpenCL环境"
)

```

**未来**: 考虑使用i18n框架

---

## 9. 日志格式规范

### 9.1 标准格式

```
{timestamp} [{level}] {module}: {message}

```

**示例**:

```
2026-04-24 14:00:00 [ERROR] src.collision.gpu.engine: GPU初始化失败 [GPU_INIT_FAILED]
  错误: pyopencl not available
  建议: 安装pyopencl并验证OpenCL环境

```

### 9.2 多行日志

**使用场景**: 复杂错误、建议信息

**格式**:

```python
logger.error(
    f"主消息: {details}\n"
    f"  原因: {reason}\n"
    f"  影响: {impact}\n"
    f"  建议: {suggestion}"
)

```

---

## 10. 审查检查清单

### 10.1 Code Review检查项

- [ ] ERROR级别是否包含完整错误信息？

- [ ] WARNING级别是否可自动恢复？

- [ ] 是否避免使用bare `except:`？

- [ ] 异常堆栈是否仅在DEBUG模式输出？

- [ ] 日志消息是否包含上下文？

- [ ] 是否提供可操作的建议？

- [ ] 敏感信息是否已过滤？

### 10.2 自动化检查

```python
# 在CI中添加日志级别检查
import re

def check_log_levels(code: str):
    """检查日志级别使用是否合理"""
    errors = []

    # 检查ERROR后是否抛出
    if re.search(r'logger\.error\(.*\)\s*pass', code):
        errors.append("ERROR级别不应静默失败")

    # 检查bare except
    if re.search(r'except\s*:', code):
        errors.append("禁止使用bare except")

    return errors

```

---

## 11. 实施计划

### 阶段1: 制定规范 [OK]

- [x] 编写日志级别使用规范

- [x] 创建示例代码

- [x] 制定检查清单

### 阶段2: 代码审查

- [ ] 审查现有代码日志使用

- [ ] 标记不当使用的日志

- [ ] 创建修复任务列表

### 阶段3: 批量修复

- [ ] 修复ERROR级别不当使用

- [ ] 修复WARNING级别不当使用

- [ ] 添加缺失的上下文信息

### 阶段4: 自动化检查

- [ ] 添加CI日志检查

- [ ] 添加pre-commit hook

- [ ] 生成日志质量报告

---

## 12. 参考资料

- [Python logging文档](https://docs.python.org/3/library/logging.html)

- [Google日志风格指南](https://google.github.io/styleguide/pyguide.html#Logging)

- [12-Factor App: Logs](https://12factor.net/logs)

---

**审批**: AI审计系统
**下次审查**: 2026-05-24
