@echo off
setlocal enabledelayedexpansion

rem ============================================
rem  BTC Collision Engine - UTF-8 Command Wrapper
rem  Runs commands with UTF-8 encoding enabled
rem ============================================

rem Set UTF-8 environment
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if "%~1"=="" (
    echo [ERROR] No command specified
    echo Usage: %~nx0 python script.py [args]
    pause
    exit /b 1
)

rem Execute user command with UTF-8 ready
%*
