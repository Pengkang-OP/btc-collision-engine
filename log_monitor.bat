@echo off
chcp 65001 >nul 2>&1
setlocal

cd /d "%~dp0"

python log_monitor.py %*

pause