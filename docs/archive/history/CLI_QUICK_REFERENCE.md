# CLI快速参考指南

## 🚀 快速开始

### 新手用户（推荐）

```bash
# 方式1: 交互式引导（最简单）
python key_collision_cli.py --quick-start

# 方式2: 查看示例后运行
python key_collision_cli.py --examples
```

### 常用命令速查

#### 基础使用

```bash
# 随机碰撞（最简单）
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random

# 推荐配置（断点续传+去重）
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --checkpoint --dedup --duration 3600

# 从文件加载目标
python key_collision_cli.py -f targets.txt -m random --checkpoint
```

#### GPU加速

```bash
# 单GPU加速
python key_collision_cli.py -t <地址> -m random --use-gpu

# 多GPU加速
python key_collision_cli.py -f targets.txt -m random --multi-gpu
```

#### 范围扫描

```bash
# 指定私钥范围
python key_collision_cli.py -t <地址> -m range --start 1 --end FFFFFFFF
```

#### 实用工具

```bash
# 检查配置状态
python key_collision_cli.py --config-check

# 系统健康检查
python key_collision_cli.py --health-check

# 验证地址文件
python key_collision_cli.py --validate-addresses targets.txt

# 清理过期数据
python key_collision_cli.py --cleanup --dry-run  # 预览
python key_collision_cli.py --cleanup            # 执行
```

---

## 📋 参数速查表

### 目标地址（必需，二选一）

| 参数 | 说明 | 示例 |
|------|------|------|
| `-t, --targets` | 单个/多个地址 | `-t 1A1zP1eP...` |
| `-f, --file` | 从文件加载 | `-f targets.txt` |

### 碰撞模式

| 参数 | 说明 | 必需参数 |
|------|------|----------|
| `-m random` | 随机碰撞（默认） | 无 |
| `-m range` | 范围扫描 | `--start`, `--end` |
| `-m brute_force` | 暴力穷举 | `--start` |

### 功能选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--checkpoint` | 启用断点续传 | 禁用 |
| `--dedup` | 启用去重过滤 | 禁用 |
| `--duration SECS` | 运行时长（秒） | 0（无限） |

### GPU加速

| 参数 | 说明 |
|------|------|
| `--use-gpu` | 启用单GPU |
| `--multi-gpu` | 启用多GPU |
| `--gpu-device INDEX` | 指定GPU索引 |

### 新增功能 ⭐

| 参数 | 说明 |
|------|------|
| `--quick-start` | 交互式快速引导 |
| `--examples` | 显示常用示例 |
| `--config-check` | 检查配置状态 |

---

## 🎯 常见场景

### 场景1: 第一次使用

```bash
# 使用交互式引导
python key_collision_cli.py --quick-start
```

### 场景2: 长时间运行

```bash
# 启用断点续传，运行24小时
python key_collision_cli.py -t <地址> -m random --checkpoint --dedup --duration 86400
```

### 场景3: GPU加速

```bash
# 检查GPU可用性
python key_collision_cli.py --health-check

# 使用GPU加速
python key_collision_cli.py -t <地址> -m random --use-gpu --checkpoint
```

### 场景4: 批量地址

```bash
# 创建目标文件
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt
echo "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" >> targets.txt

# 运行碰撞
python key_collision_cli.py -f targets.txt -m random --checkpoint --dedup
```

### 场景5: 指定范围

```bash
# 在小范围内搜索（测试用）
python key_collision_cli.py -t <地址> -m range --start 1 --end FFFFFFFF --duration 300
```

---

## ⚠️ 常见问题

### Q1: 提示"需要指定目标地址"

```bash
# 解决: 添加 -t 或 -f 参数
python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
```

### Q2: 提示"range模式需要--start参数"

```bash
# 解决: 添加 --start 和 --end 参数
python key_collision_cli.py -t <地址> -m range --start 1 --end FFFFFFFF
```

### Q3: 如何停止运行

```bash
# 按 Ctrl+C 优雅停止
# 或使用 --duration 参数自动停止
```

### Q4: 如何查看进度

```bash
# 进度会自动显示，格式如下:
[00:01:23] ████░░░░░░░░░░░░░░░░   0.1% | 1.23M/1.23B | 速度: 15.0K/s | ETA: 22.5h | 匹配: 0
```

### Q5: 配置文件检查

```bash
# 检查配置状态
python key_collision_cli.py --config-check

# 如果配置文件不存在，会自动创建
```

---

## 📚 更多信息

- 完整帮助: `python key_collision_cli.py --help`
- 使用示例: `python key_collision_cli.py --examples`
- 快速引导: `python key_collision_cli.py --quick-start`
- 配置检查: `python key_collision_cli.py --config-check`

---

**更新日期**: 2026-04-24  
**版本**: v4.2.1+
