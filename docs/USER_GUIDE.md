# BTC碰撞引擎 - 用户使用指南

**版本**: v3.3.0  
**更新日期**: 2026-04-27  
**适用对象**: 所有用户（新手到高级）

---

## 📖 目录

1. [快速入门](#快速入门)
2. [启动方式](#启动方式)
3. [命令别名（快捷命令）](#命令别名快捷命令)
4. [快速模式](#快速模式)
5. [交互式向导](#交互式向导)
6. [紧凑模式](#紧凑模式)
7. [高级用法](#高级用法)
8. [配置文件](#配置文件)
9. [常见问题](#常见问题)
10. [故障排查](#故障排查)

---

## 🚀 快速入门

### 5分钟快速开始

**Windows用户**（推荐）：

```bash
# 方法1: 双击启动
start.bat

# 方法2: 命令行快速启动
start.bat qs
```

**Linux/Mac用户**：

```bash
# 方法1: 交互式向导
python key_collision_cli.py --quick-start

# 方法2: 快速模式
python key_collision_cli.py --quick-run
```

---

## 🎯 启动方式

### 方式1: 交互式向导（推荐新手）

交互式向导会引导您完成所有配置步骤。

```bash
# Windows
start.bat qs

# Linux/Mac
python key_collision_cli.py --quick-start
```

**向导步骤**:

1. **选择目标地址来源**
   - 单个地址输入
   - 从文件读取（支持targets.txt）

2. **选择碰撞模式**
   - 随机碰撞（推荐新手）
   - 范围扫描
   - 暴力穷举

3. **选择功能选项**
   - 断点续传（强烈推荐）
   - 去重过滤（推荐）
   - 运行时长限制

4. **确认并启动**
   - 显示配置摘要
   - 3秒倒计时
   - 开始运行

---

### 方式2: 快速模式（推荐熟练用户）

快速模式使用默认配置直接启动，跳过向导。

```bash
# Windows
start.bat qr

# Linux/Mac
python key_collision_cli.py --quick-run
```

**默认配置**:

- 目标文件: `targets.txt`
- 碰撞模式: 随机碰撞
- 断点续传: 启用
- 去重过滤: 启用
- 运行时长: 无限制

**文件预览**:
快速模式会自动检测并显示`targets.txt`文件内容：

```
发现目标文件: targets.txt (3 个地址)

地址预览:
  1. 1A1zP1eP5QGefi2DMPTf...
  2. 3J98t1WpEZ73CNmQviec...
  3. bc1qxy2kgdygjrsqtzq2...
  ... 及其他 0 个地址
```

---

## ⌨️ 命令别名（快捷命令）

为了减少输入量，我们提供了6个命令别名。

### 别名列表

| 别名 | 完整命令 | 功能说明 |
|------|---------|---------|
| `qs` | `--quick-start` | 交互式快速向导 |
| `qr` | `--quick-run` | 快速模式运行 |
| `hc` | `--health-check` | 系统健康检查 |
| `cc` | `--config-check` | 配置验证 |
| `ex` | `--examples` | 显示使用示例 |
| `rec` | `--recommend` | 参数推荐 |

### 使用示例

```bash
# Windows（所有别名都可用）
start.bat qs      # 启动交互式向导
start.bat qr      # 快速模式运行
start.bat hc      # 健康检查
start.bat cc      # 配置验证
start.bat ex      # 显示示例
start.bat rec     # 参数推荐

# Linux/Mac（需要使用完整命令）
python key_collision_cli.py --quick-start
python key_collision_cli.py --quick-run
python key_collision_cli.py --health-check
python key_collision_cli.py --config-check
python key_collision_cli.py --examples
python key_collision_cli.py --recommend
```

---

## ⚡ 快速模式

快速模式是最高效的启动方式，适合已知配置的用户。

### 基本用法

```bash
# Windows
start.bat qr

# Linux/Mac
python key_collision_cli.py --quick-run
```

### 工作流程

1. **检测目标文件**
   - 自动查找`targets.txt`
   - 如果不存在，提示创建

2. **显示文件预览**
   - 统计地址数量
   - 预览前3个地址
   - 显示地址类型

3. **显示配置摘要**

   ```
   ════════════════════════════════════════════
   快速模式配置
   ════════════════════════════════════════════
   目标文件: targets.txt
   碰撞模式: random
   断点续传: 启用
   去重过滤: 启用
   运行时长: 无限制
   ════════════════════════════════════════════
   ```

4. **倒计时启动**
   - 3秒倒计时
   - 按Ctrl+C可取消

5. **开始运行**
   - 显示进度条
   - 实时更新统计

### 修改快速模式配置

如需修改默认配置，编辑`src/cli/commands.py`中的配置常量：

```python
QUICK_RUN_DEFAULTS = {
    'target_file': 'targets.txt',        # 目标文件
    'mode': 'random',                    # 碰撞模式
    'checkpoint': True,                  # 断点续传
    'dedup': True,                       # 去重过滤
    'duration': 0,                       # 运行时长（0=无限制）
    'countdown_seconds': 3,              # 倒计时秒数
}
```

---

## 🧙 交互式向导

交互式向导适合新手用户或需要自定义配置的场景。

### 启动向导

```bash
# Windows
start.bat qs

# Linux/Mac
python key_collision_cli.py --quick-start
```

### 步骤详解

#### 步骤1: 选择目标地址来源

```
【步骤 1/4】选择目标地址来源
   1. 输入单个地址
   2. 从文件读取

   [?] 提示: 支持以下地址格式:
      - P2PKH: 1开头 (例如: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa)
      - P2SH: 3开头 (例如: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy)
      - Bech32: bc1开头 (例如: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh)

请选择 (1/2):
```

**选项说明**:

- **选项1**: 手动输入单个地址
- **选项2**: 从文件读取（推荐多个地址）

**文件要求**:

- 每行一个地址
- 支持`#`注释
- 支持空行
- 推荐文件名：`targets.txt`

#### 步骤2: 选择碰撞模式

```
【步骤 2/4】选择碰撞模式
   1. 随机碰撞 (推荐新手)
   2. 范围扫描
   3. 暴力穷举

   [?] 模式说明:
      - 随机碰撞: 随机生成私钥，适合未知范围的地址 (推荐新手)
      - 范围扫描: 扫描指定的私钥范围，需要起始和结束值
      - 暴力穷举: 从指定位置开始顺序搜索

请选择 (1/2/3):
```

**模式说明**:

- **随机碰撞**: 随机生成私钥，适合大多数场景
- **范围扫描**: 指定私钥范围，适合已知范围
- **暴力穷举**: 顺序扫描，适合完整搜索

#### 步骤3: 选择功能选项

```
【步骤 3/4】选择功能选项
   [?] 功能说明:
      - 断点续传: 保存进度，中断后可继续 (强烈推荐)
      - 去重过滤: 避免重复检查相同的私钥 (推荐)
      - 运行时长: 设置最大运行时间，0表示不限制

启用断点续传? (y/n) [Y]: y
启用的去重过滤? (y/n) [Y]: y
运行时长（秒，0=无限制）[0]: 0
```

**功能说明**:

- **断点续传**: 保存进度到文件，中断后可恢复
- **去重过滤**: 使用Bloom过滤器避免重复检查
- **运行时长**: 自动停止时间（0表示不限制）

#### 步骤4: 确认并启动

```
【步骤 4/4】确认配置
╔═══════════════════════════════════════════════════════════╗
║                    配置摘要                              ║
╠═══════════════════════════════════════════════════════════╣
║ 目标地址: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa             ║
║ 碰撞模式: random                                         ║
║ 断点续传: 启用                                           ║
║ 去重过滤: 启用                                           ║
║ 运行时长: 无限制                                         ║
╚═══════════════════════════════════════════════════════════╝

将在 3 秒后启动... (按 Ctrl+C 取消)
```

---

## 📦 紧凑模式

紧凑模式跳过向导中的详细帮助信息，加快配置速度。

### 使用紧凑模式

```bash
# Windows（暂不支持，需使用完整命令）
python key_collision_cli.py --quick-start --compact

# Linux/Mac
python key_collision_cli.py --quick-start --compact
```

### 对比

**正常模式**:

```
【步骤 1/4】选择目标地址来源
   1. 输入单个地址
   2. 从文件读取

   [?] 提示: 支持以下地址格式:
      - P2PKH: 1开头 (例如: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa)
      - P2SH: 3开头 (例如: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy)
      - Bech32: bc1开头 (例如: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh)

请选择 (1/2):
```

**紧凑模式**:

```
【步骤 1/4】选择目标地址来源
   1. 输入单个地址
   2. 从文件读取

请选择 (1/2):
```

### 适用场景

- ✅ 熟练用户
- ✅ 快速测试
- ✅ 自动化脚本
- ✅ 终端窗口较小

---

## 🔧 高级用法

### 1. 自定义目标文件

创建自定义地址文件：

```bash
# 创建 targets.txt
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt
echo "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy" >> targets.txt
echo "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh" >> targets.txt
```

### 2. 指定运行时长

```bash
# 运行1小时（3600秒）
python key_collision_cli.py --quick-run --duration 3600
```

### 3. 禁用断点续传

```bash
python key_collision_cli.py --quick-run --no-checkpoint
```

### 4. 禁用去重过滤

```bash
python key_collision_cli.py --quick-run --no-dedup
```

### 5. 指定碰撞模式

```bash
# 随机模式
python key_collision_cli.py -t targets.txt -m random

# 范围扫描
python key_collision_cli.py -t targets.txt -m range --start 1 --end 1000000

# 暴力穷举
python key_collision_cli.py -t targets.txt -m brute --start 1
```

### 6. GPU加速

```bash
# 使用GPU
python key_collision_cli.py --quick-run --engine gpu

# 多GPU
python key_collision_cli.py --quick-run --engine multi-gpu
```

### 7. 进度显示

运行时会显示实时进度：

```
[00:05] [CPU] ████░░░░░░░░░░░░ 25.0% | 1,234/4,936 | 速度: 246/s | ETA: 15s | 匹配: 0
```

**进度信息说明**:

- `[00:05]`: 已运行时间
- `[CPU]`: 引擎类型（CPU/GPU/MULTI-GPU）
- `████░░░░░░░░░░░░`: 可视化进度条
- `25.0%`: 完成百分比
- `1,234/4,936`: 已检查/总数
- `速度: 246/s`: 每秒检查数量
- `ETA: 15s`: 预计剩余时间
- `匹配: 0`: 找到的匹配数

---

## 📝 配置文件

### 主配置文件

位置：`config.json`

```json
{
  "collision": {
    "mode": "random",
    "target_file": "targets.txt",
    "checkpoint": true,
    "dedup": true,
    "duration": 0
  },
  "engine": {
    "type": "cpu",
    "threads": 4
  },
  "gpu": {
    "batch_size": 10000,
    "memory_limit": 0.8
  }
}
```

### 配置示例文件

查看完整配置示例：

```bash
# Windows
notepad config.example.json

# Linux/Mac
cat config.example.json
```

---

## ❓ 常见问题

### Q1: 如何创建targets.txt文件？

**A**: 创建文本文件，每行一个地址：

```
# 我的目标地址
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
```

### Q2: 支持哪些地址格式？

**A**: 支持3种比特币地址格式：

- **P2PKH**: 以`1`开头（例：`1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`）
- **P2SH**: 以`3`开头（例：`3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy`）
- **Bech32**: 以`bc1`开头（例：`bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh`）

### Q3: 如何停止运行？

**A**: 按`Ctrl+C`即可安全停止。如果启用了断点续传，进度会自动保存。

### Q4: 如何恢复中断的运行？

**A**: 如果启用了断点续传，直接再次运行即可自动恢复：

```bash
start.bat qr
```

### Q5: 快速模式找不到targets.txt怎么办？

**A**: 系统会提示您创建文件。您可以：

1. 手动创建`targets.txt`
2. 使用交互式向导输入地址

### Q6: 命令别名不工作？

**A**: 确保：

1. 使用`start.bat`（Windows）
2. 别名在Windows批处理中定义
3. Linux/Mac需要使用完整命令

### Q7: 如何提高运行速度？

**A**:

1. 使用GPU加速（`--engine gpu`）
2. 增加线程数（`--threads 8`）
3. 启用去重过滤（避免重复检查）
4. 使用快速模式（减少启动时间）

### Q8: 如何查看帮助信息？

**A**:

```bash
# 完整帮助
start.bat --help

# 显示示例
start.bat ex

# 参数推荐
start.bat rec
```

---

## 🔍 故障排查

### 问题1: 启动失败

**症状**: 运行`start.bat`后闪退

**解决方案**:

```bash
# 1. 检查Python安装
python --version

# 2. 检查依赖
pip install -r requirements.txt

# 3. 查看详细错误
python key_collision_cli.py --help
```

### 问题2: targets.txt文件不存在

**症状**: 快速模式提示找不到文件

**解决方案**:

```bash
# 创建文件
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt

# 或使用向导
start.bat qs
```

### 问题3: GPU不可用

**症状**: GPU引擎启动失败

**解决方案**:

```bash
# 1. 检查GPU
python key_collision_cli.py --health-check

# 2. 使用CPU
start.bat qr

# 3. 安装GPU依赖
pip install -r requirements-gpu.txt
```

### 问题4: 进度显示异常

**症状**: 进度条不更新或显示错误

**解决方案**:

```bash
# 1. 检查终端支持
# 使用支持ANSI转义的终端

# 2. 禁用彩色输出
python key_collision_cli.py --quick-run --no-color

# 3. 更新依赖
pip install --upgrade rich
```

### 问题5: 国际化不工作

**症状**: 显示英文而非中文

**解决方案**:

```bash
# 设置环境变量
set LANG=zh_CN.UTF-8

# 或在Linux/Mac
export LANG=zh_CN.UTF-8
```

---

## 📚 相关文档

- [README.md](README.md) - 项目概述
- [CHANGELOG.md](CHANGELOG.md) - 版本历史
- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南
- [config.example.json](config.example.json) - 配置示例
- [docs/](docs/) - 详细文档目录

---

## 🆘 获取帮助

如果遇到问题：

1. **查看本文档** - 大多数问题可以在这里找到答案
2. **查看FAQ** - 常见问题解答
3. **查看日志** - 检查`logs/`目录下的日志文件
4. **提交Issue** - 在GitHub提交问题

---

## 🎉 快速参考卡

### 最常用命令

```bash
# 新手：交互式向导
start.bat qs

# 熟练：快速模式
start.bat qr

# 查看帮助
start.bat --help

# 查看示例
start.bat ex

# 健康检查
start.bat hc

# 配置验证
start.bat cc
```

### 文件位置

```
项目根目录/
├── start.bat              # Windows启动脚本
├── key_collision_cli.py   # CLI主程序
├── targets.txt            # 目标地址文件（需创建）
├── config.json            # 配置文件
└── logs/                  # 日志目录
```

### 快捷别名

| 别名 | 功能 | 适用场景 |
|------|------|---------|
| `qs` | 交互式向导 | 新手、自定义配置 |
| `qr` | 快速模式 | 熟练用户、快速启动 |
| `hc` | 健康检查 | 系统诊断 |
| `cc` | 配置验证 | 配置检查 |
| `ex` | 显示示例 | 学习用法 |
| `rec` | 参数推荐 | 优化配置 |

---

**文档版本**: v1.0  
**更新日期**: 2026-04-27  
**维护者**: BTC碰撞引擎团队

**祝您使用愉快！** 🚀
