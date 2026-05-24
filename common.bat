@echo off
rem ================================================================
rem  BTC Collision Engine - 共享批处理子程序库
rem  用法: call "common.bat" :子程序名 [参数]
rem        通过 goto 路由到对应标签，实现跨文件函数调用
rem ================================================================
rem 路由入口：call common.bat :label → goto :label
goto %1 2>nul || goto :eof

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
python -c "import sys; v=sys.version_info; sys.exit(0 if v.major>=3 and v.minor>=9 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python version too old (需要 >= 3.9)
    pause
    exit /b 1
)
echo [OK] Python version OK
goto :eof

rem ── 创建运行时目录 ──────────────────────────────────────────────
:create_required_dirs
set "_DIRS_OK=1"
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" (
        mkdir "%%D" >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Failed to create directory: %%D
            set "_DIRS_OK=0"
        )
    )
)
if "%_DIRS_OK%"=="0" (
    pause
    exit /b 1
)
echo [OK] Runtime directories created
goto :eof

rem ── 从 config.example.json 创建 config.json ──────────────────────
:create_config
if exist "config.json" (
    echo [INFO] config.json exists
    goto :eof
)
if exist "config.example.json" (
    copy "config.example.json" "config.json" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to copy config.example.json to config.json
        pause
        exit /b 1
    )
    echo [OK] config.json created
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
    ) else (
        echo [ERROR] Virtual environment activation failed (check venv\Scripts\activate.bat)
        exit /b 1
    )
)
echo [WARNING] Virtual env not found at venv\Scripts\activate.bat
exit /b 1
goto :eof
