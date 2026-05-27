# BTC Collision Engine — 技术路线图

> 收录 pyproject.toml 和源码中分散的未来规划项。

---

## ROADMAP #5 — 配置 Schema 单一真相源

**状态**: ✅ 已完成  
**描述**: CONFIG_SCHEMA 从 Python 模块迁移至 `config.schema.json`，所有配置验证统一从 JSON Schema 文件加载。  
**涉及文件**: `src/config/config_manager.py`, `tools/validate_config.py`, `scripts/dev/check_config_consistency.py`

---

## ROADMAP #11 — 统一入口错误处理

**状态**: 🔄 进行中  
**描述**: 确保所有入口路径（`key_collision_cli.py` / `-m` / `btc-collision`）的兜底逻辑一致。  
**涉及文件**: `src/cli/main.py`

---

## ROADMAP #13 — 协议接口消除反向依赖

**状态**: 🔄 进行中  
**描述**: 使用 `GPUEngineProtocol` 替代 `src/gpu/` → `src/collision/gpu/engine` 的 TYPE_CHECKING 反向依赖。  
**涉及文件**: `src/gpu/_engine_protocol.py`, `src/gpu/search_modes/*.py`, `src/gpu/engine_monitor.py`, `src/gpu/search_mode_coordinator.py`

---

## ROADMAP #15 — Docstring 渐进收紧

**状态**: ✅ src/ 已完成  
**描述**: Docstring (D) rules 启用 Google convention。  
- Phase 1: 修复 7841 D415 + 5 D301（已通过 `ruff --fix --unsafe-fixes`）  
- Phase 2: 从 blanket `"**/*.py" = ["D"]` 改为目录级豁免  
- Phase 3: src/ 41 文件清理（34 D205 auto-fix），所有豁免移除  
- 待处理: tests/, benchmarks/, tools/, examples/, scripts/ 的 docstring 豁免

---

## P2-23 — mypy Strict 逐步启用计划

**状态**: 🔄 进行中  
**当前**: 6 个 `[[tool.mypy.overrides]]` block，45+ 文件豁免  
**路线**（override blocks 全部消除后按顺序启用）:

| Phase | 标志 | 说明 |
|-------|------|------|
| 1 | `disallow_untyped_defs = true` | 所有函数需完整类型注解 |
| 2 | `warn_return_any = true` | 禁止 Any 返回值传播 |
| 3 | `disallow_incomplete_defs = true` | 禁止部分类型注解 |

**最终目标**: `strict = true`

---

## numpy 2.x 迁移评估

**状态**: ⏳ 待评估  
**描述**: numpy 当前锁定 1.x。numpy 2.x 含破坏性变更，需评估对 GPU 数值计算的影响后迁移。

---

## PERF-2 — Intel Arc profiling 序列化修复

**状态**: ✅ 已完成 (2026-05-28)  
**问题**: Intel Arc GPU 利用率呈尖刺/齿轮状（每批次完成→等待→下一批次）。  
**根因**: `device.py` 创建 OOO 命令队列时附加了 `PROFILING_ENABLE` 标志。  
Intel compute-runtime FAQ 确认此标志在 OOO 队列上强制内核串行执行。  
**修复**: Intel Arc 路径移除 `PROFILING_ENABLE`。全项目无 profiling 数据消费，移除无功能影响。  
**参考**: https://github.com/intel/compute-runtime/blob/master/opencl/doc/FAQ.md  
**涉及文件**: `src/gpu/device.py` (L700-730)

---

## 近期完成项

| 日期 | 项目 | 详情 |
|------|------|------|
| 2026-05-28 | PERF-2 profiling 序列化修复 | Intel Arc OOO 队列移除 PROFILING_ENABLE |
| 2026-05 | 绝对导入统一 | 32 文件 `from ...` → `from src.` |
| 2026-05 | 常量整合 | 4 → 1 (`src/constants.py`) |
| 2026-05 | 依赖版本同步 | requirements-*.txt ↔ pyproject.toml |
| 2026-05 | .gitignore 精简 | 336 → 49 行 |
| 2026-05 | .pre-commit-config.yaml | ruff + mypy hooks |
