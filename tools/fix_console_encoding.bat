@echo off
setlocal enabledelayedexpansion

call "%~dp0..\common.bat"
call :init_encoding

echo ============================================
echo   Setting Windows Console UTF-8 Encoding
echo ============================================
echo.

echo [1/3] Setting codepage to UTF-8 (65001)...
chcp 65001 >nul
if %errorlevel% == 0 (
    echo   [OK] Codepage set to UTF-8
) else (
    echo   [WARN] Failed to set codepage
)
echo.

echo [2/3] Setting Python UTF-8 environment variables...
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo   [OK] PYTHONIOENCODING=utf-8
echo   [OK] PYTHONUTF8=1
echo.

echo [3/3] Verifying encoding settings...
python -c "import sys; print(f'  Default encoding: {sys.getdefaultencoding()}'); print(f'  Filesystem encoding: {sys.getfilesystemencoding()}'); print(f'  Stdout encoding: {sys.stdout.encoding}')"
echo.

echo ============================================
echo   Encoding setup complete!
echo ============================================
echo.
echo You can now run Python scripts without UTF-8 issues:
echo   python your_script.py
echo.

pause