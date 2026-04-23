#!/usr/bin/env bash
# BTC 碰撞引擎 - Linux/macOS 启动脚本
# 用法: ./start.sh [参数]  (参数将透传给 key_collision_cli.py)

set -e

echo "========================================"
echo "BTC 碰撞引擎 - 命令行模式"
echo "========================================"
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

# 检测 Python 命令
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "[错误] 未找到 Python，请先安装 Python 3.7+"
    exit 1
fi

# 检查虚拟环境
if [ -f "venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source venv/bin/activate
    echo "[信息] 已激活虚拟环境: venv/"
elif [ -f ".venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
    echo "[信息] 已激活虚拟环境: .venv/"
fi

exec $PYTHON key_collision_cli.py "$@"
