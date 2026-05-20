#!/bin/bash
# BTC 碰撞引擎 - Linux/macOS 安装脚本

set -euo pipefail

# 切换到脚本所在目录，确保相对路径正确
cd "$(dirname "$0")/.." || exit 1

echo "========================================"
echo "BTC 碰撞引擎 - 安装脚本"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查Python版本
echo "[1/7] 检查Python版本..."
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[错误] 未找到Python3，请先安装Python 3.9+${NC}"
    echo "Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "Fedora: sudo dnf install python3"
    echo "macOS: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}[成功]${NC} Python版本: $PYTHON_VERSION"

# 检查Python版本是否 >= 3.9
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
    echo -e "${RED}[错误] Python版本过低，需要3.9或更高版本${NC}"
    echo "当前版本: $PYTHON_VERSION"
    exit 1
fi

# 2. 检查虚拟环境
echo ""
echo "[2/7] 检查虚拟环境..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}[信息]${NC} 检测到现有虚拟环境"
    read -r -p "是否使用现有虚拟环境? (y/N): " USE_EXISTING || USE_EXISTING="n"
    if [ "$USE_EXISTING" = "y" ] || [ "$USE_EXISTING" = "Y" ]; then
        source venv/bin/activate
        echo -e "${GREEN}[成功]${NC} 虚拟环境已激活"
    else
        echo -e "${YELLOW}[信息]${NC} 删除现有虚拟环境..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    # 创建虚拟环境
    echo -e "${YELLOW}[信息]${NC} 创建虚拟环境..."
    if ! python3 -m venv venv; then
        echo -e "${RED}[错误] 创建虚拟环境失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}[成功]${NC} 虚拟环境创建成功"

    # 3. 激活虚拟环境
    echo ""
    echo "[3/7] 激活虚拟环境..."
    if ! source venv/bin/activate; then
        echo -e "${RED}[错误] 激活虚拟环境失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}[成功]${NC} 虚拟环境已激活"
fi

# 4. 安装基础依赖
echo ""
echo "[4/7] 安装基础依赖..."
echo -e "${YELLOW}[信息]${NC} 这可能需要几分钟时间，请耐心等待..."

# 升级 pip 以支持更多预编译 wheel
python3 -m pip install --upgrade pip --quiet

# 优先尝试安装 coincurve（先预编译，失败则源码编译）
echo -e "${YELLOW}[信息]${NC} 安装 coincurve..."
set +e
pip install "coincurve>=18.0.0" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[警告]${NC} 预编译安装失败，尝试源码编译..."
    pip install --no-binary :all: coincurve
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}[警告]${NC} coincurve 安装失败，将使用 ecdsa 作为备选"
    fi
fi
set -e

# 安装其余基础依赖（允许失败后继续）
set +e
pip install -r requirements-base.txt
PIP_EXIT=$?
set -e
if [ $PIP_EXIT -ne 0 ]; then
    echo -e "${YELLOW}[警告]${NC} 基础依赖安装失败，尝试继续..."
else
    echo -e "${GREEN}[成功]${NC} 基础依赖安装完成"
fi

# 5. 提示安装GPU依赖
echo ""
echo "[5/7] GPU加速支持（可选）..."
read -r -p "是否安装GPU加速依赖? (y/N): " INSTALL_GPU || INSTALL_GPU="n"
if [ "$INSTALL_GPU" = "y" ] || [ "$INSTALL_GPU" = "Y" ]; then
    echo -e "${YELLOW}[信息]${NC} 安装GPU依赖..."
    set +e
    pip install -r requirements-gpu.txt
    GPU_EXIT=$?
    set -e
    if [ $GPU_EXIT -ne 0 ]; then
        echo -e "${YELLOW}[警告]${NC} GPU依赖安装失败，可以稍后手动安装"
    else
        echo -e "${GREEN}[成功]${NC} GPU依赖安装完成"
    fi
else
    echo -e "${YELLOW}[信息]${NC} 跳过GPU依赖安装"
fi

# 6. 复制配置文件
echo ""
echo "[6/7] 初始化配置文件..."
if [ ! -f "config.json" ]; then
    cp config.example.json config.json
    echo -e "${GREEN}[成功]${NC} 配置文件已创建: config.json"
else
    echo -e "${YELLOW}[信息]${NC} 配置文件已存在: config.json"
fi

# 7. 验证关键依赖
echo ""
echo "[7/7] 验证关键依赖..."
echo -e "${YELLOW}[验证]${NC} 检查关键依赖..."
python3 -c "import coincurve; print(f'  coincurve {coincurve.__version__} ✓')" 2>/dev/null || echo -e "  ${RED}coincurve 未安装${NC}"
python3 -c "import gmpy2; print(f'  gmpy2 {gmpy2.version} ✓')" 2>/dev/null || echo -e "  ${YELLOW}gmpy2 未安装（可选加速）${NC}"
python3 -c "import psutil; print(f'  psutil {psutil.__version__} ✓')" 2>/dev/null || echo -e "  ${RED}psutil 未安装${NC}"
python3 -c "import ecdsa; print(f'  ecdsa {ecdsa.__version__} ✓')" 2>/dev/null || echo -e "  ${YELLOW}ecdsa 备选库 ✓${NC}"

# 创建必要目录
mkdir -p logs data_logs monitoring_data

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "快速开始:"
echo "  1. 激活虚拟环境: source venv/bin/activate"
echo "  2. 运行碰撞测试: python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random --duration 10"
echo "  3. 查看帮助: python key_collision_cli.py --help"
echo ""
echo "或使用启动脚本:"
echo "  ./start.sh -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random"
echo ""
