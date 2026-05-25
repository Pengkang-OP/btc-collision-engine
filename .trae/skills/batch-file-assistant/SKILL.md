---
name: "batch-file-assistant"
description: "Assists with creating and debugging Windows batch scripts (.bat/.cmd). Invoke when user asks to create, debug, or fix batch files."
---

# Batch File Assistant

批处理文件助手 - 帮助创建和调试 Windows 批处理脚本

## 功能

- 创建 .bat / .cmd 批处理文件
- 调试批处理脚本错误
- 修复批处理语法问题
- 优化批处理命令

## 常用命令

### 创建批处理文件

```batch
@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
```

### 环境变量

```batch
set "VAR=value"
echo %VAR%
```

### 条件判断

```batch
if "%CHOICE%"=="1" (
    echo Option 1
) else if "%CHOICE%"=="2" (
    echo Option 2
)
```

### 循环

```batch
for %%f in (*.txt) do (
    echo Found: %%f
)
```

### 函数定义

```batch
:my_function
echo Running function
exit /b 0
```

## 常见问题修复

1. **中文乱码**: 在文件开头添加 `chcp 65001 >nul 2>&1`
2. **路径问题**: 使用 `cd /d "%~dp0"` 切换到脚本所在目录
3. **命令分隔符**: PowerShell 中使用 `;` 而非 `&&`

## 调试技巧

```batch
@echo on
echo Debugging...
pause
```
