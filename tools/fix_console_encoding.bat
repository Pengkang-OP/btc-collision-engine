@echo off
REM ============================================
REM Windows控制台UTF-8编码设置脚本
REM 解决Python脚本中文乱码问题
REM ============================================

echo ============================================
echo   设置Windows控制台UTF-8编码
echo ============================================
echo.

REM 1. 设置代码页为UTF-8
echo [1/3] 设置代码页为UTF-8 (65001)...
chcp 65001 >nul
if %errorlevel% == 0 (
    echo   [PASS] 代码页设置成功
) else (
    echo   [WARN] 代码页设置失败
)
echo.

REM 2. 设置Python环境变量
echo [2/3] 设置Python UTF-8环境变量...
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo   [PASS] PYTHONIOENCODING=utf-8
echo   [PASS] PYTHONUTF8=1
echo.

REM 3. 验证编码设置
echo [3/3] 验证编码设置...
python -c "import sys; print(f'  默认编码: {sys.getdefaultencoding()}'); print(f'  文件系统编码: {sys.getfilesystemencoding()}'); print(f'  标准输出编码: {sys.stdout.encoding}')"
echo.

echo ============================================
echo   编码设置完成!
echo ============================================
echo.
echo 现在可以运行Python脚本而不会出现乱码:
echo   python your_script.py
echo.
echo 或者直接运行:
echo   run_gpu_diagnostic.bat
echo.

pause
