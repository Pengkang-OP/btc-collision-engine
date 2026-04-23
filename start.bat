@echo off
chcp 65001 > nul
echo ========================================
echo BTC 碰撞引擎
echo ========================================
echo.
echo 请选择启动模式:
echo.
echo 1. 图形界面 (GUI) [暂不可用]
echo 2. 命令行模式
echo.
set /p choice=请输入选项 (1 或 2): 

if "%choice%"=="1" (
    echo.
    echo [警告] 图形界面当前暂不可用。
    echo 请使用命令行模式（选项 2）或直接运行:
    echo   python key_collision_cli.py --help
    echo.
) else if "%choice%"=="2" (
    echo.
    echo 正在启动命令行模式...
    python key_collision_cli.py
) else (
    echo.
    echo 无效的选项！
    pause
    exit /b 1
)

pause
