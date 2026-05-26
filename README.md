# BTC 碰撞引擎

比特币私钥碰撞引擎，支持CPU和GPU加速，用于学习和研究比特币地址碰撞。

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-5.0.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Contributions](https://img.shields.io/badge/Contributions-Welcome-orange.svg)](CONTRIBUTING.md)

**📚 想参与开发？查看 [贡献指南](CONTRIBUTING.md)**

## 功能特性

- ✅ **交互式向导** (v5.0.0 成熟稳定模块化架构)
  - 4 步引导流程 (目标地址 → 碰撞模式 → 功能选项 → GPU加速)
  - 模块化策略组件 (目标/模式/选项/GPU 选择器)
  - 自动设备检测与推荐
  - 配置预览与一键执行
- ✅ 多种碰撞模式
  - 随机碰撞：随机生成私钥进行匹配
  - 范围扫描：在指定范围内顺序扫描
  - 暴力穷举：从指定起点开始递增
- ✅ GPU加速（OpenCL）
  - 支持NVIDIA、AMD、Intel显卡
  - 批量并行计算
  - 异步流水线优化
  - 自动内存优化
- ✅ **多格式地址智能匹配** (v5.0.0 稳定支持)
  - 自动检测目标地址格式
  - 按需生成对应格式地址
  - P2PKH只匹配P2PKH目标，Bech32只匹配Bech32目标
  - 支持完整检查所有格式
- ✅ 多地址类型支持
  - P2PKH地址（1开头）
  - P2SH地址（3开头）
  - Bech32地址（bc1q开头，SegWit v0）
  - Taproot地址（bc1p开头，SegWit v1）
  - WIF私钥、公钥、Hash160
- ✅ 断点续传
  - 自动保存进度
  - 支持从断点恢复
- ✅ 去重过滤
  - Bloom过滤器去重
  - 防止重复检测
- ✅ 实时监控
  - 性能指标统计
  - 进度可视化
  - 数据日志记录
- ✅ **性能优化** (v5.0.0)
  - GPU PRNG 私钥生成（消除 CPU→GPU 传输瓶颈）
  - secp256k1 预计算表常数化（`__constant` 内存）
  - 模逆加法链优化（mul 减少 89%）
  - **异步双缓冲架构** (计算队列+传输队列,性能+63.9%)
  - **GPU 引擎架构重构** (协议层+外观层+核心层+监控管道+厂商策略)
  - Intel Arc A770: **4.89M keys/s**（异步模式,峰值5.08M）
  - **引擎代码复杂度 -73%** (1466→<400行), 导入模块 -70% (49→<15)
- ✅ **GPU 引擎架构重构** (v5.0.0, 2026-05)
  - 协议层+外观层+核心层+监控管道+厂商策略 完整解耦
  - 代码复杂度 -73%（1466→<400行），导入模块 -70%（49→<15）
  - Shim 层 100% 向后兼容，29 个专项测试全部通过
  - 新增 search_mode_coordinator / data_logger_adapter 等 5 个子模块

> 📢 **v5.0.0 重大重构**: 移除 LegacyTargetResolver 和 CollisionCLI 旧版 CLI，Shim 层 100% 向后兼容，29 项专项测试全通过。配置预设文件注释化，文档链接全面修复。详见 [CHANGELOG](CHANGELOG.md)。
> 📢 **v4.4.0 安全修复**: 新增多项安全修复（安全清零、侧信道安全、敏感数据脱敏、线程安全统计等）。详见 [SECURITY_IMPROVEMENTS](docs/SECURITY_IMPROVEMENTS.md)。
> 📢 **v4.3.0 多格式地址支持**: 新增格式感知目标管理器，支持P2PKH/P2SH/Bech32/Taproot格式智能匹配，按需生成地址提升性能。
> 📢 **v5.0.0 重大重构**: GPU 引擎架构重构完成（引擎行数 -73%, 导入模块 -70%）, 29 项专项测试全通过。详见 [CHANGELOG](CHANGELOG.md)。
> 📢 **v5.0.0 全栈优化**: 全模块类型提示补全 (104 文件)、配置热重载、多渠道告警系统。详见 [CHANGELOG](CHANGELOG.md)。

### 安全特性 (v4.4.0)

- ✅ **安全清零实现** (C-1)
  - 使用 `ctypes.memset` 直接清零内存，防止编译器优化导致清零被跳过
  - 添加清零验证步骤，确保内存被正确清零
  - 失败时抛出 `SecureMemoryError` 异常

- ✅ **侧信道安全** (C-2)
  - OpenSSL 后端不可用时拒绝回退到非恒定时间实现
  - `scalar_multiply()` 抛出异常而不是静默回退
  - 确保密码学操作符合安全要求

- ✅ **敏感数据脱敏** (H-4)
  - 使用 `SensitiveDataFilter` 对错误消息进行敏感数据过滤
  - 保留异常类型用于诊断，隐藏私钥等敏感信息
  - 避免敏感数据泄露到日志文件

- ✅ **线程安全统计** (C-3)
  - 使用 `threading.Lock` 保护类级别统计变量
  - 确保清零统计的原子更新
  - 解决多线程并发访问时的竞态条件

- ✅ **配置值边界验证** (M-3)
  - 验证 `worker_join_timeout`、`workload_monitor_interval`、`total_pool_mb` 等参数
  - 超出范围时自动使用默认值并记录警告
  - 避免无效配置导致的问题

## 快速开始

### 命令行模式

```bash
python key_collision_cli.py --help
```

### 示例：随机碰撞

```bash
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
```

## 目标地址格式支持

### 📋 支持的地址格式 (v4.3.0+)

| 格式 | 前缀 | GPU支持 | CPU支持 | 说明 |
|------|------|--------|---------|------|
| **P2PKH** | `1` | ✅ | ✅ | 标准比特币地址，hash160(pubkey) |
| **Bech32 P2WPKH** | `bc1q` | ✅ | ✅ | SegWit v0，witness_program = hash160(pubkey) |
| **P2SH** | `3` | ❌ | ❌ | 脚本哈希，无法通过私钥碰撞匹配 |
| **Bech32 P2WSH** | `bc1q` (42+字符) | ❌ | ❌ | SegWit v0脚本哈希，无法匹配 |
| **Taproot** | `bc1p` | ❌ | ❌ | SegWit v1，密钥路径不同，无法匹配 |

### 🔐 密码学原理

**可匹配的格式**:

```
私钥 → ECDSA secp256k1 → 公钥
                               ↓
                    hash160(pubkey) [20字节]
                               ↓
         ┌──────────────────┬──────────────────┐
         ↓                  ↓                  ↓
    P2PKH地址          Bech32 P2WPKH      其他格式
    (1开头)           (bc1q开头)
```

**不可匹配的格式**:

```
P2SH: payload = hash160(redeemScript) ≠ hash160(pubkey) ❌
P2WSH: payload = sha256(redeemScript) ≠ hash160(pubkey) ❌
Taproot: x-only pubkey + 密钥路径 ≠ 标准公钥 ❌
```

### 💡 使用建议

**✅ 推荐的目标格式**:

```bash
# P2PKH地址 (最常用)
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --use-gpu

# Bech32 P2WPKH地址 (v4.3.0+ GPU支持)
python key_collision_cli.py -t bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4 --use-gpu

# 混合目标文件
# 文件内容示例:
# 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa  # P2PKH
# bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4  # Bech32 P2WPKH
python key_collision_cli.py -t targets.txt --use-gpu
```

**❌ 不推荐的目标格式** (会显示警告并被跳过):

```bash
# P2SH地址 - 无法匹配
python key_collision_cli.py -t 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy --use-gpu
# 输出: WARNING - P2SH地址无法用于碰撞匹配

# Taproot地址 - 无法匹配
python key_collision_cli.py -t bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2yx7tqsp6h3m --use-gpu
# 输出: WARNING - Taproot无法通过私钥碰撞匹配
```

### 📊 格式检测示例

引擎会自动检测地址格式:

```
输入: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
检测: P2PKH ✅
引擎: 生成hash160(pubkey)进行比较

输入: bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4
检测: Bech32 P2WPKH ✅
引擎: 提取witness_program作为hash160比较

输入: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
检测: P2SH ⚠️
引擎: 跳过 (显示警告)

输入: bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2yx7tqsp6h3m
检测: Taproot ⚠️
引擎: 跳过 (显示警告)
```

### 🔧 引擎差异

| 特性 | GPU引擎 | CPU引擎 |
|------|---------|---------|
| P2PKH支持 | ✅ | ✅ |
| Bech32 P2WPKH支持 | ✅ (v4.3.0+) | ✅ |
| 匹配算法 | hash160直接比较 | 格式感知地址生成 |
| 性能 | ~2-5M keys/s | ~100-1K keys/s |
| 内存占用 | GPU显存 | 系统内存 |

## 项目结构

```
btc-collision-engine/
├── key_collision_cli.py      # 统一命令行入口（根级代理 → src/cli/main.py）
├── key_collision.py          # 旧版主引擎（兼容保留）
├── gpu_engine.py             # GPU引擎实现
├── src/                      # 核心模块
│   ├── wizard/               # 交互式向导 (v3.4.0 全新)
│   │   ├── wizard_engine.py          # 向导引擎 (4步编排)
│   │   ├── target_selector.py        # 目标地址选择器
│   │   ├── mode_selector.py          # 碰撞模式选择器
│   │   ├── option_selector.py        # 功能选项选择器
│   │   ├── gpu_selector.py           # GPU加速选择器
│   │   ├── config_builder.py         # 配置构建器
│   │   ├── interfaces.py             # 协议接口定义
│   │   ├── events.py                 # 事件系统
│   │   └── message_queue.py          # 消息队列
│   ├── collision/            # 碰撞引擎
│   │   ├── key_collision_engine.py    # CPU碰撞引擎
│   │   ├── gpu_collision_engine.py    # GPU碰撞引擎 (Shim层, v6.0.0)
│   │   ├── gpu/                       # GPU引擎重构模块 (Phase 1-6 ✅)
│   │   │   ├── engine.py              # 引擎协调器 (Phase 6, <400行)
│   │   │   ├── __init__.py            # 模块入口+工厂函数 (8个get_*)
│   │   │   ├── protocols.py           # 核心协议定义 (5个接口)
│   │   │   ├── facade.py              # GPU引擎外观层
│   │   │   ├── core.py                # 碰撞核心 (stats/checkpoint/dedup)
│   │   │   ├── monitoring.py          # 性能监控管道
│   │   │   ├── vendor_strategy.py     # 厂商优化策略工厂
│   │   │   ├── device_manager_adapter.py   # 设备管理器适配器
│   │   │   ├── kernel_adapter.py           # 内核执行器适配器
│   │   │   ├── async_pipeline_adapter.py   # 异步管道适配器
│   │   │   ├── data_logger_adapter.py      # 数据日志适配器
│   │   │   └── search_mode_coordinator.py  # 搜索模式协调器
│   │   ├── checkpoint_manager.py      # 断点管理
│   │   ├── deduplication_filter.py    # 去重过滤器
│   │   ├── collision_stats.py         # 统计数据
│   │   └── target_resolver.py         # 目标地址解析
│   ├── logging/              # 日志子系统 (v3.4.0 新增)
│   │   ├── log_collector.py           # 日志收集器
│   │   ├── log_processor.py           # 日志处理器
│   │   ├── log_storage.py             # 日志存储
│   │   ├── log_query.py               # 日志查询
│   │   └── events.py                  # 日志事件定义
│   ├── monitoring/           # 监控系统
│   ├── core/                 # 加密核心（共享）
│   ├── config/               # 配置管理
│   └── utils/                # 工具模块
├── docs/                     # 文档
├── tests/                    # 测试文件
├── tools/                    # 辅助工具
├── monitoring_data/          # 监控数据
├── data_logs/               # 数据日志
├── logs/                    # 运行日志
├── config.json             # 配置文件
├── requirements.txt        # 依赖列表
└── valid_addresses.txt     # 测试地址
```

## 安装依赖

### 方法一：自动化安装脚本（推荐，5分钟完成）

**Windows**:

```bash
scripts/install/install.bat
```

**Linux / macOS**:

```bash
bash scripts/install/install.sh
```

安装脚本会自动完成：

- ✅ Python版本检查（需要3.12+）
- ✅ 虚拟环境创建和激活
- ✅ 依赖安装（基础+可选GPU）
- ✅ 配置文件初始化
- ✅ 依赖验证和目录创建

### 方法二：手动安装（高级用户）

#### 第一步：创建虚拟环境（强烈推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate
```

#### 第二步：安装基础依赖

```bash
pip install -r requirements-base.txt
```

> 💡 **提示**: `requirements.txt` 包含所有依赖（包括开发工具），普通用户使用 `requirements-base.txt` 即可。

#### 第三步：初始化配置文件

```bash
# Windows
copy config.example.json config.json

# Linux / macOS
cp config.example.json config.json
```

> 然后按需编辑 `config.json`，设置目标地址、碰撞模式等参数。

### GPU加速（可选）

> **要求**：Python 3.12+、已安装 GPU 驱动、支持 OpenCL 1.2+
>
> **详细配置指南请查看：[⚙️ GPU配置指南](GPU_CONFIG_GUIDE.md)

#### NVIDIA GPU

```bash
# Windows / Linux
# 1. 安装 CUDA Toolkit ≥ 11.0（包含 OpenCL 运行时）
#    下载: https://developer.nvidia.com/cuda-downloads

# 2. 安装 PyOpenCL
pip install pyopencl

# 3. 验证
python -c "import pyopencl; print([d.name for p in pyopencl.get_platforms() for d in p.get_devices()])"
```

#### AMD GPU

```bash
# Windows
# 1. 安装 AMD 软件（包含 OpenCL），驱动版本 >= 21.x
#    下载: https://www.amd.com/en/support

# Linux
# sudo apt install mesa-opencl-icd  # Ubuntu/Debian
# sudo dnf install opencl-filesystem mesa-libOpenCL  # Fedora

# 2. 安装 PyOpenCL
pip install pyopencl
```

#### Intel GPU（Arc / UHD 集成显卡）

```bash
# Windows
# 1. 安装 Intel Arc 客户端驱动 >= 31.0.101.4146
#    下载: https://www.intel.com/content/www/us/en/download-center/home.html

# Linux
# sudo apt install intel-opencl-icd  # Ubuntu

# 2. 安装 PyOpenCL
pip install pyopencl

# 3. 验证 Intel GPU 可识别
python -c "import pyopencl as cl; [print(d.name) for p in cl.get_platforms() for d in p.get_devices()]"
```

#### GPU 不可用时的降级

当 PyOpenCL 未安装或无 GPU 设备时，引擎自动降级为 CPU 模式运行，不会报错退出。

### 性能优化（推荐）

```bash
# coincurve: 提升CPU性能3-5倍
pip install coincurve

# numpy: GPU计算优化
pip install numpy

# v2.2.0 新增性能优化模块
pip install gmpy2>=2.1.5            # 大整数运算优化 (模逆元 +1455%)
pip install pycryptodome>=3.19.0    # SIMD哈希优化 (AES-NI加速)
```

## 系统维护（推荐）

### 健康检查

运行健康检查诊断系统状态：

```bash
# 基础检查
python -m src.utils.health_check

# 包含GPU检查
python -m src.utils.health_check --gpu

# 生成报告文件
python -m src.utils.health_check --report health_report.txt
```

### 数据清理

定期清理过期数据，防止磁盘空间耗尽：

```bash
# 试运行（查看将删除什么）
python -m src.utils.data_cleanup --dry-run

# 实际清理
python -m src.utils.data_cleanup

# 自定义保留天数
python -m src.utils.data_cleanup --temp-days 14 --data-days 60
```

## 使用方法

### 多格式地址匹配 (v4.3.0 新增)

```python
from src.collision.targets.format_aware_manager import FormatAwareTargetManager
from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat

# 初始化格式感知管理器
manager = FormatAwareTargetManager()

# 添加多种格式的目标地址（自动检测格式）
manager.add_target("1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")  # P2PKH
manager.add_target("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")  # P2SH
manager.add_target("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")  # Bech32
manager.add_target("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0")  # Taproot

# 查看格式统计
print(manager.get_format_stats())
# 输出: {'p2pkh': 1, 'p2sh': 1, 'bech32': 1, 'taproot': 1}

# 方式1: 快速匹配（找到第一个匹配就返回）
is_match, matched_addr, matched_fmt = manager.check_match(private_key)
if is_match:
    print(f"找到匹配! {matched_fmt}: {matched_addr}")

# 方式2: 完整检查所有格式（推荐）
is_match_all, matches = manager.check_match_all(private_key)
if is_match_all:
    for addr, fmt in matches:
        print(f"找到匹配! {fmt}: {addr}")
```

### 多格式地址生成

```python
from src.core.multi_format_generator import MultiFormatAddressGenerator, AddressFormat

generator = MultiFormatAddressGenerator()

# 生成特定格式地址
p2pkh_addr = generator.generate_address(private_key, AddressFormat.P2PKH)
bech32_addr = generator.generate_address(private_key, AddressFormat.BECH32)

# 生成所有格式地址
addresses = generator.generate_all_formats(private_key)
print(f"P2PKH: {addresses['p2pkh']}")
print(f"Bech32: {addresses['bech32']}")
```

### 命令行使用

```bash
# 查看所有参数
python key_collision_cli.py --help

# 随机碰撞（无限运行，Ctrl+C 停止）
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random

# 从文件加载目标地址，范围扫描
python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF

# 暴力穷举模式，多线程
python key_collision_cli.py -t 1A1z... -m brute_force --start 1 --workers 8

# 启用断点续传，运行120秒后自动停止
python key_collision_cli.py -t 1A1z... -m random --checkpoint --duration 120

# 启用去重过滤
python key_collision_cli.py -t 1A1z... -m random --dedup
```

## 性能优化配置 (v3.2.0)

### GPU 性能基准

| 模式 | 速度 | 说明 |
|------|------|------|
| 初始基准 (CPU) | **44K keys/s** | 无GPU优化 |
| GPU 异步双缓冲 | **~520K keys/s** | v3.0 |
| GPU PRNG + 双缓冲 | **3.07M keys/s** | v3.2.0, 不含异步双缓冲, **70x 提升** |
| GPU PRNG + 异步双缓冲 | **4.89M keys/s** | v3.5.0 最新, 峰值 5.08M |

最优配置：`batch_size=1,048,576`，`async_execution=true`（参考 `config.intel_arc.json`）

### 使用Python API

```python
from src.collision.key_collision_engine import KeyCollisionEngine

# 方式1: 默认配置(自动启用所有优化)
engine = KeyCollisionEngine(
    targets={'1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'}
)

# 方式2: 自定义优化配置
engine = KeyCollisionEngine(
    targets=targets,
    use_performance_optimization=True,  # 启用优化
    precomputed_window_size=8,          # 预计算表窗口大小(4-8)
    use_simd_hash=True,                 # SIMD哈希优化
    use_memory_pool=True                # 内存池
)

# 方式3: 禁用优化(兼容模式)
engine = KeyCollisionEngine(
    targets=targets,
    use_performance_optimization=False
)
```

### 性能对比数据

### CPU 优化模块性能对比

| 优化模块 | 性能提升 | 说明 |
|---------|---------|------|
| 预计算点表 | **+46%** | 标量乘法 1.46x 加速 |
| gmpy2模逆元 | **+1455%** | 大整数运算 14.55x 加速 |
| SIMD哈希 | **已启用** | AES-NI 指令集加速 |
| 内存池 | **-60%延迟** | 对象分配优化 |
| GPU内存池 | **-60%开销** | 缓冲区复用 |
| **GPU PRNG** | **70x 总提升** | **Intel Arc A770: 3.07M keys/s** |

> 📊 查看完整性能数据: [性能优化文档](docs/technical-docs/performance-optimization.md)

### 安装优化依赖

```bash
# 必需依赖
pip install gmpy2>=2.1.5            # 大整数优化 (推荐)
pip install pycryptodome>=3.19.0    # SIMD哈希 (推荐)

# 可选依赖
pip install memory-profiler>=0.61   # 内存分析
pip install pytest-benchmark>=4.0   # 性能测试
```

### 运行性能基准测试

## 测试质量保证

### 测试覆盖率

项目拥有完善的测试体系，确保代码质量：

```
┌─────────────────────────────────┐
│      完整测试状态                │
├──────────────┬────────┬─────────┤
│ 测试类别     │ 用例数 │ 通过率  │
├──────────────┼────────┼─────────┤
│ 核心加密     │ 25     │ 100% ✅ │
│ 碰撞引擎     │ 14     │ 100% ✅ │
│ 配置管理     │ 33     │ 100% ✅ │
│ 异常处理     │ 42     │ 100% ✅ │
│ GPU引擎      │ 8      │ 100% ✅ │
│ CLI工具      │ 7      │ 100% ✅ │
│ 性能基准     │ 16     │ 100% ✅ │
│ 安全合规     │ 16     │ 100% ✅ │
│ 其他         │ 100    │ 95%+ ✅ │
├──────────────┼────────┼─────────┤
│ **总计**     │ **261**| **97%+**✅│
└──────────────┴────────┴─────────┘
```

### 测试分类

| 分类 | Marker | 说明 |
|------|--------|------|
| GPU硬件测试 | `@pytest.mark.gpu_hardware` | 需要真实GPU硬件 |
| GPU单元测试 | `@pytest.mark.gpu_unit` | 可Mock的GPU测试 |
| GPU集成测试 | `@pytest.mark.gpu_integration` | GPU集成测试 |
| 性能测试 | `@pytest.mark.performance` | 性能基准测试 |
| 安全测试 | `@pytest.mark.security` | 安全合规测试 |

### 运行测试

```bash
# 运行所有测试
pytest

# 仅运行GPU单元测试（不需要真实GPU）
pytest -m gpu_unit

# 跳过需要GPU硬件的测试
pytest -m "not gpu_hardware"

# 运行特定测试文件
pytest tests/test_gpu_collision_engine.py -v

# 生成测试覆盖率报告
pytest --cov=src --cov-report=html
```

### 测试ID索引

所有带有skip标记的测试都有唯一的测试ID，详情请查看：[测试ID索引](docs/TEST_ID_INDEX.md)

### 代码质量评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码结构 | ⭐⭐⭐⭐⭐ | 模块化设计 |
| 类型安全 | ⭐⭐⭐⭐⭐ | 完整类型注解 |
| 文档质量 | ⭐⭐⭐⭐⭐ | 详细文档字符串 |
| 线程安全 | ⭐⭐⭐⭐⭐ | 无竞态条件 |
| 安全设计 | ⭐⭐⭐⭐ | 使用安全随机源 |
| 测试覆盖 | ⭐⭐⭐⭐⭐ | 97%+通过率 |

**综合评分**: ⭐⭐⭐⭐⭐ (5.0/5.0)

```bash
# 验证gmpy2性能
python benchmarks/verify_gmpy2_performance.py

# 完整基准测试
python benchmarks/benchmark_optimizations.py

# 集成测试
python tests/test_optimization_integration.py
```

## 碰撞模式详解

### 1. 随机碰撞 (Random Search)

- **原理**: 随机生成私钥，检查是否匹配目标
- **适用场景**: 未知目标私钥范围
- **优势**: 覆盖范围广
- **劣势**: 可能重复检测

### 2. 范围扫描 (Range Scan)

- **原理**: 在指定范围内顺序扫描
- **适用场景**: 已知目标私钥在特定范围
- **优势**: 不会重复，可精确控制
- **劣势**: 需要知道大致范围

### 3. 暴力穷举 (Brute Force)

- **原理**: 从起点开始无限递增
- **适用场景**: 小范围私钥测试
- **优势**: 简单直接
- **劣势**: 范围太大时效率低

## GPU加速配置

### 检测GPU设备

```python
from src.collision.gpu.engine import GPUCollisionEngine

# 列出所有可用GPU设备
GPUCollisionEngine.list_devices()
```

### 选择特定GPU

在代码中指定GPU设备索引：

```python
engine = GPUCollisionEngine(
    targets=targets,
    device_index=0,  # GPU设备索引
    batch_size=100000  # 批次大小
)
```

### 性能优化建议

1. **批次大小**:
   - 小内存GPU: 10,000 - 50,000
   - 中等GPU: 100,000 - 500,000
   - 大内存GPU: 1,000,000+

2. **设备选择**:
   - 优先选择独立显卡
   - 避免使用集成显卡（性能较低）

## 断点续传

### 自动保存

- 默认每30秒自动保存
- 可在配置文件中调整间隔

### 手动保存

引擎停止时自动保存最新进度

### 恢复方法

启动时如果检测到断点文件，会提示是否恢复

## 监控和日志

### 实时监控

CLI 运行时实时输出：

- 总检测数
- 当前速度（次/秒）
- 运行时间
- 匹配数量

### 数据日志

位置: `data_logs/`

- `current_data.json`: 当前状态
- `history_data.json`: 历史数据
- `performance.log`: 性能日志

### 运行日志

位置: `logs/`

- `collision.log`: 碰撞引擎日志
- 自动轮转，保留最近5个文件

## 配置文件

编辑 `config.json`:

```json
{
    "collision": {
        "checkpoint_interval": 30,
        "dedup_max_size": 1000000,
        "progress_interval": 1000,
        "max_workers": null
    },
    "gpu": {
        "batch_size": 100000,
        "device_index": 0,
        "auto_select": true
    },
    "monitoring": {
        "enabled": true,
        "interval": 5
    },
    "logging": {
        "level": "INFO",
        "file": "logs/collision.log"
    }
}
```

## 测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行碰撞引擎测试
python -m pytest tests/test_collision_*.py

# 运行GPU测试
python -m pytest tests/test_gpu_*.py

# 运行断点续传测试
python test_checkpoint_resume.py
```

## 性能基准

### CPU性能

- 纯Python: ~100-500 次/秒
- coincurve: ~1,000-3,000 次/秒
- 多线程(8核): ~5,000-10,000 次/秒

### GPU性能

**最新实测数据** (Intel Arc A770, v5.0.0):

| 指标 | 数值 | 说明 |
|------|------|------|
| 峰值吞吐量 (异步) | **4.89M keys/s** | 异步双缓冲 + GPU PRNG |
| 峰值吞吐量 (同步) | **3.07M keys/s** | GPU PRNG + 双缓冲 |
| 显存使用 | 0.42 MB/批次 | 高效利用 |
| 错误率 | 0.00% | 稳定运行 |

> **历史数据** (Intel Arc A770, v2.2.0, 已废弃): 平均吞吐量 ~203K keys/s, 峰值 ~240K keys/s, 批次 5,000-10,000。
> 从 v2.2.0 到 v3.5.0，性能提升 **24x** (203K→4.89M keys/s)。

**理论性能参考**:

- 中端GPU (GTX 1060): ~50,000-100,000 次/秒
- 高端GPU (RTX 3080): ~200,000-500,000 次/秒
- 旗舰GPU (RTX 4090): ~1,000,000+ 次/秒

> 📊 查看完整GPU测试指南: [GPU引擎指南](docs/gpu-engine-guide.md)

*实际性能取决于批次大小、目标数量和设备性能*

## 安全注意事项

⚠️ **重要提示**

- 本项目仅用于学习和研究
- 不要用于非法用途
- 碰撞真实地址的概率极低（2^-256）
- 发现的私钥应立即安全处理

> 📚 **v4.4.0 安全改进**: 本版本包含多项安全修复，详见 [安全改进文档](docs/SECURITY_IMPROVEMENTS.md)。

## 技术架构

### 核心组件

1. **碰撞引擎**
   - KeyCollisionEngine: CPU多线程引擎
   - GPUCollisionEngine: GPU加速引擎

2. **目标管理**
   - TargetResolver: 地址验证和解析
   - O(1)哈希查找优化

3. **状态管理**
   - CheckpointManager: 断点保存/恢复
   - DeduplicationFilter: Bloom过滤器去重

4. **监控系统**
   - 性能指标采集
   - 数据日志记录
   - 实时统计

### 线程模型

```
主线程 (CLI)
    ↓
工作线程池 (CPU模式)
    ├── Worker 1
    ├── Worker 2
    └── ...

或

GPU线程 (GPU模式)
    └── GPU批量计算
```

## 常见问题

### Q: GPU初始化失败？

A: 检查：

1. 是否安装了pyopencl
2. OpenCL驱动是否正确
3. GPU设备是否支持OpenCL

### Q: 如何提高性能？

A:

1. 安装coincurve库
2. 启用GPU加速
3. 调整批次大小
4. 增加工作线程数

### Q: 断点文件在哪？

A: `data_logs/checkpoint.json`

### Q: 如何添加更多目标地址？

A:

1. CLI: 使用 `-t` 参数直接传入，或 `-f` 指定文件（每行一个）
2. 代码: 传入targets集合

## 贡献

欢迎提交Issue和Pull Request！

## 加密出口管制

本软件包含加密功能，可能受到美国出口管制条例 (EAR 742.15) 及其他国家出口管制法规的约束。用户有责任确保遵守当地法律法规。

- 加密功能：secp256k1 椭圆曲线、SHA-256/RIPEMD-160 哈希、AES 对称加密
- 出口分类：可能属于 ECC 5A002 类（加密物品）

详情请参考：[加密出口管制声明](docs/legal/export-control.md)

## 许可证

本项目仅供学习和研究使用。项目使用 MIT 许可证，详情见 [LICENSE](LICENSE)。

## 相关链接

- [比特币白皮书](https://bitcoin.org/bitcoin.pdf)
- [OpenCL规范](https://www.khronos.org/opencl/)
- [secp256k1椭圆曲线](https://en.bitcoin.it/wiki/Secp256k1)
- [生日悖论](https://en.wikipedia.org/wiki/Birthday_problem)

## 文档

- [📚 文档索引](docs/DOCUMENT_INDEX.md) - 完整文档导航
- [🚀 GPU引擎使用指南](docs/gpu-engine-guide.md) - GPU加速详细指南
- [⚙️ GPU配置指南](GPU_CONFIG_GUIDE.md) - GPU配置优化指南（新增）
- [🔑 Bech32/P2SH地址支持](docs/bech32-p2sh-support.md) - 多地址类型支持
- [📖 API参考](docs/api-reference.md) - 完整API文档
- [⚡ 性能优化](docs/technical-docs/performance-optimization.md) - 性能调优指南
- [🔒 安全指南](docs/security-guidelines.md) - 安全最佳实践
