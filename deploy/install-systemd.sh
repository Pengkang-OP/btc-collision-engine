#!/bin/bash
# BTC碰撞引擎 - systemd服务安装脚本

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查root权限
if [[ $EUID -ne 0 ]]; then
   log_error "此脚本需要root权限运行"
   log_error "请使用: sudo $0"
   exit 1
fi

echo "========================================"
echo "  BTC碰撞引擎 - systemd服务安装"
echo "========================================"
echo ""

# 1. 创建用户和组
log_info "创建btc-engine用户和组..."
if id "btc-engine" >/dev/null 2>&1; then
    log_warning "用户btc-engine已存在"
else
    useradd -r -m -d /opt/btc-collision-engine -s /bin/bash btc-engine
    log_success "用户创建完成"
fi

# 2. 创建目录结构
log_info "创建目录结构..."
mkdir -p /opt/btc-collision-engine/{logs,data_logs,monitoring_data}
chown -R btc-engine:btc-engine /opt/btc-collision-engine
chmod 750 /opt/btc-collision-engine/{logs,data_logs,monitoring_data}
log_success "目录创建完成"

# 3. 复制应用文件
log_info "复制应用文件..."
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || { log_error "无法确定应用目录"; exit 1; }

# 排除虚拟环境和不必要的文件
rsync -avz --exclude='venv' \
           --exclude='.git' \
           --exclude='__pycache__' \
           --exclude='*.pyc' \
           --exclude='.pytest_cache' \
           --exclude='tests' \
           --exclude='docs/archive' \
           "$APP_DIR/" /opt/btc-collision-engine/

chown -R btc-engine:btc-engine /opt/btc-collision-engine
log_success "应用文件复制完成"

# 4. 创建虚拟环境
log_info "创建Python虚拟环境..."
cd /opt/btc-collision-engine
python3 -m venv venv
chown -R btc-engine:btc-engine venv

# 切换到btc-engine用户安装依赖
su - btc-engine -c "cd /opt/btc-collision-engine && ./venv/bin/pip install --upgrade pip setuptools wheel"
su - btc-engine -c "cd /opt/btc-collision-engine && ./venv/bin/pip install -r requirements-base.txt"
log_success "虚拟环境创建完成"

# 5. 安装systemd服务文件
log_info "安装systemd服务文件..."
cp "$APP_DIR/deploy/systemd/btc-collision-engine.service" /etc/systemd/system/
systemctl daemon-reload
log_success "systemd服务文件安装完成"

# 6. 设置配置文件
log_info "配置生产环境..."
if [[ ! -f /opt/btc-collision-engine/config.production.json ]]; then
    cp /opt/btc-collision-engine/config.example.json /opt/btc-collision-engine/config.production.json
    chown btc-engine:btc-engine /opt/btc-collision-engine/config.production.json
    chmod 600 /opt/btc-collision-engine/config.production.json
    log_warning "请编辑配置文件: /opt/btc-collision-engine/config.production.json"
fi

# 7. 启用和启动服务
log_info "启用服务..."
systemctl enable btc-collision-engine

echo ""
log_info "服务管理命令:"
echo "  启动服务: systemctl start btc-collision-engine"
echo "  停止服务: systemctl stop btc-collision-engine"
echo "  重启服务: systemctl restart btc-collision-engine"
echo "  查看状态: systemctl status btc-collision-engine"
echo "  查看日志: journalctl -u btc-collision-engine -f"
echo ""

# 8. 询问是否启动
read -p "是否现在启动服务? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "启动服务..."
    systemctl start btc-collision-engine
    
    sleep 5
    
    # 检查服务状态
    if systemctl is-active --quiet btc-collision-engine; then
        log_success "服务启动成功！"
        echo ""
        log_info "服务状态:"
        systemctl status btc-collision-engine --no-pager
    else
        log_error "服务启动失败，请检查日志:"
        journalctl -u btc-collision-engine -n 50 --no-pager
        exit 1
    fi
else
    log_warning "服务已启用但未启动"
    log_info "使用以下命令手动启动:"
    echo "  systemctl start btc-collision-engine"
fi

echo ""
log_success "安装完成！"
echo ""
log_info "后续步骤:"
echo "  1. 编辑配置文件: nano /opt/btc-collision-engine/config.production.json"
echo "  2. 添加目标地址: echo '\''1A1z...'\'' >> /opt/btc-collision-engine/targets.txt"
echo "  3. 启动服务: systemctl start btc-collision-engine"
echo "  4. 查看日志: journalctl -u btc-collision-engine -f"
echo ""