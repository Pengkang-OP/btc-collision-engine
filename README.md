# BTC 碰撞引擎

比特币私钥碰撞引擎，支持CPU和GPU加速，用于学习和研究比特币地址碰撞。

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Contributions](https://img.shields.io/badge/Contributions-Welcome-orange.svg)](CONTRIBUTING.md)

**📚 想参与开发？查看 [贡献指南](CONTRIBUTING.md)**

## 功能特性

- ✅ 多种碰撞模式
  - 随机碰撞：随机生成私钥进行匹配
  - 范围扫描：在指定范围内顺序扫描
  - 暴力穷举：从指定起点开始递增
- ✅ GPU加速（OpenCL）
  - 支持NVIDIA、AMD、Intel显卡
  - 批量并行计算
  - 异步流水线优化
  - 自动内存优化
- ✅ 多地址类型支持
  - P2PKH地址（1开头）
  - P2SH地址（3开头）
  - Bech32地址（bc1开头，SegWit）
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
- ✅ 图形界面
  - 友好的操作界面
  - 实时状态显示
  - 目标地址管理

## 快速开始

### 图形界面模式

```bash
python key_collision_gui.py
```

### 命令行模式

```bash
python key_collision_cli.py
```

### 旧版主引擎（纯Python）

```bash
python key_collision.py
```

## 项目结构

```
btc-collision-engine/
├── key_collision_gui.py      # GUI主程序
├── key_collision_cli.py      # 命令行程序
├── key_collision.py          # 旧版主引擎
├── gpu_engine.py             # GPU引擎实现
├── src/                      # 核心模块
│   ├── collision/            # 碰撞引擎
│   │   ├── key_collision_engine.py    # CPU碰撞引擎
│   │   ├── gpu_collision_engine.py    # GPU碰撞引擎
│   │   ├── checkpoint_manager.py      # 断点管理
│   │   ├── deduplication_filter.py    # 去重过滤器
│   │   ├── collision_stats.py         # 统计数据
│   │   └── target_resolver.py         # 目标地址解析
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

### 基础依赖

```bash
pip install -r requirements.txt
```

### GPU加速（可选）

```bash
# 安装 PyOpenCL
pip install pyopencl

# 安装对应平台的OpenCL驱动
# NVIDIA: 安装CUDA Toolkit
# AMD: 安装AMD GPU驱动
# Intel: 安装Intel Graphics驱动
```

### 性能优化（推荐）

```bash
# coincurve: 提升CPU性能3-5倍
pip install coincurve

# numpy: GPU计算优化
pip install numpy
```

## 使用方法

### GUI操作

1. **启动程序**
   ```bash
   python key_collision_gui.py
   ```

2. **添加目标地址**
   - 在文本框中输入比特币地址（每行一个）
   - 或从文件加载地址列表
   - 点击"解析"按钮验证地址

3. **选择碰撞模式**
   - **随机碰撞**: 无限随机生成私钥
   - **范围扫描**: 设置起止范围（十六进制）
   - **暴力穷举**: 设置起始点

4. **高级选项**
   - ☑️ 启用断点续传
   - ☑️ 启用去重过滤
   - ☑️ 使用GPU加速

5. **启动碰撞**
   - 点击"开始"按钮
   - 实时查看统计信息
   - 随时可以暂停/停止

### 命令行使用

```bash
# 从文件加载目标地址
python key_collision_cli.py --targets addresses.txt

# 使用随机模式
python key_collision_cli.py --mode random

# 使用GPU加速
python key_collision_cli.py --gpu

# 启用断点续传
python key_collision_cli.py --checkpoint
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
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 列出所有可用GPU设备
GPUCollisionEngine.list_devices()
```

### 选择特定GPU

在GUI的"高级选项"中选择GPU设备索引，或在代码中指定：

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

GUI界面显示：
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

- 中端GPU (GTX 1060): ~50,000-100,000 次/秒
- 高端GPU (RTX 3080): ~200,000-500,000 次/秒
- 旗舰GPU (RTX 4090): ~1,000,000+ 次/秒

*实际性能取决于批次大小、目标数量和设备性能*

## 安全注意事项

⚠️ **重要提示**

- 本项目仅用于学习和研究
- 不要用于非法用途
- 碰撞真实地址的概率极低（2^-256）
- 发现的私钥应立即安全处理

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
主线程 (GUI/CLI)
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
1. GUI: 直接在文本框输入
2. CLI: 使用 `--targets` 参数指定文件
3. 代码: 传入targets集合

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

本项目仅供学习和研究使用。

## 相关链接

- [比特币白皮书](https://bitcoin.org/bitcoin.pdf)
- [OpenCL规范](https://www.khronos.org/opencl/)
- [secp256k1椭圆曲线](https://en.bitcoin.it/wiki/Secp256k1)
- [生日悖论](https://en.wikipedia.org/wiki/Birthday_problem)

## 文档

- [📚 文档索引](docs/DOCUMENT_INDEX.md) - 完整文档导航
- [🚀 GPU引擎使用指南](docs/gpu-engine-guide.md) - GPU加速详细指南
- [🔑 Bech32/P2SH地址支持](docs/bech32-p2sh-support.md) - 多地址类型支持
- [📖 API参考](docs/api-reference.md) - 完整API文档
- [⚡ 性能优化](docs/performance-optimization.md) - 性能调优指南
- [🔒 安全指南](docs/security-guidelines.md) - 安全最佳实践
