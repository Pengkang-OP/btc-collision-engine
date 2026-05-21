# 测试规范

> **版本**: v4.2.2 | **更新日期**: 2026-05-15 | **适用范围**: btc-collision-engine 全体测试代码

---

## 1. 测试框架与目录结构

### 1.1 使用规范

项目统一使用 **pytest** 作为测试框架，配置文件为 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

### 1.2 目录结构

```
tests/
├── conftest.py                 # 全局 Fixture 与测试配置
├── gpu_mock_factory.py         # GPU Mock 工厂（所有 GPU 测试共用）
├── test_helpers.py             # 通用断言辅助函数
├── verify_scripts/             # 独立验证脚本（不通过 pytest 运行）
│   └── verify_*.py
├── archive/                    # 已归档的历史测试
└── test_<module_name>.py       # 各模块测试文件
```

**约定**：

- 每个源码模块对应一个测试文件，命名为 `test_<模块名>.py`
- 集成测试文件以 `test_<模块名>_integration.py` 结尾
- 性能测试放入 `tests/` 下并以 `test_<模块名>_performance.py` 命名

---

## 2. 测试命名规范

### 2.1 测试文件

```
test_<模块名>.py                  # 单元测试
test_<模块名>_integration.py      # 集成测试
test_<模块名>_performance.py      # 性能测试
```

示例（对应 `src/` 下的实际模块）：

| 源码模块 | 测试文件 |
|---------|---------|
| `src/core/key_generator.py` | `tests/test_core_crypto.py` |
| `src/collision/gpu_collision_engine.py` | `tests/test_gpu_collision_engine.py` |
| `src/monitoring/alert_system.py` | `tests/test_alert_system.py` |
| `src/cli/main.py` | `tests/test_cli.py` |

### 2.2 测试类与方法

测试类使用 `PascalCase`，前缀 `Test`：

```python
class TestSecureKeyGenerator:        # 对应 SecureKeyGenerator 类
class TestGPUCollisionEngine:         # 对应 GPUCollisionEngine 类
class TestBatchSizeCalculation:       # 对应特定功能
```

测试方法使用 `snake_case`，格式为 `test_<功能描述>_<预期结果>`：

```python
# ✅ 正确：清晰描述测试场景和预期结果
def test_generate_batch_returns_correct_count(self):
def test_generate_batch_raises_when_count_is_zero(self):
def test_gpu_init_fails_without_opencl(self):
def test_batch_size_capped_at_max_when_mem_is_small(self):

# ❌ 避免：命名过于模糊
def test_generate(self):
def test_error(self):
def test_1(self):
```

---

## 3. pytest Fixture 规范

### 3.1 conftest.py 共享 Fixture

共享 Fixture 统一定义在 `tests/conftest.py`，避免跨文件复制。

**Fixture 作用域选择**：

| 作用域 | 装饰器 | 适用场景 |
|-------|-------|---------|
| 函数级（默认） | `@pytest.fixture` | 每个测试独立隔离（推荐默认）|
| 模块级 | `@pytest.fixture(scope='module')` | 只读测试、性能测试 |
| 会话级 | `@pytest.fixture(scope='session')` | 全局配置、数据库连接 |

```python
# tests/conftest.py 示例（参考项目现有实现）

@pytest.fixture
def mock_gpu_chain():
    """提供完整的7层GPU Mock链，用于GPU碰撞引擎测试

    封装层次：
        1. PYOPENCL_AVAILABLE
        2. GPUDeviceDetector.is_gpu_available
        3. GPUDevice
        4. GPUContext
        5. GPUKernel
        6. GPUProfileLoader
        7. identify_vendor

    Yields:
        tuple: (mock_device, mock_context, mock_kernel)
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects()
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
        yield mocks


@pytest.fixture(scope='module')
def mock_gpu_chain_module():
    """模块级共享的GPU Mock链（适用于只读集成测试）

    ⚠️ 注意：此 Fixture 在模块内共享，不适合修改 Mock 状态的测试！
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects()
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
        yield mocks
```

### 3.2 参数化测试

使用 `@pytest.mark.parametrize` 对多组输入进行覆盖：

```python
import pytest

@pytest.mark.parametrize("batch_size,expected", [
    (1024,    1024),
    (65536,   65536),
    (0,       None),    # 无效输入
    (-1,      None),    # 负数输入
])
def test_validate_batch_size(batch_size: int, expected):
    """验证批次大小校验逻辑"""
    if expected is None:
        with pytest.raises(ValueError):
            validate_batch_size(batch_size)
    else:
        assert validate_batch_size(batch_size) == expected


@pytest.mark.parametrize("vendor,expected_workaround", [
    ("nvidia", False),
    ("amd",    False),
    ("intel",  True),   # Intel Arc 需要 uint32 workaround
])
def test_vendor_workaround_flag(vendor: str, expected_workaround: bool):
    result = should_use_uint32_workaround(vendor)
    assert result == expected_workaround
```

---

## 4. Mock 使用规范

### 4.1 Mock 工厂模式

项目统一使用 `tests/gpu_mock_factory.py` 中的 `GPUMockFactory` 提供标准化 Mock 对象，**禁止**在各测试文件中独立手写 GPU Mock。

```python
from tests.gpu_mock_factory import GPUMockFactory

class TestGPUKernel:
    def test_run_batch_returns_empty_on_no_match(self):
        """GPU批次执行无碰撞时返回空列表"""
        with GPUMockFactory.patch_gpu_collision_engine(batch_size=1000) as mocks:
            engine = GPUCollisionEngine(targets, batch_size=1000)
            result = engine._execute_gpu_batch(keys)
            assert result == []

    def test_run_batch_raises_on_oom(self):
        """GPU显存不足时抛出 MemoryError"""
        with GPUMockFactory.patch_gpu_collision_engine(
            run_batch_side_effect=MemoryError("OOM")
        ) as mocks:
            engine = GPUCollisionEngine(targets)
            with pytest.raises(MemoryError):
                engine._execute_gpu_batch(keys)
```

### 4.2 预置 Mock 设备

`GPUMockFactory` 提供主流 GPU 的预置 Mock：

```python
# 预置设备（tests/gpu_mock_factory.py 中定义）
nvidia_device = GPUMockFactory.nvidia_device()      # RTX 3080, 8GB
amd_device    = GPUMockFactory.amd_device()         # RX 6800 XT, 16GB
intel_device  = GPUMockFactory.intel_arc_device()   # Arc A770, 16GB
cpu_device    = GPUMockFactory.cpu_device()         # CPU 设备

# 多厂商平台列表（用于多GPU测试）
platforms = GPUMockFactory.multi_vendor_platforms()
```

### 4.3 conftest.py 厂商预设 Fixture

```python
# 按厂商选择 Fixture（tests/conftest.py 中定义）
def test_nvidia_batch(mock_gpu_chain_nvidia):
    mock_device, mock_context, mock_kernel = mock_gpu_chain_nvidia
    ...

def test_intel_workaround(mock_gpu_chain_intel):
    mock_device, mock_context, mock_kernel = mock_gpu_chain_intel
    assert mock_kernel.use_uint32_workaround is True
```

### 4.4 Mock pyopencl.Buffer

`pyopencl.Buffer` 需要真实 OpenCL 上下文，**必须通过 `sys.modules` patch**：

```python
# ✅ 正确（参考 tests/conftest.py _apply_gpu_patches）
mock_cl_module = Mock()
mock_cl_module.Buffer = Mock(return_value=Mock())
mock_cl_module.mem_flags = Mock()
mock_cl_module.mem_flags.READ_WRITE = 1

with patch.dict('sys.modules', {
    'pyopencl': mock_cl_module,
    'pyopencl.array': Mock(),
}):
    ...

# ❌ 错误（无法拦截函数级 import）
with patch('pyopencl.Buffer', return_value=Mock()):
    ...  # 仅在模块级 import 时有效，函数级 import 无效
```

### 4.5 Mock 使用原则

- **最小化 Mock**：只 Mock 外部依赖（GPU 硬件、网络、文件 I/O），不 Mock 被测逻辑
- **验证 Mock 调用**：使用 `assert_called_once_with()` 验证关键调用
- **避免过度 Mock**：Mock 层次超过 3 层时考虑重构代码

```python
def test_cleanup_called_on_engine_stop(mock_gpu_chain):
    mock_device, mock_context, mock_kernel = mock_gpu_chain
    engine = GPUCollisionEngine(targets)
    engine.stop()
    # 验证清理方法被调用
    mock_kernel.cleanup.assert_called_once()
    mock_device.cleanup.assert_called_once()
```

---

## 5. 测试分层

### 5.1 单元测试

- **目标**：测试单个函数或类的行为，完全隔离外部依赖
- **覆盖重点**：边界值、异常路径、正常路径
- **运行速度**：< 100ms / 个测试

```python
class TestBatchSizeCalculation:
    """单元测试：批次大小计算逻辑"""

    def test_normal_mem_size(self):
        """8GB显存下计算正常批次大小"""
        mem_size = 8 * 1024 ** 3
        result = calculate_batch_size(mem_size)
        assert 1024 <= result <= 1_048_576

    def test_min_batch_size_on_small_mem(self):
        """极小显存下返回最小批次大小"""
        result = calculate_batch_size(256 * 1024 * 1024)  # 256MB
        assert result == MIN_BATCH_SIZE

    def test_raises_on_zero_mem(self):
        """显存为0时抛出 ValueError"""
        with pytest.raises(ValueError, match="显存大小不能为0"):
            calculate_batch_size(0)
```

### 5.2 集成测试

- **目标**：测试多个模块协同工作
- **依赖**：允许使用 Mock 替代 GPU 硬件，但不 Mock 项目内部模块
- **文件命名**：`test_*_integration.py`

```python
class TestGPUEngineIntegration:
    """集成测试：GPU碰撞引擎完整工作流"""

    def test_engine_full_cycle(self, mock_gpu_chain):
        """GPU引擎完整运行周期：初始化→运行→停止"""
        mock_device, mock_context, mock_kernel = mock_gpu_chain
        targets = load_test_targets()
        engine = GPUCollisionEngine(targets)
        engine.start(mode="random")
        time.sleep(0.1)
        engine.stop()
        # 验证生命周期方法均被调用
        mock_device.initialize.assert_called_once()
        mock_kernel.cleanup.assert_called_once()
```

### 5.3 性能测试

- **工具**：`pytest-benchmark`（已在 `pyproject.toml` dev 依赖中）
- **目录**：`benchmarks/` 或 `tests/test_*_performance.py`
- **标准**：核心密钥生成 ≥ 10,000 keys/s（CPU），GPU 路径 ≥ 100,000 keys/s

```python
def test_key_generation_throughput(benchmark):
    """基准测试：批量密钥生成吞吐量"""
    generator = SecureKeyGenerator({'batch_size': 1000})
    result = benchmark(generator.generate_batch, 1000)
    assert len(result) == 1000
```

---

## 6. 覆盖率要求

| 模块类型 | 最低覆盖率 | 说明 |
|---------|----------|------|
| `src/core/` | ≥ 80% | 核心密码学与密钥生成 |
| `src/collision/` | ≥ 80% | 碰撞引擎主逻辑 |
| `src/gpu/` | ≥ 70% | GPU加速层（硬件分支可豁免）|
| `src/monitoring/` | ≥ 70% | 监控与告警系统 |
| `src/cli/` | ≥ 65% | CLI 交互层 |
| `src/utils/` | ≥ 60% | 工具函数 |
| `src/config/` | ≥ 60% | 配置管理 |

```bash
# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term-missing

# 只检查核心模块覆盖率
pytest tests/test_core_crypto.py --cov=src/core --cov-fail-under=80
```

---

## 7. 测试数据管理

### 7.1 目录规范

```
test_data/
├── archive/              # 已归档的历史测试数据（只读）
│   ├── gpu_integration_test_report.json
│   └── stability_test_final_report.json
└── fixtures/             # 可复用的测试数据文件
    ├── valid_addresses.txt
    └── sample_keys.json
```

### 7.2 使用规范

- 测试用比特币地址使用 `valid_addresses.txt`（已在项目根目录）
- 大文件（> 1MB）不提交至 git，使用生成函数动态创建
- 敏感测试数据（私钥、种子）使用 `secrets` 模块生成，不硬编码

```python
# ✅ 正确：动态生成测试数据
@pytest.fixture
def sample_target_addresses():
    """生成测试用目标地址集合"""
    return {
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf6",  # 创世区块地址（公开已知）
        "1BpEi6DfDAUFd153wiGrvkiKW1J1t1V8U",
    }

# ✅ 正确：读取项目测试数据文件
@pytest.fixture
def valid_address_list(tmp_path):
    src = Path("valid_addresses.txt")
    data = src.read_text(encoding="utf-8").splitlines()[:100]  # 仅取前100行
    return data
```

### 7.3 临时文件

测试中产生的临时文件使用 pytest 内置的 `tmp_path` Fixture：

```python
def test_checkpoint_save_and_load(tmp_path):
    """测试检查点保存与加载"""
    checkpoint_file = tmp_path / "checkpoint.json"
    manager = CheckpointManager(str(checkpoint_file))
    manager.save({"progress": 12345})
    loaded = manager.load()
    assert loaded["progress"] == 12345
```

---

## 8. CI 集成要求

### 8.1 GitHub Actions 配置（`.github/workflows/ci.yml`）

```yaml
- name: Run Tests
  run: |
    pytest tests/ -v --tb=short --cov=src --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### 8.2 提交前检查（pre-commit）

见 `.pre-commit-config.yaml`，提交前自动运行：

1. `black` 代码格式化
2. `flake8` 风格检查
3. `bandit` 安全扫描（排除 `tests/`）

### 8.3 测试执行命令

```bash
# 运行全量测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_core_crypto.py -v

# 运行含 GPU Mock 的测试（无需真实 GPU）
pytest tests/test_gpu_collision_engine.py -v

# 跳过性能测试（CI 快速通道）
pytest tests/ -v -m "not benchmark"

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html -q
```

---

## 9. 常见问题

### Q1: GPU 集成测试失败，提示"pyopencl 未安装"？

使用 `tests/conftest.py` 中的 `mock_gpu_chain` Fixture 而非直接初始化 GPU 引擎。详见 [tests/conftest.py](../../tests/conftest.py)。

### Q2: 测试在 pytest 下失败，但直接运行脚本正常？

部分 GPU 集成脚本（`scripts/test_gpu_*.py`）需要直接运行：

```bash
# ❌ 不通过 pytest 运行
pytest scripts/test_gpu_collision_actual.py

# ✅ 直接运行
python scripts/test_gpu_collision_actual.py
```

### Q3: Windows 下 pytest 导入失败如何处理？

使用 Python 导入验证替代 pytest：

```bash
python -c "from src.collision.gpu.engine import GPUCollisionEngine; print('OK')"
```

---

*参考文件*：

- `tests/conftest.py` — 全局 Fixture 与 GPU Mock 链实现
- `tests/gpu_mock_factory.py` — GPU Mock 工厂（标准化 Mock 对象）
- `pyproject.toml` — pytest 与开发依赖配置
- `.pre-commit-config.yaml` — 提交前自动检查配置
