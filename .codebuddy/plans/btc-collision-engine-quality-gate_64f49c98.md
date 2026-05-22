---
name: btc-collision-engine-quality-gate
overview: 对项目执行全面的代码质量门禁检查（9大项），自动修复发现的问题，并生成完整的 Markdown 质量报告。检查范围覆盖整个项目（src/, tests/, scripts/, benchmarks/ 等所有目录）。
todos:
  - id: format-and-lint
    content: 使用 ruff/black 格式化代码并自动修复代码风格问题（E203, E501, F401, F402, F841等）
    status: completed
  - id: security-scan
    content: 使用 Bandit 扫描安全漏洞，修复 HIGH/MEDIUM 级别问题，审查 LOW 级别问题
    status: completed
    dependencies:
      - format-and-lint
  - id: type-check
    content: 使用 mypy 检查类型错误，优先修复 P0 级别问题（未定义变量、跨平台兼容性）
    status: completed
    dependencies:
      - security-scan
  - id: gpu-and-test
    content: 执行 GPU 源码专项静态检查和核心功能测试（pytest smoke/unit/gpu）
    status: completed
    dependencies:
      - type-check
  - id: config-and-docs
    content: 验证项目配置文件和文档完整性，检查 config*.json 和 docs/ 目录
    status: completed
    dependencies:
      - gpu-and-test
  - id: report-and-gate
    content: 生成代码质量报告和门禁决策，汇总所有检查结果到 code_quality_report.md
    status: completed
    dependencies:
      - config-and-docs
---

## 产品概述

对 btc-collision-engine 项目执行全面的代码质量门禁检查，自动修复发现的问题，并生成完整的代码质量报告。

## 核心功能

1. **代码质量检查** - 使用 ruff/pylint 检查代码风格和质量问题
2. **导入路径有效性验证** - 验证所有模块导入路径是否正确
3. **核心功能关键测试执行** - 使用 pytest 执行核心功能测试
4. **项目配置文件验证** - 验证 config*.json 等配置文件的格式和 schema 合规性
5. **代码格式化与规范检查** - 使用 ruff format/black 格式化代码
6. **文档完整性与规范性检查** - 检查 docs/ 目录和根目录文档的完整性
7. **使用 Bandit 执行安全漏洞扫描** - 扫描安全漏洞并自动修复
8. **使用 mypy 执行严格类型检查** - 检查类型错误并自动修复
9. **GPU 源码专项静态检查** - 检查 src/gpu/ 目录的 Python 代码和 OpenCL 内核文件
10. **CI 门禁最终阻断与状态汇总** - 汇总所有检查结果，生成报告并决定是否阻断

## 技术栈选择

- **代码格式化**: ruff format + black (pyproject.toml 已配置)
- **代码质量检查**: ruff check + pylint
- **安全扫描**: bandit (pyproject.toml 已配置，exclude_dirs=["tests", "docs", "benchmarks"])
- **类型检查**: mypy (pyproject.toml 已配置，exclude=["tests/", "benchmarks/", "tools/", "scripts/"])
- **测试执行**: pytest (pyproject.toml 已配置，testpaths=["tests"])
- **文档检查**: docstr-coverage + pydocstyle
- **配置文件验证**: jsonschema (已在依赖中)
- **GPU 专项检查**: 自定义 OpenCL 内核检查脚本

## 实现方法

### 整体策略

按照依赖关系和优先级分阶段执行检查，先修复会导致后续检查失败的问题，再逐步执行其他检查。

### 阶段一：代码格式化和基础修复

1. 使用 `ruff format --check` 检查格式化问题
2. 使用 `ruff format --diff` 预览格式化变更
3. 使用 `ruff check --fix` 自动修复代码风格问题
4. 使用 `black --check` 检查剩余格式化问题

### 阶段二：导入路径验证

1. 使用 `pylint --errors-only` 检查导入错误
2. 使用 Python 编译检查验证关键模块导入
3. 修复未使用的导入 (F401)、未定义的名称 (F821) 等问题

### 阶段三：安全漏洞扫描和修复

1. 运行 `bandit -r src/ -f json -o bandit_report_new.json`
2. 分析 Bandit 报告，优先修复 HIGH/MEDIUM 级别问题
3. 对 LOW 级别问题进行审查，添加 `#nosec` 注释（如适用）
4. 修复 B101 (assert 语句)、B404 (subprocess)、B105 (硬编码密码) 等问题

### 阶段四：严格类型检查和修复

1. 运行 `mypy src/` 获取完整类型错误列表
2. 优先修复 P0 级别问题：

- 未定义变量 `recent_metrics`/`avg_execution_time` (src/gpu/performance_optimizer.py)
- 未定义名称 `pk_bytes` (src/collision/multiprocess_engine.py:249)

3. 修复 P1 级别问题：

- SIGALRM 跨平台不兼容 (src/collision/base_engine.py, src/utils/timeout.py)
- None 检查缺失 (src/gpu/performance_optimizer.py)

4. 逐步修复其他类型错误

### 阶段五：GPU 源码专项静态检查

1. 检查 `src/gpu/` 目录下的 Python 代码
2. 验证 OpenCL 内核文件 (.cl) 的正确性
3. 检查 GPU 相关配置和依赖

### 阶段六：核心功能测试执行

1. 运行 `pytest tests/ -v --tb=short -m "smoke or unit or gpu"` 执行核心测试
2. 重点关注 smoke, unit, gpu 标记的测试
3. 修复测试失败的问题

### 阶段七：配置文件和文档验证

1. 验证 `config*.json` 文件格式和 schema 合规性
2. 检查 `docs/` 目录文档完整性
3. 验证 README.md, CHANGELOG.md 等根目录文档

### 阶段八：CI 门禁和报告生成

1. 汇总所有检查结果
2. 生成完整的 Markdown 报告 (code_quality_report.md)
3. 生成 JSON 格式的门禁结果数据 (quality_gate_results.json)
4. 根据门禁规则决定是否阻断（如有 P0/P1 问题未修复）

## 实现细节

### 性能考虑

- 使用 `ruff` 替代 `flake8` 以提高检查速度
- 并行运行独立的检查工具（bandit, mypy, pylint）
- 限制检查范围，排除已标记的目录

### 向后兼容性

- 修复类型错误时保持 API 兼容性
- 添加平台条件判断时不破坏现有功能
- 安全修复不影响核心业务逻辑

### 关键文件修改

1. **src/gpu/performance_optimizer.py**: 修复未定义变量 `recent_metrics`, `avg_execution_time`，添加完整类型注解
2. **src/collision/multiprocess_engine.py**: 修复未定义名称 `pk_bytes` (line 249)
3. **src/collision/base_engine.py**: 添加 `SIGALRM` 跨平台兼容处理
4. **src/utils/timeout.py**: 添加 `SIGALRM`/`setitimer` 跨平台兼容处理
5. **src/monitoring/**: 添加 `import time` 修复 F821 错误
6. **src/utils/init.py**: 清理未使用的导入 (F401)

## 架构设计

### 系统架构

```
代码质量门禁执行流程:
1. 代码格式化 (ruff format, black)
2. 代码质量检查 (ruff check, pylint)
3. 导入路径验证 (pylint, Python导入测试)
4. 安全漏洞扫描 (bandit)
5. 类型检查 (mypy)
6. GPU专项检查 (自定义脚本)
7. 核心测试执行 (pytest)
8. 配置文件验证 (jsonschema)
9. 文档完整性检查 (docstr-coverage)
10. 报告生成和门禁决策
```

### 数据流

```
源码文件 → 格式化工具 → 规范化代码
规范化代码 → 质量检查工具 → 问题列表
问题列表 → 自动修复 → 修复后的代码
修复后的代码 → 测试执行 → 测试结果
所有结果 → 报告生成器 → Markdown报告
```

## 目录结构

```
f:\Qoder\btc-collision-engine\
├── src/                                      [MODIFY] 修复类型错误、代码风格问题
│   ├── gpu/
│   │   └── performance_optimizer.py          [MODIFY] 修复未定义变量 recent_metrics, avg_execution_time
│   ├── collision/
│   │   ├── base_engine.py                    [MODIFY] 添加 SIGALRM 跨平台兼容处理
│   │   └── multiprocess_engine.py            [MODIFY] 修复未定义名称 pk_bytes
│   ├── utils/
│   │   ├── timeout.py                        [MODIFY] 添加 SIGALRM/setitimer 跨平台兼容处理
│   │   └── __init__.py                       [MODIFY] 清理未使用的导入 (F401)
│   └── monitoring/                           [MODIFY] 添加 import time 修复 F821 错误
├── tests/                                    [CHECK] 执行核心功能测试
├── scripts/                                  [CHECK] 检查脚本质量
├── benchmarks/                               [CHECK] 检查基准测试
├── docs/                                      [CHECK] 检查文档完整性
├── config.json                                [VALIDATE] 验证配置文件格式
├── config.example.json                        [VALIDATE] 验证配置文件格式
├── pyproject.toml                            [CHECK] 检查工具配置
├── bandit_report.json                        [GENERATE] 新的安全扫描报告
├── mypy_report.txt                           [GENERATE] 类型检查报告
├── pylint_report.txt                         [GENERATE] pylint检查报告
├── code_quality_report.md                    [GENERATE] 完整的代码质量报告
└── quality_gate_results.json                 [GENERATE] 门禁结果数据（JSON格式）
```

## 关键代码结构

### 1. 跨平台兼容性处理（src/utils/timeout.py）

```python
import sys

# 平台特定导入
if sys.platform != "win32":
    import signal
    HAS_SIGALRM = hasattr(signal, "SIGALRM")
else:
    HAS_SIGALRM = False
    
# 使用条件判断替代直接导入
def set_timeout(seconds: int) -> None:
    if sys.platform != "win32" and HAS_SIGALRM:
        signal.alarm(seconds)
    else:
        # Windows 兼容实现
        pass
```

### 2. GPU性能优化器类型注解（src/gpu/performance_optimizer.py）

```python
from typing import Optional, List, Dict, Any

class GPUPerformanceOptimizer:
    def __init__(self) -> None:
        self.recent_metrics: List[Dict[str, Any]] = []
        self.avg_execution_time: Optional[float] = None
        self._profile: Optional["GPUProfile"] = None
```

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 探索代码库，定位需要修复的文件和函数
- Expected outcome: 准确找到所有需要修复的位置，包括未定义变量、类型错误、导入错误等