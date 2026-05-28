# BTC碰撞引擎 v2.2.0 完整文档索引

> 本文档提供BTC碰撞引擎项目的完整文档导航，帮助您快速找到所需信息。
>
> **版本**: v2.2.0 | **最后更新**: 2026-04-21
>
> [ANNOUNCE] **v2.2.0重大更新**: 新增8个性能优化模块，综合性能提升30-50%，GPU性能达200k+ keys/s

---

## [BOOKS] 文档分类导航

### [QUICK] 1. 快速开始（新用户必读）

| 文档 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| 项目概述 | [README.md](../README.md) | 功能特性、快速开始、安装指南 | [STAR][STAR][STAR] |
| 快速使用指南 | [USAGE_GUIDE_v2.2.0.md](USAGE_GUIDE_v2.2.0.md) | v2.2.0 API使用和配置示例 | [STAR][STAR][STAR] |
| 发布说明 | [RELEASE_NOTES_v2.2.0.md](../RELEASE_NOTES_v2.2.0.md) | v2.2.0新功能和变更 | [STAR][STAR] |
| 变更日志 | [CHANGELOG.md](../CHANGELOG.md) | 完整版本历史记录 | [STAR][STAR] |

**快速开始路径**:

1. 阅读 [README.md](../README.md) 了解项目
2. 参考 [USAGE_GUIDE_v2.2.0.md](USAGE_GUIDE_v2.2.0.md) 快速上手
3. 查看 [RELEASE_NOTES_v2.2.0.md](../RELEASE_NOTES_v2.2.0.md) 了解最新功能

---

### [BOLT] 2. 性能优化（v2.2.0核心）

#### 2.1 实施报告

| 文档 | 路径 | 内容 | 状态 |
|------|------|------|------|
| 最终实施报告 | [v2.2.0-final-implementation-report.md](v2.2.0-final-implementation-report.md) | 5步执行计划完成总结 | [OK_CHECK] |
| 实施报告 | [optimization-implementation-report.md](optimization-implementation-report.md) | 6阶段优化方案详情 | [OK_CHECK] |
| 实施总结 | [optimization-implementation-summary.md](optimization-implementation-summary.md) | 2000+行代码总结 | [OK_CHECK] |
| 进度报告 | [optimization-progress-report.md](optimization-progress-report.md) | 阶段一、二完成状态 | [OK_CHECK] |

#### 2.2 性能验证

| 文档 | 路径 | 关键数据 |
|------|------|---------|
| 性能验证报告 | [performance-verification-report.md](performance-verification-report.md) | gmpy2 14.55x, 预计算表1.46x |
| 快速参考 | [optimization-quick-reference.md](optimization-quick-reference.md) | 配置调优、故障排查 |

#### 2.3 核心性能数据（v2.2.0实测）

| 优化模块 | 性能提升 | 测试条件 |
|---------|---------|---------|
| gmpy2模逆元 | **+1455%** (14.55x) | 256位大整数 |
| 预计算点表 | **+46%** (1.46x) | window_size=8 |
| SIMD哈希 | **+200%** | AES-NI启用 |
| 地址生成 | **+45%** | 59→86 addr/s |
| 内存分配 | **-60%延迟** | 对象池复用 |
| GPU内存 | **-60%开销** | 缓冲区复用 |

> [WARN] **注意**: `optimization-implementation-report.md` 中的部分数据是安装依赖前的旧数据，请以 `performance-verification-report.md` 为准。

---

### [GAME] 3. GPU加速

#### 3.1 GPU集成测试

| 文档 | 路径 | 内容 |
|------|------|------|
| 集成测试报告 | [gpu-integration-test-report-step7.md](gpu-integration-test-report-step7.md) | 步骤7测试（80%完成） |
| 代码审查 | [gpu-integration-test-code-review.md](gpu-integration-test-code-review.md) | GPU代码质量审查 |

#### 3.2 GPU监控模块

| 文档 | 路径 | 问题级别 |
|------|------|---------|
| 监控实施报告 | [gpu-monitoring-implementation-report.md](gpu-monitoring-implementation-report.md) | v2.2.1新功能 |
| P0修复报告 | [gpu-monitor-p0-fix-report.md](gpu-monitor-p0-fix-report.md) | [RED] 资源泄漏修复 |
| P1优化报告 | [gpu-monitor-p1-optimization-report.md](gpu-monitor-p1-optimization-report.md) | [YELLOW] 数据准确性优化 |

#### 3.3 GPU性能数据（Intel Arc A770实测）

| 指标 | 数值 | 状态 |
|------|------|------|
| 平均吞吐量 | **203,434 keys/s** | [OK_CHECK] |
| 峰值吞吐量 | **240,031 keys/s** | [OK_CHECK] |
| 平均执行时间 | 49.5 ms | [OK_CHECK] |
| 错误率 | 0.00% | [OK_CHECK] |
| 显存使用/批次 | 0.42 MB | [OK_CHECK] |

---

### [DESKTOP] 4. GUI/CLI集成

| 文档 | 路径 | 内容 |
|------|------|------|
| GUI/CLI集成报告 | [gui-cli-integration-report.md](gui-cli-integration-report.md) | v2.2.0优化参数集成 |

**新增CLI参数**:

- `--no-optimize`: 禁用性能优化
- `--window-size N`: 预计算表窗口大小(4-8)
- `--no-simd`: 禁用SIMD哈希
- `--no-memory-pool`: 禁用内存池

---

### [BUILD] 5. 架构与设计

| 文档 | 路径 | 说明 |
|------|------|------|
| 系统架构 | [architecture.md](architecture.md) | 17个Mermaid图表 |
| 工作流程 | [workflow_diagrams.md](workflow_diagrams.md) | 19个Mermaid图表 |
| API参考 | [api-reference.md](api-reference.md) | 2949行完整API |
| 需求规格 | [requirements.md](requirements.md) | 功能需求文档 |

---

### [LOCK] 6. 安全特性

| 文档 | 路径 | 说明 |
|------|------|------|
| 安全指南 | [security-guidelines.md](security-guidelines.md) | 安全最佳实践 |
| 密钥管理 | [secure-key-management.md](secure-key-management.md) | SecureKeyManager使用 |
| 私钥安全速查 | [quick-reference-private-key-security.md](quick-reference-private-key-security.md) | 快速参考 |

---

### [CHART] 7. 监控系统

| 文档 | 路径 | 说明 |
|------|------|------|
| 监控系统指南 | [monitoring-system-guide.md](monitoring-system-guide.md) | 性能监控使用 |
| 日志系统 | [logging-guide.md](logging-guide.md) | 日志配置和使用 |
| 日志标准 | [logging-standards.md](logging-standards.md) | 日志规范 |

---

### [CONFIG] 8. 配置与部署

| 文档 | 路径 | 说明 |
|------|------|------|
| 配置示例 | [config-usage-examples.md](config-usage-examples.md) | JSON配置详解 |
| 归档策略 | [document-archive-strategy.md](document-archive-strategy.md) | 文档管理规范 |

---

### [ART] 9. 界面使用

| 文档 | 路径 | 说明 |
|------|------|------|
| GUI使用指南 | [user-interface.md](user-interface.md) | 图形界面操作 |

---

### [WRENCH] 10. 故障排除

| 文档 | 路径 | 说明 |
|------|------|------|
| 常见问题 | [troubleshooting.md](troubleshooting.md) | 问题解决方案 |

---

## [TARGET] 按使用场景导航

### 新用户入门

1. [README.md](../README.md) - 了解项目
2. [USAGE_GUIDE_v2.2.0.md](USAGE_GUIDE_v2.2.0.md) - 快速上手
3. [user-interface.md](user-interface.md) - GUI使用

### 性能调优

1. [optimization-quick-reference.md](optimization-quick-reference.md) - 快速参考
2. [performance-verification-report.md](performance-verification-report.md) - 性能数据
3. [gpu-integration-test-report-step7.md](gpu-integration-test-report-step7.md) - GPU性能

### GPU加速

1. [gpu-monitoring-implementation-report.md](gpu-monitoring-implementation-report.md) - 监控模块
2. [gpu-integration-test-report-step7.md](gpu-integration-test-report-step7.md) - 集成测试
3. [gpu-monitor-p0-fix-report.md](gpu-monitor-p0-fix-report.md) - P0修复

### 开发贡献

1. [architecture.md](architecture.md) - 系统架构
2. [api-reference.md](api-reference.md) - API文档
3. [CONTRIBUTING.md](../CONTRIBUTING.md) - 贡献指南

### 安全审计

1. [security-guidelines.md](security-guidelines.md) - 安全指南
2. [secure-key-management.md](secure-key-management.md) - 密钥管理
3. [comprehensive-audit-report.md](comprehensive-audit-report.md) - 审计报告

---

## [PACKAGE] Archive文档归档

`archive/` 目录包含历史开发记录，按主题分类：

- **安全相关** (8个文档) - SecureKeyManager优化和审查
- **代码质量** (6个文档) - 代码审计报告
- **异常处理** (4个文档) - 异常处理优化
- **线程安全** (2个文档) - 并发修复
- **测试相关** (4个文档) - 测试验证报告
- **性能优化** (4个文档) - CI优化执行
- **其他** (15个文档) - 重构计划等

---

## [CHART] 文档统计（v2.2.0）

| 类别 | 文档数量 | 总大小 | 说明 |
|------|---------|--------|------|
| 核心文档 | ~40 | ~600KB | v2.2.0更新后 |
| Archive文档 | 43 | ~500KB | 历史开发记录 |
| **总计** | **~83** | **~1.1MB** | - |

**v2.2.0新增文档**:

- 8个性能优化相关文档
- 5个GPU监控相关文档
- 1个GUI/CLI集成文档
- 1个快速使用指南

---

## [WARN] 已知文档问题

### [RED] 需要修复

1. **版本号不一致**: DOCUMENT_INDEX.md 仍标记为 v1.2.0（应为 v2.2.0）
2. **性能数据过时**: `optimization-implementation-report.md` 包含旧数据
3. **文档缺失**: 8个v2.2.0新文档未添加到旧索引

### [YELLOW] 建议改进

1. 添加文档创建时间戳（精确到小时）
2. 统一性能数据格式（统一使用百分比或倍数）
3. GPU性能数据应同步到README.md

---

## [REFRESH] 文档更新记录

| 日期 | 更新内容 | 版本 | 负责人 |
|------|---------|------|--------|
| 2026-04-21 | 创建v2.2.0完整索引，新增14个文档 | v2.2.0 | AI Assistant |
| 2026-04-21 | 文档体系重构，清理冗余文档 | v1.2.0 | 开发团队 |
| 2026-04-20 | 更新架构和API文档 | v1.1.x | 开发团队 |

---

## [TIP] 使用建议

1. **首次使用**: 从"新用户入门"路径开始
2. **性能优化**: 优先查看 `optimization-quick-reference.md`
3. **GPU加速**: 阅读GPU监控系列文档了解最新进展
4. **遇到问题**: 查看 `troubleshooting.md`
5. **性能数据**: 以 `performance-verification-report.md` 为准
6. **历史问题**: 在 `archive/` 中查找相关报告

---

## [MEMO] 文档维护说明

- **主文档**: 保持最新，反映当前状态（v2.2.0）
- **Archive文档**: 历史记录，不建议修改
- **新增文档**: 根据功能模块添加到相应分类
- **版本同步**: 更新文档时需同步版本号、性能数据、测试结果

---

**文档索引版本**: v2.2.0  
**最后更新**: 2026-04-21  
**维护者**: BTC碰撞引擎开发团队
