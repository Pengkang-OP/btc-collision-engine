#!/bin/bash
# BTC碰撞引擎 - 部署脚本
# 自动化部署、配置和启动

set -euo pipefail

# 切换到项目根目录（脚本在 deploy/ 子目录中）
cd "$(dirname "$0")/.." || exit 1

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    # 检查Docker
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker未安装，请先安装Docker 20.10+"
        exit 1
    fi

    # 检查Docker Compose（拆分为嵌套条件，避免一行多个 &> 导致解析混淆）
    DOCKER_COMPOSE_CMD=""
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    if [[ -z "$DOCKER_COMPOSE_CMD" ]]; then
        log_error "Docker Compose未安装，请先安装Docker Compose 2.0+"
        exit 1
    fi

    # 检查NVIDIA驱动（GPU模式，拆分为嵌套if避免 [[ ]] 与 && command &> 混用）
    if [[ "$MODE" == "gpu" ]]; then
        if ! command -v nvidia-smi >/dev/null 2>&1; then
            log_warning "NVIDIA驱动未检测到，将使用CPU模式"
            MODE="cpu"
        fi
    fi

    log_success "依赖检查通过"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."

    # 创建运行时目录（与 docker-compose.yml volumes 的 bind mount 路径一致）
    mkdir -p data logs monitoring monitoring_data

    log_success "目录创建完成"
}

# 生成配置文件
generate_config() {
    if [[ ! -f "config.production.json" ]]; then
        log_info "生成生产配置文件..."

        cp config.example.json config.production.json

        log_success "配置文件已生成: config.production.json"
        log_warning "请编辑配置文件以调整参数"
    else
        log_info "配置文件已存在: config.production.json"
    fi
}

# 构建Docker镜像
build_images() {
    log_info "构建Docker镜像..."

    if [[ "$MODE" == "cpu" ]]; then
        ${DOCKER_COMPOSE_CMD} --profile cpu build
    elif [[ "$MODE" == "gpu" ]]; then
        if [[ "$GPU_VENDOR" == "nvidia" ]]; then
            ${DOCKER_COMPOSE_CMD} --profile gpu --profile nvidia build
        elif [[ "$GPU_VENDOR" == "amd" ]]; then
            ${DOCKER_COMPOSE_CMD} --profile gpu --profile amd build
        fi
    fi

    log_success "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."

    if [[ "$MODE" == "cpu" ]]; then
        ${DOCKER_COMPOSE_CMD} --profile cpu up -d
    elif [[ "$MODE" == "gpu" ]]; then
        if [[ "$GPU_VENDOR" == "nvidia" ]]; then
            ${DOCKER_COMPOSE_CMD} --profile gpu --profile nvidia up -d
        elif [[ "$GPU_VENDOR" == "amd" ]]; then
            ${DOCKER_COMPOSE_CMD} --profile gpu --profile amd up -d
        fi
    fi

    if [[ "${MONITORING:-}" == "true" ]]; then
        log_info "启动监控服务..."
        ${DOCKER_COMPOSE_CMD} --profile monitoring up -d
    fi

    log_success "服务启动完成"
}

# 健康检查
health_check() {
    log_info "等待服务启动..."
    sleep 10

    if [[ "$MODE" == "cpu" ]]; then
        CONTAINER="btc-collision-cpu"
    elif [[ "$MODE" == "gpu" ]]; then
        if [[ "$GPU_VENDOR" == "nvidia" ]]; then
            CONTAINER="btc-collision-gpu"
        elif [[ "$GPU_VENDOR" == "amd" ]]; then
            CONTAINER="btc-collision-gpu-amd"
        else
            log_error "不支持的GPU厂商: $GPU_VENDOR（支持: nvidia, amd）"
            exit 1
        fi
    else
        log_error "不支持的运行模式: $MODE（支持: cpu, gpu）"
        exit 1
    fi

    log_info "运行健康检查..."
    HEALTH_ARGS=""
    if [[ "$MODE" == "gpu" ]]; then
        HEALTH_ARGS="--gpu"
    fi
    docker exec "$CONTAINER" python -m src.utils.health_check --quiet $HEALTH_ARGS || {
        log_error "健康检查失败"
        docker logs "$CONTAINER"
        exit 1
    }

    log_success "健康检查通过"
}

# 显示状态
show_status() {
    echo ""
    log_info "服务状态:"
    ${DOCKER_COMPOSE_CMD} ps

    echo ""
    log_info "查看日志:"
    if [[ "$MODE" == "cpu" ]]; then
        echo "  ${DOCKER_COMPOSE_CMD} logs -f btc-engine-cpu"
    elif [[ "$MODE" == "gpu" ]]; then
        echo "  ${DOCKER_COMPOSE_CMD} logs -f btc-engine-gpu-${GPU_VENDOR}"
    fi

    if [[ "${MONITORING:-}" == "true" ]]; then
        echo ""
        log_info "监控服务:"
        echo "  Grafana: http://localhost:3000 (${GRAFANA_ADMIN_USER:-admin}/<见 .env 或密钥管理>)"
        echo "  Prometheus: http://localhost:9090"
    fi

    echo ""
    log_success "部署完成！"
}

# 清理资源
cleanup() {
    log_warning "清理所有资源..."

    ${DOCKER_COMPOSE_CMD} down -v
    ${DOCKER_COMPOSE_CMD} rm -f

    log_success "清理完成"
}

# 显示帮助
show_help() {
    cat << EOF
BTC碰撞引擎 - 部署脚本

用法: $0 [选项]

选项:
  -m, --mode MODE        运行模式: cpu 或 gpu (默认: cpu)
  -g, --gpu-vendor VENDOR GPU厂商: nvidia 或 amd (默认: nvidia)
  -M, --monitoring       启用监控服务
  -c, --cleanup          清理所有资源
  -h, --help            显示帮助信息

示例:
  # CPU模式部署
  $0 --mode cpu

  # NVIDIA GPU模式部署
  $0 --mode gpu --gpu-vendor nvidia

  # AMD GPU模式部署
  $0 --mode gpu --gpu-vendor amd

  # GPU模式 + 监控
  $0 --mode gpu --monitoring

  # 清理所有资源
  $0 --cleanup

EOF
}

# 解析参数
MODE="cpu"
GPU_VENDOR="nvidia"
MONITORING="false"
CLEANUP="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -g|--gpu-vendor)
            GPU_VENDOR="$2"
            shift 2
            ;;
        -M|--monitoring)
            MONITORING="true"
            shift
            ;;
        -c|--cleanup)
            CLEANUP="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 主流程
if [[ "$CLEANUP" == "true" ]]; then
    cleanup
    exit 0
fi

echo "========================================"
echo "  BTC碰撞引擎 - Docker部署"
echo "========================================"
echo "模式: $MODE"
echo "GPU厂商: $GPU_VENDOR"
echo "监控: $MONITORING"
echo "========================================"
echo ""

# 执行部署流程
check_dependencies
create_directories
generate_config
build_images
start_services
health_check
show_status
