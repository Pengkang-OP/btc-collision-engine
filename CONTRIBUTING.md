# 贡献指南

感谢你对本项目感兴趣！本文档提供了参与项目开发的指南和规范。

---

## 📋 目录

- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [导入规范](#导入规范)
- [测试规范](#测试规范)
- [提交规范](#提交规范)
- [代码审查](#代码审查)
- [弃用策略](#弃用策略)

---

## 开发环境设置

### 1. 克隆项目

```bash
git clone https://github.com/[你的GitHub用户名]/btc-collision-engine.git
cd btc-collision-engine
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装开发依赖

```bash
pip install pytest pytest-benchmark pytest-cov pylint mypy
```

### 4. 安装pre-commit钩子（推荐）

```bash
# 安装pre-commit
pip install pre-commit

# 安装git钩子
pre-commit install

# 手动运行检查
pre-commit run --all-files
```

**pre-commit钩子会自动检查**:
- ✅ 导入路径规范
- ✅ 代码格式化（Black）
- ✅ 代码质量（Flake8）
- ✅ 运行关键测试
- ✅ 提交消息格式
- ✅ 文件末尾换行符
- ✅ YAML/JSON格式
- ✅ 合并冲突检测

### 5. 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_import_paths.py -v
```

---

## 代码规范

### Python代码风格

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用4个空格缩进
- 行长度不超过100字符
- 使用类型提示

### 命名规范

- **模块名**: 小写，使用下划线（如 `target_resolver.py`）
- **类名**: 大驼峰（如 `TargetResolver`）
- **函数/方法名**: 小写，使用下划线（如 `resolve_address`）
- **常量**: 大写，使用下划线（如 `MAX_CACHE_SIZE`）
- **私有变量**: 前缀下划线（如 `_internal_var`）

### 文档字符串

所有公共API都必须包含文档字符串：

```python
def resolve_address(address: str) -> str:
    """解析比特币地址并返回标准格式。
    
    参数:
        address: 比特币地址字符串
        
    返回:
        标准格式的比特币地址
        
    异常:
        ValueError: 当地址格式无效时
        
    示例:
        >>> resolve_address('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
    """
    pass
```

---

## 导入规范

### ⚠️ 重要：TargetResolver导入路径

本项目已完成导入路径重构，请使用以下规范：

### ✅ 推荐的导入方式

```python
# 方式1: 通过包导入（推荐，最简洁）
from src.collision import TargetResolver

# 方式2: 通过完整路径导入（推荐，最明确）
from src.collision.targets.resolver import TargetResolver

# 方式3: 通过targets子包导入（推荐，导入多个模块时）
from src.collision.targets import TargetResolver, AddressMatcher, AddressCache
```

### ❌ 避免使用的导入方式

```python
# 已弃用！将在 v2.0 (2026-Q3) 中移除
from src.collision.target_resolver import TargetResolver
```

**原因**: 
- 旧路径已迁移到 `targets.resolver` 子包
- 使用旧路径会产生 `DeprecationWarning`
- 新路径模块组织更清晰，与其他targets模块一致

### 导入顺序

遵循PEP 8的导入顺序：

```python
# 1. 标准库
import os
import sys
from typing import List, Optional

# 2. 第三方库
import pytest
from coincurve import PrivateKey

# 3. 本地应用库
from src.collision import TargetResolver
from src.core.secp256k1 import Secp256k1
from src.utils.logger import get_configured_logger
```

### 检查导入路径

提交前运行检查脚本：

```bash
python scripts/check_import_paths.py
```

---

## 测试规范

### 测试文件命名

- 测试文件以 `test_` 开头
- 测试类以 `Test` 开头
- 测试函数以 `test_` 开头

### 测试示例

```python
import pytest
from src.collision import TargetResolver


class TestTargetResolver:
    """TargetResolver测试类"""
    
    def test_valid_address_resolution(self):
        """测试有效地址解析"""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        assert result is not None
    
    def test_invalid_address_handling(self):
        """测试无效地址处理"""
        resolver = TargetResolver(enable_cache=False)
        result = resolver.resolve('invalid_address')
        assert result is None
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_import_paths.py -v

# 运行并生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html

# 运行性能测试
python -m pytest tests/test_bech32_p2sh_performance.py --benchmark-only -v
```

### 测试覆盖要求

- 新功能必须包含单元测试
- 目标覆盖率: 80%+
- 所有边界条件都应测试
- 异常处理必须测试

---

## 提交规范

### 提交消息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### 类型 (type)

- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 添加或修改测试
- `chore`: 构建过程或辅助工具变动

### 示例

```bash
# 新功能
git commit -m "feat(targets): 添加P2WSH地址转换支持"

# 修复bug
git commit -m "fix(resolver): 修复Bech32地址大小写验证问题"

# 文档更新
git commit -m "docs: 更新导入路径使用指南"

# 代码重构
git commit -m "refactor(collision): 统一TargetResolver导入路径"

# 性能优化
git commit -m "perf(cache): 优化LRU缓存淘汰策略"

# 测试
git commit -m "test(import): 添加导入路径专项测试"
```

---

## 代码审查

### 提交前检查清单

- [ ] 运行所有测试并通过
- [ ] 检查代码风格（pylint）
- [ ] 检查导入路径规范
- [ ] 更新相关文档
- [ ] 添加必要的测试
- [ ] 提交消息格式正确

### 检查命令

```bash
# 运行测试
python -m pytest tests/ -v

# 检查代码风格
pylint src/collision/

# 检查导入路径
python scripts/check_import_paths.py

# 类型检查（如适用）
mypy src/collision/
```

### 审查重点

代码审查时将重点检查：

1. **功能正确性**: 代码是否按预期工作
2. **测试覆盖**: 是否有充分的测试
3. **代码规范**: 是否遵循编码规范
4. **性能影响**: 是否有性能退化
5. **向后兼容**: 是否破坏现有功能
6. **文档完整性**: 是否更新相关文档
7. **导入路径**: 是否使用正确的导入路径

---

## 弃用策略

### 弃用流程

当需要弃用某个API或模块时，遵循以下流程：

1. **标记弃用**: 添加 `DeprecationWarning`
2. **更新文档**: 在文档字符串中标明弃用信息
3. **提供迁移指南**: 清晰说明如何迁移到新API
4. **设定移除时间**: 明确标注将在哪个版本移除
5. **保持兼容**: 在移除前保持向后兼容

### 弃用示例

```python
"""旧模块 - 向后兼容

⚠️  弃用警告: 此模块已迁移到新位置。

📅 移除计划:
    - 此模块将在 v2.0 版本中移除（计划时间: 2026-Q3）
    - 建议所有用户尽快迁移到新路径

✅ 新用法（推荐）:
    from src.collision.targets.resolver import TargetResolver

❌ 旧用法（已弃用）:
    from src.collision.target_resolver import TargetResolver
"""
import warnings

warnings.warn(
    "此模块已迁移，请使用新路径",
    DeprecationWarning,
    stacklevel=2
)
```

### 当前弃用项

| 弃用项 | 替代方案 | 移除版本 | 移除时间 |
|--------|----------|----------|----------|
| `src.collision.target_resolver` | `src.collision.targets.resolver` | v2.0 | 2026-Q3 |

---

## 开发工作流

### 1. 创建功能分支

```bash
git checkout main
git pull
git checkout -b feature/your-feature-name
```

### 2. 开发和测试

```bash
# 编写代码
# 运行测试
python -m pytest tests/ -v

# 检查代码质量
pylint src/
```

### 3. 提交更改

```bash
git add .
git commit -m "feat(scope): description"
```

### 4. 推送并创建Pull Request

```bash
git push origin feature/your-feature-name
```

然后在GitHub上创建Pull Request。

---

## 常见问题

### Q: 为什么导入路径改变了？

A: 为了更好地组织模块结构，TargetResolver已迁移到 `targets` 子包中，与其他地址管理模块（matcher, cache, validator等）保持一致。

### Q: 旧导入路径还能用吗？

A: 可以，但会产生 `DeprecationWarning`。旧路径将在 v2.0 (2026-Q3) 中移除，建议尽快迁移。

### Q: 如何迁移？

A: 只需更改导入语句：

```python
# 旧代码
from src.collision.target_resolver import TargetResolver

# 新代码
from src.collision import TargetResolver
# 或
from src.collision.targets.resolver import TargetResolver
```

### Q: 测试失败怎么办？

A: 
1. 确保安装了所有依赖
2. 检查Python版本（需要3.7+）
3. 查看详细错误信息
4. 查看项目Issues是否有类似问题

---

## 联系方式

- **Issues**: [GitHub Issues](https://github.com/[你的GitHub用户名]/btc-collision-engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/[你的GitHub用户名]/btc-collision-engine/discussions)
- **Email**: [你的邮箱@example.com]

---

## 相关文档

- [README](../README.md) - 项目概述
- [架构文档](../docs/architecture.md) - 系统架构
- [API参考](../docs/api-reference.md) - API文档
- [导入路径优化报告](../docs/import-path-optimization-report.md) - 导入重构详情
- [性能优化指南](../docs/performance-optimization.md) - 性能优化

---

感谢你的贡献！🎉
