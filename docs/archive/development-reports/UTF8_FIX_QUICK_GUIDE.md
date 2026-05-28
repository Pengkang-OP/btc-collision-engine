# Windows控制台UTF-8编码乱码 - 快速修复

## [QUICK] 立即修复(30秒)

### 方法1: 使用批处理(最简单)

```powershell
# 直接运行
.\run_gpu_diagnostic.bat
```

### 方法2: PowerShell手动设置

```powershell
# 复制粘贴以下命令
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# 然后运行你的脚本
python tools/gpu_diagnostic.py
```

---

## [OK_CHECK] 验证修复

```powershell
python -c "print('测试中文: 你好世界! [EARTH]')"
```

**正确输出**:

```
测试中文: 你好世界! [EARTH]
```

---

## [DIR] 已创建的工具

| 文件 | 用途 | 使用方法 |
|------|------|---------|
| `run_gpu_diagnostic.bat` | 一键运行GPU诊断 | 双击运行 |
| `tools/fix_console_encoding.bat` | CMD编码修复 | 命令行运行 |
| `tools/fix_console_encoding.ps1` | PowerShell编码修复 | PowerShell运行 |
| `tools/permanent_utf8_fix.ps1` | 永久修复(需管理员) | 管理员PowerShell运行 |

---

## [WRENCH] 永久修复(推荐)

```powershell
# 1. 以管理员身份打开PowerShell
# 2. 运行永久修复脚本
.\tools\permanent_utf8_fix.ps1

# 3. 重启计算机
Restart-Computer
```

---

## [BOOK] 详细文档

查看完整指南: [Windows控制台UTF-8编码乱码修复指南](docs/windows-console-utf8-fix.md)

---

**更新日期**: 2026-04-21
