@echo off
setlocal enabledelayedexpansion

call "%~dp0..\common.bat"
call :init_encoding

if "%~1"=="" (
    echo [ERROR] No command specified
    echo Usage: %~nx0 python script.py [args]
    pause
    exit /b 1
)

%*