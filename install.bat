@echo off
setlocal enabledelayedexpansion
call "%~dp0common.bat" :init_encoding
call "%~dp0common.bat" :set_script_dir
call "%~dp0common.bat" :print_header "BTC Collision Engine - Installer"

call "%~dp0common.bat" :check_python
if errorlevel 1 exit /b 1
call "%~dp0common.bat" :check_python_version
if errorlevel 1 exit /b 1

call "%~dp0common.bat" :print_section "Step 2: 设置虚拟环境"

if exist "venv\Scripts\activate.bat" (
    echo [INFO] 检测到现有虚拟环境
    echo.
    echo   1. 保留现有虚拟环境 (修复问题时推荐)
    echo   2. 删除并重新创建 (环境损坏时使用)
    echo.

:ask_venv
set "VENV_CHOICE="
set /p "VENV_CHOICE=   请选择 [1/2]: "
if "!VENV_CHOICE!"=="1" goto :activate_venv
if "!VENV_CHOICE!"=="2" (
    echo [INFO] 正在删除旧虚拟环境...
    rmdir /s /q venv >nul 2>&1
    goto :create_venv
)
echo [错误] 请输入 1 或 2
goto :ask_venv
) else (
    goto :create_venv
)

:create_venv
echo [INFO] 正在创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo [错误] 无法创建虚拟环境
    echo         尝试: python -m pip install virtualenv
    pause
    exit /b 1
)
echo [OK] 虚拟环境已创建

:activate_venv
echo [INFO] 正在激活虚拟环境...
call venv\Scripts\activate.bat >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法激活虚拟环境
    pause
    exit /b 1
)
echo [OK] 虚拟环境已激活

call "%~dp0common.bat" :print_section "Step 3: 升级 pip"
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [警告] pip 升级失败，继续安装...
) else (
    echo [OK] pip 升级成功
)

call "%~dp0common.bat" :print_section "Step 4: 安装基础依赖"
echo [INFO] 这可能需要几分钟...

echo   正在安装 coincurve (预编译)...
pip install "coincurve>=18.0.0" --only-binary :all: --quiet >nul 2>&1
if errorlevel 1 (
    echo   [警告] 预编译包不可用，正在尝试源码编译...
    pip install "coincurve>=18.0.0" --quiet >nul 2>&1
    if errorlevel 1 (
        echo   [警告] coincurve 安装失败，将使用 ecdsa 备用方案
    ) else (
        echo   [OK] coincurve 已从源码安装
    )
) else (
    echo   [OK] coincurve 已安装
)

echo   正在安装基础依赖...
pip install -r requirements-base.txt --quiet >nul 2>&1
if errorlevel 1 (
    echo [警告] 部分基础依赖安装失败，正在尝试详细安装...
    pip install -r requirements-base.txt
    if errorlevel 1 (
        echo [错误] 基础依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo [OK] 基础依赖已安装
)

call "%~dp0common.bat" :print_section "Step 5: GPU 加速支持 (可选)"
echo.
echo   GPU 加速可将性能提升 100-1000 倍
echo   需要: pyopencl + 对应显卡的 OpenCL 驱动
echo.
echo   NVIDIA 显卡: 安装 CUDA Toolkit ^>= 11.0
echo   AMD 显卡   : 安装 AMD 驱动 ^>= 21.x
echo   Intel Arc  : 安装 Intel Arc 驱动 ^>= 31.0.101.4146
echo.

:ask_gpu
set "GPU_CHOICE="
set /p "GPU_CHOICE=   是否安装 GPU 依赖? [y/n]: "
if /i "!GPU_CHOICE!"=="y" (
    echo [INFO] 正在安装 GPU 依赖...
    pip install -r requirements-gpu.txt
    if errorlevel 1 (
        echo [警告] GPU 依赖安装失败
        echo         可稍后重试: pip install -r requirements-gpu.txt
    ) else (
        echo [OK] GPU 依赖已安装
    )
    goto :after_gpu
)
if /i "!GPU_CHOICE!"=="n" (
    echo [INFO] 跳过 GPU 依赖，将使用 CPU 模式
    goto :after_gpu
)
echo [错误] 请输入 y 或 n
goto :ask_gpu

:after_gpu
call "%~dp0common.bat" :print_section "Step 6: 完成设置"

call "%~dp0common.bat" :create_required_dirs
if errorlevel 1 exit /b 1

call "%~dp0common.bat" :create_config
if errorlevel 1 exit /b 1

call "%~dp0common.bat" :print_section "Step 7: 验证依赖"
python -c "import rich"         >nul 2>&1
if errorlevel 1 (echo   [缺失] rich)              else (echo   [OK] rich)
python -c "import coincurve"    >nul 2>&1
if errorlevel 1 (echo   [警告] coincurve (ecdsa 备用)) else (echo   [OK] coincurve)
python -c "import ecdsa"        >nul 2>&1
if errorlevel 1 (echo   [缺失] ecdsa)             else (echo   [OK] ecdsa)
python -c "import psutil"       >nul 2>&1
if errorlevel 1 (echo   [缺失] psutil)            else (echo   [OK] psutil)
python -c "import gmpy2"        >nul 2>&1
if errorlevel 1 (echo   [INFO] gmpy2 (可选))      else (echo   [OK] gmpy2)
python -c "import pyopencl"     >nul 2>&1
if errorlevel 1 (echo   [INFO] pyopencl (GPU 模式不可用)) else (echo   [OK] pyopencl (GPU))
python -c "import jsonschema"   >nul 2>&1
if errorlevel 1 (echo   [缺失] jsonschema)        else (echo   [OK] jsonschema)

echo.
echo ================================================================
echo   Installation complete!
echo   Run start.bat to launch the engine
echo ================================================================
echo.
if not defined CI if not defined AUTOMATION pause
