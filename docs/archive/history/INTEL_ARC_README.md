# Intel Arc A770 GPU 优化指南

## 快速开始

### 方法 1: 使用优化脚本 (推荐)

```bash
# Windows: 双击运行
optimize_arc.bat

# 然后运行主程序
python key_collision_cli.py --targets targets.txt --device 1
```

### 方法 2: Python 导入

```python
from optimize_intel_arc import setup_arc_environment, get_arc_optimization_report

# 在程序开始时调用
setup_arc_environment()
print(get_arc_optimization_report())
```

### 方法 3: 环境变量手动设置

```bash
# Windows PowerShell
$env:SYCL_DEVICE_FILTER = "opencl:gpu"
$env:INTEL_XESS_MEMORY_COMPRESSION = "1"

# Linux/macOS
export SYCL_DEVICE_FILTER=opencl:gpu
export INTEL_XESS_MEMORY_COMPRESSION=1
```

---

## 配置文件

编辑 `config.json` 中的 GPU 配置:

```json
{
  "gpu": {
    "async_execution": true,
    "queue_depth": 14,
    "memory_usage_ratio": 0.70,
    "per_device_config": {
      "1": {
        "_comment": "Intel Arc A770 16GB",
        "batch_size": 1572864,
        "work_group_size": 256,
        "queue_depth": 12,
        "memory_usage_ratio": 0.70
      }
    }
  }
}
```

---

## BIOS 设置

### 必须设置
| 选项 | 值 | 说明 |
|------|-----|------|
| Above 4G Decoding | Enabled | 必需，否则显存无法完整映射 |
| Resizable BAR | Enabled | 推荐，+5% 性能 |
| CSM | Disabled | 禁用以启用 UEFI |

### 可选设置
| 选项 | 值 | 说明 |
|------|-----|------|
| C-State | Enabled | 空闲省电 |
| P-State | Default | 保持默认 |

---

## 预期性能

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| GPU 利用率 | 18% | 30-50% | +70-180% |
| 吞吐量 | 500万/s | 800-1500万/s | +60-200% |
| 内核延迟 | 基准 | -12% | 更快 |

---

## 驱动版本

### 推荐版本
- **32.0.101.8724** (最新)
- **32.0.101.5500** (稳定)

### 获取驱动
https://www.intel.com/content/www/cn/zh/products/sku/229151/intel-arc-a770-graphics-16gb/downloads.html

---

## 故障排除

### GPU 利用率仍然很低
1. 检查是否使用了优化脚本
2. 尝试增大 `batch_size` 到 2,097,152
3. 检查 CPU 是否成为瓶颈

### 程序崩溃/冻结
1. 确保驱动是最新版本
2. 检查 `Above 4G Decoding` 是否启用
3. 查看 `INTEL_ARC_DEEP_ANALYSIS.md` 了解已知问题

### 性能持续退化
1. 重启程序
2. 更新驱动
3. 检查 GPU 温度 (应 < 85°C)

---

## 更多信息

详细的分析和优化指南请参考:
- [深度分析文档](INTEL_ARC_DEEP_ANALYSIS.md)
- [GPU 监控指南](GPU_MONITORING.md)
