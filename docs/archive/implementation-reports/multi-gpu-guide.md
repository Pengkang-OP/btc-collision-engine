# 多GPU模式使用指南

## 概述

BTC碰撞引擎现在支持完整的多GPU并行计算功能,采用**任务分割策略**,让多个GPU独立搜索不同的私钥范围,实现性能线性提升。

### 核心特性

- [OK_CHECK] **自动GPU选择** - 基于显存、计算单元、厂商的智能评分
- [OK_CHECK] **多GPU并行** - 支持NVIDIA/AMD/Intel异构混合
- [OK_CHECK] **智能负载均衡** - 按性能自动分配任务权重
- [OK_CHECK] **厂商特定优化** - 自动配置最优参数
- [OK_CHECK] **GUI/CLI支持** - 图形界面和命令行双支持

---

## 快速开始

### 1. 检测GPU设备

**命令行**:

```bash
python tools/gpu_cli.py list
```

**输出示例**:

```
检测到 2 个GPU设备:
============================================================
[STAR] GPU 1: Intel(R) Arc(TM) A770 Graphics
  厂商: INTEL
  显存: 15.56 GB
  计算单元: 512
  评分: 191.2
------------------------------------------------------------
   GPU 0: NVIDIA GeForce GTX 1660 Ti
  厂商: NVIDIA
  显存: 6.00 GB
  计算单元: 24
  评分: 81.2
```

### 2. 自动选择最佳GPU

```bash
python tools/gpu_cli.py auto
```

### 3. 测试多GPU模式

```bash
python tools/gpu_cli.py test-multi --gpu-count 2
```

### 4. 生成配置文件

```bash
# 自动生成多GPU配置
python tools/gpu_cli.py generate-config --mode multi --output config.multi.json
```

---

## 配置方式

### 方式1: 配置文件

编辑`config.json`:

```json
{
  "gpu": {
    "mode": "multi",
    "device_indices": [0, 1],
    "load_balancing": "performance",
    "auto_tuning": true,
    "per_device_config": {
      "0": {
        "batch_size": 65536,
        "work_group_size": 256
      },
      "1": {
        "batch_size": 131072,
        "work_group_size": 512
      }
    }
  }
}
```

**配置项说明**:

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| mode | string | GPU模式(auto/single/multi) | auto |
| device_indices | list | GPU索引列表 | [-1] |
| load_balancing | string | 负载策略(performance/equal) | performance |
| auto_tuning | bool | 自动调优 | true |
| per_device_config | dict | 每GPU独立配置 | {} |

### 方式2: 命令行

```bash
# 单GPU模式
python key_collision.py --gpu-mode single --gpu-devices 1

# 多GPU模式
python key_collision.py --gpu-mode multi --gpu-devices 0,1

# 指定负载策略
python key_collision.py --gpu-mode multi --gpu-devices 0,1 --gpu-load-balancing performance
```

### 方式3: GUI界面

启动GUI后,在"GPU设备选择"面板中:

1. 选择GPU模式(自动/单GPU/多GPU)
2. 从列表中选择GPU设备(多选)
3. 选择负载均衡策略
4. 点击"应用配置"

---

## GPU选择算法

### 评分公式

```
评分 = (显存_GB × 10 + 计算单元 × 0.05) × 厂商系数
```

### 厂商系数

| 厂商 | 系数 | 说明 |
|------|------|------|
| NVIDIA | 1.0 | 最优性能和兼容性 |
| AMD | 0.95 | 接近NVIDIA |
| Intel | 0.9 | 需要workarounds |
| Unknown | 0.8 | 保守估计 |

### 示例计算

**NVIDIA GTX 1660 Ti**:

- 显存: 6GB × 10 = 60
- CU: 24 × 0.05 = 1.2
- 厂商: 1.0
- **总分: 61.2**

**Intel Arc A770**:

- 显存: 16GB × 10 = 160
- CU: 512 × 0.05 = 25.6
- 厂商: 0.9
- **总分: 167.04** [STAR]

---

## 负载均衡策略

### 1. Performance(按性能)

根据GPU评分分配任务权重。

**示例**:

- GPU 0(61.2分): 27% 任务
- GPU 1(167.04分): 73% 任务

**适用场景**: 异构GPU环境,性能差异较大

### 2. Equal(平均分配)

所有GPU平均分配任务。

**示例**:

- GPU 0: 50% 任务
- GPU 1: 50% 任务

**适用场景**: 相同型号GPU,性能接近

---

## 厂商特定优化

### NVIDIA GPU

```python
{
    'batch_size': 131072,      # 128K
    'work_group_size': 512,
    'memory_usage_ratio': 0.7,
    'enable_async': True,
    'use_fast_math': True
}
```

**特点**:

- 大批次处理(128K-256K)
- 大工作组(512)
- 支持快速数学运算

### AMD GPU

```python
{
    'batch_size': 65536,       # 64K
    'work_group_size': 256,
    'memory_usage_ratio': 0.6,
    'enable_async': True,
    'use_fast_math': True
}
```

**特点**:

- 中等批次大小
- 中等工作组
- 某些型号需要禁用编译器优化

### Intel Arc GPU

```python
{
    'batch_size': 32768,       # 32K
    'work_group_size': 256,
    'memory_usage_ratio': 0.5,
    'enable_async': True,
    'use_fast_math': False,
    'use_uint32_workaround': True
}
```

**特点**:

- 较小批次(避免超时)
- **必须**启用uint32 workaround
- **必须**禁用快速数学运算(精度问题)
- **必须**启用异步执行

---

## 性能预期

### 单GPU性能

| GPU | 吞吐量 | 批次大小 |
|-----|--------|---------|
| NVIDIA GTX 1660 Ti | ~100K keys/s | 32K-64K |
| NVIDIA RTX 3080 | ~250K keys/s | 128K |
| Intel Arc A770 | ~200K keys/s | 32K-64K |
| AMD RX 6700 XT | ~220K keys/s | 64K |

### 多GPU性能

**理想加速比**: 接近线性

| 配置 | 预期吞吐量 | 加速比 |
|------|-----------|--------|
| 1x GTX 1660 Ti | 100K | 1.0x |
| 2x GTX 1660 Ti | 190K | 1.9x |
| GTX 1660 Ti + Arc A770 | 300K | 3.0x |
| 2x Arc A770 | 400K | 4.0x |

**注意**: 实际性能受以下因素影响:

- PCIe带宽
- CPU调度能力
- 内存带宽
- 目标地址数量

---

## 故障排除

### 问题1: 未检测到GPU

**症状**: `未检测到GPU设备`

**解决方案**:

1. 检查GPU驱动是否安装

   ```bash
   nvidia-smi  # NVIDIA
   clinfo      # OpenCL
   ```

2. 安装pyopencl

   ```bash
   pip install pyopencl
   ```

3. 检查GPU是否支持OpenCL

### 问题2: 多GPU性能不佳

**症状**: 多GPU加速比远低于预期

**解决方案**:

1. 检查负载均衡策略
   - 异构GPU使用`performance`
   - 同构GPU使用`equal`

2. 检查批次大小
   - 显存不足: 减小batch_size
   - GPU利用率低: 增大batch_size

3. 检查PCIe带宽
   - 使用PCIe 3.0 x16或更高
   - 避免使用PCIe 1.0插槽

### 问题3: Intel Arc GPU崩溃

**症状**: Intel Arc运行时报错

**解决方案**:

1. 确保启用uint32 workaround

   ```json
   "per_device_config": {
     "1": {
       "use_uint32_workaround": true
     }
   }
   ```

2. 禁用快速数学运算

   ```json
   "use_fast_math": false
   ```

3. 减小批次大小

   ```json
   "batch_size": 32768
   ```

### 问题4: 显存不足

**症状**: `Out of resources` 或 `CL_MEM_OBJECT_ALLOCATION_FAILURE`

**解决方案**:

1. 减小批次大小

   ```json
   "batch_size": 16384
   ```

2. 降低显存使用率

   ```json
   "memory_usage_ratio": 0.5
   ```

3. 关闭其他GPU应用

---

## 高级配置

### 动态负载重平衡

多GPU引擎每60秒自动评估实际性能,重新分配负载。

**配置**:

```python
from src.gpu.load_balancer import GPULoadBalancer

balancer = GPULoadBalancer(
    devices=devices,
    strategy='performance',
    rebalance_interval=60  # 60秒重平衡一次
)
```

### 手动配置每GPU参数

```json
{
  "gpu": {
    "auto_tuning": false,
    "per_device_config": {
      "0": {
        "batch_size": 65536,
        "work_group_size": 256,
        "memory_usage_ratio": 0.6
      },
      "1": {
        "batch_size": 131072,
        "work_group_size": 512,
        "memory_usage_ratio": 0.7
      }
    }
  }
}
```

### 编程方式使用多GPU

```python
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

# 创建引擎
engine = MultiGPUCollisionEngine()

# 初始化(使用2个最佳GPU)
engine.initialize(device_count=2, strategy='performance')

# 启动碰撞
engine.start(
    targets=target_addresses,
    mode='random',
    total_keys=10000000
)

# 获取统计
stats = engine.get_combined_stats()
print(f"总吞吐量: {stats['combined_throughput']:,.0f} keys/s")

# 停止
engine.stop()
```

---

## 最佳实践

1. **选择GPU**: 优先使用显存大、计算单元多的GPU
2. **负载策略**: 异构用performance,同构用equal
3. **批次大小**: 根据显存自动调整,通常32K-128K
4. **厂商优化**: 启用auto_tuning,自动应用最佳配置
5. **监控性能**: 定期检查各GPU吞吐量,确保负载均衡

---

## 技术支持

- **文档**: docs/multi-gpu-guide.md
- **CLI工具**: python tools/gpu_cli.py --help
- **测试**: python tests/test_multi_gpu.py
- **问题反馈**: GitHub Issues

---

**更新日期**: 2026-04-22  
**版本**: v2.0.0
