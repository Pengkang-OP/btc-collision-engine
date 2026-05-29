# BTC Collision Engine — 技术路线图

> 收录 pyproject.toml 和源码中分散的未来规划项。

---

## ROADMAP #5 — 配置 Schema 单一真相源

**状态**: [OK] 已完成  
**描述**: CONFIG_SCHEMA 从 Python 模块迁移至 `config.schema.json`，所有配置验证统一从 JSON Schema 文件加载。  
**涉及文件**: `src/config/config_manager.py`, `tools/validate_config.py`, `scripts/dev/check_config_consistency.py`

---

## ROADMAP #11 — 统一入口错误处理

**状态**: [OK] 已完成 (2026-05-29)  
**描述**: 确保所有入口路径（`key_collision_cli.py` / `-m` / `btc-collision`）的兜底逻辑一致。  
- `key_collision_cli.py`: 添加 try/except 保护模块导入失败
- `src/__main__.py`: 添加 try/except 保护模块导入失败  
- `src/cli/main.py`: main() 函数内已有完整异常处理（键盘中断、sys.exit、通用异常）
**涉及文件**: `src/cli/main.py`, `key_collision_cli.py`, `src/__main__.py`

---

## ROADMAP #13 — 协议接口消除反向依赖

**状态**: [OK] 已完成 (2026-05-29)  
**描述**: 
- TYPE_CHECKING 反向依赖: 使用 `GPUEngineProtocol` 替代 `src/gpu/` → `src/collision/gpu/engine`，已覆盖 engine_monitor、worker、search_mode_coordinator、search_modes/*
- 运行时实例化反向依赖: 在 `src/collision/gpu/__init__.py` 添加 `create_gpu_collision_engine()` 工厂函数，替代 `src/gpu/config.py`、`facade.py`、`worker.py`、`src/config/crypto_config.py` 中的直接导入
**涉及文件**: `src/gpu/_engine_protocol.py`, `src/gpu/search_modes/*.py`, `src/gpu/engine_monitor.py`, `src/gpu/search_mode_coordinator.py`, `src/collision/gpu/__init__.py`, `src/gpu/config.py`, `src/gpu/facade.py`, `src/gpu/worker.py`, `src/config/crypto_config.py`

---

## ROADMAP #15 — Docstring 渐进收紧

**状态**: [OK] 全部完成 (2026-05-29)  
**描述**: Docstring (D) rules 启用 Google convention。  
- Phase 1: 修复 7841 D415 + 5 D301（已通过 `ruff --fix --unsafe-fixes`）  
- Phase 2: 从 blanket `"**/*.py" = ["D"]` 改为目录级豁免  
- Phase 3: src/ 41 文件清理（34 D205 auto-fix），所有豁免移除  
- Phase 3 (续): tests/benchmarks/tools/examples/scripts/ + 根目录 —— 91 个文件审计，仅 `tools/update_gpu_config.py` 1 个缺少 docstring，已补；所有 9 处 D 豁免均移除  
- 至此 ruff D 规则全项目生效，零豁免残留

---

## P2-23 — mypy Strict 逐步启用计划

**状态**: [DONE] 全部完成 (2026-05-29)  
**最终配置**:  
```toml
strict = true
check_untyped_defs = true
disallow_untyped_calls = true
disallow_any_generics = true
warn_unused_ignores = true
```
- **override blocks**: 0 个（全部消除，零 ignore_errors，零 disable_error_code）
- **排除目录**: tests/, benchmarks/, scripts/, src/gpu/pyopencl_stubs/
- **228 源文件**: mypy 0 错误通过

**里程碑**: 从 6 个 override block（含 24+ 模块 ignore_errors=true）→ 0 个 block，所有 strict 覆盖配置全部启用无错误

---

## numpy 2.x / cachetools 7.x / pyopencl 2026.x 迁移评估

**状态**: [OK] 已完成 (2026-05-29)  
**描述**: 三个依赖的上限已统一放宽：
- **numpy**: `<2.0.0` → `<3.0.0` — 代码审计确认零使用已移除 API（np.object/bool/str、.ptp()、np.lib 等均未使用），NEP 50 类型提升规则不影响项目
- **cachetools**: `<7.0.0` → `<9.0.0` — 项目仅使用 LRUCache + TTLCache，不影响已移除的 MRUCache/@func.mru_cache
- **pyopencl**: `<2026.0` → `<2027.0` — 2026.x 无 API 破坏性变更（仅类型注解改进），Event.profile 命名规范化和 typing 导出变更均不影响项目

---

## PERF-2 — Intel Arc profiling 序列化修复

**状态**: [OK] 已完成 (2026-05-28)  
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
| 2026-05-29 | ROADMAP #11 统一入口错误处理 | key_collision_cli.py / __main__.py 添加导入保护 |
| 2026-05-29 | ROADMAP #13 工厂函数消除反向依赖 | create_gpu_collision_engine() 替代 4 处直接导入 |
| 2026-05-29 | mypy block 1 收紧 | 3→1 模块豁免，ignore_errors→disable_error_code |
| 2026-05-29 | mypy block 3 修复并删除 | BackendProto 引用移除 + 类名修正 |
| 2026-05-29 | mypy blocks 5+6 修复并删除 | 17 模块补充类型注解 + 逐行 type:ignore，6→3 块 |
| 2026-05-29 | ROADMAP #15 Phase 3 全部完成 | 91 文件审计，1 文件补 docstring，9 处 D 豁免移除 |
| 2026-05-29 | kernel_protocol 修复 | 移除 @abstractmethod 消除 Protocol call-arg 问题 |
| 2026-05-29 | wizard_engine 类型修复 | 移除 3 处 # type: ignore[assignment] |
| 2026-05-28 | PERF-2 profiling 序列化修复 | Intel Arc OOO 队列移除 PROFILING_ENABLE |
| 2026-05 | 绝对导入统一 | 32 文件 `from ...` → `from src.` |
| 2026-05 | 常量整合 | 4 → 1 (`src/constants.py`) |
| 2026-05-29 | P2 依赖评估完成 | numpy/pyopencl/cachetools 破坏性变更审计，上限统一放宽 |
| 2026-05-29 | P3 CI/CD 同步修复 | pre-commit/CI/Dependabot 中过时的版本上限和注释统一对齐 |
| 2026-05-29 | P2-23 Block 1 (misc) 消除 | cli.output 8 处 `# type: ignore[misc]` inline 覆盖后删除整个 block，2 block/3 模块 |
| 2026-05-29 | P2-23 Block union-attr 消除 | device/kernel_impl/secure_buffer 用 `cl: Any` + `cast(Any, None)` 替代 `cl = None`，删除整个 block |
| 2026-05 | 依赖版本同步 | requirements-*.txt ↔ pyproject.toml |
| 2026-05 | .gitignore 精简 | 336 → 49 行 |
| 2026-05 | .pre-commit-config.yaml | ruff + mypy hooks |
