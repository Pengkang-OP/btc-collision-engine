# Changelog

本文档记录 BTC Collision Engine 项目的所有 notable changes。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed
- 修复 `tests/test_wizard.py` 中的 API 不匹配问题（126 个失败）→ 更新测试以匹配 `src/wizard/events.py` 和 `src/wizard/interfaces.py` 的实际 API
- 为 `tests/unit/crypto/test_crypto_backend_edge.py` 中的 `TestCoincurveBackend` 和 `TestECDSABackend` 添加 `@unittest.skipIf` 守卫，在后端不可用时跳过测试
- 为 `tests/unit/logging/test_logging_config.py` 中的 `TestSafeRotatingFileHandler` 添加 `reset_logging_config` fixture，确保测试间状态隔离

### Added
- 新增 `CI_PROBLEM_ANALYSIS.md` 文档，系统分析 CI 问题（问题分类、影响分析、数据污染分析、环境差异分析、依赖版本分析）

### Changed
- 更新 `CI_PROBLEM_ANALYSIS.md` 以反映修复状态

### Docs
- 新增 `docs/testing.md` 作为测试指南（待创建）
- 更新 `CI_PROBLEM_ANALYSIS.md` 以反映修复状态

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
