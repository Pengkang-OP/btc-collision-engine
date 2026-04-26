@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM BTC Collision Engine - 诊断版本
echo.
echo ========================================
echo   BTC Collision Engine - 诊断工具
echo ========================================
echo.

REM 检查 Python 环境
echo [1/5] 检查 Python 环境...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python
    goto error_end
)

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
echo [OK] Python 版本: !PY_VER!

REM 检查 Python 版本
python -c "import sys; exit(0 if sys.version_info>=(3,9) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 版本过低，需要 3.9+
    goto error_end
)

REM 检查依赖
echo [2/5] 检查依赖...
python -c "import rich" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 缺少 rich 依赖
    goto error_end
)
python -c "import ecdsa" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 缺少 ecdsa 依赖
    goto error_end
)
echo [OK] 依赖检查通过

REM 检查文件结构
echo [3/5] 检查文件结构...
if not exist "key_collision_cli.py" (
    echo [ERROR] key_collision_cli.py 未找到
    goto error_end
)
echo [OK] key_collision_cli.py 存在

REM 检查模块导入
echo [4/5] 检查模块导入...
python -c "import sys; sys.path.insert(0, '.'); from src.cli.main import main; print('模块导入成功')" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 模块导入失败
    goto error_end
)
echo [OK] 模块导入成功

REM 测试快速启动向导
echo [5/5] 测试快速启动向导...
echo 正在启动快速启动向导...
python key_collision_cli.py --quick-start
set "EXIT_CODE=!errorlevel!"
echo 向导退出代码: !EXIT_CODE!

echo.
echo ========================================
echo   诊断完成
echo ========================================
echo.
pause
exit /b !EXIT_CODE!

:error_end
echo.
echo [ERROR] 诊断失败，请检查以上错误信息
echo.
pause
exit /b 1