# 快速开始与部署指南

> **版本**: v3.1.2 | **最后更新**: 2026-04-25  
> **面向**: 新用户
>
> 📢 **v3.1.1新增**: 自动化安装脚本、健康检查、数据清理功能

## 目录

- [📋 前置要求](#-前置要求)
  - [系统要求](#系统要求)
- [🚀 5分钟快速上手](#-5分钟快速上手)
  - [1. 安装依赖](#1-安装依赖)
- [2. 运行碰撞测试](#2-运行碰撞测试)
  - [方法A: 使用命令行工具](#方法a-使用命令行工具)
- [方法B: 使用测试脚本](#方法b-使用测试脚本)
- [方法C: 使用Python代码](#方法c-使用python代码)
- [🎯 三种碰撞模式](#-三种碰撞模式)
  - [1. 随机模式（推荐）](#1-随机模式推荐)
  - [2. 范围扫描模式](#2-范围扫描模式)
  - [3. 暴力穷举模式](#3-暴力穷举模式)
- [📊 性能基准](#-性能基准)
- [🧪 运行测试](#-运行测试)
  - [完整测试套件](#完整测试套件)
- [测试状态](#测试状态)
- [📁 项目结构](#-项目结构)
- [💡 使用建议](#-使用建议)
  - [1. 学习研究](#1-学习研究)
  - [2. 性能测试](#2-性能测试)
  - [3. 安全研究](#3-安全研究)
- [⚠️ 重要说明](#-重要说明)
  - [为什么找不到匹配？](#为什么找不到匹配)
  - [测试的价值](#测试的价值)
- [📚 下一步](#-下一步)
  - [深入学习](#深入学习)
  - [进阶使用](#进阶使用)
- [🆘 获取帮助](#-获取帮助)
  - [文档](#文档)
  - [测试报告](#测试报告)

## 📋 前置要求

- Python 3.9+ (推荐 3.11+)
- Windows/Linux/MacOS
- 4GB+ RAM
- 2个CPU核心+

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|----------|
| Python版本 | 3.9+ | 3.11+ |
| 内存 | 1GB | 4GB+ |
| 磁盘空间 | 200MB | 1GB+ |
| 操作系统 | Windows 10+/Linux/macOS | Windows 11/Ubuntu 22.04+ |

---

## 🚀 5分钟快速上手

### 1. 安装依赖

#### 方法A: 使用自动化安装脚本（推荐）

```bash
# Windows
scripts\install.bat

# Linux/macOS
bash scripts/install.sh
```

安装脚本会自动完成所有设置，包括：

- ✅ Python版本检查
- ✅ 虚拟环境创建
- ✅ 依赖安装
- ✅ 配置文件初始化

#### 方法B: 手动安装

```bash
# 克隆或下载项目
cd your-project-directory

# 创建并激活虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# 安装依赖
pip install -r requirements-base.txt

# 初始化配置
# Windows: copy config.example.json config.json
# Linux/macOS: cp config.example.json config.json
```

## 2. 运行碰撞测试

#### 方法A: 使用命令行工具

```bash
# 基本使用（随机模式，10秒）
python key_collision_cli.py -a "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr" -m random --duration 10

# 从文件加载地址
python key_collision_cli.py -f valid_addresses.txt -m random --duration 60

# 指定线程数
python key_collision_cli.py -f valid_addresses.txt -m random -w 4 --duration 60
```

## 方法B: 使用测试脚本

```bash
# 运行真实地址碰撞测试（10秒，2线程）
python run_real_collision_test.py

# 自定义参数（60秒，4线程）
python run_real_collision_test.py 60 4
```

## 方法C: 使用Python代码

```
from src.collision.key_collision_engine import KeyCollisionEngine
import time

# 定义目标地址
targets = {
    "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr",
    "12tkqA9xSoowkzoERHMWNKsTey55YEBqkv",
}

# 创建引擎
engine = KeyCollisionEngine(
    targets=targets,
    max_workers=2,
    dedup_enabled=True,
)

# 启动碰撞
engine.start(mode="random")

# 运行60秒
time.sleep(60)

# 停止并查看结果
engine.stop()
stats = engine.get_stats()
print(f"检查了 {stats.total_checked} 个私钥")
print(f"速度: {stats.speed:.0f} 次/秒")
```

---

## 🎯 三种碰撞模式

### 1. 随机模式（推荐）

随机生成私钥并检查是否匹配目标地址。

```bash
python key_collision_cli.py -f valid_addresses.txt -m random --duration 60
```

**适用场景**: 通用碰撞测试

### 2. 范围扫描模式

在指定的私钥范围内顺序扫描。

```bash
python key_collision_cli.py -f valid_addresses.txt -m range --start 1 --end 1000000
```

**适用场景**: 测试特定范围的私钥

### 3. 暴力穷举模式

从指定起点开始穷举。

```bash
python key_collision_cli.py -f valid_addresses.txt -m brute --start 1
```

**适用场景**: 连续私钥空间搜索

---

## 📊 性能基准

根据测试结果：

| 操作 | 速度 | 说明 |
|-----|-----|-----|
| 私钥生成 | 526,790 次/秒 | 纯密码学操作 |
| 完整流水线 | 6,778 次/秒 | 包含地址生成和碰撞检测 |
| 引擎单线程 | 7,512 次/秒 | CPU单核性能 |
| 引擎4线程 | 5,625 次/秒 | 多核并行 |

**实际测试**:

```
$ python run_real_collision_test.py 10 2

📊 测试结果:
   目标地址数: 38
   运行时间:   00:00:10
   总检查数:   32,603
   平均速度:   3.26K/s
   发现匹配:   0 个 (正常)
```

---

## 🧪 运行测试

### 完整测试套件

```
# 运行所有测试
python -m pytest tests/ -v

# 只运行性能测试
python -m pytest tests/test_performance.py -v

# 只运行安全测试
python -m pytest tests/test_security.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html
```

## 测试状态

```

✅ 261个测试用例
✅ 97%+通过率
✅ 100%核心功能覆盖

```

---

## 📁 项目结构

```

f:/BTC/
├── src/                          # 源代码
│   ├── core/                     # 核心算法
│   │   ├── secp256k1.py         # 椭圆曲线
│   │   ├── address_generator.py # 地址生成
│   │   └── ...
│   ├── collision/                # 碰撞引擎
│   │   ├── key_collision_engine.py
│   │   └── ...
│   └── ...
├── tests/                        # 测试套件
├── docs/                         # 文档
├── valid_addresses.txt           # 目标地址文件
├── run_real_collision_test.py    # 测试脚本
└── key_collision_cli.py          # CLI工具

```

---

## 💡 使用建议

### 1. 学习研究

- 使用小范围测试（10-60秒）
- 观察日志输出
- 理解碰撞原理

### 2. 性能测试

- 使用不同线程数
- 对比去重开关
- 记录性能数据

### 3. 安全研究

- 运行安全测试套件
- 查看安全审计报告
- 理解密码学原理

---

## ⚠️ 重要说明

### 为什么找不到匹配？

比特币私钥空间大小为 **2^256**（约 10^77）：

- 38个地址的概率 ≈ 38 / 2^256
- 即使每秒100万次，需要 10^64 年
- 这证明了比特币密码学的**安全性**

### 测试的价值

虽然找不到真实匹配，但可以：

- ✅ 验证引擎功能
- ✅ 测量性能指标
- ✅ 学习密码学
- ✅ 压力测试系统

---

## 📚 下一步

### 深入学习

1. 📖 阅读 [需求规格](requirements.md)
2. 🏗️ 查看 [架构文档](architecture.md)
3. 🔒 学习 [安全指南](security-guidelines.md)
4. 📊 查看 [性能优化指南](performance-optimization.md)

### 进阶使用

- 尝试GPU加速（需要NVIDIA GPU）
- 配置断点续传
- 调整去重参数
- 监控系统资源

---

## 🆘 获取帮助

### 文档

- [完整文档索引](README.md)
- [故障排除指南](troubleshooting.md)
- [API参考](api-reference.md)

### 测试报告

- [最终测试总结](test-final-summary.md)（含真实地址碰撞测试指南）
- [性能优化指南](performance-optimization.md)

---

**开始你的比特币密码学研究之旅！** 🎉
