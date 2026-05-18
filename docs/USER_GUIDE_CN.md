# BTC碰撞引擎 - 中文使用指南

**版本**: v4.2.2
**更新日期**: 2026-04-28
**语言**: 简体中文

---

## 📖 快速导航

- [5分钟快速开始](#5分钟快速开始)
- [命令速查表](#命令速查表)
- [功能详解](#功能详解)
- [常见问题](#常见问题)

---

## 🚀 5分钟快速开始

### Windows用户（推荐）

**第一步**: 双击`start.bat`或在命令行运行：

```bash
start.bat qs
```

**第二步**: 按照向导提示操作：

1. 选择地址来源（输入地址或从文件读取）
2. 选择碰撞模式（推荐"随机碰撞"）
3. 启用功能选项（推荐启用断点续传和去重）
4. 确认配置，等待3秒自动启动

**完成！** 程序开始运行，您会看到实时进度条。

---

### 已有targets.txt文件

如果您已经创建了`targets.txt`文件，可以直接使用快速模式：

```bash
start.bat qr
```

系统会自动检测文件并显示预览，3秒后开始运行。

---

## 📋 命令速查表

### 常用命令（Windows）

| 命令 | 功能 | 适用人群 |
|------|------|---------|
| `start.bat qs` | 交互式向导 | 新手、需要自定义 |
| `start.bat qr` | 快速模式 | 熟练用户、快速启动 |
| `start.bat hc` | 健康检查 | 系统诊断 |
| `start.bat cc` | 配置验证 | 检查配置 |
| `start.bat ex` | 显示示例 | 学习用法 |
| `start.bat rec` | 参数推荐 | 优化配置 |

### 常用命令（Linux/Mac）

```bash
# 交互式向导
python key_collision_cli.py --quick-start

# 快速模式
python key_collision_cli.py --quick-run

# 查看帮助
python key_collision_cli.py --help

# 显示示例
python key_collision_cli.py --examples
```

---

## 🎯 功能详解

### 1. 快速模式（--quick-run）

**最适合**: 熟练用户，已知配置

**特点**:

- ⚡ 跳过向导，直接启动
- 📁 自动检测`targets.txt`
- 👁️ 显示文件预览（前3个地址）
- ⏱️ 3秒倒计时（可取消）

**使用方法**:

```bash
start.bat qr
```

**运行流程**:

```
发现目标文件: targets.txt (3 个地址)

地址预览:
  1. 1A1zP1eP5QGefi2DMPTf...
  2. 3J98t1WpEZ73CNmQviec...
  3. bc1qxy2kgdygjrsqtzq2...

════════════════════════════════════════
快速模式配置
════════════════════════════════════════
目标文件: targets.txt
碰撞模式: random
断点续传: 启用
去重过滤: 启用
运行时长: 无限制
════════════════════════════════════════

将在 3 秒后启动... (按 Ctrl+C 取消)
```

---

### 2. 交互式向导（--quick-start）

**最适合**: 新手用户，需要引导

**特点**:

- 🧙 4步引导，简单易懂
- 💡 每步都有帮助提示
- 🎨 可视化界面
- ✅ 配置摘要确认

**使用方法**:

```bash
start.bat qs
```

**向导步骤**:

**步骤1**: 选择目标地址来源

```
【步骤 1/4】选择目标地址来源
   1. 输入单个地址
   2. 从文件读取

   [?] 提示: 支持以下地址格式:
      - P2PKH: 1开头 (例如: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa)
      - P2SH: 3开头 (例如: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy)
      - Bech32: bc1开头 (例如: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh)

请选择 (1/2): 2
```

**步骤2**: 选择碰撞模式

```
【步骤 2/4】选择碰撞模式
   1. 随机碰撞 (推荐新手)
   2. 范围扫描
   3. 暴力穷举

   [?] 模式说明:
      - 随机碰撞: 随机生成私钥，适合未知范围的地址 (推荐新手)
      - 范围扫描: 扫描指定的私钥范围，需要起始和结束值
      - 暴力穷举: 从指定位置开始顺序搜索

请选择 (1/2/3): 1
```

**步骤3**: 选择功能选项

```
【步骤 3/4】选择功能选项
   [?] 功能说明:
      - 断点续传: 保存进度，中断后可继续 (强烈推荐)
      - 去重过滤: 避免重复检查相同的私钥 (推荐)
      - 运行时长: 设置最大运行时间，0表示不限制

启用断点续传? (y/n) [Y]: y
启用去重过滤? (y/n) [Y]: y
运行时长（秒，0=无限制）[0]: 0
```

**步骤4**: 确认并启动

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

### 3. 紧凑模式（--compact）

**最适合**: 熟练用户，快速配置

**特点**:

- 📦 跳过详细帮助信息
- ⚡ 加快配置速度
- 🎯 适合小屏幕终端

**使用方法**:

```bash
python key_collision_cli.py --quick-start --compact
```

**对比示例**:

**正常模式**（显示帮助）:

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

**紧凑模式**（跳过帮助）:

```
【步骤 1/4】选择目标地址来源
   1. 输入单个地址
   2. 从文件读取

请选择 (1/2):
```

---

### 4. 进度显示

运行时会显示实时进度：

```
[00:05] [CPU] ████░░░░░░░░░░░░ 25.0% | 1,234/4,936 | 速度: 246/s | ETA: 15s | 匹配: 0
```

**详细说明**:

| 字段 | 含义 | 示例 |
|------|------|------|
| `[00:05]` | 已运行时间 | 5秒 |
| `[CPU]` | 引擎类型 | CPU / GPU / MULTI-GPU |
| `████░░░░░░░░░░░░` | 可视化进度条 | 25%完成 |
| `25.0%` | 完成百分比 | 25% |
| `1,234/4,936` | 已检查/总数 | 1234个，总共4936个 |
| `速度: 246/s` | 每秒检查数量 | 246个/秒 |
| `ETA: 15s` | 预计剩余时间 | 15秒 |
| `匹配: 0` | 找到的匹配数 | 0个 |

---

## 📝 创建目标地址文件

### 方法1: 命令行创建

**Windows**:

```bash
echo # 我的目标地址 > targets.txt
echo 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa >> targets.txt
echo 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy >> targets.txt
echo bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh >> targets.txt
```

**Linux/Mac**:

```bash
cat > targets.txt << EOF
# 我的目标地址
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
EOF
```

### 方法2: 文本编辑器创建

1. 用记事本或任何文本编辑器创建新文件
2. 输入地址（每行一个）
3. 保存为`targets.txt`

### 文件格式

```
# 这是注释，会被忽略
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

# 空行也会被忽略
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
```

**支持的地址格式**:

- ✅ **P2PKH**: 以`1`开头
- ✅ **P2SH**: 以`3`开头
- ✅ **Bech32**: 以`bc1`开头

---

## ❓ 常见问题

### Q: 我是新手，应该用什么方式启动？

**A**: 推荐使用交互式向导：

```bash
start.bat qs
```

向导会一步步引导您完成配置。

---

### Q: 如何停止运行？

**A**: 按`Ctrl+C`即可安全停止。

如果启用了断点续传，进度会自动保存，下次运行时会从断点继续。

---

### Q: 找不到targets.txt文件怎么办？

**A**: 有三种方法：

**方法1**: 创建文件

```bash
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt
```

**方法2**: 使用向导输入地址

```bash
start.bat qs
# 选择"输入单个地址"
```

**方法3**: 使用完整命令指定文件

```bash
python key_collision_cli.py -t my_addresses.txt -m random
```

---

### Q: 命令别名在Linux/Mac上不能用？

**A**: 命令别名是Windows特有的功能（在`start.bat`中定义）。

Linux/Mac用户需要使用完整命令：

```bash
# 代替 start.bat qs
python key_collision_cli.py --quick-start

# 代替 start.bat qr
python key_collision_cli.py --quick-run
```

---

### Q: 如何提高运行速度？

**A**: 有以下几种方法：

**1. 使用GPU加速**（推荐，可提速10-100倍）

```bash
python key_collision_cli.py --quick-run --engine gpu
```

**2. 增加CPU线程数**

```bash
python key_collision_cli.py --quick-run --threads 8
```

**3. 启用去重过滤**（避免重复检查）

```bash
# 默认已启用，无需额外参数
```

**4. 使用快速模式**（减少启动时间）

```bash
start.bat qr
```

---

### Q: 如何查看帮助信息？

**A**:

```bash
# 完整帮助
start.bat --help
# 或
python key_collision_cli.py --help

# 显示使用示例
start.bat ex

# 获取参数推荐
start.bat rec
```

---

### Q: 断点续传怎么用？

**A**: 断点续传默认启用，无需额外配置。

**示例**:

1. 第一次运行（启用断点续传）

   ```bash
   start.bat qr
   # 运行10分钟后按Ctrl+C停止
   ```

2. 第二次运行（自动恢复）

   ```bash
   start.bat qr
   # 系统会自动从上次的断点继续
   ```

---

### Q: 支持哪些碰撞模式？

**A**: 支持3种模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **随机碰撞** | 随机生成私钥 | 未知范围（推荐新手） |
| **范围扫描** | 扫描指定范围 | 已知私钥范围 |
| **暴力穷举** | 顺序扫描 | 完整搜索 |

**推荐**: 新手使用"随机碰撞"模式。

---

## 🔍 故障排查

### 问题1: 双击start.bat闪退

**原因**: Python未安装或环境变量未配置

**解决**:

```bash
# 1. 检查Python
python --version

# 2. 如果未安装，下载并安装Python 3.9+
# https://www.python.org/downloads/

# 3. 安装依赖
pip install -r requirements.txt
```

---

### 问题2: 提示缺少依赖

**原因**: 未安装项目依赖

**解决**:

```bash
pip install -r requirements.txt
```

---

### 问题3: GPU不可用

**原因**: GPU驱动未安装或不支持

**解决**:

**方法1**: 使用CPU

```bash
start.bat qr
```

**方法2**: 安装GPU依赖

```bash
pip install -r requirements-gpu.txt
```

**方法3**: 检查GPU状态

```bash
python key_collision_cli.py --health-check
```

---

### 问题4: 进度条不显示或显示异常

**原因**: 终端不支持ANSI转义码

**解决**:

**方法1**: 使用现代终端

- Windows: Windows Terminal
- Mac: Terminal或iTerm2
- Linux: GNOME Terminal或Konsole

**方法2**: 禁用彩色输出

```bash
python key_collision_cli.py --quick-run --no-color
```

---

## 💡 使用技巧

### 技巧1: 后台运行

**Windows**:

```bash
start /B python key_collision_cli.py --quick-run > log.txt 2>&1
```

**Linux/Mac**:

```bash
nohup python key_collision_cli.py --quick-run > log.txt 2>&1 &
```

---

### 技巧2: 定时运行

**Windows**（使用任务计划程序）:

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器和操作
4. 操作: `start.bat qr`

**Linux**（使用cron）:

```bash
crontab -e
# 添加: 0 2 * * * cd /path/to/project && python key_collision_cli.py --quick-run
```

---

### 技巧3: 批量测试

创建多个地址文件：

```
targets_small.txt     # 少量地址，快速测试
targets_medium.txt    # 中等数量，日常使用
targets_large.txt     # 大量地址，长时间运行
```

根据需要切换：

```bash
python key_collision_cli.py -t targets_small.txt -m random
```

---

## 📚 更多资源

- 📘 [完整使用指南](USER_GUIDE.md) - 详细文档
- 📖 [README](../README.md) - 项目概述
- 📝 [版本历史](../CHANGELOG.md) - 更新日志
- 🔧 [配置示例](../config.example.json) - 完整配置
- 🤝 [贡献指南](../CONTRIBUTING.md) - 参与开发

---

## 🆘 获取帮助

遇到问题？

1. **查看本文档** - 常见问题都有解答
2. **查看日志** - `logs/`目录下的日志文件
3. **查看完整文档** - `docs/`目录
4. **提交Issue** - GitHub上提问

---

**祝您使用愉快！** 🎉

有任何问题或建议，欢迎反馈！
