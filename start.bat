@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM BTC Collision Engine - Startup Script

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] 无法切换到脚本目录: %~dp0
    pause
    exit /b 1
)

if not exist "key_collision_cli.py" (
    echo [ERROR] key_collision_cli.py 文件未找到
    echo.
    echo   当前目录: %CD%
    echo   请确保 start.bat 和 key_collision_cli.py 在同一文件夹中。
    pause
    exit /b 1
)

REM ---- 处理不需要启动向导的工具命令 ----
set "TOOL_CMD="
for %%A in (%*) do (
    if /i "%%~A"=="--help"              set "TOOL_CMD=%%~A"
    if /i "%%~A"=="-h"                  set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--health-check"      set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--config-check"      set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--platform-check"    set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--examples"          set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--recommend"         set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--migrate-config"    set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--cleanup"           set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--validate-addresses" set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--template"          set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--quick-start"       set "TOOL_CMD=%%~A"
    if /i "%%~A"=="--quick-run"         set "TOOL_CMD=%%~A"
)

REM 支持命令别名 (快捷方式) - 必须在其他检测之前处理
set "ALIAS_REPLACED=0"
if /i "%~1"=="qs" (
    shift
    set "ARGS=--quick-start %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)
if /i "%~1"=="qr" (
    shift
    set "ARGS=--quick-run %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)
if /i "%~1"=="hc" (
    shift
    set "ARGS=--health-check %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)
if /i "%~1"=="cc" (
    shift
    set "ARGS=--config-check %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)
if /i "%~1"=="ex" (
    shift
    set "ARGS=--examples %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)
if /i "%~1"=="rec" (
    shift
    set "ARGS=--recommend %*"
    set "ALIAS_REPLACED=1"
    goto :after_alias_check
)

:after_alias_check
REM 如果使用了别名替换，重新检测TOOL_CMD
if "!ALIAS_REPLACED!"=="1" (
    set "HAS_ARGS=1"
    set "TOOL_CMD=1"
    REM 更新参数为替换后的值
    for %%A in (!ARGS!) do (
        if /i "%%~A"=="--help"              set "TOOL_CMD=%%~A"
        if /i "%%~A"=="-h"                  set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--health-check"      set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--config-check"      set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--platform-check"    set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--examples"          set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--recommend"         set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--migrate-config"    set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--cleanup"           set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--validate-addresses" set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--template"          set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--quick-start"       set "TOOL_CMD=%%~A"
        if /i "%%~A"=="--quick-run"         set "TOOL_CMD=%%~A"
    )
)

REM --help / -h: 显示批处理级帮助然后退出（管道时不暂停）
if /i "!TOOL_CMD!"=="--help" goto bat_help
if /i "!TOOL_CMD!"=="-h"     goto bat_help

set "PYTHON_SCRIPT=key_collision_cli.py"
set "CONFIG_EXAMPLE=config.example.json"

echo.
echo ========================================
echo   BTC Collision Engine - 启动器
echo ========================================
echo.

call :check_python
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

call :activate_venv

REM ---- 检查关键依赖（rich 是必需的）----------------------
call :check_deps
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" 2>nul
)

if not exist "config.json" (
    if exist "!CONFIG_EXAMPLE!" (
        copy "!CONFIG_EXAMPLE!" "config.json" >nul 2>&1
        echo [OK] 已从模板创建 config.json
    )
)

echo.

REM ---- 分发: 无参数 -> 向导; 工具命令 -> 直接传递; 其他 -> 运行 ----
if "!ALIAS_REPLACED!"=="1" (
    set "HAS_ARGS=1"
) else (
    set "HAS_ARGS=0"
    if NOT "%~1"=="" set "HAS_ARGS=1"
)

if "!HAS_ARGS!"=="0" (
    REM 双击启动: 运行交互式向导
    echo [INFO] 未检测到参数。启动快速启动向导...
    echo        (直接运行方式: start.bat -t ^<地址^> -m random)
    echo.
    python !PYTHON_SCRIPT! --quick-start
    set "EXIT_CODE=!errorlevel!"
) else if "!ALIAS_REPLACED!"=="1" (
    REM 使用了别名：使用替换后的参数
    python !PYTHON_SCRIPT! !ARGS!
    set "EXIT_CODE=!errorlevel!"
) else if NOT "!TOOL_CMD!"=="" (
    REM 工具命令: 直接传递所有参数，不需要横幅
    python !PYTHON_SCRIPT! %*
    set "EXIT_CODE=!errorlevel!"
) else (
    REM 使用用户提供的参数正常运行
    echo [INFO] 使用提供的参数启动引擎...
    echo.
    python !PYTHON_SCRIPT! %*
    set "EXIT_CODE=!errorlevel!"
)

echo.
if !EXIT_CODE! equ 0 (
    echo [OK] 完成。
) else if !EXIT_CODE! equ 130 (
    echo [INFO] 用户停止 (Ctrl+C)。
) else if !EXIT_CODE! equ 2 (
    echo [ERROR] 参数无效。
    echo   运行: start.bat --help
) else (
    echo [ERROR] 引擎退出，代码: !EXIT_CODE!
    echo.
    if "!HAS_ARGS!"=="0" (
        echo   提示:
        echo     1. 运行 install.bat 安装/修复依赖
        echo     2. 尝试:  start.bat -t 1A1zP1... -m random
        echo     3. 帮助: start.bat --help
    )
)

echo.
pause
exit /b !EXIT_CODE!


REM ============================================================
:check_deps
python -c "import rich" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 必需的依赖未安装。
    echo.
    echo   请先运行 install.bat 来设置环境。
    echo   位置: %~dp0install.bat
    exit /b 1
)
python -c "import ecdsa" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 必需的依赖未安装 (缺少 ecdsa)。
    echo.
    echo   请运行 install.bat 来修复环境。
    exit /b 1
)
exit /b 0


REM ============================================================
:check_python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python。
    echo.
    echo   下载: https://www.python.org/downloads/
    echo   安装时，请勾选 "Add Python to PATH"。
    exit /b 1
)
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
if "!PY_VER!"=="" set "PY_VER=unknown"
python -c "import sys; v=sys.version_info; open('__py_ver_check__.tmp','w').write('ok' if v>=(3,9) else 'low')" 2>nul
set "PY_CHECK_RESULT=low"
if exist "__py_ver_check__.tmp" (
    set /p PY_CHECK_RESULT=<__py_ver_check__.tmp
    del "__py_ver_check__.tmp" >nul 2>&1
)
if /i "!PY_CHECK_RESULT!"=="low" (
    echo [ERROR] Python 版本过低: !PY_VER! (需要 3.9+)
    exit /b 1
)
echo [OK] Python !PY_VER!
exit /b 0


REM ============================================================
:activate_venv
if defined VIRTUAL_ENV (
    echo [OK] 虚拟环境已激活: !VIRTUAL_ENV!
    exit /b 0
)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat 2>nul
    if not errorlevel 1 (
        echo [OK] 虚拟环境已激活
    ) else (
        echo [WARN] 激活虚拟环境失败，使用系统 Python
    )
) else (
    echo [WARN] 未找到 venv。运行: pip install -r requirements.txt
)
exit /b 0


REM ============================================================
:bat_help
echo.
echo BTC Collision Engine - 启动器
echo ========================================
echo.
echo 使用方法:
echo   start.bat                              双击: 启动快速启动向导
echo   start.bat [CLI 选项]                直接传递任何 CLI 选项
echo.
echo --- 目标 ---
echo   -t ^<地址^> [...]    单个或多个目标地址
echo   -f ^<文件^>             从文件加载地址（每行一个，支持 # 注释）
echo.
echo --- 模式 ---
echo   -m random              随机密钥搜索  (默认)
echo   -m range               范围扫描  (需要 --start 和 --end)
echo   -m brute_force         顺序穷举搜索
echo   --start ^<十六进制^>          范围/暴力搜索起始密钥 (十六进制)
echo   --end   ^<十六进制^>          范围搜索结束密钥 (十六进制)
echo.
echo --- GPU 加速 ---
echo   --use-gpu              启用单 GPU (需要 pyopencl)
echo   --multi-gpu            启用所有可用 GPU
echo   --gpu-device ^<索引^>   指定 GPU 索引 (-1 = 自动)
echo   --gpu-batch-size ^<N^>   每个 GPU 批次的密钥数 (默认: 自动)
echo   --gpu-count ^<N^>        多 GPU 模式下的 GPU 数量 (-1 = 全部)
echo   --gpu-indices ^<i...^>   手动指定 GPU 索引，例如 0 1
echo.
echo --- 选项 ---
echo   --checkpoint           启用断点续传
echo   --checkpoint-interval  断点保存间隔（秒，5-3600，默认: 30）
echo   --dedup                启用去重过滤 (仅随机模式)
echo   --dedup-max-size ^<N^>   去重过滤器容量 (默认: 1000000)
echo   --duration ^<秒^>      最大运行时间（秒，0 = 无限制）
echo   --workers ^<N^>          CPU 工作线程 (默认: 自动)
echo   --progress-interval    进度刷新间隔（秒，默认: 5）
echo   --sensitive-mode       密钥输出: full / masked / hash_only  (默认: full)
echo.
echo --- 性能 (高级) ---
echo   --no-optimize          禁用引擎优化 (调试)
echo   --window-size ^<4-8^>    EC 预计算窗口大小 (默认: 8)
echo   --no-simd              禁用 SIMD 哈希 (调试)
echo   --no-memory-pool       禁用内存池 (调试)
echo.
echo --- 工具命令 ---
echo   --quick-start          启动交互式向导
echo   --quick-run            快速模式：使用默认配置直接启动
echo   --health-check         系统依赖和配置健康报告
echo   --config-check         验证 config.json 结构
echo   --platform-check       跨平台兼容性检查
echo   --recommend            为当前系统推荐最佳参数
echo   --examples             显示使用示例
echo   --validate-addresses ^<文件^>  验证文件中的地址格式
echo   --template ^<名称^>      从预设模板生成 config.json
echo                          模板: gpu-performance, long-running, gpu-multi, quick-test
echo   --migrate-config       将旧 config.json 迁移到最新格式
echo   --cleanup              清理过期的临时文件和旧日志
echo   --dry-run              预览清理而不删除（与 --cleanup 一起使用）
echo   --export-progress ^<文件^>   运行后将进度数据导出到 JSON
echo   --export-matches ^<文件^>    运行后将匹配结果导出到 JSON
echo   --language ^<语言^>     界面语言: zh_CN 或 en_US
echo.
echo --- 快捷命令别名 ---
echo   qs                     交互式向导 (--quick-start)
echo   qr                     快速模式 (--quick-run)
echo   hc                     健康检查 (--health-check)
echo   cc                     配置验证 (--config-check)
echo   ex                     显示示例 (--examples)
echo   rec                    参数推荐 (--recommend)
echo.
echo --- 示例 ---
echo   start.bat
echo   start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo   start.bat -f targets.txt --use-gpu
echo   start.bat -f targets.txt -m range --start 1 --end FFFFFFFF
echo   start.bat -f targets.txt --multi-gpu --duration 3600
echo   start.bat --health-check
echo   start.bat --recommend
echo.
pause
exit /b 0
