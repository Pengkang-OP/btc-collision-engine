@echo off
REM 设置Windows控制台为UTF-8编码
REM 解决中文乱码问题

REM 设置代码页为UTF-8
chcp 65001 >nul

REM 设置环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM 运行诊断工具
python tools/gpu_diagnostic.py

pause
