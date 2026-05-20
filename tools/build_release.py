#!/usr/bin/env python3
"""
BTC Collision Engine - Release Build Script
Packages the project into a distributable release at the output directory.

Usage:
    python tools/build_release.py
    python tools/build_release.py --output-dir D:\\my-release
"""

import argparse
import shutil
import sys
from pathlib import Path

# ─────────────────────────── Config ────────────────────────────
VERSION = "4.2.3"
RELEASE_DATE = "2026-05-16"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = Path(r"F:\Qoder\btc-collision-tools")

# ──────────────────────── Script templates ──────────────────────

INSTALL_SH = r"""#!/bin/bash
set -e

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

echo "======================================================="
echo "  BTC Collision Engine v__VERSION__ - Installer (Linux/macOS)"
echo "======================================================="

# ── OS Detection ────────────────────────────────────────────────
OS=$(uname -s)
case "$OS" in
  Linux*)  info "Detected OS: Linux" ;;
  Darwin*) info "Detected OS: macOS" ;;
  *)       warning "Unrecognized OS: $OS, proceeding anyway..." ;;
esac

# ── Python version check ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Please install Python 3.9 or higher."
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  error "Python 3.9+ required. Found: $PY_VER"
fi
success "Python $PY_VER detected"

# ── System Environment Detection ─────────────────────
echo ""
echo "=== System Environment Report ==="
echo ""

# OS Detection
info "Operating System:"
if [ "$(uname)" = "Darwin" ]; then
    OS_NAME="macOS $(sw_vers -productVersion 2>/dev/null || echo 'unknown')"
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME="$NAME $VERSION"
else
    OS_NAME="$(uname -s) $(uname -r)"
fi
echo "  OS: $OS_NAME"

# CPU Architecture
ARCH=$(uname -m)
echo "  CPU Architecture: $ARCH"
if [ "$ARCH" != "x86_64" ] && [ "$ARCH" != "amd64" ]; then
    warning "Non-x86_64 architecture detected. Some binary packages may not be available."
fi

# CPU Cores
if [ "$(uname)" = "Darwin" ]; then
    CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || echo "unknown")
else
    CPU_CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo 2>/dev/null || echo "unknown")
fi
echo "  CPU Cores: $CPU_CORES"

# Memory Check
if [ "$(uname)" = "Darwin" ]; then
    TOTAL_MEM_KB=$(($(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024))
else
    TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
fi
if [ -n "$TOTAL_MEM_KB" ] && [ "$TOTAL_MEM_KB" -gt 0 ] 2>/dev/null; then
    TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))
    echo "  Total Memory: ${TOTAL_MEM_MB} MB"
    if [ "$TOTAL_MEM_MB" -lt 2048 ]; then
        warning "Less than 2GB RAM detected. Performance may be limited."
    fi
else
    echo "  Total Memory: unknown"
fi

# Disk Space Check
AVAIL_KB=$(df -k . 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$AVAIL_KB" ] && [ "$AVAIL_KB" -gt 0 ] 2>/dev/null; then
    AVAIL_MB=$((AVAIL_KB / 1024))
    echo "  Available Disk: ${AVAIL_MB} MB"
    if [ "$AVAIL_MB" -lt 500 ]; then
        warning "Less than 500MB disk space available. Installation may fail."
    fi
else
    echo "  Available Disk: unknown"
fi

# Network Connectivity
echo ""
info "Network Connectivity:"
if pip install --dry-run pip >/dev/null 2>&1 || curl -s --max-time 5 https://pypi.org >/dev/null 2>&1 || wget -q --spider --timeout=5 https://pypi.org 2>/dev/null; then
    success "PyPI reachable"
else
    warning "PyPI may be unreachable. Installation might fail if packages are not cached."
fi

# Build Tools
echo ""
info "Build Tools:"
if command -v gcc &>/dev/null; then
    GCC_VER=$(gcc --version 2>/dev/null | head -1)
    echo "  [OK] gcc: $GCC_VER"
elif command -v cc &>/dev/null; then
    echo "  [OK] C compiler available"
else
    warning "No C compiler found. Some packages requiring compilation may fail."
fi

if command -v git &>/dev/null; then
    echo "  [OK] git: $(git --version 2>/dev/null)"
else
    echo "  [--] git: not found (optional)"
fi

echo ""
echo "=================================="
echo ""

# ── Virtual environment ──────────────────────────────────────────
if [ -d "./venv" ] && [ -f "./venv/bin/activate" ]; then
  info "Existing virtual environment detected."
  read -p "Use existing venv? [Y/n]: " REUSE
  if [ "$REUSE" = "n" ] || [ "$REUSE" = "N" ]; then
    info "Removing old virtual environment..."
    rm -rf ./venv
    info "Creating new virtual environment..."
    python3 -m venv ./venv
    success "Virtual environment created"
  else
    info "Reusing existing virtual environment."
  fi
else
  info "Creating virtual environment..."
  python3 -m venv ./venv
  success "Virtual environment created"
fi

info "Activating virtual environment..."
# shellcheck disable=SC1091
source ./venv/bin/activate

# ── Upgrade pip ──────────────────────────────────────────────────
info "Upgrading pip..."
pip install --upgrade pip --quiet
success "pip upgraded"

# ── Check installed dependencies ────────────────────────────────
info "Checking installed packages..."
MISSING_DEPS=0

check_pkg() {
  if pip show "$1" > /dev/null 2>&1; then
    echo "  [OK] $1"
  else
    echo "  [MISS] $1"
    MISSING_DEPS=1
  fi
}

check_pkg "coincurve"
check_pkg "cryptography"
check_pkg "psutil"
check_pkg "ecdsa"
check_pkg "cffi"

SKIP_DEPS=0
if [ "$MISSING_DEPS" = "0" ]; then
  success "All key dependencies already installed."
  read -p "Reinstall all dependencies? [y/N]: " REINSTALL
  if [ "$REINSTALL" != "y" ] && [ "$REINSTALL" != "Y" ]; then
    info "Skipping dependency installation."
    SKIP_DEPS=1
  fi
fi

if [ "${SKIP_DEPS:-0}" != "1" ]; then

# ── Base dependencies ────────────────────────────────
info "Installing base dependencies..."
pip install -r requirements/requirements-base.txt 2>/dev/null
if [ $? -ne 0 ]; then
    warning "Some dependencies failed - handling individually..."

    # Step 1: cffi
    pip install "cffi>=1.15.0" 2>/dev/null

    # Step 2: coincurve fallback
    info "Installing coincurve..."
    pip install coincurve --only-binary=:all: 2>/dev/null || \
    pip install coincurve 2>/dev/null || \
    { warning "coincurve unavailable, using ecdsa"; pip install ecdsa>=0.18.0; }

    # Step 3: Re-install remaining deps
    info "Installing remaining dependencies..."
    pip install -r requirements/requirements-base.txt 2>/dev/null
    if [ $? -ne 0 ]; then
        warning "Installing key packages individually..."
        pip install chardet>=5.0.0 2>/dev/null
        pip install cryptography>=43.0.0 2>/dev/null
        pip install psutil>=5.9.0 2>/dev/null
        pip install requests>=2.28.0 2>/dev/null
        pip install jsonschema>=4.0.0 2>/dev/null
        pip install bech32>=1.2.0 2>/dev/null
        pip install cachetools>=5.3.0 2>/dev/null
        pip install setproctitle>=1.3.0 2>/dev/null
        pip install "PyNaCl>=1.5.0" 2>/dev/null
    fi
fi
success "Base dependencies installed"

fi  # end SKIP_DEPS

# ── GPU dependencies (optional) ─────────────────────────────────
echo ""
info "Detecting GPU environment..."
GPU_DETECTED=0

# Check if OpenCL runtime is available
if command -v clinfo &>/dev/null; then
    success "OpenCL runtime detected (clinfo available)"
    GPU_DETECTED=1
elif [ -d "/etc/OpenCL/vendors" ] && [ "$(ls -A /etc/OpenCL/vendors 2>/dev/null)" ]; then
    success "OpenCL ICD files found"
    GPU_DETECTED=1
fi

# Check if pyopencl is already installed
if pip show pyopencl &>/dev/null; then
    success "PyOpenCL already installed"
    GPU_DETECTED=1
fi

if [ "$GPU_DETECTED" = "1" ]; then
    info "GPU environment detected - recommending GPU dependencies"
    read -p "Install/update GPU dependencies (OpenCL/PyOpenCL)? [Y/n]: " gpu_choice
    gpu_choice=${gpu_choice:-Y}
else
    info "No GPU environment detected"
    read -p "Install GPU dependencies anyway? [y/N]: " gpu_choice
    gpu_choice=${gpu_choice:-N}
fi

case "$gpu_choice" in
  [Yy]|[Yy][Ee][Ss])
    info "Installing GPU dependencies..."
    pip install -r requirements/requirements-gpu.txt
    success "GPU dependencies installed"
    ;;
  *)
    info "Skipping GPU dependencies"
    ;;
esac

# ── Config initialization ────────────────────────────────────────
if [ -f "config.json" ]; then
  info "config.json already exists, keeping current config."
else
  info "Initializing config from template..."
  cp configs/config.example.json config.json
  success "config.json created"
fi

# ── Create directories ───────────────────────────────────────────
info "Creating runtime directories..."
mkdir -p logs data_logs monitoring_data
success "Directories created"

# ── Verify installation ──────────────────────────────────────────
info "Verifying installation..."
if python3 -c "from src.cli.main import main; print('OK')" 2>/dev/null; then
  success "Installation verified successfully"
else
  warning "Verification import failed - check dependencies manually"
fi

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo "======================================================="
success "Installation complete!"
echo ""
echo "  Quick start:"
echo "    chmod +x start.sh"
echo "    ./start.sh --help"
echo ""
echo "  Run collision:"
echo "    ./start.sh -t <address> -m random"
echo "======================================================="
"""

INSTALL_BAT = r"""@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =======================================================
echo   BTC Collision Engine v__VERSION__ - Installer (Windows)
echo =======================================================

:: ── Python version check ──────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found. Please install Python 3.9 or higher.
    pause & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if !PY_MAJOR! LSS 3 (
    echo [ERROR] Python 3.9+ required. Found: !PY_VER!
    pause & exit /b 1
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 9 (
    echo [ERROR] Python 3.9+ required. Found: !PY_VER!
    pause & exit /b 1
)
echo [OK] Python !PY_VER! detected

:: ── System Environment Detection ──────────────────
echo.
echo ===================================================
echo   System Environment Report
echo ===================================================
echo.

:: OS Detection
echo [INFO] Operating System:
for /f "tokens=2 delims==" %%a in ('wmic os get Caption /value 2^>nul ^| find "="') do echo   OS: %%a
for /f "tokens=2 delims==" %%a in ('wmic os get Version /value 2^>nul ^| find "="') do echo   Version: %%a

:: CPU Architecture
echo   CPU Architecture: %PROCESSOR_ARCHITECTURE%
if not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo [WARN] Non-AMD64 architecture. Some binary packages may not be available.
)

:: CPU Info
for /f "tokens=2 delims==" %%a in ('wmic cpu get NumberOfLogicalProcessors /value 2^>nul ^| find "="') do echo   CPU Cores: %%a
for /f "tokens=2 delims==" %%a in ('wmic cpu get Name /value 2^>nul ^| find "="') do echo   CPU: %%a

:: Memory Check
for /f "tokens=2 delims==" %%a in ('wmic os get TotalVisibleMemorySize /value 2^>nul ^| find "="') do set TOTAL_MEM_KB=%%a
if defined TOTAL_MEM_KB (
    set /a TOTAL_MEM_MB=!TOTAL_MEM_KB! / 1024
    echo   Total Memory: !TOTAL_MEM_MB! MB
    if !TOTAL_MEM_MB! LSS 2048 echo [WARN] Less than 2GB RAM. Performance may be limited.
)

:: Disk Space Check
for /f "tokens=3" %%a in ('dir /-C "%~dp0" 2^>nul ^| find "bytes free"') do set FREE_BYTES=%%a
if defined FREE_BYTES (
    set /a FREE_MB=!FREE_BYTES:~0,-6! 2>nul
    if defined FREE_MB (
        echo   Available Disk: ~!FREE_MB! MB
        if !FREE_MB! LSS 500 echo [WARN] Less than 500MB disk space. Installation may fail.
    )
)

:: Network Connectivity
echo.
echo [INFO] Network Connectivity:
pip install --dry-run pip >nul 2>&1
if not errorlevel 1 (
    echo   [OK] PyPI reachable
) else (
    echo [WARN] PyPI may be unreachable. Cached packages will be used if available.
)

:: Build Tools
echo.
echo [INFO] Build Tools:
where git >nul 2>&1
if not errorlevel 1 (
    echo   [OK] git available
) else (
    echo   [--] git: not found (optional)
)

where cl >nul 2>&1
if not errorlevel 1 (
    echo   [OK] Visual C++ compiler available
) else (
    echo   [--] Visual C++ compiler: not found (optional, needed for some source builds)
)

echo.
echo ===================================================
echo.

:: ── Virtual environment ───────────────────────────────────────
if exist venv\Scripts\activate.bat (
    echo [INFO] Existing virtual environment detected.
    set /p REUSE="Use existing venv? [Y/n]: "
    if /i "!REUSE!"=="n" (
        echo [INFO] Removing old virtual environment...
        rmdir /s /q venv
        echo [INFO] Creating new virtual environment...
        python -m venv venv
        if errorlevel 1 (
            echo [ERROR] Failed to create virtual environment
            pause & exit /b 1
        )
        echo [OK] Virtual environment created
    ) else (
        echo [INFO] Reusing existing virtual environment.
    )
) else (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause & exit /b 1
    )
    echo [OK] Virtual environment created
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause & exit /b 1
)

:: ── Upgrade pip ───────────────────────────────────────────────
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip upgraded

:: ── Check installed dependencies ─────────────────────────────
echo [INFO] Checking installed packages...
set MISSING_DEPS=0

pip show coincurve >nul 2>&1
if errorlevel 1 (
    echo   [MISS] coincurve
    set MISSING_DEPS=1
) else (
    echo   [OK] coincurve
)

pip show cryptography >nul 2>&1
if errorlevel 1 (
    echo   [MISS] cryptography
    set MISSING_DEPS=1
) else (
    echo   [OK] cryptography
)

pip show psutil >nul 2>&1
if errorlevel 1 (
    echo   [MISS] psutil
    set MISSING_DEPS=1
) else (
    echo   [OK] psutil
)

pip show ecdsa >nul 2>&1
if errorlevel 1 (
    echo   [MISS] ecdsa
) else (
    echo   [OK] ecdsa
)

pip show cffi >nul 2>&1
if errorlevel 1 (
    echo   [MISS] cffi
    set MISSING_DEPS=1
) else (
    echo   [OK] cffi
)

if "!MISSING_DEPS!"=="0" (
    echo [OK] All key dependencies already installed.
    set /p REINSTALL="Reinstall all dependencies? [y/N]: "
    if /i not "!REINSTALL!"=="y" (
        echo [INFO] Skipping dependency installation.
        goto :skip_deps
    )
)

:: ── Base dependencies ─────────────────────────────────────────────
echo [INFO] Installing base dependencies...
pip install -r requirements\requirements-base.txt 2>nul
if not errorlevel 1 goto :deps_ok

echo [WARN] Some base dependencies failed - handling individually...

:: Step 1: Install cffi first
echo [INFO] Installing cffi compatible version...
pip install "cffi>=1.15.0" 2>nul

:: Step 2: Handle coincurve with fallback
echo [INFO] Installing coincurve (precompiled preferred)...
pip install coincurve --only-binary=:all: 2>nul
if not errorlevel 1 goto :coincurve_ok
echo [WARN] Precompiled not available, trying source build...
pip install coincurve 2>nul
if not errorlevel 1 goto :coincurve_ok
echo [WARN] coincurve unavailable, installing ecdsa as fallback...
pip install ecdsa>=0.18.0 2>nul
:coincurve_ok
echo [OK] coincurve handled

:: Step 3: Re-install ALL remaining dependencies
echo [INFO] Installing remaining dependencies...
pip install -r requirements\requirements-base.txt 2>nul
if not errorlevel 1 goto :deps_ok

echo [WARN] Some packages may have failed, installing key packages individually...
pip install numpy>=1.24.0 2>nul
if errorlevel 1 (
    echo [WARN] numpy installation failed, but continuing...
)
pip install rich>=13.0 2>nul
if errorlevel 1 (
    echo [WARN] rich installation failed, but continuing...
)
pip install chardet>=5.0.0 2>nul
pip install cryptography>=43.0.0 2>nul
pip install psutil>=5.9.0 2>nul
pip install requests>=2.28.0 2>nul
pip install jsonschema>=4.0.0 2>nul
pip install bech32>=1.2.0 2>nul
pip install cachetools>=5.3.0 2>nul
pip install setproctitle>=1.3.0 2>nul
pip install "PyNaCl>=1.5.0" 2>nul
pip install pybloom-live>=2.2.0 2>nul
pip install gmpy2>=2.1.5 2>nul
pip install pycryptodome>=3.19.0 2>nul
pip install ecdsa>=0.18.0 2>nul
pip install bitarray>=2.6.0 2>nul
pip install xxhash>=3.0.0 2>nul

:deps_ok
echo [OK] Base dependencies installed

:skip_deps

:: ── GPU dependencies (optional) ──────────────────────────────
echo.
echo [INFO] Detecting GPU environment...
set GPU_DETECTED=0

where clinfo >nul 2>&1
if not errorlevel 1 (
    echo [OK] OpenCL runtime detected
    set GPU_DETECTED=1
)

pip show pyopencl >nul 2>&1
if not errorlevel 1 (
    echo [OK] PyOpenCL already installed
    set GPU_DETECTED=1
)

if "!GPU_DETECTED!"=="1" (
    echo [INFO] GPU environment detected - recommending GPU dependencies
    set /p GPU_INSTALL="Install/update GPU dependencies? [Y/n]: "
    if not defined GPU_INSTALL set GPU_INSTALL=Y
) else (
    echo [INFO] No GPU environment detected
    set /p GPU_INSTALL="Install GPU dependencies anyway? [y/N]: "
    if not defined GPU_INSTALL set GPU_INSTALL=N
)

if /i "!GPU_INSTALL!"=="y" goto :install_gpu
if /i "!GPU_INSTALL!"=="Y" goto :install_gpu
goto :skip_gpu

:install_gpu
echo [INFO] Installing GPU dependencies...
pip install -r requirements\requirements-gpu.txt 2>nul
if not errorlevel 1 goto :gpu_done
echo [WARN] Some GPU packages failed, trying individually...
pip install pyopencl 2>nul
pip install numpy 2>nul
:gpu_done
echo [OK] GPU dependencies handled

:skip_gpu

:: ── Config initialization ─────────────────────────────────────
:config_init
if exist config.json (
    echo [INFO] config.json already exists, keeping current config.
) else (
    echo [INFO] Initializing config from template...
    copy configs\config.example.json config.json >nul
    echo [OK] config.json created
)

:: ── Create directories ────────────────────────────────────────
echo [INFO] Creating runtime directories...
if not exist "logs" mkdir logs
if not exist "data_logs" mkdir data_logs
if not exist "monitoring_data" mkdir monitoring_data
echo [OK] Directories created

:: ── Verify installation ───────────────────────────────────────
echo [INFO] Verifying installation...
python -c "from src.cli.main import main; print('OK')" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Verification import failed - check dependencies manually
) else (
    echo [OK] Installation verified successfully
)

:: ── Done ──────────────────────────────────────────────────────
echo.
echo =======================================================
echo [OK] Installation complete!
echo.
echo   Quick start:
echo     start.bat --help
echo.
echo   Run collision:
echo     start.bat -t ^<address^> -m random
echo =======================================================
endlocal
pause
"""

START_SH = r"""#!/bin/bash
# BTC Collision Engine v__VERSION__ - Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Trap for graceful exit ───────────────────────────────────────
trap "kill 0" EXIT

# ── Virtual environment check ────────────────────────────────────
if [ -f "./venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source ./venv/bin/activate
else
    echo "[WARN] Virtual environment not found at ./venv"
    echo "       Run ./install.sh to set up the environment first"
fi

# ── Config check ─────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    if [ -f "$SCRIPT_DIR/config.example.json" ]; then
        echo "[INFO] config.json not found, creating from config.example.json..."
        cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
        echo "[OK] config.json created successfully."
    else
        echo "[WARN] Neither config.json nor config.example.json found."
    fi
fi

# ── Ensure log directory exists ──────────────────────────────────
mkdir -p logs

# ── Launch ───────────────────────────────────────────────────────
# If no arguments provided, default to quick-start wizard
if [ $# -eq 0 ]; then
    ARGS="--quick-start"
else
    ARGS="$@"
fi
exec python3 key_collision_cli.py $ARGS
"""

START_BAT = r"""@echo off
REM ============================================================
REM BTC Collision Engine v__VERSION__ - Startup Script
REM Features: Environment check, venv activation, config init, engine start
REM ============================================================

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM -- Switch to script directory --
cd /d "%~dp0"

REM -- Check --help parameter --
for %%A in (%*) do (
    if /i "%%~A"=="--help" (
        call :show_help
        exit /b 0
    )
    if /i "%%~A"=="-h" (
        call :show_help
        exit /b 0
    )
)

REM -- Initialize variables --
set "PYTHON_SCRIPT=key_collision_cli.py"
set "CONFIG_EXAMPLE=config.example.json"

echo.
echo ========================================
echo   BTC Collision Engine - Launcher
echo ========================================
echo.

REM -- Environment check --
call :check_python
if errorlevel 1 (
    pause
    exit /b 1
)

REM -- Activate virtual environment --
call :activate_venv

REM -- Create required directories --
for %%D in (logs data_logs monitoring_data) do (
    if not exist "%%D" mkdir "%%D" 2>nul
)

REM -- Initialize config file --
if not exist "config.json" (
    if exist "!CONFIG_EXAMPLE!" (
        copy "!CONFIG_EXAMPLE!" "config.json" >nul 2>&1
        echo [OK] Created config.json from template
    ) else (
        echo [WARN] Config template not found, please create config.json manually
    )
)

REM -- Start engine --
echo.
echo [INFO] Starting collision engine...
echo.

cmd /c python !PYTHON_SCRIPT! %*
set "EXIT_CODE=!errorlevel!"

REM -- Exit handling --
echo.
if !EXIT_CODE! equ 0 (
    echo [OK] Execution completed
) else if !EXIT_CODE! equ 130 (
    echo [INFO] User interrupted ^(Ctrl+C^)
) else if !EXIT_CODE! equ 2 (
    echo [ERROR] Parameter error, please run start.bat --help for usage
) else (
    echo [ERROR] Engine exited with code: !EXIT_CODE!
)

echo.
pause
exit /b !EXIT_CODE!

REM ============================================================
REM Subroutine: Check Python environment
REM ============================================================
:check_python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo.
    echo   Please download and install Python 3.9+ from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if errorlevel 1 (
    echo [ERROR] Python version too low: !PY_VER! ^(requires 3.9+^)
    exit /b 1
)
echo [OK] Python !PY_VER!
exit /b 0

REM ============================================================
REM Subroutine: Activate virtual environment
REM ============================================================
:activate_venv
if defined VIRTUAL_ENV (
    exit /b 0
)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat 2>nul
    if not errorlevel 1 (
        echo [OK] Virtual environment activated
    ) else (
        echo [WARN] Virtual environment activation failed, using system Python
    )
) else (
    echo [WARN] Virtual environment not found, recommended to run install.bat
)
exit /b 0

REM ============================================================
REM Subroutine: Show help
REM ============================================================
:show_help
echo.
echo BTC Collision Engine v__VERSION__ - Startup Script
echo ========================================
echo.
echo Usage:
echo   start.bat [options]
echo.
echo All options are passed directly to key_collision_cli.py, common options:
echo.
echo   Targets:
echo     -t ^<address^>       Specify single target address
echo     -f ^<file^>          Read target address list from file
echo.
echo   Mode:
echo     -m ^<mode^>          Collision mode: random / range / dictionary
echo     --start ^<hex^>      Range start (range mode only)
echo     --end ^<hex^>        Range end (range mode only)
echo.
echo   GPU:
echo     --use-gpu           Enable GPU acceleration
echo     --multi-gpu         Enable multi-GPU
echo     --config ^<file^>    Specify config file
echo.
echo   Control:
echo     --duration ^<sec^>   Run duration
echo     --quick-start       Start quick wizard
echo     --help              Show full help
echo.
echo Examples:
echo   start.bat --quick-start
echo   start.bat -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo   start.bat --config config.intel_arc.json --use-gpu
echo   start.bat -f targets.txt -m random --duration 3600
echo.
exit /b 0
"""

RELEASE_NOTES_MD = """# BTC Collision Engine v__VERSION__ Release Notes

## Release Date
__DATE__

## System Requirements
- Python 3.9 or higher (tested up to 3.14)
- Supported OS: Windows 10/11, Linux (Ubuntu 20.04+, CentOS 8+), macOS 12+
- Optional: OpenCL runtime for GPU acceleration

## Installation

### Script Installation (Recommended)
- **Windows**: Run `install.bat`
- **Linux/macOS**: Run `./install.sh`

### Manual Installation
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\\Scripts\\activate.bat  # Windows
pip install -r requirements/requirements-base.txt
```

### Docker Deployment
See `docker/` directory and `docs/DOCKER_DEPLOYMENT.md`

## GPU Acceleration
Supported vendors:
- **NVIDIA** (CUDA/OpenCL) - Driver 470+
- **AMD** (ROCm/OpenCL) - Driver 21.40+
- **Intel** (oneAPI/OpenCL) - Driver 2023+, Arc A-series recommended

GPU dependencies:
```bash
pip install -r requirements/requirements-gpu.txt
```

### Intel Arc Special Notes
- `configs/config.intel_arc.json` provides optimized settings for Arc A770
- `uint32_workaround` must be enabled to prevent hang issues
- Recommended `batch_size`: 1,048,576

## Configuration

| File | Purpose |
|------|---------|
| `configs/config.example.json` | General template (copy to `config.json`) |
| `configs/config.production.json` | Docker/production deployment |
| `configs/config.optimized.json` | Performance-optimized settings |
| `configs/config.intel_arc.json` | Intel Arc GPU optimized |
| `configs/config.multi_gpu.json` | Multi-GPU setup |

## Quick Start
```bash
# Show help
./start.sh --help         # Linux/macOS
start.bat --help           # Windows

# Run random collision
./start.sh -t <address> -m random
start.bat -t <address> -m random
```

## Key Features
- Multi-mode collision: random, sequential, brute-force
- GPU acceleration via OpenCL (NVIDIA/AMD/Intel)
- Multiple address types: P2PKH, P2SH, Bech32, WIF, Hash160
- Checkpoint/resume support
- Deduplication filter (Bloom filter)
- Real-time monitoring and alerting
- Internationalization (zh_CN, en_US)

## Known Issues
- `coincurve` may require a C compiler on some Linux distributions (`ecdsa` is used as fallback)
- Intel Arc async execution may be unstable; disable if encountering hangs
- GPU memory ratio should not exceed `0.80` for stability

## Changelog
See `CHANGELOG.md` for detailed version history.
"""


# ──────────────────────────── Helpers ───────────────────────────

def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def log(msg: str) -> None:
    print(f"  {msg}")


def log_step(step: str, detail: str = "") -> None:
    label = _cyan(f"[{step}]")
    print(f"  {label} {detail}")


def log_ok(detail: str) -> None:
    print(f"  {_green('[OK]')} {detail}")


def log_skip(detail: str) -> None:
    print(f"  {_yellow('[SKIP]')} {detail}")


# ──────────────────────── Build functions ───────────────────────

def _clean_output_dir(output_dir: Path) -> None:
    """Clean output directory, skipping locked files."""
    if not output_dir.exists():
        return

    skipped = []

    def on_rm_error(func, path, exc_info):
        """Handle removal errors - skip locked files."""
        skipped.append(path)

    shutil.rmtree(output_dir, onerror=on_rm_error)

    if skipped:
        print(f"  [WARN] Could not remove {len(skipped)} file(s) (locked by another process):")
        for s in skipped[:5]:
            print(f"         - {s}")
        if len(skipped) > 5:
            print(f"         ... and {len(skipped) - 5} more")

    # Ensure output directory exists (recreate if fully deleted, or reuse if partially cleaned)
    output_dir.mkdir(parents=True, exist_ok=True)


def clean_output(out: Path) -> None:
    log_step("CLEAN", str(out))
    _clean_output_dir(out)
    log_ok("Output directory ready")


def copy_source(root: Path, out: Path) -> None:
    src = root / "src"
    dst = out / "src"
    log_step("SRC", f"{src} -> {dst}")
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", ".git", "venv", ".pytest_cache"
        )
    )
    log_ok("src/ copied")


def copy_entry_files(root: Path, out: Path) -> None:
    files = ["key_collision_cli.py", "key_collision.py", "pyproject.toml"]
    for name in files:
        src = root / name
        if src.exists():
            shutil.copy2(src, out / name)
            log_ok(f"Entry: {name}")
        else:
            log_skip(f"Entry not found: {name}")


def copy_batch_scripts(root: Path, out: Path) -> None:
    """复制所有 .bat 脚本到输出目录"""
    bat_files = [
        "diagnostic.bat",
        "generate_report.bat",
        "log_monitor.bat",
        "start_async_optimized.bat",
        "start_engine.bat",
        "start_monitoring.bat",
    ]
    copied = 0
    for name in bat_files:
        src = root / name
        if src.exists():
            shutil.copy2(src, out / name)
            log_ok(f"Script: {name}")
            copied += 1
        else:
            log_skip(f"Script not found: {name}")
    if copied > 0:
        print(f"  [INFO] {copied} batch script(s) copied")


def copy_requirements(root: Path, out: Path) -> None:
    req_dir = out / "requirements"
    req_dir.mkdir(exist_ok=True)
    files = [
        "requirements-base.txt",
        "requirements-gpu.txt",
        "requirements.lock",
    ]
    for name in files:
        src = root / name
        if src.exists():
            shutil.copy2(src, req_dir / name)
            log_ok(f"Req: {name}")
        else:
            log_skip(f"Req not found: {name}")
    # 生成发布版 requirements.txt（不含 dev 依赖引用）
    release_req = req_dir / "requirements.txt"
    release_req.write_text(
        "# BTC 私钥碰撞工具依赖\n"
        "#\n"
        "# 推荐按需安装：\n"
        "#   基础功能:   pip install -r requirements-base.txt\n"
        "#   GPU 加速:   pip install -r requirements-gpu.txt\n"
        "#   全量安装:   pip install -r requirements.txt  (本文件)\n"
        "#\n"
        "jsonschema>=4.0.0\n"
        "\n"
        "# 基础依赖（必需）\n"
        "-r requirements-base.txt\n"
        "\n"
        "# GPU 加速依赖（可选）\n"
        "-r requirements-gpu.txt\n",
        encoding='utf-8'
    )
    log_ok("Req: requirements.txt (release version, no dev deps)")


def copy_configs(root: Path, out: Path) -> None:
    cfg_dir = out / "configs"
    cfg_dir.mkdir(exist_ok=True)
    files = [
        "config.example.json",
        "config.production.json",
        "config.optimized.json",
        "config.intel_arc.json",
        "config.multi_gpu.json",
    ]
    for name in files:
        src = root / name
        if src.exists():
            shutil.copy2(src, cfg_dir / name)
            log_ok(f"Config: {name}")
        else:
            log_skip(f"Config not found: {name}")

    # start.sh / start.bat expect config.example.json in the root directory
    example_src = root / "config.example.json"
    if example_src.exists():
        shutil.copy2(example_src, out / "config.example.json")
        log_ok("config.example.json copied to root (required by start scripts)")
    else:
        log_skip("config.example.json not found in source root")

    # 不复制 config.json 到发布包，由 start.bat/sh 运行时自动从 config.example.json 创建
    # 这确保用户总是使用最新的配置模板


def copy_docker(root: Path, out: Path) -> None:
    docker_dir = out / "docker"
    docker_dir.mkdir(exist_ok=True)
    files = ["Dockerfile", "Dockerfile.amd", "docker-compose.yml"]
    for name in files:
        src = root / name
        if src.exists():
            shutil.copy2(src, docker_dir / name)
            log_ok(f"Docker: {name}")
        else:
            log_skip(f"Docker file not found: {name}")

    deploy_src = root / "deploy"
    if deploy_src.exists():
        shutil.copytree(deploy_src, docker_dir / "deploy")
        log_ok("deploy/ subdirectory copied")


def copy_docs(root: Path, out: Path) -> None:
    docs_src = root / "docs"
    docs_dst = out / "docs"
    docs_dst.mkdir(exist_ok=True)

    # Copy top-level files
    for item in docs_src.iterdir():
        if item.is_file():
            shutil.copy2(item, docs_dst / item.name)

    # Copy selected subdirectories (skip archive/)
    keep_dirs = {"standards", "security", "audit-reports"}
    for item in docs_src.iterdir():
        if item.is_dir() and item.name in keep_dirs:
            shutil.copytree(item, docs_dst / item.name)
            log_ok(f"Docs subdir: {item.name}/")

    log_ok("docs/ copied (archive/ excluded)")


def copy_root_docs(root: Path, out: Path) -> None:
    files = ["README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md"]
    for name in files:
        src = root / name
        if src.exists():
            shutil.copy2(src, out / name)
            log_ok(f"Doc: {name}")
        else:
            log_skip(f"Doc not found: {name}")


def generate_install_sh(out: Path) -> None:
    content = INSTALL_SH.replace("__VERSION__", VERSION)
    target = out / "install.sh"
    target.write_text(content, encoding="utf-8", newline="\n")
    log_ok("install.sh generated (LF)")


def generate_install_bat(out: Path) -> None:
    content = INSTALL_BAT.replace("__VERSION__", VERSION)
    target = out / "install.bat"
    target.write_text(content, encoding="utf-8", newline="\r\n")
    log_ok("install.bat generated (CRLF)")


def generate_start_sh(out: Path) -> None:
    content = START_SH.replace("__VERSION__", VERSION)
    target = out / "start.sh"
    target.write_text(content, encoding="utf-8", newline="\n")
    log_ok("start.sh generated (LF)")


def generate_start_bat(out: Path) -> None:
    """复制源目录的 start.bat（带交互式菜单）"""
    src = PROJECT_ROOT / "start.bat"
    if src.exists():
        # 直接复制源文件，保留所有功能
        shutil.copy2(src, out / "start.bat")
        log_ok("start.bat copied from source (with menu)")
    else:
        # 如果源文件不存在，使用简化版模板
        content = START_BAT.replace("__VERSION__", VERSION)
        target = out / "start.bat"
        target.write_text(content, encoding="utf-8", newline="\r\n")
        log_ok("start.bat generated from template (CRLF)")


def generate_release_notes(out: Path) -> None:
    content = RELEASE_NOTES_MD.replace("__VERSION__", VERSION).replace("__DATE__", RELEASE_DATE)
    target = out / "RELEASE_NOTES.md"
    target.write_text(content, encoding="utf-8", newline="\n")
    log_ok("RELEASE_NOTES.md generated")


# ─────────────────────────── Summary ────────────────────────────

def print_summary(out: Path) -> None:
    categories = {
        "源码 (src/)": out / "src",
        "配置 (configs/)": out / "configs",
        "文档 (docs/)": out / "docs",
        "Docker (docker/)": out / "docker",
        "依赖 (requirements/)": out / "requirements",
    }

    total_files = 0
    total_bytes = 0

    print()
    print(_bold("  ── Release Package Summary ─────────────────────"))

    for label, path in categories.items():
        if not path.exists():
            continue
        files = list(path.rglob("*"))
        count = sum(1 for f in files if f.is_file())
        size = sum(f.stat().st_size for f in files if f.is_file())
        total_files += count
        total_bytes += size
        print(f"    {label:<28} {count:>4} files  {size / 1024:.1f} KB")

    # Root-level files
    root_files = [f for f in out.iterdir() if f.is_file()]
    root_count = len(root_files)
    root_size = sum(f.stat().st_size for f in root_files)
    total_files += root_count
    total_bytes += root_size
    print(f"    {'根目录文件':<28} {root_count:>4} files  {root_size / 1024:.1f} KB")

    print(_bold("  " + "─" * 50))
    print(f"    {'Total':<28} {total_files:>4} files  {total_bytes / 1024 / 1024:.2f} MB")
    print()
    print(f"  {_green('Output:')} {out}")
    print()


# ──────────────────────────── Main ──────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description=f"BTC Collision Engine v{VERSION} - Release Build Script"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out: Path = args.output_dir.resolve()

    print()
    print(_bold(f"  BTC Collision Engine v{VERSION} - Release Build"))
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Output dir   : {out}")
    print()

    steps = [
        ("Cleaning output", lambda: clean_output(out)),
        ("Copying source", lambda: copy_source(PROJECT_ROOT, out)),
        ("Copying entry files", lambda: copy_entry_files(PROJECT_ROOT, out)),
        ("Copying batch scripts", lambda: copy_batch_scripts(PROJECT_ROOT, out)),
        ("Copying requirements", lambda: copy_requirements(PROJECT_ROOT, out)),
        ("Copying config templates", lambda: copy_configs(PROJECT_ROOT, out)),
        ("Copying Docker files", lambda: copy_docker(PROJECT_ROOT, out)),
        ("Copying docs", lambda: copy_docs(PROJECT_ROOT, out)),
        ("Copying root docs", lambda: copy_root_docs(PROJECT_ROOT, out)),
        ("Generating install.sh", lambda: generate_install_sh(out)),
        ("Generating install.bat", lambda: generate_install_bat(out)),
        ("Generating start.sh", lambda: generate_start_sh(out)),
        ("Generating start.bat", lambda: generate_start_bat(out)),
        ("Generating RELEASE_NOTES.md", lambda: generate_release_notes(out)),
    ]

    for title, fn in steps:
        print(f"  {_bold(title)}")
        try:
            fn()
        except Exception as exc:
            print(f"  \033[31m[ERROR]\033[0m {title} failed: {exc}")
            return 1
        print()

    print_summary(out)
    print(_green("  Build complete!"))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
