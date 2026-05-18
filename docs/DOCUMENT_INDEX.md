# 项目文档索引

> BTC碰撞引擎项目文档导航

> **版本**: v4.4.0 | **最后更新**: 2026-05-18

> 本次更新：启动时目标格式分析与不兼容格式警告；全文"可能"→"必然"措辞修正；GPU路径一致性注释；冗余文件清理。

---

## 文档统计

| 目录 | 文档数量 | 说明 |
|------|----------|------|
| docs/*.md | 40+ | 活跃文档 |
| docs/archive/ | 30+ | 历史归档 |
| 根目录 | 3 | 核心文档 (README/CHANGELOG/CONTRIBUTING) |

---

## 核心文档 (根目录)

| 文档 | 说明 |
|------|------|
| README.md | 项目概述、快速开始 |
| CHANGELOG.md | 完整变更日志 |
| CONTRIBUTING.md | 贡献指南 |

> 其他文档已统一整理至 docs/ 目录，审核报告归档至 docs/audit-reports/。

---

## 文档分类 (docs/)

### 1. 快速开始

- getting-started.md - 详细入门指南
- use-cases.md - 使用场景
- project-status.md - 项目状态

### 2. 架构与设计

- architecture.md - 系统架构 (17个图表)
- workflow_diagrams.md - 工作流程图 (19个图表)
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

#### GPU加速

- gpu-engine-guide.md - GPU引擎指南
- GPU_CONFIG_MANAGER_GUIDE.md - GPU配置管理
- intel-arc-integration-guide.md - Intel Arc集成
- intel-arc-gpu-compatibility-research.md - Intel Arc兼容性研究
- GPU_ASYNC_LOGGING_INTEGRATION_GUIDE.md - GPU异步日志

### 4. 配置与部署

- CONFIG.md - 配置指南
- config-usage-examples.md - 配置示例
- DOCKER_DEPLOYMENT.md - Docker部署
- SYSTEMD_DEPLOYMENT.md - Systemd部署
- PRODUCTION_DEPLOYMENT.md - 生产部署

### 5. 界面使用

- user-interface.md - 用户界面
- CLI_GUIDE.md - CLI完整使用指南
- STARTUP_GUIDE.md - 启动指南

### 6. 运维与监控

- GPU_MONITORING.md - GPU监控指南
- AUTOMATION_SYSTEM.md - 端到端自动化系统

### 7. 故障排除

- troubleshooting.md - 故障排除
- FAQ.md - 常见问题

---

## 历史归档 (docs/archive/history/)

> 2026-05-16 深度清理新增归档：v3.5.1 发布说明、v3.5.1 深度分析、GPU引擎重构计划、综合审计报告、全面系统验证报告、Intel Arc快速开始/优化/深度分析、GPU异步日志使用示例、监控系统使用指南

| 归档类型 | 说明 |
|----------|------|
| PROJECT_COMPREHENSIVE_*.md | 旧版本分析报告 |
| topology-diagrams.md | 旧版拓扑图 |
| *PHASE*.md | Phase完成报告 |
| *REVIEW*.md | 代码审查报告 |
| *git_commit*.md | Git提交记录 |
| *MIGRATION*.md | 迁移报告 |
| INTEL_ARC_*.md | Intel Arc 历史文档 (3 个已归档) |
| RELEASE_NOTES_v3.5.1.md | v3.5.1 发布说明 |
| GPU_ENGINE_REFACTORING_PLAN.md | GPU引擎重构计划 (已完成) |
| comprehensive-audit-report.md | 综合审计报告 |
| 全面系统性验证报告.md | 系统验证报告 |
| GPU_ASYNC_LOGGING_USAGE_EXAMPLES.md | GPU异步日志使用示例 |
| monitoring-system-usage-guide.md | 监控系统使用指南 |
| startbat_*.md | 启动脚本相关 (已精简，保留 quick_reference) |
| CLI_AUDIT_SUMMARY.md | CLI审核总结 (2026-04-24) |
| CLI_QUICK_REFERENCE.md | CLI快速参考 (2026-04-24) |

---

## 更新记录

- v4.4.0 (2026-05-18): 安全修复增强（安全清零、侧信道防护、敏感数据脱敏、线程安全）；文档一致性整理（根目录重复文档清理，统一版本号到4.4.0）
- v4.3.1 (2026-05-16): 启动时目标格式分析与不兼容格式Rich Panel警告；全文"可能"→"必然"措辞修正(resolver.py 6处)；GPU路径一致性注释(kernel_impl.py)；i18n新增targets键；冗余文件清理
- v4.3.0 (2026-05-16): 文档深度清理 — 根目录去重 6文件，归档过时 11文件，合并冗余 4组，精简 archive/startbat/ 9文件
- v4.2.3 (2026-05-15): Bech32 编解码统一重构，WIF 防泄露，竞态条件修复，BIP-173 回归测试，注释规范化
- v4.2.2 (2026-05-15): mod_inverse Binary GCD 2^256溢出修复，生产验收测试全通过
- v4.2.1 (2026-05-12): 全项目版本统一，OpenCL内核审核修复，端到端自动化系统上线，CLI/bat文件整理
- v4.2.1 (2026-05-08): GPU引擎重构完成，测试体系增强
- v4.2.1: 首次文档大清理 (100->30文件)
