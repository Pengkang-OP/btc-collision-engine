@echo off
rem ================================================================
rem  BTC Collision Engine - 共享批处理子程序库
rem  被 install.bat / start_engine.bat / tools\*.bat 等引用
rem
rem  用法: 在调用方脚本中先 call "common.bat" 加载子程序,
rem        再 call :子程序名 来执行。
rem ================================================================
goto :eof

rem ── 编码初始化 (UTF-8) ───────────────────────────────────────────
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
    echo [ERROR] Python not found
    echo         请安装 Python 3.9+ 并添加到 PATH
    echo         下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found
goto :eof

rem ── 检查 Python 版本 >= 3.9 ─────────────────────────────────────
:check_python_version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python version too old (需要 >= 3.9)
    pause
    exit /b 1
)
echo [OK] Python version OK
goto :eof

rem ── 创建运行时目录 ──────────────────────────────────────────────
:create_required_dirs
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)
echo [OK] Runtime directories created
goto :eof

rem ── 从 config.example.json 创建 config.json ──────────────────────
:create_config
if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] config.json created
    )
) else (
    echo [INFO] config.json exists
)
goto :eof

rem ── 检查文件是否存在 (参数1 = 文件路径) ──────────────────────────
:check_file_exists
if not exist "%~1" (
    echo [ERROR] File not found: %~1
    pause
    exit /b 1
)
echo [OK] File found: %~1
goto :eof

rem ── 激活虚拟环境 ─────────────────────────────────────────────────
:activate_venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Virtual env activated
        goto :eof
    )
)
echo [WARNING] Virtual env not found
exit /b 1
goto :eof
