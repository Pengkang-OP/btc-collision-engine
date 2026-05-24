---
name: expert-team-depth-analysis
overview: 调用多个代码专家 subagent（code-reviewer、legacy-modernizer、python-expert、code-explorer）对项目进行多维度深度分析，汇总生成完整的重构事项清单
todos:
  - id: code-quality-review
    content: 使用 [skill:code-review-and-quality] 对项目进行全面的代码质量审查，重点分析架构合理性、可维护性、代码风格一致性、命名规范，输出详细报告
    status: completed
  - id: architecture-analysis
    content: 分析项目架构，评估模块耦合度、接口抽象合理性、设计模式使用正确性，识别架构层面的重构需求
    status: completed
  - id: performance-analysis
    content: 使用 [skill:python-performance-optimization] 进行性能分析，识别瓶颈和优化机会，特别关注 GPU 加速部分和密码学操作
    status: completed
  - id: security-scan
    content: 使用 [skill:Python Security Scan] 进行安全漏洞扫描，检测硬编码敏感信息、不安全函数调用、密码学实现问题
    status: completed
  - id: maintainability-analysis
    content: 分析可维护性，识别死代码、未使用导入、代码重复、模块级可变状态等问题
    status: completed
  - id: test-coverage-analysis
    content: 使用 [skill:python-testing-patterns] 分析测试覆盖情况，识别测试缺失和质量问题
    status: completed
  - id: generate-refactor-list
    content: 汇总所有分析结果，生成优先级排序的重构事项清单，包含具体文件、问题描述、严重程度、预计工作量、重构建议
    status: completed
    dependencies:
      - code-quality-review
      - architecture-analysis
      - performance-analysis
      - security-scan
      - maintainability-analysis
      - test-coverage-analysis
---

## 用户需求

调用多个代码专家对项目进行多维度深度分析，系统性识别需要重构的事项，并生成优先级排序的重构事项清单。

## 产品概述

对 btc-collision-engine 项目（比特币私钥碰撞引擎，Python v5.0.0）进行全面的代码质量、架构、安全、性能、可维护性、测试覆盖等多维度分析，识别所有需要重构的问题，生成结构化的重构事项清单（含优先级、工作量估算、具体文件路径）。

## 核心功能

- 代码质量审查：架构合理性、可维护性、代码风格一致性、命名规范
- 架构分析：模块耦合度、接口抽象合理性、设计模式使用正确性
- 性能分析：瓶颈识别、GPU 加速优化机会、内存使用分析、算法复杂度
- 安全扫描：漏洞检测、硬编码敏感信息、不安全函数调用、密码学实现正确性
- 可维护性分析：死代码、未使用导入、代码重复、模块级可变状态
- 测试覆盖分析：测试缺失、测试质量、测试覆盖率、测试标记完善度
- 生成重构事项清单：按优先级排序，包含具体文件、问题描述、严重程度、预计工作量、重构建议

## 使用的扩展

### Skill

- **code-review-and-quality**
- 用途：进行多轴代码质量审查，识别架构、可维护性、代码风格问题
- 预期结果：生成代码质量分析报告，包含具体问题和改进建议，按严重程度排序
- **python-performance-optimization**
- 用途：分析性能瓶颈，识别优化机会，特别关注 GPU 加速部分和密码学操作
- 预期结果：生成性能分析报告，包含瓶颈位置、算法复杂度分析、优化建议
- **Python Security Scan**
- 用途：扫描安全漏洞，检测硬编码敏感信息、不安全函数调用、密码学实现问题
- 预期结果：生成安全扫描报告，包含漏洞列表、风险等级、修复建议
- **python-testing-patterns**
- 用途：分析测试覆盖情况，识别测试缺失和质量问题
- 预期结果：生成测试分析报告，包含测试覆盖率、测试质量评估、改进建议