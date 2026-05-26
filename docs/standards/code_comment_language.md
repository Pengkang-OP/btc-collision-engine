# 代码注释语言规范

> **版本**: v1.0.0 | **更新日期**: 2026-05-22 | **适用范围**: btc-collision-engine 全体源码

---

## 1. 规范目标

统一项目代码注释语言，提升代码可读性和团队协作效率。

## 2. 注释语言规定

| 注释类型 | 语言要求 | 说明 |
|---------|---------|------|
| 模块级 docstring | **英文** | 符合 PEP 257 规范 |
| 类 docstring | **英文** | 简要描述类职责 |
| 函数/方法 docstring | **英文** | 包含 Args、Returns、Raises 等章节 |
| 行内注释 (`#`) | **英文** | 仅当解释复杂逻辑时使用 |
| TODO/FIXME 注释 | **中文** | 便于中文开发者理解 |
| 调试/临时注释 | **中文** | 提交前须移除 |

## 3. Docstring 格式规范

使用 Google 风格 docstring：

```python
"""Brief description of the function.

Detailed description if needed.

Args:
    param1 (type): Description of param1.
    param2 (type): Description of param2.

Returns:
    return_type: Description of return value.

Raises:
    ValueError: If param1 is invalid.
"""

```

## 4. 迁移计划

| 阶段 | 范围 | 说明 |
|------|------|------|
| 第一阶段 | `src/core/` | 核心加密模块 |
| 第二阶段 | `src/collision/` | 碰撞引擎模块 |
| 第三阶段 | `src/gpu/` | GPU 加速模块 |
| 第四阶段 | `src/web/`, `src/utils/` | 其他模块 |

## 5. 示例对比

### 修改前（中文）

```python
class CryptoBackend(ABC):
    """加密后端抽象基类

    定义椭圆曲线运算的统一接口。
    """

```

### 修改后（英文）

```python
class CryptoBackend(ABC):
    """Abstract base class for cryptographic backends.

    Defines unified interface for elliptic curve operations.
    """

```

## 6. 工具支持

- 使用 `pylint` 检查 docstring 语言（可配置）

- CI/CD 中添加注释语言检查步骤

## 7. 例外情况

以下情况可保留中文注释：

1. 引用中文技术文档的链接说明

2. 特定业务术语无英文对应时（须在术语表定义）

3. 已弃用代码的注释（整个模块即将移除）

---

*本规范自 v1.0.0 起生效，旧代码逐步迁移。*
