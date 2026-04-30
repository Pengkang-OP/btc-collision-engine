# BTC碰撞引擎 v3.4.0 发布说明

> **发布日期**: 2026-04-30
> **版本代号**: 架构重构 (Architecture Refactoring)
> **兼容性**: 完全向后兼容，无需迁移

---

## 🎯 版本亮点

v3.4.0 是一次**架构级重构**，两大核心模块完成模块化改造：

1. **Wizard 模块化重构** — 单一向导函数 → 6 个独立策略组件 + 事件驱动架构
2. **GPU 引擎协议层重构 (Phase 1+2)** — 5 层架构 (协议层/外观层/核心层/监控管道/厂商策略)

---

## 🧩 Wizard 模块架构重构

### 模块化策略组件

| 组件 | 文件 | 职责 |
|------|------|------|
| 目标地址选择器 | `target_selector.py` | 单地址/文件加载/自动去重 |
| 碰撞模式选择器 | `mode_selector.py` | random/range/brute_force |
| 功能选项选择器 | `option_selector.py` | checkpoint/dedup/duration |
| GPU 加速选择器 | `gpu_selector.py` | CPU/单GPU/多GPU + 设备检测 |
| 配置构建器 | `config_builder.py` | 向导输入 → 命令行参数 |
| 向导引擎 | `wizard_engine.py` | 4 步编排 + 紧凑模式 |

### 事件驱动架构

- `events.py` — 标准化事件定义
- `message_queue.py` — 组件解耦通信
- `interfaces.py` — Protocol-based 接口设计

---

## 🚀 GPU 引擎架构重构

### Phase 1: 协议层架构

```
protocols.py
├── ICollisionCore          # 碰撞核心接口
├── IGPUEngineFacade        # 引擎外观接口
├── IPerformanceMonitor     # 性能监控接口
└── IVendorStrategy         # 厂商策略接口
```

### Phase 2: 外观层实现

```
facade.py                   # GPUEngineFacade 统一入口
core.py                     # CollisionCore (统计/断点/去重/搜索)
monitoring.py               # PerformanceMonitoringPipeline
vendor_strategy.py          # VendorOptimizationFactory (NVIDIA/AMD/Intel)
```

---

## 📊 GPU 性能基准

| 平台 | 模式 | 速度 |
|------|------|------|
| Intel Arc A770 | 异步双缓冲 | **4.89M keys/s** |
| Intel Arc A770 | 峰值 | **5.08M keys/s** |
| NVIDIA | 异步 | 2.22M+ keys/s |

---

## 📝 日志子系统 (新增 `src/logging/`)

| 模块 | 功能 |
|------|------|
| `log_collector.py` | 多源日志汇聚 |
| `log_processor.py` | 过滤/转换/路由 |
| `log_storage.py` | 文件/内存双模式 |
| `log_query.py` | 时间范围/级别/模块过滤 |
| `events.py` | 标准化日志事件 |

---

## 🔧 CLI 增强与修复

- **CLIOutput 单例重置机制** (`reset_instance`): 测试隔离支持
- **sys.stdout 安全重配置**: `reconfigure()` 防止 I/O 缓冲区关闭
- **向导第 4 步**: GPU 加速选择 (含设备自动检测)
- **向导输入对齐**: 时长选择 1/2/3 选项

---

## 🧪 测试体系

| 类别 | 用例数 | 通过率 |
|------|--------|--------|
| CLI 测试 | 38 | 100% ✅ |
| CLI 集成测试 | 22 | 100% ✅ |
| CLI 高级功能 | 32 | 100% ✅ |
| GPU 引擎重构 | 16 | 100% ✅ |
| GPU 异常处理 | 6 | 100% ✅ |
| **CLI 合计** | **92** | **100%** ✅ |

### 预存问题修复 (11 项)

- ✅ `src/collision/gpu/` 新增 4 个工厂函数
- ✅ `_target_list` → `targets` 属性修复
- ✅ CLI 交叉污染修复 (I/O closed + 单例重置)
- ✅ `Callable` 类型导入缺失修复

---

## 📁 改动文件

```
src/wizard/                  # 新增模块 (10 文件)
src/collision/gpu/           # GPU 引擎重构 (5 文件新增)
src/logging/                 # 新增日志子系统 (5 文件)
src/cli/output.py            # CLIOutput 安全改进
src/cli/commands.py          # 向导 GPU 选择步骤
tests/test_cli.py            # CLI 测试增强
tests/test_gpu_engine_refactored.py  # 新增 GPU 测试
```

---

## 🔄 升级指南

- **无需迁移**，可直接升级
- 向导首次使用需选择 CPU/GPU 模式
- 建议观察 `src/logging/` 日志子系统运行状态

---

## 📚 相关文档

- [CHANGELOG.md](../CHANGELOG.md#340---2026-04-30)
- [架构文档](architecture.md)
- [项目状态](project-status.md)
- [文档索引](DOCUMENT_INDEX.md)
