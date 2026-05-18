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
    echo [错误] 未找到 Python
    echo         请安装 Python 3.9+ 并添加到 PATH
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] 已找到 Python
goto :eof

rem ── 检查 Python 版本 >= 3.9 ─────────────────────────────────────
:check_python_version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 版本过低
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo         当前版本: %%v
    echo         需要 Python 3.9 或更高版本
    pause
    exit /b 1
)
echo [OK] Python 版本符合要求 (>= 3.9)
goto :eof

rem ── 创建必要的运行时目录 ────────────────────────────────────────
:create_required_dirs
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" >nul 2>&1
)
echo [OK] 运行时目录已创建/验证
goto :eof

rem ── 从模板创建 config.json (如果不存在) ─────────────────────────
:create_config
if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] 已从模板创建 config.json
    ) else (
        echo [警告] 未找到 config.example.json 模板文件
    )
) else (
    echo [INFO] config.json 已存在
)
goto :eof

rem ── 激活虚拟环境 ────────────────────────────────────────────────
:activate_venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if not errorlevel 1 (
        echo [OK] 虚拟环境已激活
        goto :eof
    )
)
echo [警告] 虚拟环境未找到或激活失败
echo        请先运行 install.bat 安装环境
exit /b 1

rem ── 检查指定文件是否存在 (参数1 = 文件路径) ───────────────────
:check_file_exists
if exist "%~1" (
    echo [OK] 文件已找到: %~1
) else (
    echo [错误] 文件未找到: %~1
    echo         请检查路径是否正确，或先运行 install.bat
    pause
    exit /b 1
)
goto :eof
