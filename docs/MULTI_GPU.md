# 多 GPU 使用指南

**版本**: v4.5.1

本文档说明如何在多块 GPU 的系统上配置和运行 BTC 碰撞引擎。

---

## 目录

1. [系统要求](#系统要求)

2. [查看可用 GPU 设备](#查看可用-gpu-设备)

3. [配置多 GPU](#配置多-gpu)

4. [启动多 GPU 模式](#启动多-gpu-模式)

5. [负载均衡策略](#负载均衡策略)

6. [性能调优](#性能调优)

7. [故障排除](#故障排除)

---

## 系统要求

- **Python** >= 3.7

- **PyOpenCL** >= 2020.1

- **多块 GPU**，每块均需安装对应 OpenCL 驱动

- **系统内存** >= 4 GB（多 GPU 并发时建议 8 GB+）

---

## 查看可用 GPU 设备

运行以下命令列出系统中所有支持 OpenCL 的 GPU：

```bash
python -c "
import pyopencl as cl
for i, platform in enumerate(cl.get_platforms()):
    print(f'Platform {i}: {platform.name}')
    for j, device in enumerate(platform.get_devices()):
        mem_mb = device.global_mem_size // (1024*1024)
        print(f'  Device {j}: {device.name}  ({mem_mb} MB VRAM)')
"

```

示例输出：

```python
Platform 0: Intel(R) OpenCL Graphics
  Device 0: Intel(R) Arc(TM) A770 Graphics  (16384 MB VRAM)
Platform 1: NVIDIA CUDA
  Device 0: NVIDIA GeForce RTX 3080  (10240 MB VRAM)

```

---

## 配置多 GPU

编辑 `config.json`，在 `gpu` 节中指定设备：

### 方案一：自动选择最优 GPU（推荐）

```json
{
  "gpu": {
    "use_gpu": true,
    "auto_detect": true,
    "batch_size": 65536,
    "enable_vendor_optimizations": true
  }
}

```

> `auto_detect: true` 时，系统会自动选择性能最强的单 GPU。

### 方案二：指定单个 GPU

```json
{
  "gpu": {
    "use_gpu": true,
    "auto_detect": false,
    "device_index": 1,
    "batch_size": 131072
  }
}

```

### 方案三：启用多 GPU 并行（多卡系统）

通过代码接口启用多 GPU 引擎（`MultiGPUCollisionEngine`）：

```python
from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

engine = MultiGPUCollisionEngine(config={
    "batch_size": 65536,
    "enable_data_monitor": True,
})

# 初始化，自动选择 2 块最佳 GPU
engine.initialize(device_count=2)

# 启动碰撞搜索
engine.start(
    targets={"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    mode="random",
    match_callback=lambda match: print(f"命中: {match}")
)

# 查看汇总统计
stats = engine.get_combined_stats()
print(stats)

# 停止
engine.stop()

```

---

## 启动多 GPU 模式

也可以通过 CLI 的 `--workers` 参数并结合多 GPU 配置文件启动：

```bash
# 使用多 GPU 配置文件
copy config.multi_gpu.json config.json

# 启动 CLI（multi_gpu 模式需通过代码接口）
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --workers 4

```

---

## 负载均衡策略

多 GPU 引擎使用 `GPULoadBalancer` 自动分配任务：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 均等分割 | 每块 GPU 分到相同数量的密钥范围 | 各卡性能相近 |
| 性能加权 | 按 GPU 算力比例分配工作量 | 混合型 GPU（如 Arc + RTX）|
| 动态重均衡 | 运行时检测各 GPU 吞吐量，自动迁移负载 | 长时间运行任务 |

调整均衡策略（在 `config.json` 中）：

```json
{
  "gpu": {
    "load_balance_strategy": "performance_weighted"
  }
}

```

---

## 性能调优

### 按 GPU 显存选择 batch_size

| GPU VRAM | 推荐 batch_size |
|----------|----------------|
| <= 4 GB  | 32768          |
| 6~8 GB   | 65536          |
| 10~12 GB | 131072         |
| >= 16 GB | 262144         |

### Intel Arc + NVIDIA 混合环境

```json
{
  "gpu": {
    "use_gpu": true,
    "auto_detect": true,
    "batch_size": 65536,
    "memory_usage_ratio": 0.6,
    "enable_vendor_optimizations": true
  }
}

```

> Intel Arc 建议将 `memory_usage_ratio` 设为 0.45 以避免显存耗尽。

### 减少线程竞争

多 GPU 时减少 CPU 工作线程数，避免线程竞争：

```json
{
  "collision": {
    "max_workers": 4
  }
}

```

---

## 故障排除

### 仅一块 GPU 工作

- 确认所有 GPU 驱动都支持 OpenCL（用上面的查询命令验证）

- 检查 `device_count` 参数是否 >= 2

- 查看日志中是否有 GPU 初始化失败的 `ERROR` 信息

### 多 GPU 模式下速度没有成比例提升

- 检查是否存在 CPU 瓶颈（`max_workers` 设置过高）

- 降低单卡 `batch_size`，减少 GPU 内存传输延迟

- 确认各卡 VRAM 未接近上限

### MemoryError / 显存不足

引擎在检测到 `MemoryError` 时会自动将 `batch_size` 减半并重试。如果频繁触发，请手动降低：

```json
{
  "gpu": {
    "batch_size": 32768,
    "memory_usage_ratio": 0.4
  }
}

```

---

> 更多配置选项参考 [CONFIG.md](CONFIG.md)，故障排除参考 [FAQ.md](FAQ.md)。
