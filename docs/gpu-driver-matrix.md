# GPU 驱动兼容矩阵

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

## 概述

本文档记录了 BTC Collision Engine 支持的所有 GPU 平台及其驱动兼容性信息。

## GPU 兼容矩阵

| GPU 厂商 | 架构 | 最低驱动版本 | OpenCL 版本 | 性能等级 | 备注 |
|---------|------|------------|------------|---------|------|
| **NVIDIA** | CUDA | 11.0+ | 1.2+ | ***** | 首选平台 |
| **AMD** | RDNA 1/2/3 | 21.x+ | 1.2+ | **** | Linux 推荐 ROCm |
| **Intel** | Arc/Xe | 31.0.101.4146+ | 1.2+ | **** | ARC 系列性能优异 |
| **Intel** | UHD/HD | 最新驱动 | 1.2+ | ** | 仅测试用 |

## 详细驱动要求

### NVIDIA GPU

| GPU 系列 | 最低 CUDA | 推荐 CUDA | 实测速度 (keys/s) |
|---------|----------|----------|------------------|
| GeForce GTX 16xx | 11.0 | 11.4+ | ~500K |
| GeForce RTX 20xx | 11.0 | 11.4+ | ~800K |
| GeForce RTX 30xx | 11.0 | 11.4+ | ~1.5M |
| GeForce RTX 40xx | 11.0 | 12.0+ | ~2.5M+ |

**驱动安装**:

- Windows: [NVIDIA 驱动下载](https://www.nvidia.com/Download/index.aspx)

- Linux: `sudo apt install nvidia-driver-535` (Ubuntu) 或 `sudo dnf install akmod-nvidia` (Fedora)

**验证命令**:

```bash
nvidia-smi
python -c "import pyopencl; print([d.name for p in pyopencl.get_platforms() for d in p.get_devices()])"

```

### AMD GPU

| GPU 系列 | 最低驱动 | 推荐驱动 | 实测速度 (keys/s) |
|---------|---------|---------|------------------|
| RX 5000 (RDNA 1) | 21.x | 23.x+ | ~400K |
| RX 6000 (RDNA 2) | 21.x | 23.x+ | ~600K |
| RX 7000 (RDNA 3) | 23.x | 24.x+ | ~800K |

**驱动安装**:

- Windows: [AMD 驱动下载](https://www.amd.com/en/support)

- Linux (Ubuntu/Debian): `sudo apt install mesa-opencl-icd`

- Linux (Fedora): `sudo dnf install mesa-libOpenCL`

### Intel GPU

| GPU 系列 | 最低驱动 | 推荐驱动 | 实测速度 (keys/s) |
|---------|---------|---------|------------------|
| Arc A770 | 31.0.101.4146 | 31.0.101.xxxx | **4.89M keys/s** |
| Arc A750 | 31.0.101.4146 | 31.0.101.xxxx | ~3.5M |
| Arc A380 | 31.0.101.4146 | 31.0.101.xxxx | ~1.5M |
| UHD 7xx | 最新 | 最新 | ~50K |
| UHD 6xx | 最新 | 最新 | ~30K |

**驱动安装**:

- Windows: [Intel 驱动下载](https://www.intel.com/content/www/us/en/download-center/home.html)

- Linux: `sudo apt install intel-opencl-icd` (Ubuntu)

- [Intel Arc 优化指南](intel-arc-gpu-compatibility-research.md)

## 多 GPU 配置

| 配置 | 支持 | 说明 |
|------|------|------|
| 多块同型号 GPU | [OK] | 负载均衡 |
| 多块不同型号 GPU | [WARN] | 可能性能不均衡 |
| NVIDIA + AMD 混合 | [FAIL] | OpenCL 平台冲突 |
| GPU + CPU 混合 | [OK] | HybridCollisionEngine |

## 常见问题

### Q: 如何检测 GPU 设备？

```bash
python -c "import pyopencl as cl; [print(d.name) for p in cl.get_platforms() for d in p.get_devices()]"

```

### Q: GPU 初始化失败怎么办？

1. 检查是否安装了 `pyopencl`

2. 检查 GPU 驱动是否正确安装

3. 运行 `python -m src.utils.health_check --gpu`

4. 查看 [故障排查文档](../troubleshooting.md)

### Q: 性能低于预期？

1. 检查 batch_size 配置 (推荐 1,048,576)

2. 启用异步执行 (`async_execution: true`)

3. 检查 GPU 温度和频率 (可能过热降频)

4. 参考 [性能优化指南](../performance-optimization.md)

## 相关文档

- [GPU 引擎使用指南](../gpu-engine-guide.md)

- [性能优化指南](../performance-optimization.md)

- [故障排查文档](../troubleshooting.md)

- [Intel Arc 兼容性](../intel-arc-gpu-compatibility-research.md)

- [环境变量配置](../environment/environment-variables.md)
