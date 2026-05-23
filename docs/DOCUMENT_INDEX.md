# 项目文档索引

**版本**: v5.0.0


> BTC碰撞引擎项目文档导航


---

## 文档统计

| 目录 | 文档数量 | 说明 |
|------|----------|------|
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
- technical-docs/workflow_diagrams.md - 工作流程图 (19个图表)
- api-reference.md - API参考 (2949行)
- developer-docs/requirements.md - 需求规格

### 3. 核心功能

#### 碰撞引擎

- technical-docs/performance-optimization.md - 性能优化 (924行)
- feature-docs/checkpoint-resume-feature.md - 断点续传
- checkpoint-quick-guide.md - 断点续传快速指南
- logging-guide.md - 日志指南
- logging-standards.md - 日志标准

#### API 参考

- api-reference.md - API参考 (2949行)
- API_CHANGELOG.md - API变更日志

#### 安全特性

- security-guidelines.md - 安全指南
- secure-key-management.md - 密钥管理
- windows-memory-lock.md - 内存锁机制

#### 监控系统

- monitoring-system-guide.md - 监控指南

#### GPU加速

- gpu-engine-guide.md - GPU引擎指南
- archive/GPU_CONFIG_MANAGER_GUIDE.md - GPU配置管理 (旧版，已归档)
- intel-arc-integration-guide.md - Intel Arc集成
- intel-arc-gpu-compatibility-research.md - Intel Arc兼容性研究
- GPU_ASYNC_LOGGING_INTEGRATION_GUIDE.md - GPU异步日志
- gpu-driver-matrix.md - GPU驱动兼容矩阵

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

### 8. 开发规范 (docs/standards/)

- development_code_standards.md - 代码编写规范
- development_test_standards.md - 测试编写规范
- git_commit_standards.md - Git提交规范
- log_level_guidelines.md - 日志级别指南
- config_change_process.md - 配置变更流程

### 9. 技术专题 (docs/technical-docs/)

- cross-platform-compatibility.md - 跨平台兼容性
- gpu_best_practices.md - GPU最佳实践
- i18n-guide.md - 国际化指南
- logging-monitoring-system.md - 日志监控系统

### 10. 安全 (docs/security/)

- windows_memory_lock.md - Windows内存锁定
- threat-model.md - STRIDE威胁模型

### 11. 法律合规 (docs/legal/)

- export-control.md - 加密出口管制声明
- license-compatibility.md - 许可证兼容性报告
- third-party-attribution.md - 第三方代码归属

### 12. 环境配置 (docs/environment/)

- environment-variables.md - 环境变量配置

### 11. 用户文档 (docs/user-docs/)

- cli_export_guide.md - CLI导出指南

---

## 审计报告 (docs/audit-reports/)

| 文档 | 说明 |
|------|------|
| BAT_CLI_AUDIT_REPORT.md | BAT/CLI审计报告 |
| CLEANUP_REPORT.md | 清理报告 |
| COMPATIBILITY_AUDIT_REPORT.md | 兼容性审计报告 |
| OPENCL_KERNEL_AUDIT_REPORT.md | OpenCL内核审计报告 |
| comprehensive_audit_10dimensions_20260424.md | 十维度综合审计 |
| E2E_AUDIT_REPORT_v4.3.0.md | v4.3.0端到端审计报告 |

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
| CLI_AUDIT_SUMMARY.md | CLI审核总结 (2026-04-24) |
| CLI_QUICK_REFERENCE.md | CLI快速参考 (2026-04-24) |

---

## 更新记录

- v4.2.2 (2026-05-15): mod_inverse Binary GCD 2^256溢出修复，生产验收测试全通过
- v4.2.1 (2026-05-12): 全项目版本统一，OpenCL内核审核修复，端到端自动化系统上线，CLI/bat文件整理
- v4.2.1 (2026-05-08): GPU引擎重构完成，测试体系增强
- v4.2.1: 首次文档大清理 (100->30文件)
