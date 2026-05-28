# 使用场景指南

> **版本**: v4.2.2 | **最后更新**: 2026-05-15
> **面向**: 所有用户
> **目的**: 通过实际用例帮助用户快速上手

---

## 目录

- [场景1: 学习比特币地址生成原理](#场景1-学习比特币地址生成原理)

- [场景2: 测试GPU性能](#场景2-测试gpu性能)

- [场景3: 研究地址碰撞概率](#场景3-研究地址碰撞概率)

- [场景4: 批量地址验证](#场景4-批量地址验证)

- [场景5: 断点续传长时间运行](#场景5-断点续传长时间运行)

- [场景6: 多GPU加速碰撞](#场景6-多gpu加速碰撞)

---

## 场景1: 学习比特币地址生成原理

### 目标

了解比特币私钥、公钥和地址的生成过程

### 前置条件

- [OK] 已安装项目（使用 `scripts/install/install.bat` 或 `bash scripts/install/install.sh`）

- [OK] 已运行健康检查（`python -m src.utils.health_check`）

### 步骤

#### 步骤1: 运行基础碰撞测试

```bash
# 使用测试地址运行10秒
python key_collision_cli.py -t 12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr -m random --duration 10

```

**预期输出**:

```bash
----------------------------------------------------------------------
碰撞模式     : random
目标地址数   : 1
加速模式     : CPU
工作线程数   : 8
----------------------------------------------------------------------
[00:00:10] 已检查: 25,432 | 速度: 2.54K/s | 匹配: 0
----------------------------------------------------------------------
对撞结束 - 最终统计
----------------------------------------------------------------------
  加速模式  : CPU
  总检查数  : 25,432
  运行时间  : 00:00:10
  平均速度  : 2.54K/s
  发现匹配  : 0 个

```

#### 步骤2: 观察地址格式

创建测试脚本 `test_address_formats.py`:

```python
from src.collision.targets.resolver import TargetResolver

resolver = TargetResolver()

# 测试不同格式的地址
test_inputs = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
    "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",  # Bech32
]

for addr in test_inputs:
    result = resolver.resolve(addr)
    print(f"输入: {addr}")
    print(f"解析: {result}")
    print()

```

运行:

```bash
python test_address_formats.py

```

### 学习要点

1. 私钥是256位随机数

2. 公钥通过椭圆曲线运算从私钥生成

3. 地址通过哈希运算从公钥生成

4. 碰撞概率极低（2^-256）

### 常见问题

**Q: 为什么找不到匹配？**
A: 这是正常的！比特币地址空间太大（2^256），随机碰撞的概率几乎为零。这个工具的目的是学习和研究，而不是真正找到别人的私钥。

---

## 场景2: 测试GPU性能

### 目标

评估GPU加速效果，对比CPU和GPU性能

### 前置条件

- [OK] 已安装GPU依赖（`pip install pyopencl`）

- [OK] GPU支持OpenCL 1.2+

### 步骤

#### 步骤1: 检测GPU设备

```bash
python -c "import pyopencl as cl; [print(f'{i}: {d.name}') for i, p in enumerate(cl.get_platforms()) for d in p.get_devices()]"

```

**预期输出**:

```bash
0: Intel(R) Arc(TM) A770 Graphics
1: NVIDIA GeForce GTX 1660 Ti

```

#### 步骤2: CPU基准测试

```bash
# CPU模式，运行30秒
python key_collision_cli.py -f valid_addresses.txt -m random --duration 30

```

记录CPU速度（例如：3,000 keys/s）

#### 步骤3: GPU基准测试

```bash
# 单GPU模式
python key_collision_cli.py -f valid_addresses.txt --use-gpu -m random --duration 30

```

**预期输出**:

```bash
加速模式     : 单GPU
GPU 设备     : Intel(R) Arc(TM) A770 Graphics
批次大小     : 65536
----------------------------------------------------------------------
[00:00:30] GPU | 已检查: 6,102,450 | 速度: 203.41K/s | 匹配: 0

```

#### 步骤4: 性能对比

创建性能对比表：

| 模式 | 速度 (keys/s) | 提升倍数 |
|------|---------------|----------|
| CPU (8线程) | 3,000 | 1x |
| GPU (Arc A770) | 203,410 | **68x** |

### 优化建议

1. **调整批次大小**:

   ```bash
   # 编辑 config.json
   {
     "gpu": {
       "batch_size": 100000  # 尝试 50000-200000
     }
   }

   ```

2. **选择最佳GPU**:

   ```bash
   # 指定GPU索引
   python key_collision_cli.py -f valid_addresses.txt --use-gpu -m random --gpu-device 0

   ```

### 常见问题

**Q: GPU初始化失败？**
A: 检查：

1. 是否安装了pyopencl

2. OpenCL驱动是否正确

3. GPU设备是否支持OpenCL 1.2+

---

## 场景3: 研究地址碰撞概率

### 目标

通过实验验证生日悖论和碰撞概率

### 步骤

#### 步骤1: 小空间碰撞测试

```bash
# 在小范围内搜索（1-1000000）
python key_collision_cli.py -t 12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr -m range --start 1 --end 1000000 --duration 60

```

#### 步骤2: 统计碰撞率

创建统计脚本 `collision_stats.py`:

```python
import json
from pathlib import Path

# 读取日志数据
log_dir = Path("data_logs")
history_files = list(log_dir.glob("history_data_*.json"))

total_checked = 0
total_matches = 0

for file in history_files:
    with open(file) as f:
        data = json.load(f)
        total_checked += data.get('total_checked', 0)
        total_matches += len(data.get('matches', []))

print(f"总检查数: {total_checked:,}")
print(f"总匹配数: {total_matches}")
print(f"碰撞率: {total_matches / total_checked if total_checked > 0 else 0:.2e}")

```

运行:

```bash
python collision_stats.py

```

### 理论分析

**生日悖论**:

- 需要检查约 2^80 个地址才有50%概率找到碰撞

- 以200K keys/s速度，需要约 10^15 年

### 学习要点

1. 碰撞概率 = 检查数 / 地址空间

2. 地址空间 = 2^256（极大）

3. 实际碰撞几乎不可能

---

## 场景4: 批量地址验证

### 目标

验证大量比特币地址的有效性

### 步骤

#### 步骤1: 准备地址文件

创建 `addresses_to_validate.txt`:

```bash
# 有效的P2PKH地址
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr

# 有效的P2SH地址
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy

# 有效的Bech32地址
bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq

# 无效地址（用于测试）
invalid_address
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfN

```

#### 步骤2: 使用Python验证

```python
from src.collision.targets.resolver import TargetResolver
from src.collision.targets.validator import AddressValidator

resolver = TargetResolver()
validator = AddressValidator()

# 读取地址文件
with open('addresses_to_validate.txt') as f:
    addresses = [line.strip() for line in f if line.strip() and not line.startswith('#')]

print(f"待验证地址数: {len(addresses)}\n")

valid_count = 0
invalid_count = 0

for addr in addresses:
    is_valid = validator.validate(addr)
    if is_valid:
        valid_count += 1
        result = resolver.resolve(addr)
        print(f"[OK] {addr}")
        print(f"   解析: {result}")
    else:
        invalid_count += 1
        print(f"[FAIL] {addr} - 无效地址")
    print()

print(f"\n验证结果:")
print(f"  有效: {valid_count}")
print(f"  无效: {invalid_count}")

```

运行:

```bash
python validate_addresses.py

```

### 输出示例

```bash
待验证地址数: 5

[OK] 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
   解析: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

[OK] 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
   解析: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy

[FAIL] invalid_address - 无效地址

验证结果:
  有效: 3
  无效: 2

```

---

## 场景5: 断点续传长时间运行

### 目标

运行长时间碰撞任务，支持中断后恢复

### 步骤

#### 步骤1: 启动带断点的任务

```bash
# 启用断点续传，运行1小时
python key_collision_cli.py -f valid_addresses.txt -m random --checkpoint --checkpoint-interval 30 --duration 3600

```

#### 步骤2: 中断任务

按 `Ctrl+C` 中断：

```bash
用户中断，正在停止...
断点已保存: data_logs/checkpoint.json

对撞结束 - 最终统计
----------------------------------------------------------------------
  总检查数  : 1,234,567
  运行时间  : 00:15:23

```

#### 步骤3: 从断点恢复

```bash
# 再次运行相同命令，会自动检测断点
python key_collision_cli.py -f valid_addresses.txt -m random --checkpoint --duration 3600

```

**输出**:

```bash
检测到断点文件
  上次运行: 2026-04-23 10:30:00
  已检查数: 1,234,567

是否从断点继续? (Y/N): Y

从断点恢复运行...

```

### 断点文件位置

- **位置**: `data_logs/collision_checkpoint.json`

- **内容**: 当前检查的私钥数量、时间戳、配置

### 注意事项

1. 断点每30秒自动保存（可配置）

2. 程序停止时也会保存

3. 删除断点文件可重新开始

---

## 场景6: 多GPU加速碰撞

### 目标

使用多个GPU同时加速碰撞

### 前置条件

- [OK] 2个或更多GPU

- [OK] 已安装pyopencl

### 步骤

#### 步骤1: 列出所有GPU

```bash
python -c "import pyopencl as cl; [print(f'GPU {i}: {d.name} ({d.global_mem_size // 1024**3}GB)') for i, p in enumerate(cl.get_platforms()) for d in p.get_devices()]"

```

**输出**:

```bash
GPU 0: NVIDIA GeForce GTX 1660 Ti (6GB)
GPU 1: Intel(R) Arc(TM) A770 Graphics (16GB)

```

#### 步骤2: 运行多GPU碰撞

```bash
# 使用所有GPU
python key_collision_cli.py -f valid_addresses.txt --multi-gpu -m random --duration 60

# 或指定GPU
python key_collision_cli.py -f valid_addresses.txt --multi-gpu --gpu-indices 0,1 -m random --duration 60

```

**输出**:

```bash
加速模式     : 多GPU (2 个设备)
----------------------------------------------------------------------
[00:00:30] GPU x2 | 已检查: 8,234,567 | 速度: 274.49K/s | 匹配: 0

对撞结束 - 最终统计
----------------------------------------------------------------------
  加速模式  : 多GPU (2 个设备)
  总检查数  : 8,234,567
  运行时间  : 00:00:30
  平均速度  : 274.49K/s

  各GPU明细:
    GPU 0: 检查 2,345,678 | 速度 78.19K/s
    GPU 1: 检查 5,888,889 | 速度 196.30K/s

```

### 性能对比

| 配置 | 速度 (keys/s) | 提升 |
|------|---------------|------|
| 单GPU (GTX 1660 Ti) | 78,190 | 1x |
| 单GPU (Arc A770) | 196,300 | 2.5x |
| 多GPU (两者) | 274,490 | **3.5x** |

### 负载均衡

编辑 `config.json`:

```json
{
  "gpu": {
    "mode": "multi",
    "load_balancing": "performance",  // 按性能分配
    "auto_tuning": true
  }
}

```

---

## 通用技巧

### 1. 性能优化

```bash
# 安装优化库
pip install coincurve gmpy2 pycryptodome

# 启用所有优化
python key_collision_cli.py -f valid_addresses.txt -m random --duration 60

```

### 2. 系统维护

```bash
# 定期检查健康状态
python -m src.utils.health_check --gpu

# 清理过期数据
python -m src.utils.data_cleanup --dry-run  # 先试运行
python -m src.utils.data_cleanup             # 实际清理

```

### 3. 日志查看

```bash
# 查看最新日志
tail -f logs/collision.log  # Linux/macOS
Get-Content logs/collision.log -Wait  # Windows PowerShell

# 查看监控数据
python -m src.monitoring.monitor_cli

```

---

## 相关文档

- [快速开始指南](getting-started.md)

- [GPU引擎使用指南](gpu-engine-guide.md)

- [配置使用示例](config-usage-examples.md)

- [故障排除](troubleshooting.md)

- [API参考](api-reference.md)

---

**文档版本**: v4.2.2
**最后更新**: 2026-04-28
**维护者**: BTC Collision Team
