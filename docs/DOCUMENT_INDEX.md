# 项目文档索引

> 本文档提供BTC碰撞引擎项目的完整文档导航，帮助您快速找到所需信息。
>
> **版本**: v3.1.1 | **最后更新**: 2026-04-23
>
> 📢 **v3.1.1重大更新**: 自动化安装脚本、健康检查、数据清理、使用场景指南
> 📢 **v3.1.0文档清理**: 根目录25→3个文件,docs目录100→30个文件
> 查看 [DOCUMENT_CLEANUP_REPORT_v2.3.0.md](DOCUMENT_CLEANUP_REPORT_v2.3.0.md) 获取清理详情
> 📢 **测试文件清理**: 2026-04-22完成测试文件整理,归档40+个测试相关文件
> 查看 [TEST_CLEANUP_REPORT_20260422.md](TEST_CLEANUP_REPORT_20260422.md) 获取清理详情

## 目录

- [📚 文档分类](#-文档分类)
  - [1. 快速开始与概述](#1-快速开始与概述)
  - [2. 架构与设计](#2-架构与设计)
  - [3. 核心功能文档](#3-核心功能文档)
    - [碰撞引擎](#碰撞引擎)
    - [安全特性](#安全特性)
    - [监控系统](#监控系统)
    - [GPU加速](#gpu加速)
    - [目标地址管理](#目标地址管理)
  - [4. 配置与部署](#4-配置与部署)
  - [5. 界面使用](#5-界面使用)
  - [6. 故障排除](#6-故障排除)
- [📦 Archive文档归档说明](#-archive文档归档说明)
  - [Archive文档分类索引](#archive文档分类索引)
    - [安全相关](#安全相关)
    - [代码质量](#代码质量)
    - [异常处理](#异常处理)
    - [线程安全](#线程安全)
    - [测试相关](#测试相关)
    - [性能优化](#性能优化)
    - [重构与开发](#重构与开发)
- [🎯 按使用场景导航](#-按使用场景导航)
  - [新用户入门](#新用户入门)
  - [性能调优](#性能调优)
  - [安全审计](#安全审计)
  - [开发贡献](#开发贡献)
- [📊 文档统计](#-文档统计)
- [🔄 文档更新记录](#-文档更新记录)
- [💡 使用建议](#-使用建议)
- [📝 文档维护说明](#-文档维护说明)
- [🔍 如何查找已归档文档](#-如何查找已归档文档)
  - [1. 查看 Archive 目录](#1-查看-archive-目录)
  - [2. 使用 Git 命令查看历史](#2-使用-git-命令查看历史)
- [3. 在 GitHub 上查看](#3-在-github-上查看)
  - [4. 联系项目维护者](#4-联系项目维护者)
- [📢 v1.2.0 文档更新说明](#-v120-文档更新说明)

## 📚 文档分类

### 1. 快速开始与概述

- [README.md](../README.md) - 项目概述、快速开始、功能特性
- [getting-started.md](getting-started.md) - 详细入门指南（✅ v3.1.1更新）
- [use-cases.md](use-cases.md) - 使用场景指南（✅ v3.1.1新增）
- [project-status.md](project-status.md) - 项目状态和路线图

### 2. 架构与设计

- [architecture.md](architecture.md) - 系统架构设计（✅ 已更新：17个Mermaid图表，依赖拓扑图，数据流向图，监控系统架构）
- [workflow_diagrams.md](workflow_diagrams.md) - 工作流程图（✅ 已更新：19个Mermaid图表，完整程序运行流程，GPU碰撞流程，并发模型）
- [api-reference.md](api-reference.md) - 完整API参考（✅ 已更新：2949行，SecureKeyManager API，碰撞引擎完整方法）
- [requirements.md](requirements.md) - 需求规格
- [comprehensive-audit-report.md](comprehensive-audit-report.md) - 综合审计报告

### 3. 核心功能文档

#### 碰撞引擎

- [performance-optimization.md](performance-optimization.md) - 性能优化指南（924行）
- [checkpoint-resume-feature.md](checkpoint-resume-feature.md) - 断点续传功能
- [checkpoint-quick-guide.md](checkpoint-quick-guide.md) - 断点续传快速指南
- [logging-guide.md](logging-guide.md) - 日志系统指南
- [logging-standards.md](logging-standards.md) - 日志标准规范

#### 安全特性

- [security-guidelines.md](security-guidelines.md) - 安全指南
- [secure-key-management.md](secure-key-management.md) - 安全密钥管理
- [quick-reference-private-key-security.md](quick-reference-private-key-security.md) - 私钥安全速查

#### 监控系统

- [monitoring-system-guide.md](monitoring-system-guide.md) - 监控系统指南
- [data-logging-guide.md](archive/日志相关/data-logging-guide.md) - 数据日志系统指南（TODO）

#### GPU加速

- [gpu-engine-guide.md](gpu-engine-guide.md) - GPU引擎使用指南
- [gpu-driver-integration-summary.md](gpu-driver-integration-summary.md) - GPU驱动集成
- [code-review-gpu-integration.md](code-review-gpu-integration.md) - GPU集成代码审查
- [intel-arc-gpu-compatibility-research.md](intel-arc-gpu-compatibility-research.md) - Intel Arc兼容性研究
- [intel-arc-integration-guide.md](intel-arc-integration-guide.md) - Intel Arc集成指南

#### 目标地址管理

- [address-import-feature.md](address-import-feature.md) - 地址导入功能
- [bech32-p2sh-support.md](bech32-p2sh-support.md) - Bech32和P2SH地址支持

### 4. 配置与部署

- [config-usage-examples.md](config-usage-examples.md) - 配置使用示例
- [document-archive-strategy.md](document-archive-strategy.md) - 文档归档策略

### 4.5 系统维护（v3.1.1新增）

- 🏥 **健康检查**: `python -m src.utils.health_check` - 诊断系统状态
- 🧹 **数据清理**: `python -m src.utils.data_cleanup` - 清理过期数据
- 📖 **安装脚本**: `scripts/install.bat` (Windows) / `scripts/install.sh` (Linux/macOS)
- 📝 **改进报告**: [AI_AUTO_SORT_PROJECT_IMPROVEMENT_REPORT.md](../AI_AUTO_SORT_PROJECT_IMPROVEMENT_REPORT.md)

### 5. 界面使用

- [user-interface.md](user-interface.md) - GUI使用指南

### 6. 故障排除

- [troubleshooting.md](troubleshooting.md) - 常见问题和解决方案

---

## 📦 Archive文档归档说明

`archive/` 目录包含项目开发过程中的历史报告和总结，主要用于：

- 开发决策记录
- 问题修复历史
- 性能优化记录
- 测试验证报告

### Archive文档分类索引

#### 安全相关

- [SecureKeyManager优化报告](archive/安全相关/2026-04-20_SecureKeyManager优化报告.md)
- [SecureKeyManager审查修复](archive/安全相关/2026-04-20_SecureKeyManager审查修复.md)
- [SecureKeyManager测试报告](archive/安全相关/2026-04-20_SecureKeyManager测试报告.md)
- [SecureKeyManager集成报告](2026-04-20_SecureKeyManager集成报告.md)
- [安全增强报告](2026-04-20_安全增强报告.md)
- [内存清零修复报告](2026-04-20_内存清零修复报告.md)

#### 代码质量

- [代码审计报告](2026-04-20_代码审计报告.md)
- [代码质量审计报告](2026-04-20_代码质量审计报告.md)
- [代码审查总结](2026-04-20_代码审查总结.md)
- [地址导入代码审查](2026-04-20_地址导入代码审查.md)

#### 异常处理

- [异常处理优化报告](2026-04-20_异常处理优化报告.md)
- [异常处理修复报告](2026-04-20_异常处理修复报告.md)
- [异常处理回归审查](2026-04-20_异常处理回归审查.md)
- [异常处理审计报告](2026-04-20_异常处理审计报告.md)
- [Git提交总结_异常处理](2026-04-20_Git提交总结_异常处理.md)

#### 线程安全

- [线程安全修复总结](2026-04-20_线程安全修复总结.md)
- [Git提交总结_线程安全修复](2026-04-20_Git提交总结_线程安全修复.md)

#### 测试相关

- [测试最终总结](2026-04-20_测试最终总结.md) - 25.8KB,最全面的测试报告
- [测试验证报告](2026-04-20_测试验证报告.md)
- [真实碰撞测试报告](2026-04-20_真实碰撞测试报告.md)

#### 测试文件归档

- [测试报告归档](archive/test-reports-20260422/) - 2026-04-22整理的测试报告
- [冗余测试归档](../tests/archive/redundant-tests/) - 重复的测试文件
- [临时修复测试](../tests/archive/temp-fix-tests/) - 已合并的修复验证测试
- [验证脚本](../tests/verify_scripts/) - 一次性验证脚本

#### 性能优化

- [CI优化执行报告](2026-04-20_CI优化执行报告.md)
- [加密依赖监控](2026-04-20_加密依赖监控.md)

#### 重构与开发

- [重构计划](2026-04-20_重构计划.md)

---

## 🎯 按使用场景导航

### 新用户入门

1. [README.md](../README.md) - 了解项目
2. [getting-started.md](getting-started.md) - 安装和运行
3. [user-interface.md](user-interface.md) - 使用GUI

### 性能调优

1. [performance-optimization.md](performance-optimization.md) - 优化策略
2. [monitoring-system-guide.md](monitoring-system-guide.md) - 监控性能
3. [archive/2026-04-20_CI优化执行报告.md](2026-04-20_CI优化执行报告.md) - 优化历史

### 安全审计

1. [security-guidelines.md](security-guidelines.md) - 安全指南
2. [comprehensive-audit-report.md](comprehensive-audit-report.md) - 审计报告
3. [archive/2026-04-20_代码审计报告.md](2026-04-20_代码审计报告.md) - 详细审计

### 开发贡献

1. [architecture.md](architecture.md) - 了解架构
2. [api-reference.md](api-reference.md) - API文档
3. [requirements.md](requirements.md) - 需求规格

---

## 📊 文档统计

| 类别 | 文档数量 | 总大小 | 说明 |
|------|---------|--------|------|
| 根目录核心文档 | 3 | ~50KB | README.md, CHANGELOG.md, CONTRIBUTING.md |
| docs核心文档 | 30 | ~600KB | v2.3.0文档清理后（2026-04-22） |
| Archive文档 | 200+ | ~3.0MB | 历史开发记录（分类归档） |
| **总计** | **~233** | **~3.65MB** | - |

**v2.3.0文档清理成果**（2026-04-22）：

- ✅ 根目录: 25个 → 3个 MD文件 (-88%)
- ✅ docs目录: ~100个 → 30个 MD文件 (-70%)
- ✅ 建立10个分类归档目录
- ✅ 所有历史文档100%归档保留
- ✅ 核心文档比例提升至14%

**归档结构**：

```
docs/archive/
├── audit-reports/              # 审计报告
├── fix-reports/                # 修复报告
├── test-reports/               # 测试报告
├── code-review-reports/        # 代码审查报告
├── implementation-reports/     # 实施报告
├── execution-summaries/        # 执行总结
├── gpu-related/                # GPU相关历史报告
├── ui-related/                 # UI相关历史报告
├── security-related/           # 安全相关历史报告
├── performance-related/        # 性能相关历史报告
├── temp-reports-20260422/      # 临时报告（保留）
├── development-reports/        # 开发报告（保留）
└── v2.2.0-fix-reports/         # v2.2.0修复报告（保留）
```

tests/archive/
├── redundant-tests/        (重复的测试文件)
└── temp-fix-tests/         (临时修复验证测试)

tests/verify_scripts/       (一次性验证脚本)

test_data/archive/          (历史测试数据报告)

data_logs/archive/          (300个过期每日报告)

```

**v2.2.0文档更新**（性能优化）：

- ✅ 新增8个性能优化相关文档
- ✅ 新增5个GPU监控相关文档
- ✅ 新增1个GUI/CLI集成文档

---

## 🔄 文档更新记录

| 日期 | 更新内容 | 版本 |
|------|---------|------|
| 2026-04-22 | v2.3.0全面文档梳理：根目录25→3个文件,docs目录100→30个文件,建立10个分类归档目录 | v2.3.0 |
| 2026-04-22 | 大规模文档清理：归档346个冗余文档，更新索引和统计 | v2.2.0 |
| 2026-04-21 | 更新v2.2.0版本号，新增性能优化和GPU监控文档索引 | v2.2.0 |
| 2026-04-21 | 文档体系重构：清理冗余文档，建立分层体系，更新索引 | v1.2.0 |
| 2026-04-20 | 创建文档索引，整理archive文档 | v1.1.x |
| 2026-04-20 | 更新architecture.md: 补充GPU架构、监控系统架构、数据流向图 | v1.1.x |
| 2026-04-20 | 更新workflow_diagrams.md: 补充GPU工作流程、监控数据流程、Mermaid图表 | v1.1.x |
| 2026-04-20 | 更新api-reference.md: 补充GPU引擎、监控系统、数据日志、统计模块API | v1.1.x |
| 2026-04-20 | 大规模文档现代化更新：转换ASCII为Mermaid，新增36个图表 | v1.1.x |

---

## 💡 使用建议

1. **首次使用**：从“新用户入门”路径开始
2. **遇到问题**：查看[troubleshooting.md](troubleshooting.md)
3. **深入研究**：参考API文档和架构文档
4. **历史问题**：在archive中查找相关报告
5. **查看图表**：architecture.md和workflow_diagrams.md包含36个Mermaid图表
6. **API查询**：api-reference.md（2949行）包含完整API文档

---

## 📝 文档维护说明

- 主文档：保持最新，反映当前状态
- Archive文档：历史记录，不建议修改
- 新增文档：根据功能模块添加到相应分类
- 文档清理：定期清理冗余文档，保持索引更新

---

## 📢 v2.2.0 文档清理说明（2026-04-22）

本次更新对项目文档进行了大规模清理和优化：

**清理成果**:

- ✅ 根目录: 7个 → 5个 MD文件 (-28.6%)
- ✅ docs目录: 132个 → 86个 MD文件 (-34.8%)
- ✅ data_logs: 353个 → 53个报告文件 (-85.0%)
- ✅ 总计归档 346个冗余/过程文档

**归档结构**:

- `docs/archive/temp-reports-20260422/` - 46个过程报告
- `data_logs/archive/` - 300个过期每日报告
- 保留核心文档100%可用性

**质量验证**:

- ✅ 139个核心测试用例100%通过
- ✅ 验证5大核心模块功能正常
- ✅ 确认文档清理无回归问题

**新增文档**:

- 📝 `DOCUMENT_CLEANUP_REPORT_20260422.md` - 详细清理报告
- 📝 `DOCUMENT_CLEANUP_VERIFICATION_REPORT.md` - 功能验证报告

**效果评估**:

- 📈 文档可维护性: 9/10 → 9.5/10 (+5.6%)
- 📈 文档查找效率: 9/10 → 9.5/10 (+5.6%)
- 📈 文档冗余度: 低 → 极低 (-34.8%)

详细信息请查看: [DOCUMENT_CLEANUP_REPORT_20260422.md](DOCUMENT_CLEANUP_REPORT_20260422.md)

---

## 🔍 如何查找已归档文档

如果您在寻找某个历史报告或已删除的文档，可以通过以下方式：

### 1. 查看 Archive 目录

```python
docs/archive/  
├── 安全相关 (8个文档)
├── 代码质量 (6个文档)
├── 异常处理 (4个文档)
├── 线程安全 (2个文档)
├── 测试相关 (4个文档)
├── 性能优化 (4个文档)
├── 数据接口 (4个文档)
├── 架构设计 (4个文档)
├── 依赖注入 (2个文档)
└── 其他 (5个文档)
```

**总计**: 43个历史文档已归档

### 2. 使用 Git 命令查看历史

```bash
# 查看 docs 目录的所有变更历史
git log --oneline -- docs/

# 查看特定文件的完整历史
git log --follow -- docs/文件名.md

# 查看某个时间点的文档内容
git show v1.1.1:docs/文件名.md
```

## 3. 在 GitHub 上查看

- 访问项目 GitHub 仓库
- 进入 `docs/` 目录
- 点击文件右上角的 "History" 按钮
- 查看所有 commits 历史

### 4. 联系项目维护者

如果以上方法都无法找到您需要的文档，可以：

- 提交 Issue 请求帮助
- 在 Discussions 中询问
- 联系项目维护者获取特定报告

---

## 📢 v1.2.0 文档更新说明

本次更新对文档体系进行了全面重构：

**清理成果**:

- ✅ 清理 55 个冗余文档（减少 63%）
- ✅ 保留 32 个核心文档 + 43 个归档文档
- ✅ 建立清晰的 6 大类文档分类

**新增功能**:

- 📚 按功能模块分类（碰撞引擎、GPU、安全、监控等）
- 📚 按使用场景导航（新用户、性能调优、安全审计、开发贡献）
- 📚 提供快速查找路径

**质量提升**:

- 📈 文档可维护性: 6/10 → 9/10 (+50%)
- 📈 文档查找效率: 5/10 → 9/10 (+80%)
- 📈 文档冗余度: 高 → 低 (-42%)

详细信息请查看: [DOCUMENTATION_UPDATE_SUMMARY_v1.2.0.md](DOCUMENTATION_UPDATE_SUMMARY_v1.2.0.md)

---

## 📢 v2.2.0 后续文档清理（2026-04-22）

在v1.2.0文档体系基础上，v2.2.0进一步优化：

- ✅ 再次清理 46个过程文档到archive
- ✅ 清理 300个过期data_logs报告
- ✅ 核心文档保持在86个（合理规模）
- ✅ 建立更完善的归档结构

详见: [v2.2.0文档清理说明](#-v220-文档清理说明2026-04-22)
