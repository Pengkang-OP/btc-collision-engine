# BTC碰撞引擎 - GPU加速配置指南

**版本**: v5.0.0

## 目录
1. [GPU环境概述](#gpu环境概述)
2. [快速开始](#快速开始)
3. [配置模板](#配置模板)
4. [Intel Arc A770 优化配置](#intel-arc-a770-优化配置)
5. [性能调优](#性能调优)
6. [常见问题](#常见问题)

---

## GPU环境概述

### 系统检测到的GPU设备

| 设备 | 厂商 | 计算单元 | 显存 | 推荐用途 |
|------|------|---------|------|---------|
| **Intel Arc A770 Graphics** | Intel | 512 | 15.56 GB | [STAR] **首选** (最高性能) |
| NVIDIA GeForce GTX 1660 Ti | NVIDIA | 24 | 6.00 GB | 备用GPU |
| AMD Ryzen 7 5700X (CPU) | AMD | 16 | 31.91 GB | 仅测试用 |

### pyopencl状态
- [OK] 已安装: 版本 2026.1.2
- [OK] OpenCL平台: 3个
- [OK] 驱动: OpenCL 3.0 CUDA 13.2.73 (NVIDIA), OpenCL 3.0 NEO (Intel)

---

## 快速开始

### 1. 验证GPU环境
```bash
cd f:\Qoder\btc-collision-engine
python -c "import pyopencl as cl; platforms = cl.get_platforms(); print(f'检测到 {len(platforms)} 个OpenCL平台')"
```

### 2. 运行GPU测试 (60秒)
```bash
set PYTHONPATH=%CD%
python scripts/testing/test_gpu_collision_actual.py
```

### 3. 启用GPU模式运行引擎
```bash
python key_collision_cli.py -t <目标地址> -m random --use-gpu --duration 60
```

---

## 配置模板

### 模板 1: quick-test.json (最小化配置)
**用途**: 快速烟雾测试,资源占用最小

```json
{
    "version": "5.0.0",
    "engine": {
        "mode": "random",
        "batch_size": 500,
        "max_threads": 2
    },
    "collision": {
        "max_workers": 2,
        "progress_interval": 1,
        "dedup_max_size": 10000
    },
    "logging": {
        "level": "WARNING",
        "format": "minimal"
    },
    "gpu": {
        "device_index": -1,
        "batch_size": 1024
    },
    "optimization": {
        "uint32_workaround": false,
        "async_transfer": false
    }
}
```

**运行命令**:
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --template quick-test --duration 10
```

---

### 模板 2: gpu-performance.json (高性能配置)
**用途**: 单GPU最大性能优化

```json
{
    "version": "5.0.0",
    "engine": {
        "mode": "random",
        "batch_size": 2097152,
        "max_threads": 4
    },
    "collision": {
        "max_workers": 4,
        "progress_interval": 1000,
        "dedup_max_size": 1000000,
        "use_performance_optimization": true,
        "precomputed_window_size": 8,
        "use_simd_hash": true,
        "use_memory_pool": true,
        "use_gpu_memory_pool": true
    },
    "gpu": {
        "use_gpu": true,
        "device_index": -1,
        "batch_size": 2097152,
        "auto_detect": true,
        "memory_usage_ratio": 0.75,
        "enable_vendor_optimizations": true,
        "queue_depth": 8,
        "use_new_module": true,
        "async_execution": true,
        "seed_prefetch_size": 64,
        "timeout_protection": true,
        "base_timeout_seconds": 30,
        "max_error_retries": 100,
        "gpu_memory_pool": true,
        "max_buffers": 100,
        "max_memory_mb": 8192,
        "mode": "auto",
        "work_group_size": 256,
        "use_fast_math": true,
        "use_uint32_workaround": false,
        "driver_check": {
            "enabled": true,
            "require_minimum_version": true,
            "warn_on_unstable": true,
            "auto_fallback_conservative": true
        },
        "key_generation_strategy": "PRNG_SEED"
    },
    "optimization": {
        "uint32_workaround": true,
        "disable_async_transfer": false,
        "conservative_memory_policy": false,
        "adaptive_timeout": true
    }
}
```

**运行命令**:
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --template gpu-performance --use-gpu --duration 300
```

---

### 模板 3: gpu-multi.json (多GPU配置)
**用途**: 多GPU并行计算

```json
{
    "version": "5.0.0",
    "engine": {
        "mode": "random",
        "batch_size": 1048576,
        "max_threads": 8
    },
    "collision": {
        "max_workers": 8,
        "progress_interval": 500,
        "dedup_max_size": 500000
    },
    "gpu": {
        "use_gpu": true,
        "multi_gpu": true,
        "device_index": -1,
        "batch_size": 1048576,
        "auto_detect": true,
        "memory_usage_ratio": 0.7,
        "enable_vendor_optimizations": true,
        "queue_depth": 16,
        "async_execution": true,
        "seed_prefetch_size": 128,
        "gpu_memory_pool": true,
        "max_memory_mb": 4096
    },
    "optimization": {
        "uint32_workaround": true,
        "adaptive_timeout": true
    }
}
```

**运行命令**:
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --template gpu-multi --multi-gpu --duration 600
```

---

### 模板 4: long-running.json (长时间运行配置)
**用途**: 生产环境长时间运行

```json
{
    "version": "5.0.0",
    "engine": {
        "mode": "random",
        "batch_size": 1048576,
        "max_threads": 4
    },
    "collision": {
        "max_workers": 4,
        "progress_interval": 5000,
        "dedup_max_size": 5000000,
        "use_gpu_memory_pool": true
    },
    "logging": {
        "level": "WARNING",
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "file": "logs/collision.log",
        "max_bytes": 104857600,
        "backup_count": 10,
        "enable_console": false,
        "enable_file": true
    },
    "gpu": {
        "use_gpu": true,
        "device_index": -1,
        "batch_size": 1048576,
        "memory_usage_ratio": 0.8,
        "queue_depth": 12,
        "async_execution": true,
        "timeout_protection": true,
        "base_timeout_seconds": 60,
        "gpu_memory_pool": true,
        "max_memory_mb": 8192
    }
}
```

**运行命令**:
```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --template long-running --use-gpu --checkpoint --checkpoint-interval 60 --duration 0
```

---

## Intel Arc A770 优化配置

### 推荐配置 (基于实际测试)

**文件**: `config.json` (项目根目录)

```json
{
    "version": "5.0.0",
    "engine": {
        "mode": "random",
        "batch_size": 2097152,
        "max_threads": 4
    },
    "collision": {
        "max_workers": 4,
        "progress_interval": 1000,
        "dedup_max_size": 1000000
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/collision.log",
        "max_bytes": 52428800,
        "backup_count": 5
    },
    "gpu": {
        "use_gpu": true,
        "device_index": -1,
        "batch_size": 262144,
        "memory_usage_ratio": 0.7,
        "enable_vendor_optimizations": true,
        "queue_depth": 32,
        "async_execution": true,
        "seed_prefetch_size": 256,
        "timeout_protection": true,
        "base_timeout_seconds": 30,
        "gpu_memory_pool": true,
        "max_memory_mb": 10240,
        "work_group_size": 256,
        "use_fast_math": true,
        "use_uint32_workaround": true,
        "driver_check": {
            "enabled": true,
            "require_minimum_version": true,
            "warn_on_unstable": true,
            "auto_fallback_conservative": true
        }
    },
    "optimization": {
        "uint32_workaround": true,
        "disable_async_transfer": false,
        "adaptive_timeout": true
    }
}
```

### 关键优化参数说明

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `device_index` | -1 | 自动选择最佳GPU (Intel Arc A770) |
| `batch_size` | 262144-2097152 | 批次大小,越大吞吐量越高 |
| `memory_usage_ratio` | 0.7 | 使用70%显存,留有余量 |
| `queue_depth` | 32 | 异步队列深度,平衡延迟和吞吐 |
| `seed_prefetch_size` | 256 | 种子预生成缓存深度,消除CPU-GPU同步瓶颈 |
| `use_uint32_workaround` | true | **Intel必须启用**,避免Arc GPU hang |
| `async_execution` | true | 双缓冲优化,提高GPU利用率 |
| `timeout_protection` | true | 超时保护,防止GPU卡死 |
| `driver_check.enabled` | true | 启用驱动检查,自动检测不稳定驱动 |

---

## 性能调优

### 基准性能指标

基于Intel Arc A770 (15.56GB显存, 512计算单元):

| 配置 | 批次大小 | 队列深度 | 预期性能 |
|------|---------|---------|---------|
| 快速测试 | 262,144 | 32 | ~500K-1M keys/s |
| 性能优化 | 2,097,152 | 32 | ~2-4M keys/s |
| 极限配置 | 8,388,608 | 64 | ~5-8M keys/s |

**实测数据**:
- 初始化耗时: ~74秒 (首次编译OpenCL内核)
- 动态基准: 2,204,266 keys/s
- 60秒测试处理: 271,319,040 keys (2.7亿)

### 性能优化建议

1. **批次大小调优**
   ```bash
   # 小批次低延迟
   python key_collision_cli.py -t <addr> --use-gpu --batch-size 262144 --duration 60

   # 大批次高吞吐
   python key_collision_cli.py -t <addr> --use-gpu --batch-size 4194304 --duration 60
   ```

2. **队列深度调整**
   ```bash
   # 低延迟模式
   python key_collision_cli.py -t <addr> --use-gpu --queue-depth 16 --duration 60

   # 高吞吐模式
   python key_collision_cli.py -t <addr> --use-gpu --queue-depth 64 --duration 60
   ```

3. **多GPU并行**
   ```bash
   # 使用所有GPU
   python key_collision_cli.py -t <addr> --multi-gpu --duration 600

   # 指定特定GPU
   python key_collision_cli.py -t <addr> --use-gpu --device-index 0 --duration 60
   ```

---

## 常见问题

### Q1: GPU测试超时或初始化失败

**原因**: OpenCL内核编译时间过长 (首次可能需要60-90秒)

**解决方案**:
1. 增加超时设置
2. 预热GPU (运行一次短测试)
3. 检查GPU驱动是否最新

```bash
# 预热GPU
python key_collision_cli.py -t <addr> --use-gpu --duration 10

# 再次运行正式测试
python key_collision_cli.py -t <addr> --use-gpu --duration 300
```

### Q2: 性能报告生成器错误

**错误信息**:
```
TypeError: PerformanceReportGenerator.__init__() got an unexpected keyword argument 'gpu_engine'
```

**状态**: 非致命错误,仅影响部分监控功能,引擎核心功能正常运行

**解决方案**: 可忽略,或等待后续版本修复

### Q3: GPU内存不足

**错误信息**:
```
OutOfResourcesError: clEnqueueNDRangeKernel failed: out of resources
```

**解决方案**:
1. 减少批次大小
2. 降低memory_usage_ratio
3. 关闭其他占用GPU的程序

```bash
# 减小批次
python key_collision_cli.py -t <addr> --use-gpu --batch-size 262144 --duration 60
```

### Q4: Intel Arc GPU未检测到

**检查步骤**:
1. 验证Intel OpenCL运行时已安装
2. 检查GPU驱动版本
3. 确认GPU未被其他程序占用

```bash
# 检查OpenCL平台
python -c "import pyopencl as cl; [print(p.name) for p in cl.get_platforms()]"
```

### Q5: GPU初始化时间过长

**原因**: 首次运行时需要编译OpenCL内核

**优化**: 使用缓存的内核

```bash
# 创建内核缓存
python scripts/testing/test_gpu_collision_actual.py --warmup
```

---

## 验证清单

运行GPU测试前请确认:

- [ ] pyopencl已安装 (`python -c "import pyopencl"`)
- [ ] GPU驱动已更新
- [ ] 系统有足够的GPU显存 (至少4GB可用)
- [ ] 已设置PYTHONPATH环境变量
- [ ] config.json中gpu.use_gpu=true

---

## 性能对比

| 模式 | 速度 | 适用场景 |
|------|------|---------|
| CPU模式 | ~88 keys/s | 测试/调试 |
| GPU快速 | ~1M keys/s | 短时间搜索 |
| GPU性能 | ~2-4M keys/s | 常规生产 |
| GPU极限 | ~5-8M keys/s | 大规模搜索 |

---

## 后续步骤

1. **立即测试**:
   ```bash
   cd f:\Qoder\btc-collision-engine
   set PYTHONPATH=%CD%
   python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --use-gpu --duration 60
   ```

2. **性能基准测试**:
   ```bash
   python scripts/testing/test_gpu_collision_actual.py
   ```

3. **配置优化**: 根据上述指南调整config.json

4. **生产部署**: 使用long-running.json模板启用长时间运行

---

**文档版本**: 1.0
**更新日期**: 2026-05-26
**适用硬件**: Intel Arc A770 / NVIDIA GPU / 多GPU系统
