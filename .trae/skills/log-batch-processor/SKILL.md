---
name: "log-batch-processor"
description: "Batch processes and analyzes log files. Invoke when user needs to parse, filter, search, or aggregate log data."
---

# Log Batch Processor

日志批处理器 - 批量处理和分析日志文件

## 功能

- 日志文件解析
- 日志过滤和搜索
- 日志统计和聚合
- 日志格式转换

## 基本日志解析

```batch
@echo off
chcp 65001 >nul 2>&1

set "LOG_FILE=logs\wizard.log"
set "OUTPUT_FILE=filtered_log.txt"

if not exist "%LOG_FILE%" (
    echo [ERROR] Log file not found
    exit /b 1
)

echo [INFO] Parsing log file: %LOG_FILE%
echo [INFO] Output to: %OUTPUT_FILE%

findstr /i "error" "%LOG_FILE%" > "%OUTPUT_FILE%"

echo [OK] Filtered %ERRORLEVEL% lines.
```

## 日志级别统计

```batch
@echo off
setlocal enabledelayedexpansion

set "LOG_FILE=logs\wizard.log"

set "ERROR_COUNT=0"
set "WARN_COUNT=0"
set "INFO_COUNT=0"

for /f %%a in ('type "%LOG_FILE%" ^| find /c "ERROR"') do set ERROR_COUNT=%%a
for /f %%a in ('type "%LOG_FILE%" ^| find /c "WARNING"') do set WARN_COUNT=%%a
for /f %%a in ('type "%LOG_FILE%" ^| find /c "INFO"') do set INFO_COUNT=%%a

echo ========================================
echo           Log Statistics
echo ========================================
echo ERROR:   %ERROR_COUNT%
echo WARNING: %WARN_COUNT%
echo INFO:    %INFO_COUNT%
echo ========================================
```

## 时间范围过滤

```batch
@echo off
setlocal enabledelayedexpansion

set "LOG_FILE=logs\wizard.log"
set "START_TIME=2026-04-28"
set "OUTPUT_FILE=filtered_by_time.txt"

findstr /i "%START_TIME%" "%LOG_FILE%" > "%OUTPUT_FILE%"

echo [OK] Lines after %START_TIME% saved to %OUTPUT_FILE%
```

## 日志轮转

```batch
@echo off
setlocal enabledelayedexpansion

set "LOG_DIR=logs"
set "ARCHIVE_DIR=logs\archive"
set "MAX_SIZE_MB=10"

if not exist "%ARCHIVE_DIR%" mkdir "%ARCHIVE_DIR%"

for %%f in ("%LOG_DIR%\*.log") do (
    set "FILE_SIZE=%%~zf"
    set /a FILE_SIZE_MB=FILE_SIZE / 1048576
    
    if !FILE_SIZE_MB! gtr %MAX_SIZE_MB% (
        echo [ARCHIVE] %%~nxf
        move "%%f" "%ARCHIVE_DIR%\%%~nxf" >nul
    )
)

echo [OK] Log rotation completed.
```

## Python 辅助脚本

创建 `analyze_log.py` 进行高级分析：

```python
import re
import sys
from collections import Counter

def analyze_log(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    levels = Counter()
    errors = []
    
    for line in lines:
        if 'ERROR' in line:
            levels['ERROR'] += 1
            errors.append(line.strip())
        elif 'WARNING' in line:
            levels['WARNING'] += 1
        elif 'INFO' in line:
            levels['INFO'] += 1
    
    print("=== Log Analysis ===")
    print(f"Total lines: {len(lines)}")
    print(f"Level counts: {dict(levels)}")
    print(f"Recent errors: {errors[-5:]}")

if __name__ == "__main__":
    analyze_log(sys.argv[1] if len(sys.argv) > 1 else "logs/wizard.log")
```