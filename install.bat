@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM BTC Collision Engine - Install / Repair Script
REM Run this once before first use, or to repair a broken environment.

cd /d "%~dp0"

echo.
echo ========================================
echo   BTC Collision Engine - Installer
echo ========================================
echo.

REM ── Step 1: Check Python ────────────────────────────────────────────────────
echo [1/6] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo.
    echo   Please install Python 3.9+ from: https://www.python.org/downloads/
    echo   During install, check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
if "!PY_VER!"=="" set "PY_VER=unknown"

python -c "import sys; v=sys.version_info; open('__py_ver_check__.tmp','w').write('ok' if v>=(3,9) else 'low')" 2>nul
set "PY_RESULT=low"
if exist "__py_ver_check__.tmp" (
    set /p PY_RESULT=<__py_ver_check__.tmp
    del "__py_ver_check__.tmp" >nul 2>&1
)
if /i "!PY_RESULT!"=="low" (
    echo [ERROR] Python !PY_VER! is too old. Requires Python 3.9+.
    echo.
    echo   Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python !PY_VER!

REM ── Step 2: Virtual Environment ─────────────────────────────────────────────
echo.
echo [2/6] Setting up virtual environment...

if exist "venv\Scripts\activate.bat" (
    echo [INFO] Existing venv detected.
    echo.
    echo   1. Keep existing venv  (recommended if just repairing)
    echo   2. Delete and recreate (use if environment is broken)
    echo.
    :ask_venv
    set "VENV_CHOICE="
    set /p VENV_CHOICE="   Choose [1/2]: "
    if "!VENV_CHOICE!"=="1" goto activate_venv
    if "!VENV_CHOICE!"=="2" (
        echo [INFO] Removing old venv...
        rmdir /s /q venv 2>nul
        goto create_venv
    )
    echo [ERROR] Please enter 1 or 2.
    goto ask_venv
) else (
    goto create_venv
)

:create_venv
echo [INFO] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    echo   Try: python -m pip install virtualenv
    pause
    exit /b 1
)
echo [OK] Virtual environment created.

:activate_venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment active.

REM ── Step 3: Upgrade pip ──────────────────────────────────────────────────────
echo.
echo [3/6] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip up to date.

REM ── Step 4: Install base dependencies ───────────────────────────────────────
echo.
echo [4/6] Installing base dependencies (requirements-base.txt)...
echo       This may take a few minutes...
echo.

REM coincurve: prefer prebuilt wheel to avoid MSVC compile issues
echo   Installing coincurve (prebuilt)...
pip install "coincurve>=18.0.0" --only-binary :all: --quiet 2>nul
if errorlevel 1 (
    echo   [WARN] Prebuilt coincurve not available, trying source build...
    pip install "coincurve>=18.0.0" --quiet 2>nul
    if errorlevel 1 (
        echo   [WARN] coincurve install failed. Will fall back to pure-Python ecdsa backend.
    ) else (
        echo   [OK] coincurve installed from source.
    )
) else (
    echo   [OK] coincurve installed.
)

pip install -r requirements-base.txt --quiet
if errorlevel 1 (
    echo [WARN] Some base dependencies failed. Attempting verbose install for diagnosis...
    pip install -r requirements-base.txt
) else (
    echo [OK] Base dependencies installed.
)

REM ── Step 5: GPU dependencies (optional) ─────────────────────────────────────
echo.
echo [5/6] GPU acceleration (optional)
echo.
echo   GPU acceleration can multiply performance by 100-1000x.
echo   Requires: pyopencl + OpenCL driver for your GPU.
echo.
echo   NVIDIA : Install CUDA Toolkit ^>= 11.0
echo   AMD    : Install AMD driver ^>= 21.x
echo   Intel  : Install Intel Arc driver ^>= 31.0.101.4146
echo.
:ask_gpu
set "GPU_CHOICE="
set /p GPU_CHOICE="   Install GPU dependencies? [y/n]: "
if /i "!GPU_CHOICE!"=="y" (
    echo [INFO] Installing GPU dependencies (requirements-gpu.txt)...
    pip install -r requirements-gpu.txt
    if errorlevel 1 (
        echo [WARN] Some GPU dependencies failed. GPU mode may not work.
        echo        You can retry later: pip install -r requirements-gpu.txt
    ) else (
        echo [OK] GPU dependencies installed.
    )
    goto after_gpu
)
if /i "!GPU_CHOICE!"=="n" (
    echo [INFO] Skipping GPU dependencies. CPU mode will be used.
    goto after_gpu
)
echo [ERROR] Please enter y or n.
goto ask_gpu

:after_gpu

REM ── Step 6: Config & directories ────────────────────────────────────────────
echo.
echo [6/6] Finalizing setup...

for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" (
        mkdir "%%D" 2>nul
        echo [OK] Created directory: %%D
    )
)

if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul 2>&1
        echo [OK] config.json created from template.
    ) else (
        echo [WARN] config.example.json not found. config.json not created.
        echo        The engine will use built-in defaults.
    )
) else (
    echo [INFO] config.json already exists (not overwritten).
)

REM ── Verify key packages ──────────────────────────────────────────────────────
echo.
echo Verifying installed packages...
python -c "import rich"         2>nul && echo   [OK] rich            || echo   [MISS] rich
python -c "import coincurve"    2>nul && echo   [OK] coincurve       || echo   [WARN] coincurve  (ecdsa fallback will be used)
python -c "import ecdsa"        2>nul && echo   [OK] ecdsa           || echo   [MISS] ecdsa
python -c "import psutil"       2>nul && echo   [OK] psutil          || echo   [MISS] psutil
python -c "import gmpy2"        2>nul && echo   [OK] gmpy2           || echo   [INFO] gmpy2 not installed (optional, improves performance)
python -c "import pyopencl"     2>nul && echo   [OK] pyopencl (GPU)  || echo   [INFO] pyopencl not installed (GPU mode unavailable)
python -c "import jsonschema"   2>nul && echo   [OK] jsonschema      || echo   [MISS] jsonschema

REM ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo   Installation complete!
echo ========================================
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
