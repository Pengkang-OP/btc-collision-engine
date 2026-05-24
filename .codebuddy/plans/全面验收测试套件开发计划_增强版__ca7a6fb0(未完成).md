---
name: 全面验收测试套件开发计划（增强版）
overview: 为 BTC 碰撞引擎项目编写全面的验收测试套件，覆盖功能层、数据层、逻辑层三个维度，并添加端到端测试、白盒/黑盒测试、生命周期测试、辅助功能测试、辅助数据测试等多种测试类型，采用多模式、多状态、多数据组合方式，确保对项目所有核心路径和边界场景实现全面覆盖。
todos:
  - id: create-acceptance-dir
    content: 创建 tests/acceptance/ 目录和测试数据结构
    status: pending
  - id: create-conftest
    content: 编写验收测试共享 conftest.py fixture配置
    status: pending
    dependencies:
      - create-acceptance-dir
  - id: create-engine-tests
    content: 编写引擎核心验收测试 test_acceptance_engine.py（功能层+逻辑层+白盒+黑盒）
    status: pending
    dependencies:
      - create-conftest
  - id: create-crypto-tests
    content: 编写加密后端验收测试 test_acceptance_crypto.py（功能层+数据层+逻辑层）
    status: pending
    dependencies:
      - create-conftest
  - id: create-gpu-tests
    content: 编写GPU引擎验收测试 test_acceptance_gpu.py（多状态+多数据组合）
    status: pending
    dependencies:
      - create-conftest
  - id: create-data-tests
    content: 编写数据层验收测试 test_acceptance_data.py（数据流+数据管道+数据类型）
    status: pending
    dependencies:
      - create-conftest
  - id: create-e2e-tests
    content: 编写端到端验收测试 test_acceptance_e2e.py（完整用户场景）
    status: pending
    dependencies:
      - create-engine-tests
      - create-crypto-tests
      - create-gpu-tests
  - id: create-lifecycle-tests
    content: 编写生命周期验收测试 test_acceptance_lifecycle.py（组件完整生命周期）
    status: pending
    dependencies:
      - create-engine-tests
      - create-crypto-tests
  - id: create-aux-function-tests
    content: 编写辅助功能验收测试 test_acceptance_aux_functions.py（辅助函数和工具）
    status: pending
    dependencies:
      - create-conftest
  - id: create-aux-data-tests
    content: 编写辅助数据验收测试 test_acceptance_aux_data.py（数据辅助工具和转换）
    status: pending
    dependencies:
      - create-conftest
  - id: create-integration-tests
    content: 编写集成验收测试 test_acceptance_integration.py（端到端多模式验证）
    status: pending
    dependencies:
      - create-e2e-tests
      - create-lifecycle-tests
  - id: update-pytest-ini
    content: 更新 pytest.ini 添加 acceptance marker 配置
    status: pending
    dependencies:
      - create-acceptance-dir
  - id: run-acceptance-tests
    content: 运行验收测试套件并验证覆盖率
    status: pending
    dependencies:
      - update-pytest-ini
---

## 产品概述

为 btc-collision-engine (v5.0.0) 比特币私钥碰撞引擎项目编写全面的验收测试套件，严格验证功能层、数据层、逻辑层三个维度，并包含端到端测试、白盒测试、黑盒测试、生命周期测试、辅助功能测试和辅助数据测试，采用多模式、多状态、多数据组合方式，确保对项目所有核心路径和边界场景实现全面覆盖。

## 核心功能

### 功能层验证

- 功能正确性：验证所有public方法的功能正确性
- 功能调用：测试回调函数调用时机和参数
- 功能判断：验证状态判断逻辑（is_running, is_initialized等）

### 数据层验证

- 数据：验证数据格式和值
- 数据流：验证数据流完整性（生成→处理→存储）
- 数据管道：测试数据管道各阶段数据格式
- 数据类型：验证数据类型转换正确性
- 数据调用：测试数据调用接口（内存池、检查点文件）

### 逻辑层验证

- 代码正确性：验证核心算法逻辑正确性
- 逻辑：测试条件判断分支覆盖
- 逻辑正确性：验证错误处理和异常路径
- 逻辑判断：测试并发逻辑和线程安全性

### 测试类型

- **端到端测试**：完整的用户场景测试
- **白盒测试**：基于内部代码结构的测试
- **黑盒测试**：基于规格说明的功能测试
- **生命周期测试**：组件完整生命周期测试
- **辅助功能测试**：辅助函数和工具测试
- **辅助数据测试**：数据辅助工具和转换测试

### 测试策略

- **多模式**：测试随机碰撞、范围扫描、暴力穷举三种搜索模式
- **多状态**：测试初始化、运行、暂停、停止、错误恢复等状态转换
- **多数据组合**：测试不同数据类型、格式、边界条件组合

## 技术栈

- **测试框架**：pytest + pytest-cov + pytest-timeout + pytest-benchmark
- **Mock框架**：unittest.mock (Patch, MagicMock, Mock)
- **类型检查**：mypy (可选)
- **代码覆盖率**：pytest-cov with HTML report

## 实现方法

### 验收测试策略

1. **分层验收测试架构**：

- `tests/acceptance/` - 验收测试根目录
- `test_acceptance_engine.py` - 引擎核心验收测试（功能层+逻辑层+白盒+黑盒）
- `test_acceptance_crypto.py` - 加密后端验收测试（功能层+数据层+逻辑层）
- `test_acceptance_gpu.py` - GPU引擎验收测试（多状态+多数据组合）
- `test_acceptance_data.py` - 数据层验收测试（数据流+数据管道+数据类型）
- `test_acceptance_e2e.py` - 端到端验收测试（完整用户场景）
- `test_acceptance_lifecycle.py` - 生命周期验收测试（组件完整生命周期）
- `test_acceptance_aux_functions.py` - 辅助功能验收测试（辅助函数和工具）
- `test_acceptance_aux_data.py` - 辅助数据验收测试（数据辅助工具和转换）
- `test_acceptance_integration.py` - 集成验收测试（端到端多模式验证）

2. **多模式测试设计**：

- 参数化测试 (`@pytest.mark.parametrize`) 覆盖三种搜索模式
- 状态机测试覆盖所有状态转换
- 数据组合测试使用参数化或手动组合

3. **测试数据管理**：

- 使用 `conftest.py` 共享fixture
- 预设测试数据集（有效/无效/边界/异常）
- Mock外部依赖（GPU硬件、网络、文件系统）

### 关键技术方案

1. **功能层测试**：

- 验证所有public方法的功能正确性
- 测试回调函数调用时机和参数
- 验证状态判断逻辑（is_running, is_initialized等）

2. **数据层测试**：

- 验证数据流完整性（生成→处理→存储）
- 测试数据管道各阶段数据格式
- 验证数据类型转换正确性
- 测试数据调用接口（内存池、检查点文件）

3. **逻辑层测试**：

- 验证核心算法逻辑正确性
- 测试条件判断分支覆盖
- 验证错误处理和异常路径
- 测试并发逻辑和线程安全性

4. **端到端测试**：

- 完整用户场景测试（从CLI输入到结果输出）
- 测试所有搜索模式的完整流程
- 验证错误处理和用户反馈

5. **白盒测试**：

- 基于内部代码结构的测试
- 测试所有条件分支和循环
- 验证私有方法和内部状态

6. **黑盒测试**：

- 基于规格说明的功能测试
- 测试输入输出规范
- 验证功能需求符合性

7. **生命周期测试**：

- 组件完整生命周期测试
- 测试初始化、运行、暂停、停止、错误恢复
- 验证资源正确释放

8. **辅助功能测试**：

- 辅助函数和工具测试
- 测试utils/目录下的所有辅助函数
- 验证编码转换、文件操作、异常处理等

9. **辅助数据测试**：

- 数据辅助工具和转换测试
- 测试fast_json、encoding_utils、hash_utils等
- 验证数据格式转换正确性

### 性能考虑

- 使用 `pytest.mark.timeout` 防止测试挂起
- Mock GPU操作避免真实硬件依赖
- 使用临时目录和文件自动清理
- 测试数据最小化原则