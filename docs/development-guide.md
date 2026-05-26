# BTC 碰撞引擎开发指南

> **版本**: v4.2.2 | **更新日期**: 2026-05-15 | **适用范围**: btc-collision-engine 开发人员

---

## 1. 项目概述

BTC 碰撞引擎是一个比特币私钥碰撞研究项目，支持 CPU 和 GPU 加速。项目采用模块化架构，主要包含以下特性：

- **多种碰撞模式**：随机碰撞、范围扫描、暴力穷举

- **GPU 加速**：支持 NVIDIA、AMD、Intel 显卡（OpenCL）

- **断点续传**：自动保存进度，支持从断点恢复

- **去重过滤**：Bloom 过滤器防止重复检测

- **实时监控**：性能指标统计、进度可视化

### 1.1 技术栈概览

| 类别 | 技术 |
|------|------|
| Python 版本 | 3.9+ |
| 加密库 | coincurve, gmpy2, pycryptodome, cryptography |
| GPU 计算 | pyopencl, numpy |
| 地址解析 | cachetools, pybloom-live, bech32 |
| 测试框架 | pytest >= 9.0.0 |
| 代码质量 | black, flake8, mypy, bandit |

---

## 2. 开发环境搭建

### 2.1 环境要求

- Python >= 3.9

- Git

- OpenCL 运行时（可选，用于 GPU 支持）

### 2.2 快速安装

```bash
# 克隆项目
git clone <repository-url>
cd btc-collision-engine

# 运行安装脚本（推荐）
scripts/install/install.bat    # Windows
bash scripts/install/install.sh  # Linux/macOS

# 或手动安装
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/macOS

# 安装基础依赖
pip install -r requirements-base.txt

# 安装 GPU 依赖（可选）
pip install -r requirements-gpu.txt

# 安装开发依赖（可选）
pip install -r requirements-dev.txt

```

### 2.3 依赖说明

| 文件 | 内容 | 必需 |
|------|------|------|
| `requirements-base.txt` | 核心加密和工具库 | 是 |
| `requirements-gpu.txt` | pyopencl + nvidia-ml-py（继承 base） | 否（GPU 支持）|
| `requirements-dev.txt` | pytest + 代码质量工具 | 否（开发用）|
| `requirements.txt` | 全量依赖 | 完整安装 |

### 2.4 GPU 环境验证

```bash
# 验证 OpenCL 是否可用
python -c "import pyopencl; print([d.name for p in pyopencl.get_platforms() for d in p.get_devices()])"

# 运行健康检查
python -m src.utils.health_check --gpu

```

---

## 3. 项目结构

```bash
btc-collision-engine/
├── src/                        # 核心源码
│   ├── cli/                    # 命令行界面
│   │   ├── main.py            # CLI 主入口
│   │   ├── arg_parser.py      # 参数解析
│   │   ├── commands.py       # 命令实现
│   │   ├── engine_runner.py   # 引擎运行器
│   │   └── ...
│   ├── collision/              # 碰撞引擎
│   │   ├── key_collision_engine.py    # CPU 引擎
│   │   ├── gpu_collision_engine.py    # GPU 引擎（Shim 层）
│   │   ├── gpu/                       # GPU 引擎重构模块
│   │   │   ├── engine.py              # 引擎协调器
│   │   │   ├── facade.py              # 外观层
│   │   │   ├── core.py                # 碰撞核心
│   │   │   ├── protocols.py           # 核心协议
│   │   │   ├── vendor_strategy.py     # 厂商策略
│   │   │   └── monitoring.py         # 性能监控
│   │   ├── checkpoint_manager.py      # 断点管理
│   │   ├── deduplication_filter.py    # 去重过滤
│   │   └── ...
│   ├── core/                  # 加密核心
│   │   ├── key_generator.py          # 密钥生成
│   │   ├── secp256k1.py              # 椭圆曲线
│   │   ├── hash_utils.py             # 哈希工具
│   │   ├── address_generator.py      # 地址生成
│   │   ├── bigint_optimizer.py       # 大整数优化
│   │   ├── simd_hash.py              # SIMD 哈希
│   │   └── ...
│   ├── gpu/                   # GPU 管理
│   │   ├── kernels/                  # OpenCL 内核
│   │   ├── vendors/                   # 厂商支持
│   │   │   ├── nvidia.py
│   │   │   ├── amd.py
│   │   │   └── intel.py
│   │   ├── auto_tuner.py             # 自动调优
│   │   ├── optimization_pipeline.py  # 优化流水线
│   │   └── ...
│   ├── config/                 # 配置管理
│   ├── monitoring/             # 监控系统
│   ├── logging/                # 日志子系统
│   ├── wizard/                 # 交互式向导
│   └── utils/                  # 工具模块
├── tests/                      # 测试文件
├── docs/                       # 文档
├── benchmarks/                  # 性能基准
├── scripts/                    # 辅助脚本（分类子目录）
├── tools/                      # 工具脚本
├── config.example.json         # 配置示例
└── pyproject.toml             # 项目配置

```

---

## 4. 核心模块说明

### 4.1 碰撞引擎 (`src/collision/`)

| 模块 | 职责 |
|------|------|
| `key_collision_engine.py` | CPU 多线程碰撞引擎 |
| `gpu_collision_engine.py` | GPU 引擎 Shim 层 |
| `gpu/engine.py` | GPU 引擎协调器（Phase 6 重构）|
| `checkpoint_manager.py` | 断点保存与恢复 |
| `deduplication_filter.py` | Bloom 过滤器去重 |
| `target_resolver.py` | 目标地址解析 |

### 4.2 加密核心 (`src/core/`)

| 模块 | 职责 |
|------|------|
| `key_generator.py` | 安全私钥生成 |
| `secp256k1.py` | secp256k1 椭圆曲线运算 |
| `hash_utils.py` | SHA256/RIPEMD160 哈希 |
| `address_generator.py` | 比特币地址生成 |
| `bigint_optimizer.py` | gmpy2 大整数优化 |
| `simd_hash.py` | SIMD 哈希加速 |

### 4.3 GPU 管理 (`src/gpu/`)

| 模块 | 职责 |
|------|------|
| `device_manager.py` | GPU 设备管理 |
| `kernel.py` | OpenCL 内核执行 |
| `vendors/` | 厂商特定优化策略 |
| `auto_tuner.py` | 自动性能调优 |
| `optimization_pipeline.py` | 优化流水线 |

---

## 5. 开发工作流

### 5.1 代码编写规范

遵循项目代码规范（详见 [开发代码标准](standards/development_code_standards.md）：

```python
# -*- coding: utf-8 -*-
"""模块简短描述"""

import os
import threading
from typing import List, Optional

import coincurve

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)

MAX_BATCH_SIZE = 1_048_576

class MyClass:
    """类文档描述"""

    def __init__(self, config: Optional[dict] = None) -> None:
        config = config or {}
        self.batch_size: int = config.get("batch_size", 1000)

    def process_batch(self, data: List[bytes]) -> int:
        """处理批次数据

        参数:
            data: 输入数据列表

        返回:
            处理数量
        """
        count = 0
        try:
            with self._lock:
                for item in data:
                    self._process_item(item)
                    count += 1
        except Exception as e:
            logger.error("处理失败: %s", e, exc_info=True)
            raise
        return count

```

### 5.2 测试编写规范

遵循项目测试规范（详见 [测试标准](standards/development_test_standards.md）：

```python
# tests/test_my_module.py

import pytest
from tests.gpu_mock_factory import GPUMockFactory

class TestMyClass:
    """MyClass 单元测试"""

    def test_process_batch_returns_correct_count(self):
        """验证批次处理返回正确数量"""
        obj = MyClass({"batch_size": 10})
        data = [b"test" for _ in range(10)]
        result = obj.process_batch(data)
        assert result == 10

    def test_process_batch_raises_on_error(self):
        """验证异常时抛出"""
        obj = MyClass()
        with pytest.raises(RuntimeError):
            obj.process_batch(None)

class TestMyClassIntegration:
    """MyClass 集成测试"""

    def test_full_cycle(self, mock_gpu_chain):
        """完整生命周期测试"""
        with GPUMockFactory.patch_gpu_collision_engine() as mocks:
            # 测试代码
            pass

```

### 5.3 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_core_crypto.py -v

# 运行带 Mock 的 GPU 测试
pytest tests/test_gpu_collision_engine.py -v

# 运行特定标记的测试
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v

# 跳过 GPU 硬件测试
pytest tests/ -m "not gpu_hardware" -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html

```

### 5.4 代码质量检查

```bash
# 格式化代码
black src/ tests/

# 检查代码风格
flake8 src/ --max-line-length=100

# 类型检查
mypy src/

# 安全扫描
bandit -r src/

```

---

## 6. 功能开发指南

### 6.1 添加新碰撞模式

1. 在 `src/collision/` 创建搜索模式类

2. 实现 `BaseSearch` 接口

3. 在 `src/gpu/search_modes/` 添加 GPU 支持

4. 添加相应测试

5. 更新配置解析

```python
# src/collision/search_modes/base_search.py
from abc import ABC, abstractmethod

class BaseSearch(ABC):
    """碰撞搜索模式基类"""

    @abstractmethod
    def generate_batch(self, count: int) -> list[bytes]:
        """生成指定数量的私钥"""
        pass

    @abstractmethod
    def get_state(self) -> dict:
        """获取当前状态"""
        pass

```

### 6.2 添加新 GPU 厂商支持

1. 在 `src/gpu/vendors/` 创建厂商类

2. 继承 `BaseVendorStrategy`

3. 实现厂商特定优化

4. 在 `vendor_strategy.py` 注册

```python
# src/gpu/vendors/new_vendor.py
from .base import BaseVendorStrategy

class NewVendorStrategy(BaseVendorStrategy):
    """新厂商优化策略"""

    VENDOR_NAME = "NewVendor"

    def get_optimization_flags(self) -> dict:
        return {
            "use_local_memory": True,
            "work_group_size": 256,
        }

```

### 6.3 添加新地址类型

1. 在 `src/core/address_converter.py` 添加解析逻辑

2. 在 `src/core/address_generator.py` 添加生成支持

3. 更新 `src/collision/target_resolver.py`

4. 添加测试用例

---

## 7. 配置管理

### 7.1 配置文件结构

```json
{
    "collision": {
        "checkpoint_interval": 30,
        "dedup_max_size": 1000000,
        "progress_interval": 1000,
        "max_workers": null
    },
    "gpu": {
        "batch_size": 100000,
        "device_index": 0,
        "auto_select": true
    },
    "monitoring": {
        "enabled": true,
        "interval": 5
    },
    "logging": {
        "level": "INFO",
        "file": "logs/collision.log"
    }
}

```

### 7.2 配置加载

```python
from src.config.config_manager import ConfigManager

config = ConfigManager()
settings = config.get_all()
gpu_batch_size = settings.get("gpu", {}).get("batch_size", 100000)

```

---

## 8. 日志与监控

### 8.1 日志使用

```python
from src.utils.logger import get_configured_logger

logger = get_configured_logger(__name__)

logger.info("操作信息: %s", detail)
logger.warning("警告信息: %s", detail)
logger.error("错误信息: %s", e, exc_info=True)

```

### 8.2 性能监控

```python
from src.monitoring.enhanced_monitoring import EnhancedMonitoring

monitor = EnhancedMonitoring()
monitor.start_monitoring()
# ... 执行操作 ...
stats = monitor.get_stats()

```

---

## 9. 提交代码

### 9.1 提交前检查清单

- [ ] 代码通过 `black` 格式化

- [ ] 代码通过 `flake8` 检查

- [ ] 所有公开函数有类型注解

- [ ] 新功能有对应测试

- [ ] 测试通过 `pytest`

- [ ] 更新相关文档

### 9.2 Git 提交规范

```bash
<类型>(<模块>): <简短描述>

详细说明（可选）

类型: feat/fix/docs/style/refactor/test/chore

```

示例：

```bash
feat(gpu): 添加 Intel Arc A770 支持

- 新增 uint32 workaround 标志
- 添加内存对齐优化
- 更新性能基准测试

```

---

## 10. 常见问题

### Q1: GPU 初始化失败？

检查：

1. 是否安装了 pyopencl

2. OpenCL 驱动是否正确

3. GPU 设备是否支持 OpenCL 1.2

### Q2: 测试在 CI 通过但本地失败？

可能是平台差异，检查：

1. GPU Mock 是否正确注入

2. 临时文件路径权限

3. 环境变量配置

### Q3: 如何调试 GPU 内核？

使用 `pyopencl` 的分析工具：

```python
import pyopencl as cl
ctx = cl.create_some_context()
prof = ctx.create_profiling_events()

```

---

## 11. 相关文档

- [开发代码标准](standards/development_code_standards.md)

- [测试标准](standards/development_test_standards.md)

- [GPU 引擎指南](gpu-engine-guide.md)

- [安全指南](security-guidelines.md)

- [性能优化](performance-optimization.md)

---

*最后更新: 2026-05-04*
