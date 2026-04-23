#!/usr/bin/env bash
# BTC 碰撞引擎 - Linux/macOS 启动脚本
# 用法: ./start.sh [参数]  (参数将透传给 key_collision_cli.py)

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "BTC 碰撞引擎 - 命令行模式"
echo "========================================"
echo ""

# 1. 检查Python
echo "[1/4] 检查Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "${RED}[错误] 未找到Python，请先安装Python 3.9+${NC}"
    echo "Ubuntu/Debian: sudo apt install python3"
    echo "Fedora: sudo dnf install python3"
    echo "macOS: brew install python"
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version | awk '{print $2}')
echo -e "${GREEN}[成功]${NC} Python版本: $PYTHON_VERSION"

# 2. 检查虚拟环境
echo ""
echo "[2/4] 检查虚拟环境..."
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}[警告]${NC} 虚拟环境未激活"
    if [ -f "venv/bin/activate" ]; then
        read -p "是否激活虚拟环境? (y/N): " ACTIVATE
        if [ "$ACTIVATE" = "y" ] || [ "$ACTIVATE" = "Y" ]; then
            source venv/bin/activate
            echo -e "${GREEN}[成功]${NC} 虚拟环境已激活: venv/"
        fi
    elif [ -f ".venv/bin/activate" ]; then
        read -p "是否激活虚拟环境? (y/N): " ACTIVATE
        if [ "$ACTIVATE" = "y" ] || [ "$ACTIVATE" = "Y" ]; then
            source .venv/bin/activate
            echo -e "${GREEN}[成功]${NC} 虚拟环境已激活: .venv/"
        fi
    else
        echo -e "${YELLOW}[信息]${NC} 未找到虚拟环境，建议先运行: bash scripts/install.sh"
    fi
else
    echo -e "${GREEN}[成功]${NC} 虚拟环境已激活: $VIRTUAL_ENV"
fi

# 3. 检查配置文件
echo ""
echo "[3/4] 检查配置文件..."
if [ ! -f "config.json" ]; then
    echo -e "${YELLOW}[警告]${NC} 配置文件不存在，从示例复制..."
    if [ -f "config.example.json" ]; then
        cp config.example.json config.json
        echo -e "${GREEN}[成功]${NC} 配置文件已创建: config.json"
    else
        echo -e "${RED}[错误]${NC} 示例配置文件也不存在"
        exit 1
    fi
else
    echo -e "${GREEN}[成功]${NC} 配置文件已存在: config.json"
fi

# 4. 检查必要目录
echo ""
echo "[4/4] 检查必要目录..."
mkdir -p logs data_logs monitoring_data
echo -e "${GREEN}[成功]${NC} 目录检查完成"

echo ""
echo "用法示例:"
echo ""
echo "  随机碰撞:"
echo "    python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random"
echo ""
echo "  范围扫描:"
echo "    python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF"
echo ""
echo "  查看全部选项:"
echo "    python key_collision_cli.py --help"
echo ""

exec $PYTHON key_collision_cli.py "$@"
