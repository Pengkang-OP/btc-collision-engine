@echo off
rem ================================================================
rem  BTC Collision Engine - Shared Batch Subroutine Library
rem  被 install.bat / start_async_optimized.bat / tools\*.bat 引用
rem
rem  用法: 在调用方脚本中先 call "common.bat" 加载子程序,
rem        再 call :子程序名 来执行。
rem ================================================================
goto :eof

rem ── 编码初始化 ──────────────────────────────────────────────────
:init_encoding
chcp 65001 >nul 2>&1
goto :eof

rem ── 切换到脚本所在目录 ──────────────────────────────────────────
:set_script_dir
cd /d "%~dp0"
goto :eof

rem ── 打印页首横幅 (参数1 = 标题文本) ────────────────────────────
:print_header
echo.
echo ================================================================
echo   %~1
echo ================================================================
echo.
goto :eof

rem ── 打印步骤标题 ────────────────────────────────────────────────
:print_section
echo.
echo --- %~1 ---
echo.
goto :eof

rem ── 检查 Python 是否在 PATH 中 ──────────────────────────────────
:check_python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    echo         Please install Python 3.9+ and add it to PATH
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found in PATH
goto :eof

rem ── 检查 Python 版本 >= 3.9 ─────────────────────────────────────
:check_python_version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python version is too old
    echo         Python 3.9 or higher is required
    pause
    exit /b 1
)
echo [OK] Python version meets requirements (>= 3.9)
goto :eof

rem ── 创建必要的运行时目录 ────────────────────────────────────────
:create_required_dirs
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)
echo [OK] Required directories created/verified
goto :eof

rem ── 从模板创建 config.json (如果不存在) ─────────────────────────
:create_config
if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] config.json created from template
    ) else (
        echo [WARN] Neither config.json nor config.example.json found
    )
) else (
    echo [INFO] config.json already exists
)
goto :eof

rem ── 激活虚拟环境 ────────────────────────────────────────────────
:activate_venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Virtual environment activated
        goto :eof
    )
)
echo [WARN] Virtual environment not found or activation failed
echo        Run install.bat to set up the environment
goto :eof

rem ── 检查指定文件是否存在 (参数1 = 文件路径) ───────────────────
:check_file_exists
if exist "%~1" (
    echo [OK] File found: %~1
) else (
    echo [ERROR] File not found: %~1
    echo         Please verify the path or run install.bat first
    pause
    exit /b 1
)
goto :eof
