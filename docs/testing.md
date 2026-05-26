# Testing Guide

本文档介绍 BTC Collision Engine 项目的测试框架、组织结构和最佳实践。

## 1. 测试框架

本项目使用以下测试框架：

- **pytest**: 主测试框架，提供 fixture、参数化测试、标记等功能

- **unittest**: 标准库测试框架，部分测试使用 `unittest.TestCase`

- **pytest-cov**: 覆盖率报告

- **pytest-timeout**: 测试超时控制

## 2. 测试组织

测试文件位于 `tests/` 目录下，按功能模块组织：

```
tests/
├── unit/               # 单元测试
│   ├── crypto/        # 加密相关测试
│   ├── logging/       # 日志配置测试
│   ├── engine/        # 引擎相关测试
│   └── ...           # 其他模块测试
├── integration/        # 集成测试
├── acceptance/         # 验收测试
├── gpu/               # GPU 相关测试
├── benchmarks/         # 性能基准测试
└── *.py               # 其他测试文件

```

## 3. 运行测试

### 3.1 运行所有测试

```bash
# 运行所有测试（排除 GPU 和集成测试）
pytest tests/ -v --tb=short -m "not (gpu or gpu_kernel or multi_gpu or integration)"

```

### 3.2 运行特定模块的测试

```bash
# 运行加密模块测试
pytest tests/unit/crypto/ -v

# 运行日志配置测试
pytest tests/unit/logging/ -v

# 运行向导模块测试
pytest tests/test_wizard.py -v

```

### 3.3 运行特定测试类或方法

```bash
# 运行特定测试类
pytest tests/unit/crypto/test_crypto_backend_edge.py::TestCoincurveBackend -v

# 运行特定测试方法
pytest tests/unit/crypto/test_crypto_backend_edge.py::TestCoincurveBackend::test_name -v

```

### 3.4 带覆盖率的测试

```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term

```

## 4. 常见问题和解决方案

### 4.1 加密后端不可用

**问题**: 测试失败，提示加密后端不可用。

**解决方案**:

- 确保已安装系统依赖：`libsecp256k1-dev` (Linux) 或相应 Windows 库

- 测试已添加 `@unittest.skipIf` 守卫，后端不可用时会自动跳过

- 检查 `conftest.py` 中的自动跳过逻辑

### 4.2 测试间状态污染

**问题**: 测试 A 通过，但测试 B 失败时，测试 A 也失败。

**解决方案**:

- 使用 fixture 重置全局状态

- 对于日志配置测试，使用 `reset_logging_config` fixture

- 对于加密后端测试，每个测试前重置 `CryptoBackendManager` 状态

### 4.3 stdin 读取问题

**问题**: 测试尝试读取 stdin，但 CI 环境无 TTY。

**解决方案**:

- 使用 `unittest.mock.patch` 模拟 stdin 读取

- 示例：

  ```python
  with patch("sys.stdin") as mock_stdin:
      mock_stdin.isatty.return_value = False
      mock_stdin.read.return_value = "test input"
      # 测试代码

  ```

### 4.4 日志配置污染

**问题**: 测试间日志配置未隔离，导致断言失败。

**解决方案**:

- 使用 `reset_logging_config` fixture

- 每个测试前后重置 `LoggingConfig` 单例和 root logger handlers

## 5. CI 相关说明

### 5.1 CI 环境差异

CI 环境与本地开发环境存在差异：

| 维度 | 开发环境（本地） | CI 环境（GitHub Actions） |
|------|-------------------|--------------------------|
| **操作系统** | Windows 11 | Ubuntu Latest (22.04/24.04) |
| **Python 版本** | 3.12.10 | 3.12.x（GitHub 托管） |
| **系统依赖** | 可能预装 | 需要 `apt-get install` |
| **GPU 可用性** | 可能有 | 无 |
| **文件系统** | 大小写不敏感 | 大小写敏感 |
| **熵源** | 真实硬件 | 虚拟机 |

### 5.2 CI 门禁

CI 门禁检查包括：

1. **静态分析**: ruff format/check 格式问题

2. **安全扫描**: Bandit + pip-audit

3. **测试**: 单元测试和集成测试

4. **扩展测试**: 综合测试、核心引擎测试

5. **性能回归**: 基准测试

6. **文档检查**: Markdown 规范

### 5.3 调试 CI 失败

**步骤**:

1. 下载 CI 日志和 artifact

2. 分析失败测试分类（参考 `CI_PROBLEM_ANALYSIS.md`）

3. 本地复现问题

4. 修复问题并提交

## 6. 最佳实践

### 6.1 编写测试

- 使用 descriptive 的测试方法和类名

- 每个测试方法只测试一个功能点

- 使用 fixture 管理测试依赖

- 模拟外部依赖（文件、网络、环境变量等）

- 添加适当的断言消息

### 6.2 组织测试

- 按功能模块组织测试文件

- 使用测试类分组相关测试方法

- 使用 pytest 标记分类测试（unit、integration、gpu 等）

### 6.3 避免常见陷阱

- **不要**依赖测试执行顺序

- **不要**修改全局状态且不清理

- **不要**硬编码路径或环境变量

- **不要**在测试中使用真实网络连接

- **不要**忽略警告或异常处理

## 7. 参考资料

- [pytest 文档](https://docs.pytest.org/)

- [unittest 文档](https://docs.python.org/3/library/unittest.html)

- [CI_PROBLEM_ANALYSIS.md](./CI_PROBLEM_ANALYSIS.md) - CI 问题系统性分析

- [CHANGELOG.md](../CHANGELOG.md) - 项目变更日志
