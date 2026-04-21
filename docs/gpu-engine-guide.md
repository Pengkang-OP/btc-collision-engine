# GPU引擎使用指南

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **面向**: 开发者


> 本文档详细介绍如何使用BTC碰撞引擎的GPU加速功能，包括安装、配置、性能调优和故障排除。


## 目录

- [📋 目录](#-目录)
- [GPU加速概述](#gpu加速概述)
  - [支持的GPU设备](#支持的gpu设备)
  - [性能对比](#性能对比)
- [环境准备](#环境准备)
  - [1. 安装OpenCL驱动](#1-安装opencl驱动)
    - [NVIDIA GPU](#nvidia-gpu)
- [AMD GPU](#amd-gpu)
- [Intel Arc GPU](#intel-arc-gpu)
- [2. 安装Python依赖](#2-安装python依赖)
- [3. 验证GPU可用性](#3-验证gpu可用性)
- [快速开始](#快速开始)
  - [方法1: GUI界面](#方法1-gui界面)
  - [方法2: 命令行](#方法2-命令行)
- [方法3: Python代码](#方法3-python代码)
- [高级配置](#高级配置)
  - [GPU设备选择](#gpu设备选择)
- [Batch Size调优](#batch-size调优)
- [内存优化](#内存优化)
- [性能调优](#性能调优)
  - [1. 异步流水线优化](#1-异步流水线优化)
  - [2. 目标地址优化](#2-目标地址优化)
- [3. 超时保护](#3-超时保护)
- [4. 性能监控](#4-性能监控)
- [故障排除](#故障排除)
  - [问题1: GPU初始化失败](#问题1-gpu初始化失败)
- [问题2: 显存不足](#问题2-显存不足)
- [问题3: GPU执行超时](#问题3-gpu执行超时)
  - [问题4: Intel Arc GPU Hang](#问题4-intel-arc-gpu-hang)
- [问题5: 性能低于预期](#问题5-性能低于预期)
- [最佳实践](#最佳实践)
  - [1. 设备选择](#1-设备选择)
- [2. Batch Size策略](#2-batch-size策略)
- [3. 错误处理](#3-错误处理)
  - [4. 资源清理](#4-资源清理)
- [5. 长时间运行](#5-长时间运行)
- [技术架构](#技术架构)
  - [GPU计算流程](#gpu计算流程)
  - [OpenCL内核优化](#opencl内核优化)
- [附录](#附录)
  - [A. GPU设备检测脚本](#a-gpu设备检测脚本)
  - [B. 性能基准测试](#b-性能基准测试)
- [参考资源](#参考资源)
## 📋 目录

1. [GPU加速概述](#gpu加速概述)
2. [环境准备](#环境准备)
3. [快速开始](#快速开始)
4. [高级配置](#高级配置)
5. [性能调优](#性能调优)
6. [故障排除](#故障排除)
7. [最佳实践](#最佳实践)

---

## GPU加速概述

### 支持的GPU设备

- **NVIDIA**: GeForce系列、RTX系列、Tesla系列
- **AMD**: Radeon系列、RX系列
- **Intel**: Arc系列独立显卡

**注意**：项目自动过滤以下设备：
- CPU设备（不使用CPU模拟OpenCL）
- Intel集成显卡（HD Graphics、UHD Graphics、Iris）

### 性能对比

| 设备类型 | 性能范围 | 推荐场景 |
|---------|---------|---------|
| CPU (8核) | 5,000-10,000 次/秒 | 小规模测试 |
| 中端GPU (GTX 1060) | 50,000-100,000 次/秒 | 日常使用 |
| 高端GPU (RTX 3080) | 200,000-500,000 次/秒 | 大规模扫描 |
| 旗舰GPU (RTX 4090) | 1,000,000+ 次/秒 | 专业研究 |

---

## 环境准备

### 1. 安装OpenCL驱动

#### NVIDIA GPU
```bash
# 安装CUDA Toolkit (包含OpenCL)
# 下载地址: https://developer.nvidia.com/cuda-toolkit
```markdown

## AMD GPU
```bash
# 安装AMD GPU驱动
# 下载地址: https://www.amd.com/en/support
```markdown

## Intel Arc GPU
```bash
# 安装Intel Graphics驱动
# 下载地址: https://www.intel.com/content/www/us/en/download-center/home.html
```markdown

## 2. 安装Python依赖

```bash
# 安装PyOpenCL
pip install pyopencl

# 安装NumPy（GPU计算优化）
pip install numpy

# 可选：安装性能优化库
pip install coincurve  # CPU后端优化
```markdown

## 3. 验证GPU可用性

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 检查GPU是否可用
if GPUCollisionEngine.is_gpu_available():
    print("✅ GPU可用")
else:
    print("❌ GPU不可用")

# 列出所有GPU设备
GPUCollisionEngine.list_devices()
```python

---

## 快速开始

### 方法1: GUI界面

1. 启动GUI程序
```bash
python key_collision_gui.py
```python

2. 在"高级选项"中勾选"使用GPU加速"

3. 选择GPU设备索引（默认自动选择）

4. 点击"开始"按钮

### 方法2: 命令行

```bash
# 使用GPU加速
python key_collision_cli.py --targets addresses.txt --gpu

# 指定GPU设备
python key_collision_cli.py --targets addresses.txt --gpu --gpu-device 0

# 设置batch size
python key_collision_cli.py --targets addresses.txt --gpu --gpu-batch-size 100000
```markdown

## 方法3: Python代码

```python
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# 自动选择（优先GPU）
engine = create_collision_engine(targets, mode='auto')

# 强制使用GPU
engine = create_collision_engine(targets, mode='gpu')

# 强制使用CPU
engine = create_collision_engine(targets, mode='cpu')
```python

---

## 高级配置

### GPU设备选择

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine, GPUDevice

# 检测所有可用设备
devices = GPUDevice.detect_devices()

for i, device in enumerate(devices):
    print(f"设备 {i}: {device['name']}")
    print(f"  厂商: {device['vendor']}")
    print(f"  显存: {device['global_mem_size'] / (1024**3):.2f} GB")

# 创建引擎时指定设备
engine = GPUCollisionEngine(
    targets=targets,
    device_index=0,  # 使用第一个GPU
    batch_size=100000
)
```markdown

## Batch Size调优

Batch size是影响GPU性能的关键参数：

| GPU显存 | 推荐Batch Size | 说明 |
|---------|---------------|------|
| < 2GB | 10,000 - 50,000 | 低显存GPU |
| 2-4GB | 50,000 - 200,000 | 中端GPU |
| 4-8GB | 200,000 - 500,000 | 高端GPU |
| > 8GB | 500,000 - 2,000,000 | 旗舰GPU |

**自动计算**（推荐）：
```python
# 不指定batch_size，系统会根据显存自动计算
engine = GPUCollisionEngine(targets=targets)
# 或使用配置
config.json: "gpu_batch_size": -1  # -1表示自动
```markdown

## 内存优化

```python
# GPU引擎使用持久化缓冲区，避免频繁分配
# 目标地址缓冲区只在初始化时设置一次
# 私钥缓冲区复用，减少内存传输
```python

---

## 性能调优

### 1. 异步流水线优化

GPU引擎使用异步私钥生成技术：
- GPU计算当前批次时，CPU并行生成下一批私钥
- 减少GPU等待时间，提高利用率

**效果**：吞吐量提升30-50%

### 2. 目标地址优化

```python
# 目标地址在初始化时预转换并上传到GPU
# 减少每次计算的传输开销

# 建议：目标地址数量 < 10,000
# 大量目标地址会降低GPU效率
```markdown

## 3. 超时保护

GPU引擎内置30秒超时机制：
- 防止GPU内核hang导致程序卡死
- 特别适用于Intel Arc GPU

```python
# 超时自动触发错误恢复
# 日志输出: "GPU执行超时(30秒)，可能存在内核hang问题"
```markdown

## 4. 性能监控

```python
# 启用监控系统查看GPU性能
from src.monitoring import EnhancedMonitoringSystem

monitor = EnhancedMonitoringSystem(engine, collection_interval=5)
monitor.start()

# 查看GPU错误统计
stats = engine.get_stats()
print(f"GPU错误数: {stats.gpu_errors}")
print(f"资源不足错误: {stats.resource_errors}")
```python

---

## 故障排除

### 问题1: GPU初始化失败

**症状**: `RuntimeError: GPU初始化失败`

**解决方案**:
```bash
# 1. 检查pyopencl安装
python -c "import pyopencl; print(pyopencl.__version__)"

# 2. 检查OpenCL设备
python -c "import pyopencl as cl; print(cl.get_platforms())"

# 3. 更新GPU驱动
# 访问GPU厂商官网下载最新驱动
```markdown

## 问题2: 显存不足

**症状**: `cl_out_of_resources` 或 `memory allocation failed`

**解决方案**:
```python
# 减小batch size
engine = GPUCollisionEngine(
    targets=targets,
    batch_size=50000  # 从默认值减小
)

# 或在config.json中设置
{
  "gpu": {
    "gpu_batch_size": 50000
  }
}
```yaml

## 问题3: GPU执行超时

**症状**: `GPU执行超时(30秒)`

**解决方案**:
1. 这是保护机制，不是错误
2. 引擎会自动恢复并继续
3. 如果频繁超时，尝试：
   - 减小batch size
   - 更新GPU驱动
   - 检查GPU散热

### 问题4: Intel Arc GPU Hang

**症状**: GPU卡死，程序无响应

**解决方案**:
```python
# GPU引擎已内置超时保护（30秒）
# 使用uint32替代uint8避免global char* hang bug

# 如果问题持续，尝试：
# 1. 更新Intel驱动到最新版本
# 2. 减小batch size到10000
# 3. 使用NVIDIA/AMD GPU替代
```markdown

## 问题5: 性能低于预期

**检查清单**:
- [ ] 是否使用了独立GPU（非集成显卡）
- [ ] batch size是否合适
- [ ] 目标地址数量是否过多（>10,000）
- [ ] 是否启用了异步流水线（默认启用）
- [ ] GPU驱动是否为最新版本

---

## 最佳实践

### 1. 设备选择

```python
# 优先级: NVIDIA > AMD > Intel Arc
# 系统会自动选择最佳设备，或手动指定：
device_index = 0  # 通常NVIDIA是第一个设备
```markdown

## 2. Batch Size策略

```python
# 首次使用：自动计算
engine = GPUCollisionEngine(targets=targets)

# 性能测试后：手动调优
# 根据GPU显存和性能测试调整
optimal_batch_size = 200000  # 根据您的GPU调整
```markdown

## 3. 错误处理

```python
try:
    engine = create_collision_engine(targets, mode='gpu')
    engine.start(mode='random')
except RuntimeError as e:
    print(f"GPU不可用，回退到CPU: {e}")
    engine = create_collision_engine(targets, mode='cpu')
    engine.start(mode='random')
```markdown

### 4. 资源清理

```python
# 引擎停止时自动清理GPU资源
engine.stop()

# 手动清理（通常不需要）
if hasattr(engine, '_gpu_kernel'):
    engine._gpu_kernel.cleanup()
if hasattr(engine, '_gpu_device'):
    engine._gpu_device.cleanup()
```markdown

## 5. 长时间运行

```python
# 启用断点续传
engine = GPUCollisionEngine(
    targets=targets,
    checkpoint_enabled=True,
    checkpoint_interval=30  # 每30秒保存
)

# 意外中断后可恢复
# 重新启动时会自动检测断点文件
```python

---

## 技术架构

### GPU计算流程

```
1. 初始化阶段
   ├─ 检测GPU设备
   ├─ 选择最佳设备
   ├─ 创建OpenCL上下文
   └─ 编译内核程序

2. 目标地址准备
   ├─ 解析目标地址
   ├─ 提取Hash160
   └─ 上传到GPU缓冲区

3. 碰撞检测循环
   ├─ CPU生成私钥批次
   ├─ 上传私钥到GPU
   ├─ GPU并行计算
   ├─ 下载匹配结果
   └─ 处理匹配（WIF编码等）

4. 异步优化
   ├─ GPU计算批次N
   └─ CPU生成批次N+1（并行）
```markdown

### OpenCL内核优化

- **持久化缓冲区**: 避免频繁分配/释放
- **uint32优化**: 替代uint8，性能提升4倍
- **异步执行**: 减少CPU-GPU同步等待
- **超时保护**: 30秒超时防止hang

---

## 附录

### A. GPU设备检测脚本

```python
#!/usr/bin/env python3
"""检测系统可用的OpenCL GPU设备"""

import pyopencl as cl

print("=" * 60)
print("OpenCL GPU设备检测")
print("=" * 60)

for platform in cl.get_platforms():
    print(f"\n平台: {platform.get_info(cl.platform_info.NAME)}")
    print("-" * 60)
    
    for device in platform.get_devices():
        device_type = device.get_info(cl.device_info.TYPE)
        
        if device_type != cl.device_type.GPU:
            continue
        
        print(f"\n设备名称: {device.get_info(cl.device_info.NAME)}")
        print(f"厂商: {device.get_info(cl.device_info.VENDOR)}")
        print(f"显存: {device.global_mem_size / (1024**3):.2f} GB")
        print(f"计算单元: {device.max_compute_units}")
        print(f"最大工作项: {device.max_work_group_size}")

print("\n" + "=" * 60)
```markdown

### B. 性能基准测试

```python
import time
from src.collision import create_collision_engine

targets = {'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}

# CPU基准
print("CPU性能测试...")
cpu_engine = create_collision_engine(targets, mode='cpu')
cpu_engine.start(mode='random')
time.sleep(10)
cpu_stats = cpu_engine.get_stats()
print(f"CPU速度: {cpu_stats.speed:.0f} 次/秒")
cpu_engine.stop()

# GPU基准
print("\nGPU性能测试...")
gpu_engine = create_collision_engine(targets, mode='gpu')
gpu_engine.start(mode='random')
time.sleep(10)
gpu_stats = gpu_engine.get_stats()
print(f"GPU速度: {gpu_stats.speed:.0f} 次/秒")
gpu_engine.stop()

print(f"\n加速比: {gpu_stats.speed / cpu_stats.speed:.1f}x")
```

---

## 参考资源

- [OpenCL规范](https://www.khronos.org/opencl/)
- [PyOpenCL文档](https://documen.tician.de/pyopencl/)
- [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit)
- [AMD GPU驱动](https://www.amd.com/en/support)
- [性能优化指南](performance-optimization.md)

---

**文档版本**: v1.0  
**最后更新**: 2026-04-20  
**维护者**: AI Assistant
