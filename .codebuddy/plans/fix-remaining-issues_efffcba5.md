---
name: fix-remaining-issues
overview: 逐一处理项目中新增的遗漏事项，包括配置漂移修复、空代码块清理、依赖版本统一、.gitignore 补全、异常处理改进等。
---

## 用户需求

用户要求对项目中新增的遗漏事项进行逐一处理。这些事项来自代码库的全面审计，分为高、中、低三个优先级，共 15 个事项。

## 产品概述

BTC 碰撞引擎是一个比特币私钥碰撞工具，支持 CPU 和 GPU 加速，多格式地址支持。当前需要对代码库中的配置不一致、异常处理、代码规范等问题进行修复。

## 核心功能

1. **高优先级事项处理**（3项）：

- 修复 `config.example.json` 中重复的 `gpu` 配置段和 `queue_depth` 不一致
- 修复 `config.example.json` 中 `use_uint32_workaround` 默认值风险（Intel Arc 用户会遇到 hang bug）
- 修复 `src/config/config_watcher.py` 析构函数中的 `except Exception: pass` 异常处理

2. **中优先级事项处理**（5项）：

- 清理 4 个文件中的空 `TYPE_CHECKING` 块
- 删除 `src/core/optimized_address_generator.py:86` 中的 `else: pass` 空分支
- 统一 `gmpy2` 版本上限（requirements-base.txt 和 pyproject.toml）
- 清理 `requirements-gpu.txt` 中的重复依赖声明
- 补全 `.gitignore` 遗漏项（如 `*.ruff_cache/`）

3. **低优先级事项处理**（2项）：

- 补充 `config.json` 缺少的 `gui` 配置段
- 为部分 `except Exception: pass` 添加 debug 日志（暂不处理，因属于代码风格改进）

## 功能内容和视觉效果

本任务不涉及 UI 修改，纯后端代码和配置修复。修复后将提升代码质量、配置一致性和运行时稳定性。

## 技术栈

- 语言：Python 3.9+
- 配置格式：JSON
- 依赖管理：requirements.txt + pyproject.toml
- GPU：OpenCL (pyopencl)
- 代码质量工具：ruff, mypy, black

## 实现方案

### 事项 6：修复 `config.example.json` 中重复的 `gpu` 配置段和 `queue_depth` 不一致

**问题分析**：

- `config.example.json` 包含两个 `gpu` 配置段（第 70 行和第 172 行）
- 第一个 `gpu` 段（第 70 行开始）包含正确的 `queue_depth: 16`（第 84 行）
- 第二个 `gpu` 段（第 172 行开始）包含旧的 `queue_depth: 4`（第 190 行）
- JSON 格式不允许重复键，第二个 `gpu` 段会覆盖第一个

**解决方案**：

1. 合并两个 `gpu` 配置段为一个
2. 保留第二个 `gpu` 段中的特有字段（如 `use_async_logging`、`async_log_file` 等）
3. 确保所有值与 `config.json` 和 `DEFAULT_CONFIG` 一致
4. 统一 `queue_depth` 为 16（与 `config.json` 一致，Intel Arc 推荐值）

**文件修改**：

- `f:/Qoder/btc-collision-engine/config.example.json`：重构整个文件，合并重复的 `gpu` 段

### 事项 7：修复 `use_uint32_workaround` 默认值风险

**问题分析**：

- `config.example.json` 第 116 行：`"use_uint32_workaround": false`
- `config.json` 第 126 行：`"use_uint32_workaround": true`
- Intel Arc 用户若拷贝 example 配置会遭遇 hang bug

**解决方案**：

1. 将 `config.example.json` 中的 `use_uint32_workaround` 改为 `true`
2. 与 `config.json` 保持一致

**文件修改**：

- `f:/Qoder/btc-collision-engine/config.example.json`：第 116 行值改为 `true`

### 事项 8：修复 `config_watcher.py` 析构函数中的异常处理

**问题分析**：

- `src/config/config_watcher.py` 第 257-258 行：`except Exception: pass`
- 第 262-264 行：外层 `except Exception: pass`
- 析构函数中吞掉所有异常，可能隐藏资源泄露

**解决方案**：

1. 在第 257 行添加 `logger.debug()` 日志，记录异常信息
2. 在第 262-264 行添加 `logger.debug()` 日志
3. 使用 `logging` 模块记录异常，便于调试

**文件修改**：

- `f:/Qoder/btc-collision-engine/src/config/config_watcher.py`：添加 debug 日志

### 事项 9：清理空 `TYPE_CHECKING` 块

**问题分析**：

- 4 个文件中有空的 `if TYPE_CHECKING: pass` 块，无实际内容

**解决方案**：

1. 删除 `src/gpu/nvidia_optimizer.py:29-30` 的空块
2. 删除 `src/gpu/amd_optimizer.py:29-30` 的空块
3. 删除 `src/gpu/search_modes/range_scan_search.py:13-14` 的空块
4. 删除 `src/gpu/search_modes/brute_force_search.py:13-14` 的空块

**文件修改**：

- `f:/Qoder/btc-collision-engine/src/gpu/nvidia_optimizer.py`
- `f:/Qoder/btc-collision-engine/src/gpu/amd_optimizer.py`
- `f:/Qoder/btc-collision-engine/src/gpu/search_modes/range_scan_search.py`
- `f:/Qoder/btc-collision-engine/src/gpu/search_modes/brute_force_search.py`

### 事项 10：删除 `else: pass` 空分支

**问题分析**：

- `src/core/optimized_address_generator.py:86`：`else: pass` 空分支

**解决方案**：

1. 直接删除 `else: pass` 分支
2. 或添加注释说明为何不需要处理

**文件修改**：

- `f:/Qoder/btc-collision-engine/src/core/optimized_address_generator.py`

### 事项 11：统一 `gmpy2` 版本上限

**问题分析**：

- `requirements-base.txt` 第 21 行：`gmpy2>=2.1.0,