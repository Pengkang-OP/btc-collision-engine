# BTC碰撞引擎 - 快速参考卡

**版本**: v3.3.1 | **更新日期**: 2026-04-28

---

## 🚀 快速启动（3种方式）

### 方式1: 交互式向导（推荐新手）

```bash
start.bat qs          # Windows
python key_collision_cli.py --quick-start    # Linux/Mac
```

### 方式2: 快速模式（推荐熟练用户）

```bash
start.bat qr          # Windows
python key_collision_cli.py --quick-run      # Linux/Mac
```

### 方式3: 直接命令

```bash
python key_collision_cli.py -t targets.txt -m random
```

---

## ⌨️ 命令别名（仅Windows）

| 命令 | 功能 | 说明 |
|------|------|------|
| `start.bat qs` | 交互式向导 | 逐步引导配置 |
| `start.bat qr` | 快速模式 | 使用默认配置直接运行 |
| `start.bat hc` | 健康检查 | 检查系统状态 |
| `start.bat cc` | 配置验证 | 验证配置文件 |
| `start.bat ex` | 显示示例 | 查看使用示例 |
| `start.bat rec` | 参数推荐 | 获取优化建议 |

---

## 📋 常用参数

### 基本参数

```
-t, --target FILE        目标地址文件
-m, --mode MODE          碰撞模式 (random/range/brute)
-e, --engine TYPE        引擎类型 (cpu/gpu/multi-gpu)
-d, --duration SECONDS   运行时长 (0=无限制)
```

### 功能开关

```
--checkpoint             启用断点续传 (默认启用)
--no-checkpoint          禁用断点续传
--dedup                  启用去重过滤 (默认启用)
--no-dedup               禁用去重过滤
--compact                紧凑模式（跳过帮助信息）
```

### 帮助命令

```
-h, --help               显示帮助信息
--examples               显示使用示例
--recommend              参数推荐
--quick-start            交互式向导
--quick-run              快速模式
```

---

## 📁 重要文件

| 文件 | 用途 | 位置 |
|------|------|------|
| `start.bat` | Windows启动脚本 | 项目根目录 |
| `key_collision_cli.py` | CLI主程序 | 项目根目录 |
| `targets.txt` | 目标地址文件 | 项目根目录（需创建） |
| `config.json` | 配置文件 | 项目根目录 |
| `config.example.json` | 配置示例 | 项目根目录 |

---

## 📝 创建targets.txt

```
# 我的目标地址
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy
bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh
```

**规则**:

- ✅ 每行一个地址
- ✅ 支持`#`注释
- ✅ 支持空行
- ✅ 支持3种地址格式（1开头、3开头、bc1开头）

---

## 🎯 典型使用场景

### 场景1: 新手第一次使用

```bash
# 使用交互式向导
start.bat qs
```

向导会引导您完成：

1. 选择地址来源
2. 选择碰撞模式
3. 选择功能选项
4. 确认并启动

### 场景2: 快速测试

```bash
# 1. 创建targets.txt
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt

# 2. 快速模式运行
start.bat qr
```

### 场景3: 指定运行时长

```bash
# 运行1小时
python key_collision_cli.py --quick-run --duration 3600
```

### 场景4: GPU加速

```bash
# 使用GPU
python key_collision_cli.py --quick-run --engine gpu
```

### 场景5: 后台运行

```bash
# Windows
start /B python key_collision_cli.py --quick-run > log.txt 2>&1

# Linux/Mac
nohup python key_collision_cli.py --quick-run > log.txt 2>&1 &
```

---

## 🔍 进度显示

运行时显示：

```
[00:05] [CPU] ████░░░░░░░░░░░░ 25.0% | 1,234/4,936 | 速度: 246/s | ETA: 15s | 匹配: 0
```

**说明**:

- `[00:05]` - 已运行时间
- `[CPU]` - 引擎类型（CPU/GPU/MULTI-GPU）
- `████░░░░░░░░░░░░` - 可视化进度条
- `25.0%` - 完成百分比
- `1,234/4,936` - 已检查/总数
- `速度: 246/s` - 每秒检查数量
- `ETA: 15s` - 预计剩余时间
- `匹配: 0` - 找到的匹配数

---

## ❓ 快速故障排查

### 问题: 找不到targets.txt

**解决**: 创建文件或使用向导

```bash
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt
```

### 问题: 启动失败

**解决**: 检查Python和依赖

```bash
python --version
pip install -r requirements.txt
```

### 问题: GPU不可用

**解决**: 使用CPU或安装GPU依赖

```bash
# 使用CPU
start.bat qr

# 或安装GPU依赖
pip install -r requirements-gpu.txt
```

### 问题: 如何停止

**解决**: 按Ctrl+C

```
按 Ctrl+C 安全停止（进度会自动保存）
```

---

## 💡 提示

- ✅ **新手**: 使用`start.bat qs`交互式向导
- ✅ **熟练**: 使用`start.bat qr`快速模式
- ✅ **测试**: 先用少量地址测试
- ✅ **性能**: 启用GPU可提速10-100倍
- ✅ **安全**: 启用断点续传防止进度丢失
- ✅ **效率**: 启用去重过滤避免重复检查

---

## 📚 完整文档

- [用户使用指南](docs/USER_GUIDE.md) - 详细使用指南
- [README](README.md) - 项目概述
- [CHANGELOG](CHANGELOG.md) - 版本历史
- [配置示例](config.example.json) - 完整配置

---

**打印此页作为桌面参考！** 📄
