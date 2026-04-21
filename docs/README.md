# 比特币私钥碰撞工具 - 文档中心

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **面向**: 所有用户



## 目录

- [快速入口](#快速入口)
- [文档导航](#文档导航)
  - [📖 入门指南 (3个)](#-入门指南-3个)
  - [🏗️ 架构设计 (2个)](#-架构设计-2个)
  - [💻 API和界面 (2个)](#-api和界面-2个)
  - [🔒 安全和性能 (3个)](#-安全和性能-3个)
  - [🔧 运维和监控 (3个)](#-运维和监控-3个)
  - [📦 功能特性 (4个)](#-功能特性-4个)
  - [📦 归档文档](#-归档文档)
- [系统概览](#系统概览)
- [核心特性](#核心特性)
- [代码质量](#代码质量)
- [测试状态](#测试状态)
- [文件结构](#文件结构)
## 快速入口

- 🚀 [快速开始指南](getting-started.md) - 5分钟上手
- 📊 [项目状态总览](project-status.md) - 当前状态
- 🔍 [综合审计报告](comprehensive-audit-report.md) - 15维度全面审计(2026-04-20) ⭐
- 📦 [归档文档](archive/README.md) - 历史过程文档

---

## 文档导航

### 📖 入门指南 (3个)
- [getting-started.md](getting-started.md) - 快速开始与部署指南 ⭐
- [project-status.md](project-status.md) - 项目状态总览 ⭐
- [requirements.md](requirements.md) - 需求规格和功能规划

### 🏗️ 架构设计 (2个)
- [architecture.md](architecture.md) - 系统架构设计（含代码审核和算法）⭐
- [workflow_diagrams.md](workflow_diagrams.md) - 工作流程图

### 💻 API和界面 (2个)
- [api-reference.md](api-reference.md) - 完整API文档 ⭐
- [user-interface.md](user-interface.md) - GUI使用指南

### 🔒 安全和性能 (3个)
- [security-guidelines.md](security-guidelines.md) - 安全最佳实践（含审计发现） ⭐
- [secure-key-management.md](secure-key-management.md) - 私钥安全管理指南
- [performance-optimization.md](performance-optimization.md) - 性能调优指南

### 🔧 运维和监控 (3个)
- [troubleshooting.md](troubleshooting.md) - 故障排除指南
- [logging-guide.md](logging-guide.md) - 日志配置指南（含数据日志集成、监控指南）
- [monitoring-system-guide.md](monitoring-system-guide.md) - 监控系统指南

### 📦 功能特性 (4个)
- [checkpoint-resume-feature.md](checkpoint-resume-feature.md) - 断点续传功能
- [checkpoint-quick-guide.md](checkpoint-quick-guide.md) - 断点续传快速指南
- [address-import-feature.md](address-import-feature.md) - 地址导入功能
- [quick-reference-private-key-security.md](quick-reference-private-key-security.md) - 私钥安全快速参考

### 📦 归档文档
历史过程文档已归档到 [archive](archive/README.md) 目录，包括：
- 异常处理系列（4个文档）
- SecureKeyManager系列（4个文档）
- 代码审查系列（4个文档）
- Git提交记录（2个文档）
- 测试和修复报告（10个文档）

共24个归档文档，详见 [archive/README.md](archive/README.md)

---

**文档总数**: 18个核心文档 + 24个归档文档  
**核心文档**: 8个（⭐标记）  
**最后更新**: 2026-04-20

## 系统概览

```python
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI/GUI    │────▶│   Engine    │────▶│   Crypto    │
│   界面层     │     │   碰撞引擎   │     │   核心算法   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴────────────┐
                    ▼                   ▼
              ┌─────────┐     ┌─────────┐
              │  Stats  │     │Checkpoint│
              │  统计   │     │  断点   │
              └─────────┘     └─────────┘
                           │
                    ┌──────┴────────────┐
                    ▼                   ▼
              ┌─────────┐     ┌─────────┐
              │ Config  │     │Monitoring│
              │  配置   │     │  监控   │
              └─────────┘     └─────────┘
```

## 核心特性

- ✅ 三种碰撞模式：随机、范围扫描、暴力穷举
- ✅ 多格式目标解析：地址、WIF、公钥
- ✅ 断点续传：JSON格式持久化
- ✅ 去重过滤：滑动窗口+指纹
- ✅ 多后端加密：PurePython/OpenSSL/coincurve/ecdsa
- ✅ 实时统计：速度、进度、ETA
- ✅ 双界面：CLI命令行 + GUI图形界面
- ✅ 配置管理：统一的配置系统
- ✅ 监控系统：实时监控碰撞过程
- ✅ 数据日志：自动记录性能指标和引擎状态
- ✅ 294+单元测试（99.7%+通过率）

## 代码质量

| 维度 | 评分 | 审计得分 |
|------|------|----------|
| 代码结构 | ★★★★★ | 9.5/10 |
| 类型安全 | ★★★★★ | 9.8/10 |
| 文档质量 | ★★★★☆ | 8.8/10 |
| 线程安全 | ★★★★★ | 9.7/10 |
| 安全设计 | ★★★★★ | 9.7/10 |
| 测试覆盖 | ★★★★★ | 9.7/10 |
| 算法正确性 | ★★★★★ | 9.8/10 |
| 性能优化 | ★★★★★ | 9.0/10 |

**综合评分: 9.2/10 ⭐⭐⭐⭐⭐** (详见[综合审计报告](comprehensive-audit-report.md))

> 📦 **注意**: 历史过程文档（异常处理、SecureKeyManager、代码审查等系列）已归档到 [archive](archive/README.md) 目录。

## 测试状态

```python
✅ 400+ 单元测试 - 97%+通过率
✅ 48 secp256k1扩展测试 - 100%通过
✅ 16 crypto_backend测试 - 100%通过
✅ 53 gpu_memory_utils测试 - 100%通过
✅ 性能基准测试 - 100%通过
✅ 安全测试 - 100%通过
```

**测试通过率**: ✅ **97%+** (400+用例)

## 文件结构

```python
f:/BTC/
├── docs/                          # 文档目录 (18个核心文档 + 24个归档文档)
│   ├── README.md                  # 文档索引（本文档）
│   ├── getting-started.md         # 快速开始与部署指南 ⭐
│   ├── project-status.md          # 项目状态总览 ⭐
│   ├── requirements.md            # 需求规格
│   ├── architecture.md            # 架构文档（含代码审核和算法）⭐
│   ├── workflow_diagrams.md       # 工作流程图
│   ├── api-reference.md           # API参考 ⭐
│   ├── user-interface.md          # GUI使用指南
│   ├── security-guidelines.md     # 安全指南（含审计发现）⭐
│   ├── secure-key-management.md   # 私钥安全管理指南
│   ├── performance-optimization.md # 性能优化
│   ├── troubleshooting.md         # 故障排除
│   ├── logging-guide.md           # 日志指南（含数据日志集成、监控指南）
│   ├── monitoring-system-guide.md # 监控系统指南
│   ├── checkpoint-resume-feature.md   # 断点续传功能
│   ├── checkpoint-quick-guide.md      # 断点续传快速指南
│   ├── address-import-feature.md      # 地址导入功能
│   ├── quick-reference-private-key-security.md # 私钥安全快速参考
│   ├── comprehensive-audit-report.md  # 15维度全面技术审计 ⭐
│   └── archive/                     # 归档文档目录（24个历史过程文档）
│       └── README.md                # 归档文档索引
├── src/                           # 源代码
│   ├── core/                      # 核心算法
│   ├── collision/                 # 碰撞引擎
│   ├── cli/                       # 命令行工具
│   ├── config/                    # 配置管理
│   ├── monitoring/                # 监控系统
│   └── utils/                     # 工具类
├── tests/                         # 测试套件
├── valid_addresses.txt            # 目标地址文件(38个)
├── run_real_collision_test.py     # 真实地址测试脚本
├── key_collision_cli.py           # CLI工具
├── key_collision_gui.py           # GUI工具
└── requirements.txt               # 依赖清单
```

---

*文档生成时间: 2026-04-20*  
*最近审计: 2026-04-20 (全面技术审计通过 9.2/10)*
