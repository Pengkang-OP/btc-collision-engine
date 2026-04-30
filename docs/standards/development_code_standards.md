# Python 代码规范

> **版本**: v3.3.1 | **更新日期**: 2026-04-28 | **适用范围**: btc-collision-engine 全体 Python 源码

---

## 1. 文件头部模板

每个 Python 源文件（`.py`）必须以如下标准头部开始：

```python
# -*- coding: utf-8 -*-
"""模块简短描述（一行，不超过80字符）

详细说明（可选）：
    - 模块用途
    - 主要类/函数
    - 依赖关系

典型用法:
    >>> from src.core.key_generator import SecureKeyGenerator
    >>> gen = SecureKeyGenerator({'batch_size': 1000})
"""
```

**规则**：

- 第一行固定为 `# -*- coding: utf-8 -*-`
- 模块级 docstring 必须存在，至少包含一行功能描述
- 脚本入口文件（如 `key_collision_cli.py`）首行改为 `#!/usr/bin/env python3`，第二行为编码声明

---

## 2. 命名约定

### 2.1 模块与包

| 类型 | 规则 | 示例 |
|------|------|------|
| 包名 | 全小写，单词间用下划线 | `src/gpu/`, `src/collision/` |
| 模块名 | 全小写，单词间用下划线 | `gpu_collision_engine.py`, `key_generator.py` |

### 2.2 类名

- 使用 **PascalCase**（大驼峰）
- 名称应清晰表达职责

```python
# 正确
class SecureKeyGenerator:
class GPUCollisionEngine:
class AsyncGPUExecutor:

# 错误
class secure_key_generator:   # 不使用下划线
class Gpu:                     # 过于简短，语义不清
```

### 2.3 函数与方法

- 使用 **snake_case**（下划线小写）
- 私有方法前缀单下划线 `_`，强内部方法前缀双下划线 `__`（谨慎使用）
- 动词开头，语义清晰

```python
# 正确
def generate_batch(self, count: int) -> list:
def _check_entropy_health(self) -> bool:
def calculate_batch_size(mem_size: int) -> int:

# 错误
def gen(self, n):              # 过于简短
def GenerateBatch(self, count): # 不使用驼峰
```

### 2.4 变量与属性

- 使用 **snake_case**
- 布尔变量建议以 `is_`、`has_`、`use_` 为前缀

```python
batch_size = 65536
is_gpu_available = True
use_uint32_workaround = False
total_generated = 0
```

### 2.5 常量

- 使用 **UPPER_SNAKE_CASE**（全大写下划线）
- 定义在模块顶层或类体内

```python
# 模块级常量
MAX_BATCH_SIZE = 1_048_576      # 1M
DEFAULT_BATCH_SIZE = 65_536
VENDOR_NVIDIA = "NVIDIA Corporation"
VENDOR_INTEL = "Intel Corporation"

# 类内常量（集中管理，提高可维护性）
class GPUConstants:
    DEFAULT_MEM_SIZE = 8 * 1024 ** 3   # 8GB
    HIGH_MEM_SIZE = 16 * 1024 ** 3     # 16GB
```

---

## 3. 格式化工具要求

项目使用 **black** 作为代码格式化器，**flake8** 进行代码风格检查。

### 3.1 配置参考（`pyproject.toml`）

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.bandit]
exclude_dirs = ["tests", "docs", "benchmarks"]
skips = ["B101"]
```

> 项目当前 `pyproject.toml` 未显式定义 `[tool.black]` 和 `[tool.flake8]`，遵循以下默认约定：

### 3.2 black 规范

| 选项 | 值 | 说明 |
|------|-----|------|
| `line-length` | 100 | 最大行宽 |
| `target-version` | py39 | 最低 Python 版本（见 pyproject.toml `requires-python = ">=3.9"`）|
| `skip-string-normalization` | false | 统一使用双引号 |

```bash
# 格式化单个文件
black src/core/key_generator.py

# 格式化整个源码目录
black src/ tests/
```

### 3.3 flake8 规范

| 规则 | 配置 | 说明 |
|------|------|------|
| `max-line-length` | 100 | 与 black 保持一致 |
| `max-complexity` | 10 | 单函数圈复杂度上限 |
| `ignore` | E203, W503 | 与 black 兼容的豁免项 |

```bash
# 检查代码风格
flake8 src/ --max-line-length=100 --max-complexity=10
```

---

## 4. 类型注解要求

**所有公开函数和方法的签名必须有完整的类型注解**，私有方法建议注解。

### 4.1 基本规则

```python
from typing import List, Dict, Optional, Tuple, Any

# 正确：参数和返回值均有注解
def generate_batch(self, count: int) -> List[bytes]:
    ...

def get_device_info(self) -> Dict[str, Any]:
    ...

def calculate_batch_size(
    mem_size: int,
    safety_factor: float = 0.8
) -> int:
    ...

# 错误：无注解
def generate_batch(self, count):
    ...
```

### 4.2 Optional 与 None

```python
# 参数可为 None 时使用 Optional
def __init__(self, config: Optional[Dict] = None) -> None:
    config = config or {}
```

### 4.3 Python 3.9+ 内置泛型

项目最低要求 Python 3.9（见 `pyproject.toml`），可使用内置泛型：

```python
# Python 3.9+ 风格（推荐）
def process(items: list[str]) -> dict[str, int]:
    ...

# 兼容旧风格（from typing import ... 亦可接受）
from typing import List, Dict
def process(items: List[str]) -> Dict[str, int]:
    ...
```

---

## 5. 注释规范

### 5.1 语言要求

- **注释使用中文为主**（项目面向中文开发团队）
- 关键算法、协议实现部分补充英文术语
- 代码中不得存在无意义注释（如 `# TODO: fix this` 悬挂超过 2 个版本）

### 5.2 行内注释

```python
# 初始化日志系统
init_logging()
logger = get_configured_logger("SecureKeyGenerator")

batch_size = config.get('batch_size', 1000)  # 每批生成数量，默认1000
self._lock = threading.Lock()                 # 线程安全锁
```

### 5.3 函数/方法 docstring

必须采用以下格式（参考 `src/core/key_generator.py`）：

```python
def _check_entropy_health(self) -> bool:
    """检查系统熵池健康状态

    防止低熵环境下生成弱密钥（P1-3修复）。
    Windows 下通过 CryptGenRandom 获取熵估计值。

    返回:
        bool: True 表示熵池充足，False 表示熵池不足需告警

    异常:
        OSError: 读取系统熵源失败时抛出
    """
```

### 5.4 类 docstring

```python
class SecureKeyGenerator:
    """
    安全私钥生成器 - 符合 Bitcoin Core 规范

    使用 CSPRNG（密码学安全伪随机数生成器）生成私钥，
    确保生成的私钥符合加密货币行业安全标准。

    属性:
        batch_size (int): 每批生成数量
        rate_limit (int): 每秒生成速率（0=无限制）
        key_manager: 私钥管理器（用于安全清零）

    示例:
        >>> config = {'batch_size': 1000, 'rate_limit': 0}
        >>> generator = SecureKeyGenerator(config)
        >>> keys = generator.generate_batch(1000)
    """
```

---

## 6. 导入排序规则

遵循 **PEP 8** 三段式导入规范，各段间空一行：

```
1. 标准库（stdlib）
2. 第三方库（third-party）
3. 项目内部模块（local）
```

```python
# ✅ 正确示例（参考 src/core/key_generator.py）
import os
import secrets
import threading
from datetime import datetime
from typing import List, Dict, Optional

import coincurve
import gmpy2
import numpy as np

from ..utils import init_logging, get_configured_logger
from .secp256k1 import Secp256k1
from .secure_key_manager import SecureKeyManager
```

**规则**：

- 每段内按字母顺序排序
- 使用 `isort` 工具自动整理（`isort --profile black src/`）
- 禁止使用 `from module import *`（明确导入所有需要的名称）
- 相对导入（`from ..utils import ...`）仅在包内使用

---

## 7. 异常处理规范

### 7.1 禁止裸 except

```python
# ❌ 禁止
try:
    result = gpu_kernel.run_batch(batch)
except:
    pass

# ❌ 禁止（except Exception 不记录日志）
try:
    result = gpu_kernel.run_batch(batch)
except Exception:
    pass

# ✅ 正确：捕获具体异常并记录日志
try:
    result = gpu_kernel.run_batch(batch)
except RuntimeError as e:
    logger.error("GPU批次执行失败: %s", e, exc_info=True)
    raise
except MemoryError as e:
    logger.critical("GPU显存不足: %s", e)
    self._handle_oom()
```

### 7.2 异常日志记录

```python
import logging
logger = logging.getLogger(__name__)

# 记录异常堆栈（exc_info=True）
logger.error("操作失败: %s", str(e), exc_info=True)

# 记录结构化上下文
logger.warning(
    "批次大小超出上限: requested=%d, max=%d，已自动截断",
    requested_size,
    MAX_BATCH_SIZE
)
```

### 7.3 自定义异常

项目异常类统一定义在 `src/collision/types.py` 或各子模块的 `exceptions.py` 中：

```python
class GPUInitializationError(RuntimeError):
    """GPU 初始化失败时抛出"""

class BatchSizeError(ValueError):
    """批次大小配置无效时抛出"""
```

### 7.4 资源清理

使用 `try/finally` 或上下文管理器确保资源释放：

```python
# ✅ 推荐使用上下文管理器
with GPUMockFactory.patch_gpu_collision_engine() as mocks:
    engine = GPUCollisionEngine(targets)

# ✅ 无上下文管理器时使用 try/finally
gpu_device = None
try:
    gpu_device = GPUDevice(config)
    gpu_device.initialize()
    # ... 业务逻辑
finally:
    if gpu_device is not None:
        gpu_device.cleanup()
```

---

## 8. 代码示例

以下示例取自项目现有代码（`src/core/key_generator.py`），展示规范的综合应用：

```python
# -*- coding: utf-8 -*-
"""安全私钥生成器 - 符合 Bitcoin Core 规范"""

import os
import secrets
import threading
from datetime import datetime
from typing import Dict, List, Optional

from ..utils import get_configured_logger, init_logging
from .secp256k1 import Secp256k1
from .secure_key_manager import SecureKeyManager

# 初始化日志系统
init_logging()
logger = get_configured_logger("SecureKeyGenerator")

# 模块级常量
DEFAULT_BATCH_SIZE: int = 1000
MIN_ENTROPY_BITS: int = 1000


class SecureKeyGenerator:
    """
    安全私钥生成器 - 符合 Bitcoin Core 规范

    使用 CSPRNG 生成私钥，确保符合加密货币行业安全标准。

    属性:
        batch_size (int): 每批生成数量
        rate_limit (int): 每秒生成速率（0=无限制）
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        初始化私钥生成器

        参数:
            config (Optional[Dict]): 配置字典
                - batch_size (int): 每批生成数量（默认 1000）
                - rate_limit (int): 每秒速率（默认 0=无限制）
        """
        config = config or {}
        self.batch_size: int = config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.rate_limit: int = config.get("rate_limit", 0)
        self.key_manager = SecureKeyManager()
        self._lock = threading.Lock()  # 线程安全锁

        logger.info(
            "SecureKeyGenerator初始化: batch_size=%d, rate_limit=%d",
            self.batch_size,
            self.rate_limit,
        )

    def generate_batch(self, count: int) -> List[bytes]:
        """批量生成安全私钥

        参数:
            count (int): 生成数量，必须大于 0

        返回:
            List[bytes]: 私钥字节列表（每个 32 字节）

        异常:
            ValueError: count <= 0 时抛出
        """
        if count <= 0:
            raise ValueError(f"生成数量必须大于0，实际值: {count}")

        keys: List[bytes] = []
        try:
            with self._lock:
                for _ in range(count):
                    key = secrets.token_bytes(32)
                    keys.append(key)
        except Exception as e:
            logger.error("批量生成私钥失败: %s", e, exc_info=True)
            raise

        logger.debug("成功生成 %d 个私钥", len(keys))
        return keys
```

---

## 9. 代码审查清单

提交代码前请检查：

- [ ] 文件头部有编码声明和模块 docstring
- [ ] 所有公开函数/方法有类型注解和 docstring
- [ ] 没有裸 `except`，异常必须记录日志
- [ ] 常量使用 `UPPER_SNAKE_CASE`，类名使用 `PascalCase`
- [ ] 导入按三段式排序（stdlib → third-party → local）
- [ ] 无注释掉的死代码（`# old_func(x)`）
- [ ] 资源（GPU显存、文件句柄）在 `finally` 或上下文管理器中释放
- [ ] 通过 `black` 格式化和 `flake8` 检查

---

*参考文件*：

- `pyproject.toml` — 构建与工具配置
- `src/core/key_generator.py` — 标准代码风格示例
- `src/collision/types.py` — 类型定义与异常类示例
- `tests/conftest.py` — 常量集中管理示例（`GPUConstants`）
