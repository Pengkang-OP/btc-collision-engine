# 项目文档索引

> 本文档提供BTC碰撞引擎项目的完整文档导航，帮助您快速找到所需信息。

## 📚 文档分类

### 1. 快速开始与概述
- [README.md](../README.md) - 项目概述、快速开始、功能特性
- [getting-started.md](getting-started.md) - 详细入门指南
- [project-status.md](project-status.md) - 项目状态和路线图

### 2. 架构与设计
- [architecture.md](architecture.md) - 系统架构设计（✅ 已更新：17个Mermaid图表，依赖拓扑图，数据流向图，监控系统架构）
- [workflow_diagrams.md](workflow_diagrams.md) - 工作流程图（✅ 已更新：19个Mermaid图表，完整程序运行流程，GPU碰撞流程，并发模型）
- [api-reference.md](api-reference.md) - 完整API参考（✅ 已更新：2949行，SecureKeyManager API，碰撞引擎完整方法）
- [mermaid-rendering-check.md](mermaid-rendering-check.md) - Mermaid图表渲染检查报告（🆕 新增）

### 3. 核心功能文档

#### 碰撞引擎
- [performance-optimization.md](performance-optimization.md) - 性能优化指南（924行）
- [checkpoint-resume-feature.md](checkpoint-resume-feature.md) - 断点续传功能
- [logging-guide.md](logging-guide.md) - 日志系统指南
- [gpu-engine-guide.md](gpu-engine-guide.md) - GPU引擎使用指南（TODO）

#### 安全特性
- [security-guidelines.md](security-guidelines.md) - 安全指南
- [secure-key-management.md](secure-key-management.md) - 安全密钥管理
- [quick-reference-private-key-security.md](quick-reference-private-key-security.md) - 私钥安全速查

#### 监控系统
- [monitoring-system-guide.md](monitoring-system-guide.md) - 监控系统指南
- [data-logging-guide.md](data-logging-guide.md) - 数据日志系统指南（TODO）

#### 目标地址管理
- [address-import-feature.md](address-import-feature.md) - 地址导入功能

### 4. 界面使用
- [user-interface.md](user-interface.md) - GUI使用指南

### 5. 开发文档
- [requirements.md](requirements.md) - 需求规格
- [comprehensive-audit-report.md](comprehensive-audit-report.md) - 综合审计报告

---

## 📦 Archive文档归档说明

`archive/` 目录包含项目开发过程中的历史报告和总结，主要用于：
- 开发决策记录
- 问题修复历史
- 性能优化记录
- 测试验证报告

### Archive文档分类索引

#### 安全相关
- [SecureKeyManager优化报告](2026-04-20_SecureKeyManager优化报告.md)
- [SecureKeyManager审查修复](2026-04-20_SecureKeyManager审查修复.md)
- [SecureKeyManager测试报告](2026-04-20_SecureKeyManager测试报告.md)
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
- [测试最终总结](2026-04-20_测试最终总结.md) - 25.8KB，最全面的测试报告
- [测试验证报告](2026-04-20_测试验证报告.md)
- [真实碰撞测试报告](2026-04-20_真实碰撞测试报告.md)

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
| 主文档 | 16 | ~480KB（已更新） | 含36个Mermaid图表 |
| Archive文档 | 25 | ~280KB | 历史记录 |
| **总计** | **41** | **~760KB** | - |

**核心文档更新统计**：
- architecture.md：~786行，17个Mermaid图表
- workflow_diagrams.md：~827行，19个Mermaid图表
- api-reference.md：~2949行，完整API文档
- **新增总计**：约4562行高质量内容

---

## 🔄 文档更新记录

| 日期 | 更新内容 | 更新者 |
|------|---------|--------|
| 2026-04-20 | 创建文档索引，整理archive文档 | AI Assistant |
| 2026-04-20 | 更新architecture.md: 补充GPU架构、监控系统架构、数据流向图 | AI Assistant |
| 2026-04-20 | 更新workflow_diagrams.md: 补充GPU工作流程、监控数据流程、Mermaid图表 | AI Assistant |
| 2026-04-20 | 更新api-reference.md: 补充GPU引擎、监控系统、数据日志、统计模块API | AI Assistant |
| **2026-04-20** | **大规模文档现代化更新**（本次） | **AI Assistant** |
| | • architecture.md：转换ASCII为Mermaid，新增依赖拓扑图、程序运行流程图 | |
| | • workflow_diagrams.md：转换全部ASCII序列图为Mermaid（19个图表） | |
| | • api-reference.md：补充SecureKeyManager API、碰撞引擎完整方法 | |
| | • 新增mermaid-rendering-check.md：图表渲染检查报告 | |
| | • **总计新增约4562行高质量内容，36个Mermaid图表** | |

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
