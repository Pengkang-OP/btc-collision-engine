# BTC碰撞引擎 v3.5.0 发布说明

> **发布日期**: 2026-05-01
> **版本代号**: 类型系统工程化 (Type System Engineering)
> **兼容性**: 完全向后兼容，无需迁移

---

## 🎯 版本亮点

v3.5.0 是一次**类型系统工程化**版本，核心成果：

1. **全模块类型提示渐进式补全** — 7 模块 104 文件 (+743/-730 行)，零破坏性变更
2. **运行时基础设施增强** — 配置热重载、多渠道告警系统

---

## 🏗️ 类型系统工程化 (P3-3)

### 覆盖模块

| 模块 | 文件数 | 关键文件 |
|------|--------|----------|
| `cli/` | 9 | commands, engine_builder, log_window, pagination, stats_performance_monitor |
| `collision/` | 32 | key_collision_engine, gpu_collision_engine, event_bus, factory, observers, dependency_container |
| `core/` | 13 | secp256k1, crypto_backend, thread_pool, key_generator, precomputed_table, bigint_optimizer |
| `gpu/` | 24 | kernel_impl, device_manager, multi_gpu_engine, load_balancer, data_monitor, search_modes |
| `monitoring/` | 3 | data_logger, enhanced_monitoring, storage_config |
| `utils/` | 21 | logger, performance_monitor, log_platform_adapter, logging_config, exceptions |
| `wizard/` | 1 | target_selector |

### 规范

- `self`/`cls` 参数免标注
- 嵌套非下划线函数需类型提示
- 114 处 mypy 规则豁免分类管理

### 回归验证

- 1471 测试选中, ~765 执行 (52%)
- 7 失败全部预存, 零破坏性变更

---

## ⚡ 新增功能

### P2-4 配置热重载

- **`config_watcher.py`** — 运行时检测配置文件变更并自动生效
- 集成 `ConfigManager`, 无需重启引擎

### P2-7 告警系统多渠道通知

- **`NotificationChannel`** 抽象基类
- **`Console`** / **`LogFile`** / **`Composite`** 通道实现
- 引擎层完整集成
- 新增 `src/collision/alert_system.py`

---

## 🔧 代码质量改进

### P3-1 地址生成器架构去重

- 提取 `BaseAddressGenerator` 共享基类
- 消除 P2PKH/P2SH 重复代码

### P3-4~P3-6 类型注解与异常增强

- 29 文件初步类型注解
- GPU 异常分类细化
- ExceptionHandler 增强

### P3-7 内存池优化

- `ObjectPool` 增强: `shrink()` / `hit_ratio` / `auto_tune()`
- `GlobalPoolManager` 自适应调优

### P3-8 线程池配置优化

- 可观测性提升
- 健康监控与边界校验
- 配置系统集成

### P3-10 序列化性能优化

- 统一 `fast_json` 模块
- `orjson` 优先, `json` 降级

### P3-11 GPU 设备评分统一

- 新增 `GPUDeviceScorer`
- 消除三套不一致评分公式

---

## 🧪 测试增强 (P3-12)

- 新增 **70 个测试用例**
- 覆盖类型安全、配置热重载、告警通道、内存池、评分统一等

---

## 📁 改动文件

```
src/                              # 104 文件类型提示补全 (+743/-730 行)
src/config/config_watcher.py      # 新增配置监听器
src/utils/notification_channel.py # 新增告警通道
src/collision/alert_system.py     # 新增告警系统
src/core/address_generator.py     # BaseAddressGenerator 共享基类
src/gpu/memory_pool.py            # ObjectPool 增强
src/core/thread_pool.py           # 线程池可观测性增强
src/gpu/scorer.py                 # GPU 评分统一
tests/                            # 70 个新测试
```

---

## 📊 性能基准（无变化）

| 平台 | 模式 | 速度 |
|------|------|------|
| Intel Arc A770 | 异步双缓冲 | **4.89M keys/s** |
| Intel Arc A770 | 峰值 | **5.08M keys/s** |
| NVIDIA | 异步 | 2.22M+ keys/s |

> v3.5.0 为纯代码质量改进版本，无性能退化。

---

## 🔄 升级指南

- **无需迁移**，可直接升级
- 类型提示补全为纯静态标注，运行时行为不变
- 配置热重载为新增特性，默认启用
- 告警系统新增通知通道，可按需配置

---

## 📚 相关文档

- [CHANGELOG.md](../CHANGELOG.md#350---2026-04-30)
- [项目状态](project-status.md)
- [架构文档](architecture.md)
- [文档索引](DOCUMENT_INDEX.md)
- [v3.4.0 发布说明](RELEASE_NOTES_v3.4.0.md)
