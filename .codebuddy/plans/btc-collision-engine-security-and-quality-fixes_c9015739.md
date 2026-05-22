---
name: btc-collision-engine-security-and-quality-fixes
overview: 分阶段修复 btc-collision-engine 项目中的安全漏洞和代码质量问题。优先处理高风险问题（弃用代码清理、内存锁定失败处理、加密后端回退路径），然后解决中风险问题（文件权限、线程安全、输入验证），最后优化低风险问题（依赖版本、日志过滤、注释规范）。
todos:
  - id: fix-h3-memory-lock
    content: "修复H3: 提升内存锁定失败日志级别为ERROR并添加配置提示"
    status: completed
  - id: fix-m1-crypto-fallback
    content: "修复M1: 确保加密后端回退路径使用恒定时间实现"
    status: completed
  - id: fix-h4-dashboard-auth
    content: "修复H4: Web仪表板生产环境强制启用API Key认证"
    status: completed
  - id: fix-h1-deprecated-warn
    content: "修复H1: KeyCollisionEngine类添加强制弃用警告"
    status: completed
  - id: fix-h2-secp256k1-docs
    content: "修复H2: 完善secp256k1.py文档明确标注教学实现限制"
    status: completed
  - id: fix-m2-windows-acl
    content: "修复M2: 改进Windows文件权限设置减少外部命令依赖"
    status: completed
    dependencies:
      - fix-h3-memory-lock
  - id: fix-m3-thread-safety
    content: "修复M3: 添加静态分析和单元测试验证线程安全性"
    status: completed
  - id: fix-m7-input-limit
    content: "修复M7: 添加输入长度限制防止ReDoS攻击"
    status: completed
  - id: fix-l1-deps-review
    content: "修复L1: 审查依赖版本约束并更新requirements文件"
    status: completed
  - id: fix-l2-log-filter
    content: "修复L2: 完善日志敏感信息过滤正则表达式"
    status: completed
  - id: fix-l3-comments
    content: "修复L3: 制定并应用代码注释语言统一规范"
    status: completed
---

## 需求描述

根据全面Debug审查诊断报告，按照高风险→中风险→低风险的优先级，制定详细的修复计划。

## 核心修复任务

1. **H3** (高风险): 内存锁定失败仅记录WARNING - 需提升为ERROR/CRITICAL并添加系统配置提示
2. **M1** (中风险): 加密后端回退路径可能使用非恒定时间实现 - 需确保使用scalar_multiply_const_time()
3. **H4** (高风险): Web仪表板未启用认证时所有端点可公开访问 - 需在生产环境强制启用认证
4. **H1** (高风险): key_collision.py中的KeyCollisionEngine类已弃用但未清理 - 需添加强制弃用警告
5. **H2** (高风险): secp256k1.py教学实现可能用于生产环境 - 需完善文档说明
6. **M2** (中风险): Windows文件权限设置依赖外部icacls命令 - 需改进为优先使用pywin32
7. **M3** (中风险): 多线程锁顺序需要验证 - 需添加静态分析和单元测试
8. **M7** (中风险): 目标地址解析未限制输入长度 - 需添加1000字符长度限制防止ReDoS
9. **L1** (低风险): 依赖版本约束可能过时 - 需定期审查并更新
10. **L2** (低风险): 日志敏感信息过滤可能不完整 - 需更新正则表达式模式
11. **L3** (低风险): 代码注释语言不一致 - 需制定并应用代码规范

## 技术栈

- 语言: Python 3.9+
- 框架: Flask (Web仪表板)
- 加密库: coincurve, cryptography, PyNaCl
- 测试: pytest
- 静态分析: flake8-threading, pylint

## 关键修复方案

### H3修复: secure_key_manager.py 第146-147行

将内存锁定失败的日志级别从WARNING提升为ERROR，并添加系统配置提示：

- Linux: 提示运行 `ulimit -l unlimited`
- Windows: 提示以管理员权限运行

### M1修复: crypto_backend.py 第219-225行, 322-327行, 384-386行

确保所有回退路径使用 `scalar_multiply_const_time()` 恒定时间实现，并记录WARNING日志。

### H4修复: dashboard.py 第684-692行

在生产环境（非debug模式）未设置API Key时记录CRITICAL级别警告，并可选拒绝启动。

### H1修复: key_collision.py 第314行

在KeyCollisionEngine类添加 `warnings.warn()` 弃用警告，引导用户使用新API。

### H2修复: secp256k1.py

在所有公共方法添加文档说明，明确标注此为教学参考实现，不应在生产环境使用。

### M2修复: checkpoint_manager.py 第175-225行

改进 `_set_windows_file_permissions()` 方法，优先使用pywin32，失败时提供明确的用户指导。

### M3修复: 多线程代码

添加 `flake8-threading` 静态分析配置，并创建单元测试模拟并发场景验证锁顺序正确性。

### M7修复: resolver.py 第104-186行

在 `detect_format()` 方法开头添加输入长度限制（最大1000字符）。

### L1修复: requirements-*.txt

审查并更新版本约束，考虑使用兼容性运算符（如 `~=`），并在CI/CD中添加依赖版本检查。

### L2修复: security_log_filter.py, sensitive_patterns.py

审查并更新正则表达式模式，确保覆盖所有格式的私钥/WIF/地址，并添加单元测试验证过滤正确性。

### L3修复: 所有Python文件

制定代码注释语言规范（建议英文，符合PEP 8），并统一现有代码的注释语言。

## 测试计划

- 每个修复完成后运行现有测试套件（760+ 测试）
- 添加针对修复的单元测试
- 手动验证安全关键修复（如内存锁定、认证）

## 回滚计划

- 每个修复独立提交，便于回滚
- 在提交消息中引用诊断报告的问题编号（如 H3, M1）
- 保留弃用警告一个版本后再移除代码