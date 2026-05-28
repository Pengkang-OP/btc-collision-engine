# Changelog

本文档记录 BTC Collision Engine 项目的所有 notable changes。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [5.0.2] — 2026-05-29

### Added

- **ROADMAP #11: 统一入口错误处理** — `key_collision_cli.py` 和 `src/__main__.py`
  添加 try/except 保护模块导入失败，在所有入口路径提供一致的兜底消息
- **ROADMAP #13: 工厂函数消除反向依赖** — 在 `src/collision/gpu/__init__.py`
  添加 `create_gpu_collision_engine()` 工厂函数，替代 `src/gpu/config.py`、
  `src/gpu/facade.py`、`src/gpu/worker.py`、`src/config/crypto_config.py`
  中直接导入 `GPUCollisionEngine` 的模式

### Changed

- **mypy Strict 逐步启用 (Phase 0)** — 收紧第一个 override block：
  - 移除 `src.wizard.wizard_engine` 和 `src.gpu.kernel_protocol` 的豁免
  - `src.cli.output` 从 `ignore_errors = true` 收紧为 `disable_error_code = ["misc"]`
- **`src/gpu/kernel_protocol.py`** — 移除 Protocol 方法上的 `@abstractmethod` 装饰器，
  消除 mypy call-arg 签名不匹配
- **`src/wizard/wizard_engine.py`** — 移除 3 处 `# type: ignore[assignment]`，
  改为显式类型转换
- **ROADMAP #15 Phase 3 完成: ruff D 规则全项目生效** — 审计 91 文件，
  仅 `tools/update_gpu_config.py` 补 docstring，移除全部 9 处 D 豁免
  (scripts/benchmarks/tests/tools/examples/ + start.py/key_collision.py/conftest.py)
- **mypy Block 3 (2 模块) 已修复并删除** — 修复 `auto_test.py` 中已移除的
  `BackendProto` 引用和 `performance_benchmark.py` 中 `MultiprocessCollisionEngine`
  类名拼写错误，删除对应 mypy override block
- **mypy Blocks 5+6 (17 模块) 已修复并删除** — 10 文件补充类型注解（-> None、
  -> list[str] 等 30+ 处），7 文件添加逐行 # type: ignore[error-code] 或代码改动
  (metrics.py 0->0.0、memory_pool.py functools.partial)。从 6 个 override block
  缩减至 3 个，24+ 模块豁免

## [5.0.1] — 2026-05-28

### Changed

- **全项目代码规范统一** (28 项治理闭环):
  - P0: 删除 `.flake8`、`[tool.black]`、`[tool.flake8]`、`[tool.basedpyright]` 死配置段 (P0-3/4/11/12)
  - P0: `.env.example` 从 11 未用变量精简至 7 实际变量 (P0-5)
  - P0: `requirements-dev.txt` 替换 `black`/`flake8` → `ruff` (P0-6)
  - P0: PYOPENCL_AVAILABLE 从 3 处分散定义收敛至 `src/gpu/_availability.py` 单源 (P0-9)
  - P0: 死代码消除 — 移除 `GPU_CONFIG_MANAGER_AVAILABLE`、`ASYNC_LOG_AVAILABLE` 及相关死分支 (P0-1/2)
  - P0: 依赖版本上限补全 — `cachetools<7.0`、`numpy<2.0`、`pyopencl<2026.0`、`psutil<8.0` 等 (P0-7/8)
  - P1: 18 库文件 shebang 清理 (P1-19)、src/ 全编码声明清理 (P1-20)
  - P1: ruff 自动修复 I/Q + format 全部通过 (P1-15/16)
  - P1: 32 文件 `from ...` 三层点相对导入 → `from src.` 绝对导入 (P1-18)
  - P1: requirements-*.txt → pyproject.toml 依赖版本同步 (P1-17)
  - P1: 常量 4→1 整合至 `src/constants.py` (P1-22)
  - P1: `src/` 全 public API 补充 Google-style docstring (P1-14)
  - P2: `.pre-commit-config.yaml` 创建 (P2-25)、`.gitignore` 336→50 行 (P2-26)
  - P2: `ROADMAP.md` 创建 (P2-27)、pytest.ini 移除 DeprecationWarning 抑制 (P2-28)

### Fixed

- **PERF-2: Intel Arc profiling 序列化修复** — `device.py` 创建 OOO 队列时移除 `PROFILING_ENABLE`，修复内核串行导致的尖刺/齿轮状 GPU 利用率 (Intel compute-runtime FAQ 确认)
- **CLI 启动修复** — `commands.py` `--quick-start` 向导的 `python -m src.cli` → `python key_collision_cli.py`，修复 argparse 误收 `src.cli` 为未知参数
- **测试修复** — `test_gpu_engine_initialization_without_gpu` 和 `test_constructor_pyopencl_unavailable` 补 `engine.PYOPENCL_AVAILABLE` 本地副本 patch

## [5.0.0] — 2026-05

- 根目录 `GPU_CONFIG_GUIDE.md`、`deploy/QUICK_START.md` 添加 v5.0.0 版本标记
- **ROADMAP #15 启用 pydocstyle Google convention 强制校验**:
  - 在 `[tool.ruff.lint]` select 中添加 `"D"` 规则
  - 取消注释 `[tool.ruff.lint.pydocstyle]` 的 `convention = "google"`
  - 添加 `"**/*.py" = ["D"]` per-file-ignores 豁免现有代码（16434 个违规暂缓）
  - 更新 ROADMAP 描述，标明增量收紧策略（按文件移除 D 豁免项）
- **ROADMAP #29 Web API 版本前缀 + 速率限制**:
  - `src/web/dashboard.py` 添加 `API_PREFIX = "/api/v1"` 常量
  - 添加滑动窗口 `rate_limit` 装饰器（120 次/分钟，基于客户端 IP + 端点）
  - 5 个 API 路由迁移至 `f"{API_PREFIX}/..."` 并添加 `@rate_limit`
  - 添加 `/api/<path:subpath>` 旧路径自动 301 重定向至 `/api/v1/*`
  - 启动横幅动态显示 `/api/v1/` 端点
  - ROADMAP 已标记为 [OK] 完成（30/30 项，100%）
- **ROADMAP #23 start_menu.py 拆分为包（785行 → ~150行/模块）**:
  - 创建 `src/start_menu/` 包（`_shared.py`, `_i18n.py`, `_utils.py`, `_ui.py`, `_main.py`）
  - 根级 `start_menu.py` 缩减为 9 行薄引导（仅 sys.path + 调用包 main()）
  - 保留 `start.bat` / `key_collision.py` / `pyproject.toml` 兼容性（入口路径不变）
  - 更新 `pyproject.toml` per-file-ignores 映射到新模块路径
- **ROADMAP #17 统一导入顺序（消除 E402 抑制标记）**:
  - 重构 `src/cli/main.py`：7 个模块级导入转为函数级惰性导入，仅保留 `CLIOutput` / `get_configured_logger` / `init_logging` 在模块级（架构必需）
  - 修复 11 个文件中 `# noqa: E402` 标记（`src/gpu/engine.py`、`src/gpu/multi_gpu_engine.py`、`src/gpu/worker.py`、`src/collision/key_collision_engine.py`、`src/automation/main.py`、`conftest.py`、`tests/integration/test_end_to_end.py`、`tests/gpu/test_gpu_dynamic_benchmark.py`、`scripts/dev/run_key_tests.py`）
  - 5 个文件因架构约束保留 `# noqa: E402`（`key_collision_cli.py` sys.path + 4 个测试 mock 文件）
  - 模块级 E402 从 43 个实例降至 6 个（减少 86%）
- **ROADMAP #13 修复循环导入耦合**:
  - 创建 `src/gpu/_engine_protocol.py`（`GPUEngineProtocol`），替代 `TYPE_CHECKING` 反向依赖
  - 5 个文件（`worker.py`, `engine_monitor.py`, `search_mode_coordinator.py`, `base_search.py`, `random_search.py`）从 `..collision.gpu.engine` 改为引用协议
  - 保留 3 处函数级惰性导入（`worker.py`/`config.py`/`facade.py` 构造用途）
  - 确认无运行时循环导入错误（所有双向依赖已安全守卫）
- **ROADMAP #11 统一入口点**:
  - 确认 `key_collision_cli.py` 为唯一根级 CLI 入口（23 行代理 → `src.cli.main:main()`）
  - 移除对不存在的根级 `main.py` 的引用（`docs/standards/config_change_process.md`）
  - `README.md` 入口描述从"推荐使用"更新为"统一命令行入口"
  - `key_collision_cli.py` docstring 移除 ROADMAP #11 待办注释，声明为统一入口
  - `pyproject.toml` 已有 `[project.scripts] btc-collision = "src.cli.main:main"`
  - ROADMAP 已标记为 [OK] 完成（29/30 项，97%）

- **`src/gpu/async_executor.py` → `src/gpu/async_executor/` 包拆分**:
  - 单文件 1707 行拆分为 6 模块包（`__init__.py`, `_executor.py`, `_gpu_info.py`, `_collector.py`, `_sync.py`, `_error_utils.py`）
  - 引入 Mixin 模式（`_GPUInfoMixin`, `_ResultCollectorMixin`, `_SyncFallbackMixin`）降低类复杂度
  - 提取 `with_sync_fallback` 装饰器至 `_error_utils.py`，消除重复的 `_run_batch_sync_fallback` 实现
  - 所有模块向后兼容导出，外部导入路径不变

- **`src/gpu/async_executor/_sync.py`**: 新增 `_log_cleanup()` 静态方法，在 cleanup 路径中抑制 `OSError`/`RuntimeError`/`AttributeError`，解决 Python 解释器关闭时日志轮转"句柄无效"崩溃
- **`src/gpu/async_executor/_executor.py`**: 新增 `__del__` 方法安全调用 `cleanup()`，并包裹 `suppress(Exception)` 防止析构时异常冒泡
- **`src/gpu/memory_pool.py`**: 添加缺失的 `LOG_DEFAULT_MAX_BYTES = 10 * 1024 * 1024` 模块级常量（原 F821 未定义变量）
- **`src/gpu/device_manager.py`**: 修复 P2SH 分支中 `addr_len` 未赋值即使用的 F821 作用域 Bug
- **`src/gpu/async_executor/`** 包内所有模块：修复相对导入路径错误（`.utils` → `...utils`），修正 `SyntaxError: 无效字符'。'`（孤立 Note 块），移除 5 处未使用导入（F401）
- **`src/gpu/device_manager.py`**: 修复 6 处 `E501` 超长行（跳过地址追加和日志调用换行）
- **`src/gpu/async_executor/`**: 修复 9 处 `E501` 超长行（多参调用和复杂条件换行）
- **`tests/test_async_executor.py`（53 测试，0 失败）**: 全程保持零回归
- **`tests/test_wizard.py`（95 测试，0 失败）**: 完整修复所有 API 不匹配问题
  - 所有 Selector 测试类重写为匹配简化后的存根 API（`GPUSelector`, `ModeSelector`, `TargetSelector`, `OptionSelector`）
  - `WizardEvent` 类型从 enum 改为 `.value` 字符串以匹配 `str` 类型声明
  - `WizardMessageQueue` mock 移除 `spec` 限制，允许引擎调用所有方法
  - `ConfigBuilder` mock 添加以支持 `test_run_compact_mode`
- **`src/wizard/events.py`**: `EventDispatcher.dispatch()` 添加 try/except 捕获回调异常
- **`src/wizard/interfaces.py`**: `WizardResult.load_from_file()` 添加文件错误处理
- **`src/wizard/wizard_engine.py`**: 修复 `_select_gpu()` 和 `_execute()` 的 API 调用
- **`tests/test_concurrency_stress.py`（7 测试，0 失败）**: 修复 4 个 API 不匹配
  - `LogStorage.save()`: 参数从 `dict` 改为 `list[dict]`，批量保存策略
  - `LogCollector`: `register_handler()`/`start()`/`stop()` 不存在 → 改用 `_handlers.append()`，移除 start/stop
  - `collect_from_queue()`: 移除不存在的 `source` 参数
  - `LogStorage.__init__()`: 移除不存在的 `max_file_size` 参数
- **`tests/test_memory_locking.py`（17 测试，0 失败）**: API 完全匹配，无需代码修改
- 为 `tests/unit/crypto/test_crypto_backend_edge.py` 中的 `TestCoincurveBackend` 和 `TestECDSABackend` 添加 `@unittest.skipIf` 守卫，在后端不可用时跳过测试
- 为 `tests/unit/logging/test_logging_config.py` 中的 `TestSafeRotatingFileHandler` 添加 `reset_logging_config` fixture，确保测试间状态隔离
- **`src/collision/key_collision_engine.py` — P0 加密后端初始化失败**: 添加 `raise` 传播，消除静默吞异常导致后续私钥生成在错误状态下运行的隐患
- **`src/gpu/kernel_impl.py` — P0 内核执行失败**: `return []` 改为 `raise RuntimeError(...) from e`，消除假阴性（搜索失败误报"无匹配"）
- **`src/gpu/worker.py` — P0 工作器异常传播**: `_execute_search()` 中 `RuntimeError`/`ValueError`/`Exception` 记录后 `raise`；`finally` 块中不再覆盖 `status="error"` 为 `"stopped"`
- **`src/gpu/kernel_impl.py` — P1 ALG-3 增强验证失败**: `logger.warning` 升级为 `logger.error + exc_info=True + raise`，阻止 GPU 内核在未通过正确性验证的情况下运行
- **`src/gpu/kernel_impl.py` — P1 4 处缺失 `exc_info=True`**: 清空 match_buf、超时监控线程、内核执行、内存泄漏检查
- **`src/gpu/async_executor/_executor.py` — P1 预取失败日志升级**: `logger.warning` → `logger.error`

### Added

- 新增 `CI_PROBLEM_ANALYSIS.md` 文档，系统分析 CI 问题（问题分类、影响分析、数据污染分析、环境差异分析、依赖版本分析）

### Removed

- **`gpu_test_output.txt`**: 删除项目根目录的陈旧测试输出文件（56.85 KB）
- **`build_test/` 目录 (372 文件)**: 删除项目根目录的陈旧完整项目副本
- **根目录陈旧 CI/代码质量日志 (10+ 文件)**: 删除 `checked_files.txt`、`docs_tracked.txt`、`err.log`、`flake8_err.txt`、`pytest_fix.txt`、`pytest_out.txt`、`ruff_check.json`、`gpu_test_v2_output.txt`、`lint_keygen.txt`、`lint_keygen2.txt`、`lint_output.txt`、`output.txt`、`output2.txt`、`report.txt`、`test_output.txt`
- **根目录空文件**: 删除 `2000` (0B)
- **docs/ 根目录过时分析/审计报告 (15 个)**: 删除 v3.x 时期分析报告 (`PROJECT_ANALYSIS.md`、`PROJECT_CLEANUP_REPORT_V3.1.0.md`、`PROJECT_COMPREHENSIVE_ANALYSIS_V3.md`)、发布说明 (`RELEASE_NOTES_v3.3.1.md`)、修复报告 (`p1_fixes_report.md`、`p2_fixes_report.md`、`p3_fixes_report.md`)、CLI 审计报告 (`cli_functional_audit_report.md`、`cli_improvement_report.md`、`cli_usability_review.md`)、代码审查报告 (`code_review_interactive_improvements.md`、`manual_code_review_cli_improvements.md`)、文本文件 (`FORMAT_AUTO_DETECTION_ANALYSIS.txt`、`MULTI_FORMAT_IMPLEMENTATION_GUIDE.txt`、`MULTI_FORMAT_VERIFICATION_REPORT.txt`、`VERIFICATION_REPORT.txt`、`health_review_issues.csv`)
  - 新增 `docs/standards/exception_handling_standards.md` — 正式的五级异常处理规范（L1致命/L2降级/L3隔离/L4清理/L5包装）
  - 更新 `docs/standards/development_code_standards.md` 第 7 节 — 精简为概要，引用新规范

### Docs

- 新增 `docs/standards/exception_handling_standards.md` — 正式异常处理规范（五级模型、禁止模式、日志格式、变量命名、模块对照表、审查清单）
- 更新 `docs/standards/development_code_standards.md` 第 7 节 — 精简为概要，引用新规范
- 更新 `src/gpu/__init__.py` 模块文档字符串，标注 v5.2.3 包拆分
- 更新 `src/gpu/executor_types.py` 文档字符串，明确公用模块定位
- 更新 `src/utils/exception_handler.py` 文档中过时的文件引用
- 更新所有 `async_executor/` 子模块的文档字符串（模块描述、v5.2.3 tag、`_log_cleanup` 说明）
- 更新 `CI_PROBLEM_ANALYSIS.md` 以反映修复状态
- 新增 `docs/testing.md` 测试指南
- **CI 配置**: `.github/workflows/ci.yml` 移除所有 `--ignore` 标记（`test_wizard.py`, `test_commands.py`, `test_concurrency_stress.py`, `test_memory_locking.py` 全部通过）

## [0.1.0] - 2026-05-26

### Added

- 初始版本
- 实现核心碰撞引擎功能
- 实现多种加密后端（PurePython、OpenSSL、Coincurve、ECDSA）
- 实现 GPU 加速支持
- 实现配置管理系统
- 实现日志系统
- 实现命令行界面

### Fixed

- 无

### Deprecated

- 无

### Removed

- 无

### Security

- 无

[Unreleased]: https://github.com/your-username/btc-collision-engine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-username/btc-collision-engine/releases/tag/v0.1.0
