# GPU性能监控系统使用说明

## 概述

GPU性能监控系统为BTC Collision Engine提供完整的GPU硬件利用率、性能分析和自适应优化功能。

## 功能特性

### 1. GPU硬件监控
- **GPU利用率** - 实时监控GPU计算使用率
- **显存使用** - 监控显存占用情况
- **温度监控** - 实时GPU温度
- **功耗监控** - GPU功耗监测

### 2. 性能分析
- 内核执行时间和吞吐量
- 错误率监控
- 性能退化检测
- 自适应batch_size调整

### 3. 兼容性
- NVIDIA GPU (pynvml)
- AMD GPU (pyamdgpuinfo, 预留接口)
- Intel Arc GPU (预留接口)

## 快速开始

### 1. 安装依赖

#### NVIDIA GPU
```bash
pip install pynvml
```

#### AMD GPU
```bash
pip install pyamdgpuinfo
```

### 2. 基本使用

#### 方式一：使用独立监控器
```python
from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

# 创建监控器
monitor = GPUPerformanceMonitor(check_interval=2.0)

# 启动监控
monitor.start()

# 获取实时统计
stats = monitor.get_stats()
print(f"GPU利用率: {stats['avg_gpu_utilization'] * 100:.1f}%")
print(f"温度: {stats['avg_temperature']:.1f}°C")
print(f"吞吐量: {stats['current_throughput']:.0f} keys/s")

# 停止监控
monitor.stop()
```

#### 方式二：与GPU引擎集成
```python
from src.collision.gpu.engine import GPUCollisionEngine
from src.monitoring.gpu_performance_monitor import GPUPerformanceMonitor

# 创建引擎
engine = GPUCollisionEngine(targets={"target1", "target2"})

# 创建并启动监控
monitor = GPUPerformanceMonitor(engine=engine)
monitor.start()

# 启动搜索
engine.start(mode="random")

# 获取性能数据
stats = monitor.get_stats()

# 清理
engine.stop()
monitor.stop()
```

### 3. 运行示例

```bash
# 运行独立GPU监控示例
python gpu_monitoring_example.py
```

## 统计数据说明

### get_stats() 返回字段

| 字段 | 说明 | 单位 |
|------|------|
| avg_gpu_utilization | 平均GPU利用率 | 0.0-1.0 |
| avg_memory_used_mb | 平均已用显存 | MB |
| avg_temperature | 平均GPU温度 | °C |
| avg_power_usage_w | 平均功耗 | W |
| current_throughput | 当前吞吐量 | keys/s |
| avg_throughput | 平均吞吐量 | keys/s |
| total_batches | 总批次数 | - |
| total_keys_processed | 总处理密钥数 | - |
| total_errors | 总错误数 | - |
| memory_usage | 显存详细信息 | dict |
| device_name | GPU设备名称 | - |
| vendor | GPU厂商 | - |
| hardware_monitoring_active | 硬件监控是否活跃 | bool |

## 自适应优化

### GPU引擎会根据GPU利用率自动调整batch_size：

```python
# 当GPU利用率 < 50% 时:
#   - 自动增大 batch_size
# 当错误率 > 1% 时:
#   - 自动减小 batch_size
```

### 手动优化

```python
# 设置监控回调
def on_degradation(metrics, ratio):
    print(f"性能退化: {ratio * 100:.1f}%")

monitor.on_degradation(on_degradation)
```

## 故障排除

### GPU利用率低 (< 50%

可能原因：
1. batch_size太小
2. CPU处理瓶颈
3. 数据传输瓶颈

解决方案：
- 增大batch_size
- 使用异步执行
- 启用共享内存优化

### 显存溢出

可能原因：
1. batch_size太大
2. 多个程序同时运行

解决方案：
- 减小batch_size
- 关闭其他GPU程序

### 温度过高 (> 85°C

可能原因：
1. 散热不良
2. 超频

解决方案：
- 减少GPU功耗
- 检查散热器
- 改善通风

## 完整监控流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    GPU性能监控系统架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐       ┌──────────────┐      ┌──────────────┐    │
│  │ 硬件监控  │       │  内核监控   │      │  性能分析   │    │
│  │  (pynvml) │───────│   (OpenCL)  │─────│  (自适应)  │    │
│  └──────────────┘       └──────────────┘      └──────────────┘    │
│         │                   │                   │            │    │
│         ▼                   ▼                   ▼            │    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              事件总线 & 监控管道                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 性能基准

### 推荐的GPU性能参考：

| GPU型号 | 预期吞吐量 | 功耗 | 温度 |
|---------|-----------|------|
| NVIDIA RTX 4090 | 1-2亿 keys/s | 300-450W | 70-85°C |
| NVIDIA RTX 3090 | 5000万-1亿 keys/s | 280-350W | 65-80°C |
| AMD RX 7900 XTX | 8000万-1.5亿 keys/s | 300-355W | 70-85°C |
| Intel Arc A770 | 2000万-5000万 keys/s | 200-225W | 65-80°C |

## 更新日志

### v4.2 (2026-05-11
- ✅ 添加真实GPU硬件利用率监控
- ✅ NVIDIA GPU监控初始化
- ✅ GPU温度、功耗、显存监控
- ✅ 独立GPU监控示例
- ✅ 监控管道集成
