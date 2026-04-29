@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   CMD环境日志测试
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 测试基本日志输出...
python -c "import logging; from src.utils import init_logging, get_configured_logger; init_logging(); logger = get_configured_logger('CMD测试'); logger.info('这是一条中文日志消息'); logger.warning('警告：测试警告信息'); logger.error('错误：测试错误信息')"
echo.

echo [2/3] 测试碰撞引擎日志...
python -c "from src.core.crypto_backend import logger; logger.info('加密后端日志测试 - 中文正常')"
echo.

echo [3/3] 检查日志文件编码...
if exist "logs\collision.log" (
    powershell -Command "Get-Content 'logs\collision.log' -Encoding UTF8 | Select-Object -Last 5"
) else (
    echo 日志文件不存在
)
echo.

echo ========================================
echo   测试完成
echo ========================================
echo.
pause
