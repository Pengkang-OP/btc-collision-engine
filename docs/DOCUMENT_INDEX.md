# 项目文档索引

> BTC碰撞引擎项目文档导航

> **版本**: v4.2.1 | **最后更新**: 2026-05-12

---

## 文档统计

| 目录 | 文档数量 | 说明 |
|------|----------|------|
| docs/*.md | 63 | 活跃文档 |
| docs/archive/ | 19 | 历史归档 |
| 根目录 | 10 | 核心文档 |

---

## 核心文档 (根目录)

| 文档 | 说明 |
|------|------|
| README.md | 项目概述、快速开始 |
| CHANGELOG.md | 完整变更日志 |
| CLI_GUIDE.md | CLI使用指南 |
| STARTUP_GUIDE.md | 启动指南 |
| CONTRIBUTING.md | 贡献指南 |
| GPU_MONITORING.md | GPU监控指南 |
| INTEL_ARC_OPTIMIZATION.md | Intel Arc优化 |
| OPENCL_KERNEL_AUDIT_REPORT.md | OpenCL内核审核 |
| AUTOMATION_SYSTEM.md | 端到端自动化系统 |

---

## 文档分类 (docs/)

### 1. 快速开始
- getting-started.md - 详细入门指南
- use-cases.md - 使用场景
- project-status.md - 项目状态

### 2. 架构与设计
- architecture.md - 系统架构 (17个图表)
- workflow_diagrams.md - 工作流程图 (19个图表)
- topology-diagrams-v3.5.1.md - 拓扑图集 (11张)
- PROJECT_COMPREHENSIVE_DEEP_ANALYSIS_V3.5.1.md - 深度分析报告
- api-reference.md - API参考 (2949行)
- requirements.md - 需求规格

### 3. 核心功能

#### 碰撞引擎
- performance-optimization.md - 性能优化 (924行)
- checkpoint-resume-feature.md - 断点续传
- checkpoint-quick-guide.md - 断点续传快速指南
- logging-guide.md - 日志指南
- logging-standards.md - 日志标准

#### 安全特性
- security-guidelines.md - 安全指南
- secure-key-management.md - 密钥管理
- windows-memory-lock.md - 内存锁机制

#### 监控系统
- monitoring-system-guide.md - 监控指南
- monitoring-system-usage-guide.md - 监控使用

#### GPU加速
- gpu-engine-guide.md - GPU引擎指南
- GPU_CONFIG_MANAGER_GUIDE.md - GPU配置管理
- intel-arc-integration-guide.md - Intel Arc集成

### 4. 配置与部署
- CONFIG.md - 配置指南
- config-usage-examples.md - 配置示例
- DOCKER_DEPLOYMENT.md - Docker部署
- SYSTEMD_DEPLOYMENT.md - Systemd部署
- PRODUCTION_DEPLOYMENT.md - 生产部署

### 5. 界面使用
- user-interface.md - 用户界面
- CLI_GUIDE.md (根目录) - CLI完整使用指南

### 6. 故障排除
- troubleshooting.md - 故障排除
- FAQ.md - 常见问题

---

## 历史归档 (docs/archive/history/)

> 以下历史文档已归档，不再维护

| 归档类型 | 说明 |
|----------|------|
| PROJECT_COMPREHENSIVE_*.md | 旧版本分析报告 |
| topology-diagrams.md | 旧版拓扑图 |
| *PHASE*.md | Phase完成报告 |
| *REVIEW*.md | 代码审查报告 |
| *git_commit*.md | Git提交记录 |
| *MIGRATION*.md | 迁移报告 |
| startbat_*.md | 启动脚本相关 |
| CLI_AUDIT_SUMMARY.md | CLI审核总结 (2026-04-24) |
| CLI_QUICK_REFERENCE.md | CLI快速参考 (2026-04-24) |

---

## 更新记录

- v4.2.1 (2026-05-12): OpenCL内核审核修复，端到端自动化系统上线，CLI/bat文件整理
- v3.5.1 (2026-05-08): GPU引擎重构完成，测试体系增强
- v3.1.0: 首次文档大清理 (100->30文件)
