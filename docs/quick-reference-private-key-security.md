# 私钥安全管理 - 快速参考

> **版本**: v4.2.2 | **最后更新**: 2026-05-15
> **面向**: 开发者/安全工程师

## 目录

- [🚀 快速开始](#-快速开始)

  - [最简用法（推荐）](#最简用法推荐)

- [📦 安装](#-安装)

- [🔧 常用模式](#-常用模式)

  - [1. 单次使用](#1-单次使用)

- [2. 批量处理](#2-批量处理)

  - [3. 异常安全](#3-异常安全)

  - [4. 已知私钥](#4-已知私钥)

- [✅ DO / ❌ DON'T](#-do---dont)

  - [✅ 应该做](#-应该做)

  - [❌ 不应该做](#-不应该做)

- [🔍 验证](#-验证)

- [📊 安全等级](#-安全等级)

- [📚 更多信息](#-更多信息)

- [⚠️ Python限制](#-python限制)

## 🚀 快速开始

### 最简用法（推荐）

```python
from src.core.secure_key_manager import SecureKeyManager

with SecureKeyManager() as key_mgr:
    key_mgr.generate_key()
    private_key = key_mgr.get_key()
    # 使用私钥...
# 自动清零 ✅

```python

---

## 📦 安装

```bash
# 已安装（requirements.txt中）
pip install cryptography  # ✅ 已安装
pip install pynacl        # ✅ 已安装

```python

---

## 🔧 常用模式

### 1. 单次使用

```python
with SecureKeyManager() as km:
    km.generate_key()
    use_key(km.get_key())
# 自动清零

```markdown

## 2. 批量处理

```python
for i in range(100):
    with SecureKeyManager() as km:
        km.generate_key()
        process(km.get_key())
    # 每次循环清零

```markdown

### 3. 异常安全

```python
try:
    with SecureKeyManager() as km:
        km.generate_key()
        risky_operation(km.get_key())
except:
    pass  # 仍然清零 ✅

```markdown

### 4. 已知私钥

```python
with SecureKeyManager() as km:
    km.generate_key(known_key_bytes)
    use(km.get_key())

```yaml

---

## ✅ DO / ❌ DON'T

### ✅ 应该做

- 使用上下文管理器 `with SecureKeyManager()`

- 最小化私钥存活时间

- 安装cryptography库

- 使用bytearray（不是bytes）

- 异常也要清零

### ❌ 不应该做

- 不要记录私钥到日志

- 不要创建私钥副本

- 不要传递给不可信函数

- 不要忽略清零

- 不要使用bytes类型

---

## 🔍 验证

```python
# 验证已清零
with SecureKeyManager() as km:
    km.generate_key()

assert all(b == 0 for b in km._key)  # ✅

```

---

## 📊 安全等级

| 场景 | 方案 | 安全度 |
|------|------|--------|
| 测试 | bytearray+memset | ⭐⭐⭐ |
| 个人 | SecureKeyManager | ⭐⭐⭐⭐ |
| 商业 | + cryptography | ⭐⭐⭐⭐⭐ |
| 金融 | HSM | ⭐⭐⭐⭐⭐⭐ |

---

## 📚 更多信息

- **完整指南**: `docs/secure-key-management.md`

- **使用示例**: `examples/secure_key_manager_example.py`

- **修复报告**: `docs/security-enhancement-report.md`

---

## ⚠️ Python限制

即使使用最佳方案，仍有以下限制：

1. ❌ GC可能复制对象

2. ❌ 交换文件可能包含数据

3. ❌ CPU缓存可能残留

**最高安全要求必须使用HSM硬件！**
