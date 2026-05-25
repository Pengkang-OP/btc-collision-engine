---
name: "task-batch-processor"
description: "Automates execution of multiple tasks via batch processing. Invoke when user needs to run sequential or parallel batch operations."
---

# Task Batch Processor

任务批处理器 - 自动执行多个任务的批处理系统

## 功能

- 顺序执行多个任务
- 并行执行独立任务
- 任务状态跟踪
- 错误处理和恢复

## 基本结构

```batch
@echo off
chcp 65001 >nul 2>&1

setlocal enabledelayedexpansion

set "TASK_COUNT=3"
set "CURRENT_TASK=0"

:task_loop
set /a CURRENT_TASK+=1
if %CURRENT_TASK% gtr %TASK_COUNT% goto :task_complete

echo [TASK %CURRENT_TASK%/%TASK_COUNT%] Starting...

REM 执行任务
call :task_%CURRENT_TASK%

goto :task_loop

:task_complete
echo All tasks completed.
pause

:task_1
echo Running Task 1...
REM 任务1逻辑
exit /b 0

:task_2
echo Running Task 2...
REM 任务2逻辑
exit /b 0

:task_3
echo Running Task 3...
REM 任务3逻辑
exit /b 0
```

## 配置文件驱动

```batch
@echo off
setlocal enabledelayedexpansion

set "CONFIG_FILE=tasks.txt"

if not exist "%CONFIG_FILE%" (
    echo [ERROR] Config file not found
    exit /b 1
)

for /f "usebackq tokens=*" %%line in ("%CONFIG_FILE%") do (
    echo [EXEC] %%line
    call %%line
    if errorlevel 1 (
        echo [ERROR] Task failed: %%line
    )
)

echo [OK] All tasks processed.
```

## 任务状态日志

```batch
set "LOG_FILE=task_log.txt"
echo [%date% %time%] Task started >> "%LOG_FILE%"
```

## 并行执行

使用 `start` 命令并行启动任务：

```batch
start "Task1" cmd /c "task1.bat"
start "Task2" cmd /c "task2.bat"
start "Task3" cmd /c "task3.bat"

REM 等待所有任务完成
wait
```
