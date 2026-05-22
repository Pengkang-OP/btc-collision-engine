# BTC碰撞引擎完整启动指南

**版本**: v4.5.1


## 概述

本脚本实现了完整的BTC碰撞引擎启动流程，包括：

- ✅ 从文件加载目标比特币地址
- ✅ 地址格式验证和过滤
- ✅ GPU加速的随机碰撞模式
- ✅ 端到端性能监控系统
- ✅ 实时异常检测和告警
- ✅ 完整的日志记录系统

## 快速开始

### 1. 基本使用

```bash
python key_collision_cli.py
```

这将：

- 启动交互式命令行向导
- 支持随机碰撞、范围扫描、暴力穷举三种模式
- 自动检测并启用 GPU 加速
- 提供完整的监控和日志记录

### 2. 指定运行时长

编辑脚本的 `main()` 函数：

```python
# 运行1小时
launcher.run(duration_seconds=3600)

# 运行30分钟
launcher.run(duration_seconds=1800)

# 无限运行
launcher.run(duration_seconds=None)
```

## 配置选项

### 修改目标地址文件

```python
# 在 main() 函数中修改
address_file = str(project_root / "your_address_file.txt")
```

### 配置GPU参数

```python
config = {
    'batch_size': None,      # None=自动计算，或指定具体值如 262144
    'device_index': -1,      # -1=自动选择，或指定GPU索引 0, 1, 2...
}
```

## 系统架构

### 核心组件

1. **BTCCollisionLauncher** - 主启动器
   - 地址加载和验证
   - GPU引擎初始化
   - 监控系统集成
   - 运行状态管理

2. **GPUCollisionEngine** - GPU碰撞引擎
   - OpenCL设备检测
   - 随机碰撞模式
   - 异步双缓冲执行
   - Intel GPU优化

3. **MonitoringSystem** - 监控系统
   - 性能数据采集（每5秒）
   - 异常检测
   - 告警生成
   - 报告生成

4. **DataLogger** - 数据日志系统
   - 当前状态记录
   - 历史数据保存
   - 性能日志
   - 错误追踪

## 监控数据文件

所有监控数据保存在 `data_logs/` 目录：

| 文件 | 说明 | 更新频率 |
|------|------|---------|
| `current_data.json` | 当前运行状态 | 每10秒 |
| `history_data.json` | 历史性能数据 | 每10秒 |
| `error_log.json` | 错误和异常记录 | 实时 |
| `performance.log` | 性能CSV日志 | 实时 |
| `alert_history.json` | 告警历史记录 | 实时 |
| `report_daily_*.json` | 每日性能报告 | 每小时 |

### 查看当前状态

```bash
# Windows PowerShell
Get-Content data_logs\current_data.json | ConvertFrom-Json | Format-List

# 或查看JSON文件
cat data_logs\current_data.json
```

### 示例输出

```json
{
  "saved_at": "2026-04-24T04:13:08.684324",
  "uptime": 8811.05,
  "performance": {
    "speed": 125000.5,
    "total_checked": 1000000000,
    "matches_found": 0,
    "cpu_usage": 45.2,
    "memory_usage": 256.5,
    "thread_count": 8
  },
  "engine": {
    "mode": "random",
    "target_count": 190,
    "is_running": true
  }
}
```

## 告警系统

系统会自动检测以下异常：

### 性能告警

- ⚠️ 检测速率过低 (< 100 keys/s)
- ⚠️ CPU使用率过高 (> 90%)
- ⚠️ 内存使用过高 (> 1024 MB)
- ⚠️ 引擎运行但速度为0

### GPU告警

- ⚠️ GPU执行超时 (> 30秒)
- ⚠️ 显存使用过高 (> 45%)
- ⚠️ GPU内核hang检测

### 告警输出

告警会同时输出到：

1. 控制台（彩色高亮）
2. `data_logs/alert_history.json`
3. `data_logs/error_log.json`
4. 系统日志

## 性能优化建议

### 1. 批次大小调整

```python
# 小显存GPU (< 4GB)
config = {'batch_size': 65536}  # 64K

# 中等显存GPU (4-8GB)
config = {'batch_size': 262144}  # 256K

# 大显存GPU (> 8GB)
config = {'batch_size': 1048576}  # 1M（默认）
```

### 2. Intel Arc GPU优化

系统已自动应用Intel Arc优化：

- ✅ uint32 workaround（避免global char* hang）
- ✅ 30秒超时保护
- ✅ 70%显存使用限制
- ✅ 异步双缓冲执行

### 3. 多GPU系统

```python
# 指定GPU设备
config = {'device_index': 0}  # 使用第一个GPU
config = {'device_index': 1}  # 使用第二个GPU
```

## 故障排除

### 问题1: GPU不可用

**症状**: `pyopencl不可用` 或 `未检测到可用的OpenCL设备`

**解决方案**:

```bash
# 安装pyopencl
pip install pyopencl

# 安装GPU驱动
# Intel: https://www.intel.com/opencl
# NVIDIA: https://developer.nvidia.com/cuda-downloads
# AMD: https://www.amd.com/en/support
```

### 问题2: 地址加载失败

**症状**: `未找到有效的比特币地址`

**解决方案**:

- 检查地址文件格式（每行一个地址）
- 验证地址是否为有效的P2PKH格式（以'1'开头）
- 查看日志中的详细错误信息

### 问题3: 性能低下

**症状**: 速度 < 1000 keys/s

**解决方案**:

1. 确认GPU正在被使用（查看日志中的GPU设备信息）
2. 增加batch_size
3. 检查GPU驱动是否为最新版本
4. 关闭其他占用GPU的程序

### 问题4: 内存泄漏

**症状**: 内存使用持续增长

**解决方案**:

- 系统已启用GPU内存池（最大512MB）
- 检查是否有其他进程占用内存
- 定期重启引擎

## 日志分析

### 查看性能趋势

```python
import json

with open('data_logs/history_data.json', 'r') as f:
    history = json.load(f)

# 提取速度数据
speeds = [h['performance']['speed'] for h in history if 'performance' in h]

print(f"平均速度: {sum(speeds)/len(speeds):.2f} keys/s")
print(f"最高速度: {max(speeds):.2f} keys/s")
print(f"最低速度: {min(speeds):.2f} keys/s")
```

### 查看错误日志

```python
import json

with open('data_logs/error_log.json', 'r') as f:
    errors = json.load(f)

for error in errors[-10:]:  # 最近10个错误
    print(f"[{error['datetime']}] {error['type']}: {error['message']}")
```

## 高级用法

### 自定义回调函数

```python
def on_progress(stats):
    """自定义进度回调"""
    print(f"进度: {stats.total_checked:,} keys, {stats.speed:,.2f} keys/s")

def on_match(match_info):
    """自定义匹配回调"""
    print(f"🎯 发现匹配: {match_info['address']}")
    # 保存到数据库或发送通知

launcher = BTCCollisionLauncher(
    address_file="targets.txt",
    config={
        'on_progress': on_progress,
        'on_match': on_match
    }
)
```

### 集成外部监控系统

```python
# 获取实时数据
current_data = launcher.data_logger.get_current_data()
statistics = launcher.data_logger.get_statistics()

# 发送到外部系统（如Prometheus、Grafana）
send_to_monitoring_system(statistics)
```

## 安全注意事项

1. **私钥保护**: 日志系统已启用安全过滤器，防止私钥泄露
2. **文件权限**: 监控数据文件设置为仅所有者可读写（0o600）
3. **路径安全**: 防止路径遍历攻击
4. **输入验证**: 所有地址都经过严格验证

## 性能基准

### Intel Arc A770 (参考)

| 指标 | 值 |
|------|-----|
| GPU设备 | Intel(R) Arc(TM) A770 Graphics |
| 显存 | 15.6 GB |
| 批次大小 | 1,048,576 |
| 预期速度 | 100,000 - 500,000 keys/s |
| CPU使用 | 30-50% |
| 内存使用 | 200-400 MB |

## 技术支持

如遇到问题，请检查：

1. 日志文件: `data_logs/error_log.json`
2. 系统日志: 控制台输出
3. GPU诊断: `python scripts/diagnose.py`

## 许可证

本项目仅供学习和研究使用。
