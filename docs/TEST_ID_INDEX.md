# 测试ID索引文档

**版本**: v4.4.1  
**最后更新**: 2026-04-29  
**状态**: 活跃维护

---

## 目录

- [概述](#概述)

- [测试ID命名规范](#测试id命名规范)

- [skip标记分类](#skip标记分类)

- [测试ID索引表](#测试id索引表)

- [测试ID详细信息](#测试id详细信息)

- [运行条件参考](#运行条件参考)

- [维护指南](#维护指南)

---

## 概述

本文档维护所有带有skip标记的测试用例的详细信息，包括跳过原因、运行条件、关联文档等。

---

## 测试ID命名规范

测试ID采用以下格式：

```json

```

[分类]-[类型]-[序号]

```

| 分类 | 含义 | 示例 |
|------|------|------|
| GPU | GPU相关测试 | GPU-HW-001 |
| PERF | 性能测试 | PERF-001 |
| SEC | 安全测试 | SEC-001 |
| INT | 集成测试 | INT-001 |

| 类型 | 含义 |
|------|------|
| HW | 需要硬件 |
| SKIP | 条件跳过 |
| TODO | 待完成 |

---

## skip标记分类

### 1. GPU硬件依赖 (GPU-HW)

需要真实GPU硬件环境才能运行的测试。

### 2. 性能基准测试 (PERF)

需要特定硬件配置或长时间运行的性能测试。

### 3. 安全合规测试 (SEC)

需要特定安全环境或权限的测试。

### 4. 集成测试 (INT)

需要完整环境的集成测试。

---

## 测试ID索引表

| 测试ID | 测试文件 | 跳过原因 | 状态 | 关联文档 |
|--------|----------|----------|------|----------|
| GPU-HW-001 | `tests/test_gpu_collision_engine.py` | 需要NVIDIA GPU | ⏸️ 跳过 | [GPU引擎指南](gpu-engine-guide.md) |
| GPU-HW-002 | `tests/test_gpu_collision_engine.py` | 需要AMD GPU | ⏸️ 跳过 | [GPU引擎指南](gpu-engine-guide.md) |
| GPU-HW-003 | `tests/test_gpu_collision_engine.py` | 需要Intel Arc GPU | ⏸️ 跳过 | [Intel Arc集成指南](intel-arc-gpu-compatibility-research.md) |
| GPU-HW-004 | `tests/test_multi_gpu.py` | 需要多GPU环境 | ⏸️ 跳过 | [多GPU指南](MULTI_GPU.md) |
| PERF-001 | `tests/test_performance_monitor.py` | 长时间运行测试 | ⏸️ 跳过 | [性能优化指南](performance-optimization.md) |
| PERF-002 | `tests/test_gpu_performance.py` | GPU性能基准 | ⏸️ 跳过 | GPU性能监控（文档已移除） |

---

## 测试ID详细信息

### GPU-HW-001: NVIDIA GPU初始化测试

**测试文件**: `tests/test_gpu_collision_engine.py`  
**函数名**: `test_gpu_engine_initialization_nvidia`  
**跳过原因**: 需要真实NVIDIA GPU硬件  
**运行条件**:

- 安装NVIDIA GPU驱动

- 安装pyopencl和NVIDIA OpenCL运行时

- 至少8GB显存

**预期行为**:

- 测试GPU引擎在NVIDIA设备上的初始化流程

- 验证设备信息读取正确性

- 验证上下文创建成功

**关联文档**:

- [GPU引擎指南](gpu-engine-guide.md)

- [NVIDIA优化配置](GPU_CONFIG_MANAGER_GUIDE.md)

---

### GPU-HW-002: AMD GPU初始化测试

**测试文件**: `tests/test_gpu_collision_engine.py`  
**函数名**: `test_gpu_engine_initialization_amd`  
**跳过原因**: 需要真实AMD GPU硬件  
**运行条件**:

- 安装AMD GPU驱动

- 安装pyopencl和AMD OpenCL运行时

**预期行为**:

- 测试GPU引擎在AMD设备上的初始化流程

- 验证AMD特定优化是否生效

---

### GPU-HW-003: Intel Arc GPU初始化测试

**测试文件**: `tests/test_gpu_collision_engine.py`  
**函数名**: `test_gpu_engine_initialization_intel_arc`  
**跳过原因**: 需要真实Intel Arc GPU硬件  
**运行条件**:

- 安装Intel Arc GPU驱动

- 安装pyopencl和Intel OpenCL运行时

- 启用Intel特定优化

**预期行为**:

- 测试GPU引擎在Intel Arc设备上的初始化流程

- 验证uint32 workaround是否正确应用

**关联文档**:

- [Intel Arc集成指南](intel-arc-gpu-compatibility-research.md)

---

### GPU-HW-004: 多GPU环境测试

**测试文件**: `tests/test_multi_gpu.py`  
**函数名**: `test_multi_gpu_engine`  
**跳过原因**: 需要多个GPU设备  
**运行条件**:

- 系统中安装多个GPU

- 所有GPU都支持OpenCL

- 足够的系统内存

**预期行为**:

- 测试多GPU引擎的初始化和负载均衡

- 验证多GPU协作功能

**关联文档**:

- [多GPU指南](MULTI_GPU.md)

---

### PERF-001: 性能监控基准测试

**测试文件**: `tests/test_performance_monitor.py`  
**函数名**: `test_performance_monitor_long_running`  
**跳过原因**: 运行时间超过30分钟  
**运行条件**:

- 空闲系统资源

- 稳定的电源供应

- 可选：性能监控工具

**预期行为**:

- 验证性能监控系统在长时间运行下的稳定性

- 检查内存泄漏和资源消耗

**关联文档**:

- [性能优化指南](performance-optimization.md)

---

### PERF-002: GPU性能基准测试

**测试文件**: `tests/test_gpu_performance.py`  
**函数名**: `test_gpu_performance_benchmark`  
**跳过原因**: 需要真实GPU且运行时间较长  
**运行条件**:

- 真实GPU硬件

- 足够的测试时间（约10分钟）

- 关闭其他GPU密集型应用

**预期行为**:

- 测量GPU碰撞引擎的实际性能

- 验证性能指标是否符合预期

---

## 运行条件参考

### GPU硬件要求

| 厂商 | 最低要求 | 推荐配置 |
|------|----------|----------|
| NVIDIA | GeForce GTX 1060+ | RTX 3080+ |
| AMD | Radeon RX 580+ | RX 6800 XT+ |
| Intel | UHD 630+ | Arc A770+ |

### 软件环境要求

| 组件 | 最低版本 |
|------|----------|
| Python | 3.14 |
| pyopencl | 2023.1 |
| numpy | 1.24 |

---

## 维护指南

### 添加新测试ID

1. 在索引表中添加新条目

2. 创建详细信息章节

3. 更新关联文档链接

4. 在测试代码中使用规范的skip原因格式：

   ```

   ```python

   ```

   @pytest.mark.skip(reason="[GPU-HW-001] 需要真实NVIDIA GPU")
   def test_gpu_engine_initialization_nvidia():
       pass