# CLI 命令行工具完整使用指南

## 📋 目录

1. [基础用法](#基础用法)
2. [GPU加速选项](#gpu加速选项)
3. [性能调优](#性能调优)
4. [性能监控](#性能监控)
5. [工具命令](#工具命令)
6. [搜索模式](#搜索模式)
7. [配置文件](#配置文件)
8. [完整示例](#完整示例)

---

## 🚀 基础用法

### 基本语法
```bash
python key_collision_cli.py [选项]
```

### 获取帮助
```bash
# 查看所有参数
python key_collision_cli.py --help

# 查看版本
python key_collision_cli.py --version

# 查看示例
python key_collision_cli.py --examples
```

---

## 🎮 GPU加速选项

### 自动检测GPU类型（推荐）
```bash
# Intel Arc A770 优化
python key_collision_cli.py -f targets.txt --intel-arc

# NVIDIA GPU 优化
python key_collision_cli.py -f targets.txt --nvidia

# AMD GPU 优化
python key_collision_cli.py -f targets.txt --amd
```

### 手动指定GPU
```bash
# 使用GPU设备1（Intel Arc）
python key_collision_cli.py -f targets.txt --use-gpu --gpu-device 1

# 使用GPU设备0（NVIDIA）
python key_collision_cli.py -f targets.txt --use-gpu --gpu-device 0

# 指定批次大小
python key_collision_cli.py -f targets.txt --use-gpu --gpu-device 1 --gpu-batch-size 1048576
```

### 多GPU模式
```bash
# 自动使用所有GPU
python key_collision_cli.py -f targets.txt --multi-gpu

# 指定使用的GPU数量
python key_collision_cli.py -f targets.txt --multi-gpu --gpu-count 2

# 手动指定GPU索引
python key_collision_cli.py -f targets.txt --multi-gpu --gpu-indices 0 1
```

---

## ⚡ 性能调优

### 核心优化选项
```bash
# 启用异步执行
python key_collision_cli.py -f targets.txt --use-gpu --async-execution

# 启用双缓冲（最大化GPU利用率）
python key_collision_cli.py -f targets.txt --use-gpu --double-buffering

# 组合优化
python key_collision_cli.py -f targets.txt --use-gpu \
    --async-execution \
    --double-buffering \
    --gpu-batch-size 1048576
```

### 线程配置
```bash
# 指定CPU工作线程数
python key_collision_cli.py -f targets.txt --workers 8

# 进度刷新间隔
python key_collision_cli.py -f targets.txt --progress-interval 3
```

---

## 📊 性能监控

### 实时监控面板
```bash
# 启用实时性能监控
python key_collision_cli.py -f targets.txt --use-gpu --monitor

# 自定义监控间隔
python key_collision_cli.py -f targets.txt --use-gpu --monitor --monitor-interval 1

# 设置GPU利用率告警阈值
python key_collision_cli.py -f targets.txt --use-gpu --monitor --alert-threshold 60

# 导出性能统计到文件
python key_collision_cli.py -f targets.txt --use-gpu --stats-file performance.log
```

### 监控输出示例
```bash
┌─────────────────────────────────────────────────────────────┐
│                    GPU性能监控面板                          │
├─────────────────────────────────────────────────────────────┤
│  GPU 状态                                                  │
│  ├─ 利用率: 82.3%                                         │
│  ├─ 温度: 71.2°C                                          │
│  ├─ 显存: 6,234/16,384 MB                                 │
│  └─ 功耗: 201 W                                          │
│                                                            │
│  性能                                                      │
│  ├─ 吞吐量: 42,345,678 keys/s                            │
│  ├─ 平均吞吐量: 41,234,567 keys/s                         │
│  ├─ 已检查: 1,234,567,890                                 │
│  └─ 批次: 587                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 工具命令

### 系统检测
```bash
# 列出所有GPU设备
python key_collision_cli.py --list-gpus

# 运行健康检查
python key_collision_cli.py --health-check

# 平台兼容性检查
python key_collision_cli.py --platform-check

# 配置文件验证
python key_collision_cli.py --config-check
```

### 性能分析
```bash
# 获取推荐配置
python key_collision_cli.py --recommend

# 运行基准测试
python key_collision_cli.py --benchmark
```

### 配置管理
```bash
# 生成配置模板
python key_collision_cli.py --template gpu-performance

# 迁移旧配置
python key_collision_cli.py --migrate-config

# 清理临时文件
python key_collision_cli.py --cleanup

# 预览清理（不实际删除）
python key_collision_cli.py --cleanup --dry-run
```

---

## 🔍 搜索模式

### 随机搜索（默认）
```bash
# 基础随机搜索
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

# 多地址随机搜索
python key_collision_cli.py -f targets.txt --use-gpu

# 启用去重
python key_collision_cli.py -f targets.txt --use-gpu --dedup
```

### 范围扫描
```bash
# 扫描指定范围
python key_collision_cli.py -f targets.txt --use-gpu \
    -m range \
    --start 1 \
    --end FFFFFFFF

# 十六进制范围
python key_collision_cli.py -f targets.txt --use-gpu \
    -m range \
    --start 0x10000000000000000000000000000000 \
    --end 0xFFFFFFFFFFFFFFFF
```

### 暴力穷举
```bash
# 从0开始暴力搜索
python key_collision_cli.py -f targets.txt --use-gpu -m brute_force

# 指定起始点
python key_collision_cli.py -f targets.txt --use-gpu \
    -m brute_force \
    --start 1000000000
```

---

## ⚙️ 配置文件

### 配置文件结构
```json
{
  "gpu": {
    "preferred_vendor": "intel",
    "device_index": 1,
    "batch_size": 1048576,
    "max_batch_size": 2097152,
    "use_async_execution": true,
    "use_double_buffering": true
  },
  "performance": {
    "workers": 8,
    "progress_interval": 5.0
  },
  "monitoring": {
    "enabled": true,
    "interval": 2.0,
    "alert_threshold": 50.0
  }
}
```

### 使用配置文件
```bash
# 指定配置文件
python key_collision_cli.py -f targets.txt --config config.json

# 生成预定义模板
python key_collision_cli.py --template gpu-performance > config.json
```

---

## 📝 完整示例

### 示例1：Intel Arc A770 优化运行
```bash
python key_collision_cli.py \
    -f targets.txt \
    --intel-arc \
    --monitor \
    --duration 3600
```

### 示例2：NVIDIA RTX 4090 优化运行
```bash
python key_collision_cli.py \
    -f targets.txt \
    --nvidia \
    --gpu-batch-size 4194304 \
    --async-execution \
    --double-buffering \
    --monitor
```

### 示例3：范围扫描 + 断点续传
```bash
python key_collision_cli.py \
    -f targets.txt \
    --use-gpu \
    --gpu-device 1 \
    -m range \
    --start 1 \
    --end FFFFFFFF \
    --checkpoint \
    --checkpoint-interval 60
```

### 示例4：快速测试模式
```bash
# 使用默认配置快速启动
python key_collision_cli.py --quick-run
```

### 示例5：限时运行 + 导出结果
```bash
python key_collision_cli.py \
    -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa \
    --use-gpu \
    --gpu-device 1 \
    --duration 300 \
    --export-progress progress.json \
    --export-matches matches.json
```

---

## 🎯 推荐配置

### Intel Arc A770
```bash
python key_collision_cli.py -f targets.txt \
    --intel-arc \
    --monitor \
    --async-execution \
    --double-buffering
```

### NVIDIA RTX 30/40 系列
```bash
python key_collision_cli.py -f targets.txt \
    --nvidia \
    --monitor \
    --gpu-batch-size 4194304
```

### AMD RX 6000/7000 系列
```bash
python key_collision_cli.py -f targets.txt \
    --amd \
    --monitor \
    --gpu-batch-size 2097152
```

---

## 🔑 参数优先级

1. **命令行参数**（最高优先级）
2. **配置文件** (`--config`)
3. **预设模板** (`--template`)
4. **默认配置**（最低优先级）

---

## 📌 快捷键

| 按键 | 功能 |
|------|------|
| `Ctrl+C` | 停止搜索并保存检查点 |
| `Ctrl+Z` | 暂停搜索（Windows） |

---

## 📁 输出文件

| 文件 | 说明 |
|------|------|
| `checkpoint.dat` | 断点续传数据 |
| `found_keys.txt` | 找到的匹配结果 |
| `performance.log` | 性能统计日志 |
| `progress.json` | 进度数据导出 |
| `matches.json` | 匹配结果导出 |

---

**🎉 更多帮助：** `python key_collision_cli.py --help`
