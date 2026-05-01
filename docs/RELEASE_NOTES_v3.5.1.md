# BTC碰撞引擎 v3.5.1 (Phase 6) 发布说明

> **发布日期**: 2026-05-01
> **版本代号**: GPU 引擎架构重构完成 (GPU Engine Refactoring Phase 6)
> **兼容性**: 100% 向后兼容，无需迁移

---

## 🎯 版本亮点

v3.5.1 是一次**里程碑版本**，核心成果：

1. **GPU 引擎架构重构完成** (Phase 6, v6.0.0) — 引擎行数 -73%，导入模块 -70%
2. **测试体系增强** — 交叉污染修复，139 项联合测试全通过
3. **项目清理** — data_logs 归档，临时文件整理

---

## 🏗️ GPU 引擎架构重构完成 (Phase 6)

### 重构成果

| 指标 | 重构前 | 重构后 | 改进 |
|------|--------|--------|------|
| 引擎行数 | 1466 行 | <400 行 | **-73%** |
| 导入模块 | 49 个 | <15 个 | **-70%** |
| Mock 层数 | 7+ 层 | 1-2 层 | **-80%** |
| Phase 6 测试 | — | 29 项 | **100% 通过** |

### 新增/重写组件

| 文件 | 说明 |
|------|------|
| `engine.py` | 引擎协调器，统一管理 GPU 组件 |
| `gpu_collision_engine.py` | Shim 薄层，100% 向后兼容 |
| `device_manager_adapter.py` | Device/Detector/Context 三层适配 |
| `kernel_adapter.py` | 真实编译流程 + 参数修正 |
| `async_pipeline_adapter.py` | prefetch/flush_pending/get_stats |
| `data_logger_adapter.py` | 数据日志适配器 |
| `search_mode_coordinator.py` | 搜索模式委托协调器 |
| `__init__.py` | 8 个 get_* 工厂函数 |

### 实施阶段回顾

- ✅ **Phase 1**: 基础设施准备（协议定义、模块骨架）
- ✅ **Phase 2**: 外观层实现（设备/内核/管道适配器）
- ✅ **Phase 3**: 监控管道实现（PerformanceMonitoringPipeline）
- ✅ **Phase 4**: 碰撞核心实现（CollisionCore: stats/checkpoint/dedup/search）
- ✅ **Phase 5**: 引擎协调器重构（VendorOptimizationFactory）
- ✅ **Phase 6**: 迁移验证（Shim 兼容层 + 29 项专项测试）

---

## 🧪 测试体系增强

### 交叉污染修复

- 🐛 **A1**: `engine_builder.py` — pyopencl 不可用时 `GPUCollisionEngine`/`MultiGPUCollisionEngine` 属性缺失 → 初始化 `None`
- 🐛 **A2**: `test_import_order_independence` — `sys.modules` 清除后未恢复 → 保存/恢复模块引用
- 🐛 **B1-B3**: CLI 测试交叉污染 — CLIOutput/LogWindow 单例重置、Rich Console `reconfigure()`

### 联合测试验证

| 测试集 | 结果 |
|--------|------|
| test_gpu_engine_refactored.py | 15 passed ✅ |
| test_gpu_exception_handling.py | 14 passed ✅ |
| test_gpu_refactored_methods.py | 18 passed ✅ |
| test_gpu_collision_engine.py | 17 passed, 3 skipped ✅ |
| test_p0_gpu_safety_fixes.py | 32 passed ✅ |
| test_cli.py | 38 passed ✅ |
| test_cli_integration.py | 22 passed ✅ |
| test_cli_advanced_features.py | 32 passed ✅ |
| **全量联合** | **171 passed, 3 skipped** ✅ |

---

## 🧹 项目清理

- 📦 data_logs/report_daily_*.json 归档 ~850 个 → `data_logs/archive/`（保留最新 5 个）
- 📦 `test_import_facade` 过时 pass 占位清理
- 📦 test_matches/ 和 mypy_*.txt 加入 .gitignore

---

## 📁 改动文件

```
src/collision/gpu/engine.py               # 新增引擎协调器 (Phase 6 核心)
src/collision/gpu/gpu_collision_engine.py  # Shim 后向兼容层
src/collision/gpu/__init__.py              # 8个工厂函数 + __all__
src/collision/gpu/device_manager_adapter.py  # 设备适配器
src/collision/gpu/kernel_adapter.py          # 内核适配器
src/collision/gpu/async_pipeline_adapter.py  # 异步管道适配器
src/collision/gpu/data_logger_adapter.py     # 数据日志适配器
src/collision/gpu/search_mode_coordinator.py # 搜索模式协调器
src/collision/gpu/README.md                 # GPU 模块文档 (Phase 1-6 ✅)
src/cli/engine_builder.py                   # GPUCollisionEngine 初始化修复
tests/test_gpu_engine_refactored.py         # sys.modules 保存/恢复
tests/test_gpu_refactored_methods.py        # Phase 6 兼容 mock
CHANGELOG.md                                # v3.5.1 条目补全
README.md                                   # 版本更新 + 结构同步
docs/project-status.md                      # 版本/里程碑更新
docs/DOCUMENT_INDEX.md                      # 版本号更新
docs/RELEASE_NOTES_v3.5.1.md               # 本文件
```

---

## 🔄 升级指南

- **无需迁移**，可直接升级
- GPU 引擎 API 完全向后兼容（`from src.collision.gpu_collision_engine import GPUCollisionEngine` 继续工作）
- 新增 `src/collision/gpu/` 下工厂函数可用于依赖注入场景

---

## 📊 性能基准（无变化）

| 平台 | 模式 | 速度 |
|------|------|------|
| Intel Arc A770 | 异步双缓冲 | **4.89M keys/s** |
| Intel Arc A770 | 峰值 | **5.08M keys/s** |

> v3.5.1 Phase 6 为架构重构版本，无性能退化。

---

## 📚 相关文档

- [CHANGELOG.md](../CHANGELOG.md#351---2026-05-01)
- [项目状态](project-status.md)
- [架构文档](architecture.md)
- [文档索引](DOCUMENT_INDEX.md)
- [v3.5.0 发布说明](RELEASE_NOTES_v3.5.0.md)
- [GPU 引擎重构 README](../src/collision/gpu/README.md)
