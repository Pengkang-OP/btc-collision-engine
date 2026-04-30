@echo off
setlocal enabledelayedexpansion

call "%~dp0common.bat"
call :init_encoding
call :set_script_dir

call :print_header "BTC Collision Engine - Installer"

call :print_section "Step 1: Check Python Environment"
call :check_python

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
echo [OK] Python version: !PY_VER!

call :check_python_version

call :print_section "Step 2: Setup Virtual Environment"

if exist "venv\Scripts\activate.bat" (
    echo [INFO] Existing virtual environment detected
    echo.
    echo   1. Keep existing venv (recommended if repairing)
    echo   2. Delete and recreate (use if environment is broken)
    echo.
    
    :ask_venv
    set "VENV_CHOICE="
    set /p "VENV_CHOICE=   Choose [1/2]: "
    if "!VENV_CHOICE!"=="1" goto :activate_venv
    if "!VENV_CHOICE!"=="2" (
        echo [INFO] Removing old venv...
        rmdir /s /q venv >nul 2>&1
        goto :create_venv
    )
    echo [ERROR] Please enter 1 or 2
    goto :ask_venv
) else (
    goto :create_venv
)

:create_venv
echo [INFO] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    echo         Try: python -m pip install virtualenv
    pause
    exit /b 1
)
echo [OK] Virtual environment created

:activate_venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

call :print_section "Step 3: Upgrade pip"
python -m pip install --upgrade pip --quiet
echo [OK] pip upgraded successfully

call :print_section "Step 4: Install Base Dependencies"
echo [INFO] This may take a few minutes...

echo   Installing coincurve (prebuilt)...
pip install "coincurve>=18.0.0" --only-binary :all: --quiet >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Prebuilt coincurve not available, trying source build...
    pip install "coincurve>=18.0.0" --quiet >nul 2>&1
    if errorlevel 1 (
        echo   [WARN] coincurve install failed, will use ecdsa fallback
    ) else (
        echo   [OK] coincurve installed from source
    )
) else (
    echo   [OK] coincurve installed
)

echo   Installing base dependencies...
pip install -r requirements-base.txt --quiet >nul 2>&1
if errorlevel 1 (
    echo [WARN] Some base dependencies failed, attempting verbose install...
    pip install -r requirements-base.txt
) else (
    echo [OK] Base dependencies installed
)

call :print_section "Step 5: GPU Acceleration (Optional)"
echo.
echo   GPU acceleration can multiply performance by 100-1000x
echo   Requires: pyopencl + OpenCL driver for your GPU
echo.
echo   NVIDIA : Install CUDA Toolkit >= 11.0
echo   AMD    : Install AMD driver >= 21.x
echo   Intel  : Install Intel Arc driver >= 31.0.101.4146
echo.

:ask_gpu
set "GPU_CHOICE="
set /p "GPU_CHOICE=   Install GPU dependencies? [y/n]: "
if /i "!GPU_CHOICE!"=="y" (
    echo [INFO] Installing GPU dependencies...
    pip install -r requirements-gpu.txt
    if errorlevel 1 (
        echo [WARN] GPU dependencies installation failed
        echo        You can retry later: pip install -r requirements-gpu.txt
    ) else (
        echo [OK] GPU dependencies installed
    )
    goto :after_gpu
)
if /i "!GPU_CHOICE!"=="n" (
    echo [INFO] Skipping GPU dependencies, CPU mode will be used
    goto :after_gpu
)
echo [ERROR] Please enter y or n
goto :ask_gpu

:after_gpu
call :print_section "Step 6: Finalize Setup"

call :create_required_dirs
call :create_config

call :print_section "Verify Installed Packages"
echo.

python -c "import rich"         >nul 2>&1 && echo   [OK] rich            || echo   [MISS] rich
python -c "import coincurve"    >nul 2>&1 && echo   [OK] coincurve       || echo   [WARN] coincurve  (ecdsa fallback)
python -c "import ecdsa"        >nul 2>&1 && echo   [OK] ecdsa           || echo   [MISS] ecdsa
python -c "import psutil"       >nul 2>&1 && echo   [OK] psutil          || echo   [MISS] psutil
python -c "import gmpy2"        >nul 2>&1 && echo   [OK] gmpy2           || echo   [INFO] gmpy2 (optional)
python -c "import pyopencl"     >nul 2>&1 && echo   [OK] pyopencl (GPU)  || echo   [INFO] pyopencl (GPU mode unavailable)
python -c "import jsonschema"   >nul 2>&1 && echo   [OK] jsonschema      || echo   [MISS] jsonschema

call :print_header "Installation Complete!"
echo.
echo   Next steps:
echo     Double-click  start.bat        to launch the quick-start wizard
echo     Or run:       start.bat --help  to see all options
echo.
echo   Direct run example:
echo     start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo.
pause
exit /b 0