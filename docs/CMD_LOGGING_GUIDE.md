# CMD环境下引擎日志使用指南

**版本**: v4.5.1

## 📋 目录

- [环境配置](#环境配置)

- [启动方式](#启动方式)

- [日志输出说明](#日志输出说明)

- [常见问题](#常见问题)

- [日志文件位置](#日志文件位置)

---

## 环境配置

### 1. 编码设置

`start.bat` 已自动配置UTF-8编码：

```batch
@echo off
chcp 65001 >nul 2>&1    ← 设置UTF-8编码
setlocal enabledelayedexpansion

```

### 2. 日志处理器

系统使用 `SafeStreamHandler` 处理CMD环境的编码问题：

- ✅ 自动检测控制台编码

- ✅ 中文字符安全转换

- ✅ 兼容GBK和UTF-8

---

## 启动方式

### 方式1: 双击启动（推荐）

```yaml
直接双击: start.bat

```

会显示启动选择菜单：

```yaml
========================================
  BTC Collision Engine - 启动选择
========================================

请选择启动模式:

  1. 交互式向导 (推荐新手)
  2. 快速模式 (使用 targets.txt)
  3. Interactive Menu
  0. 取消启动

```

### 方式2: 命令行启动

```cmd
# 快速模式（使用targets.txt）
start.bat qr

# 交互式向导
start.bat qs

# 指定目标地址
start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random

# 从文件加载
start.bat -f targets.txt --use-gpu

# 健康检查
start.bat hc

# 查看示例
start.bat ex

```

### 方式3: 直接调用Python

```cmd
python key_collision_cli.py --quick-run
python key_collision_cli.py --health-check
python key_collision_cli.py -f targets.txt --duration 300

```

---

## 日志输出说明

### 控制台输出

日志会同时输出到控制台和文件：

```bash
[INFO] 日志安全过滤器已启用（防止私钥泄露）
2026-04-27 19:26:36,238 - CMD测试 - INFO - 日志系统初始化完成
2026-04-27 19:26:36,239 - CMD测试 - INFO - 目标地址数: 4
2026-04-27 19:26:36,239 - CMD测试 - WARNING - 警告：内存使用率超过90%
2026-04-27 19:26:36,239 - CMD测试 - ERROR - 错误：断点保存失败

```

### 日志级别

| 级别 | 颜色 | 说明 | 示例 |
|------|------|------|------|
| DEBUG | 青色 | 调试信息 | 详细执行步骤 |
| INFO | 绿色 | 一般信息 | 系统初始化完成 |
| WARNING | 黄色 | 警告信息 | 内存使用率过高 |
| ERROR | 红色 | 错误信息 | 文件保存失败 |
| CRITICAL | 紫色 | 严重错误 | 系统崩溃 |

### 日志格式

```bash
时间戳 - 模块名 - 级别 - 消息

```

示例：

```bash
2026-04-27 19:22:12,480 - CryptoBackend - INFO - 加密后端初始化完成
2026-04-27 19:22:12,571 - BigIntOptimizer - INFO - gmpy2大整数优化已启用

```

---

## 日志文件

### 文件位置

```bash
项目根目录/
└── logs/
    ├── collision.log          ← 当前日志
    ├── collision.log.1        ← 备份日志1
    ├── collision.log.2        ← 备份日志2
    └── ...

```

### 查看日志

**PowerShell:**

```powershell
# 查看最新20行
Get-Content "logs\collision.log" -Tail 20 -Encoding UTF8

# 实时监控
Get-Content "logs\collision.log" -Tail 10 -Wait -Encoding UTF8

# 搜索错误
Select-String -Path "logs\collision.log" -Pattern "ERROR"

```

**CMD:**

```cmd
# 查看最新日志
type logs\collision.log | more

# 搜索错误
findstr "ERROR" logs\collision.log

```

### 日志轮转

- **轮转方式**: 按大小轮转

- **单文件最大**: 10MB

- **保留数量**: 5个备份

- **编码**: UTF-8 with BOM (utf-8-sig)

---

## 常见问题

### Q1: 日志中文乱码？

**原因**: CMD默认使用GBK编码

**解决方案**:

- ✅ `start.bat` 已自动设置UTF-8 (`chcp 65001`)

- ✅ 日志系统使用 `SafeStreamHandler` 自动处理编码

- ✅ 日志文件使用 `utf-8-sig` 编码

如果仍然乱码，手动执行：

```cmd
chcp 65001
start.bat

```

### Q2: 日志不显示？

**检查项**:

1. 配置文件 `config.json` 中 `logging.enable_console` 是否为 `true`

2. 日志级别是否设置过高

3. 控制台是否被最小化

**解决方案**:

```cmd
# 使用-v参数增加详细度
start.bat -v -f targets.txt

# 或使用-vvv显示所有调试信息
start.bat -vvv -f targets.txt

```

### Q3: 如何保存日志到文件？

日志**自动保存**到 `logs/collision.log`

**禁用文件日志**（不推荐）:
编辑 `config.json`:

```json
{
  "logging": {
    "enable_file": false
  }
}

```

### Q4: 日志文件太大？

**自动轮转**: 超过10MB自动创建新文件

**手动清理**:

```cmd
# 使用清理工具
start.bat --cleanup

# 预览清理（不实际删除）
start.bat --cleanup --dry-run

```

### Q5: 如何在后台运行并记录日志？

**方式1**: 使用Windows任务计划程序

**方式2**: 使用vbs脚本隐藏窗口
创建 `run_hidden.vbs`:

```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "start.bat qr", 0, False

```

**方式3**: 使用PowerShell

```powershell
Start-Process python -ArgumentList "key_collision_cli.py","--quick-run" -WindowStyle Hidden

```

---

## 日志配置

### 修改日志级别

编辑 `config.json`:

```json
{
  "logging": {
    "level": "INFO",  // DEBUG, INFO, WARNING, ERROR, CRITICAL
    "enable_console": true,
    "enable_file": true
  }
}

```

### 修改日志路径

```json
{
  "logging": {
    "file": "logs/collision.log"  // 自定义路径
  }
}

```

### 修改轮转设置

```json
{
  "logging": {
    "max_bytes": 10485760,    // 10MB
    "backup_count": 5,        // 保留5个备份
    "rotation_type": "size"   // size=按大小, time=按时间
  }
}

```

---

## 高级技巧

### 1. 日志级别快捷参数

```cmd
# 静默模式（只显示WARNING以上）
start.bat --quiet -f targets.txt

# 显示调试信息
start.bat -v -f targets.txt

# 显示所有调试信息
start.bat -vvv -f targets.txt

```

### 2. 日志窗口

系统会创建独立的日志窗口（GUI），与主界面分离：

- ✅ 实时显示日志

- ✅ 支持级别过滤

- ✅ 支持自动滚动

- ✅ 单例模式（不重复创建）

### 3. 日志安全

- ✅ 私钥自动屏蔽（安全过滤器）

- ✅ 敏感信息自动隐藏

- ✅ 日志文件权限保护（600）

### 4. 性能优化

- ✅ 异步日志写入（v4.2.1）

- ✅ 批量日志缓冲

- ✅ 磁盘满保护

---

## 故障排查

### 问题: 日志重复输出

**原因**: 多个进程同时写入

**解决**:

```cmd
# 检查运行的进程
tasklist | findstr python

# 终止多余进程
taskkill /F /IM python.exe

```

### 问题: 日志文件权限错误

**错误信息**:

```bash
PermissionError: [WinError 5] 拒绝访问

```

**解决**:

1. 以管理员身份运行CMD

2. 检查文件是否被其他程序占用

3. 重启计算机释放文件锁

### 问题: 磁盘空间不足

**警告**:

```bash
[磁盘警告] 日志目录可用空间不足

```

**解决**:

```cmd
# 清理旧日志
start.bat --cleanup

# 或手动删除
del logs\collision.log.*

```

---

## 最佳实践

1. ✅ **始终使用 `start.bat` 启动**（自动配置环境）

2. ✅ **定期检查日志文件**（监控运行状态）

3. ✅ **保持日志级别为INFO**（平衡性能和信息量）

4. ✅ **定期清理旧日志**（释放磁盘空间）

5. ✅ **备份重要日志**（用于问题诊断）

---

## 技术支持

如遇问题，请提供：

1. 完整的日志文件 (`logs/collision.log`)

2. 启动命令

3. 错误截图

4. 系统信息（Windows版本）

---

**最后更新**: 2026-04-27
**版本**: v4.2.2
