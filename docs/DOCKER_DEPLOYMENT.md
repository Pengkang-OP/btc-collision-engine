# Docker部署指南

本文档提供BTC碰撞引擎的Docker容器化部署详细说明。

## 📋 目录

- [快速开始](#快速开始)
- [CPU模式部署](#cpu模式部署)
- [GPU模式部署](#gpu模式部署)
- [多GPU部署](#多gpu部署)
- [监控配置](#监控配置)
- [数据持久化](#数据持久化)
- [日志管理](#日志管理)
- [性能调优](#性能调优)
- [故障排除](#故障排除)

---

## 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA GPU（GPU模式，可选）
- NVIDIA Container Toolkit（GPU模式，必需）

### 安装NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 重启Docker
sudo systemctl restart docker
```

---

## CPU模式部署

### 1. 准备配置文件

```bash
# 创建生产配置
cp config.example.json config.production.json

# 编辑配置
nano config.production.json
```

### 2. 启动服务

```bash
# 构建镜像
docker-compose --profile cpu build

# 启动服务
docker-compose --profile cpu up -d

# 查看日志
docker-compose logs -f btc-engine-cpu
```

### 3. 验证运行

```bash
# 检查容器状态
docker ps

# 运行健康检查
docker exec btc-collision-cpu python -m src.utils.health_check --gpu

# 查看性能指标
docker exec btc-collision-cpu cat data_logs/current_data.json
```

---

## GPU模式部署

### NVIDIA GPU

#### 1. 构建GPU镜像

```bash
# 构建NVIDIA GPU镜像
docker-compose --profile gpu --profile nvidia build
```

#### 2. 启动服务

```bash
# 启动GPU服务
docker-compose --profile gpu --profile nvidia up -d

# 查看GPU使用情况
docker exec btc-collision-gpu nvidia-smi

# 查看日志
docker-compose logs -f btc-engine-gpu-nvidia
```

#### 3. 验证GPU加速

```bash
# 检查GPU是否被识别
docker exec btc-collision-gpu python -c "
import pyopencl as cl
print('GPU设备:')
for platform in cl.get_platforms():
    for device in platform.get_devices():
        print(f'  - {device.name} ({device.vendor})')
"
```

### AMD GPU

#### 1. 构建AMD GPU镜像

```bash
# 构建AMD GPU镜像
docker-compose --profile gpu --profile amd build
```

#### 2. 启动服务

```bash
# 启动AMD GPU服务
docker-compose --profile gpu --profile amd up -d

# 查看日志
docker-compose logs -f btc-collision-gpu-amd
```

---

## 多GPU部署

### 配置多GPU

编辑 `config.production.json`:

```json
{
  "gpu": {
    "mode": "multi",
    "device_indices": [0, 1, 2],
    "load_balancing": "performance",
    "auto_tuning": true
  }
}
```

### 启动多GPU服务

```bash
# 启动多GPU服务
docker-compose --profile gpu --profile nvidia up -d

# 查看各GPU状态
docker exec btc-collision-gpu python -c "
from src.gpu import get_gpu_selector
selector = get_gpu_selector()
devices = selector.detect_all_devices()
for i, dev in enumerate(devices):
    print(f'GPU {i}: {dev[\"name\"]} - 显存: {dev[\"global_mem_gb\"]:.1f}GB')
"
```

---

## 监控配置

### 启用监控服务

```bash
# 启动监控栈（Grafana + Prometheus）
docker-compose --profile monitoring up -d

# 访问Grafana
# URL: http://localhost:3000
# 用户名: admin
# 密码: btc-monitor-2024

# 访问Prometheus
# URL: http://localhost:9090
```

### 自定义监控

```bash
# 编辑Grafana仪表板配置
nano deploy/grafana/dashboards/btc-engine.json

# 编辑Prometheus配置
nano deploy/prometheus/prometheus.yml
```

---

## 数据持久化

### 数据卷说明

```yaml
volumes:
  btc-data:      # 断点、历史数据
  btc-logs:      # 运行日志
  btc-monitor:   # 监控数据
```

### 备份数据

```bash
# 备份所有数据
docker-compose down
tar czf btc-data-backup-$(date +%Y%m%d).tar.gz data/ logs/ monitoring_data/

# 恢复数据
tar xzf btc-data-backup-20240101.tar.gz
docker-compose up -d
```

### 清理旧数据

```bash
# 清理30天前的数据
docker exec btc-collision-cpython -m src.utils.data_cleanup \
    --temp-days 14 \
    --data-days 30 \
    --log-days 30
```

---

## 日志管理

### 查看日志

```bash
# 实时日志
docker-compose logs -f btc-engine-cpu

# 最近100行
docker-compose logs --tail=100 btc-engine-cpu

# 带时间戳
docker-compose logs -t btc-engine-cpu
```

### 日志轮转

Docker Compose已配置日志轮转：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"    # 单个日志文件最大50MB
    max-file: "10"     # 保留10个文件
    compress: "true"   # 压缩旧日志
```

### 导出日志

```bash
# 导出所有日志
docker-compose logs btc-engine-cpu > btc-engine-$(date +%Y%m%d).log

# 导出错误日志
docker-compose logs btc-engine-cpu | grep ERROR > btc-engine-errors.log
```

---

## 性能调优

### CPU优化

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '8.0'      # 限制使用8核
      memory: 16G      # 限制使用16GB内存
```

### GPU优化

```json
{
  "gpu": {
    "batch_size": 131072,        // 增大批次大小
    "memory_usage_ratio": 0.8,   // 使用80%显存
    "enable_vendor_optimizations": true
  }
}
```

### 性能监控

```bash
# 实时监控性能
docker exec btc-collision-gpu watch -n 5 'cat /opt/btc-collision-engine/data_logs/current_data.json | jq ".performance"'

# 查看GPU利用率
docker exec btc-collision-gpu nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used --format=csv -l 5
```

---

## 故障排除

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs btc-engine-cpu

# 检查配置文件
docker exec btc-collision-cpu python -c "
import json
with open('config.production.json') as f:
    config = json.load(f)
    print('配置加载成功')
"

# 运行健康检查
docker exec btc-collision-cpu python -m src.utils.health_check
```

### GPU不可用

```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# 重新配置NVIDIA Container Toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 性能低下

```bash
# 检查当前配置
docker exec btc-collision-gpu cat config.production.json | jq '.gpu'

# 查看性能指标
docker exec btc-collision-gpu cat data_logs/current_data.json | jq '.performance'

# 运行基准测试
docker exec btc-collision-gpu python benchmarks/benchmark_optimizations.py
```

### 断点恢复

```bash
# 检查断点文件
docker exec btc-collision-cpu ls -lh data_logs/checkpoint.json

# 查看断点信息
docker exec btc-collision-cpython -c "
import json
with open('data_logs/checkpoint.json') as f:
    checkpoint = json.load(f)
    print(f\"已检测: {checkpoint.get('total_checked', 0):,} 个密钥\")
    print(f\"运行时间: {checkpoint.get('elapsed_time', 0):.2f} 秒\")
"

# 强制从断点恢复
docker-compose restart btc-engine-cpu
```

---

## 维护操作

### 更新镜像

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build --no-cache

# 重启服务
docker-compose down
docker-compose up -d
```

### 清理系统

```bash
# 清理未使用的镜像
docker image prune -a

# 清理未使用的卷
docker volume prune

# 清理所有未使用的资源
docker system prune -a --volumes
```

### 导出配置

```bash
# 导出当前配置
docker exec btc-collision-cpu cat config.production.json > backup-config.json

# 导出数据
docker exec btc-collision-cpython -c "
import json
with open('data_logs/history_data.json') as f:
    data = json.load(f)
    print(json.dumps(data, indent=2))
" > history-data.json
```

---

## 安全建议

### 文件权限

```bash
# 设置配置文件权限（仅所有者可读写）
chmod 600 config.production.json

# 设置数据目录权限
chmod 750 data/ logs/ monitoring_data/
```

### 网络安全

```bash
# 仅监听localhost
# 修改docker-compose.yml中的端口映射
ports:
  - "127.0.0.1:3000:3000"  # Grafana
  - "127.0.0.1:9090:9090"  # Prometheus
```

### 用户隔离

Docker容器默认以非root用户（btc-engine）运行，已配置安全加固：

```dockerfile
RUN groupadd -r btc-engine && useradd -r -g btc-engine
USER btc-engine
```

---

## 常见问题

### Q: 如何修改碰撞模式？

A: 编辑 `docker-compose.yml` 中的 `command` 部分：

```yaml
command: >
  python key_collision_cli.py
  --config /opt/btc-collision-engine/config.production.json
  --mode range  # 改为range或brute_force
  --start 1
  --end FFFFFFFF
```

### Q: 如何添加目标地址？

A: 创建 `targets.txt` 文件：

```bash
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt
echo "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" >> targets.txt
```

### Q: 如何备份断点数据？

A:

```bash
# 复制断点文件
docker cp btc-collision-cpu:/opt/btc-collision-engine/data_logs/checkpoint.json ./backup-checkpoint.json
```

### Q: 容器日志过大怎么办？

A:

```bash
# 清理容器日志
truncate -s 0 $(docker inspect --format='{{.LogPath}}' btc-collision-cpu)
```

---

## 相关资源

- [README.md](../README.md) - 项目主文档
- [config.example.json](../config.example.json) - 配置示例
- [deploy/systemd/](./systemd/) - systemd服务文件
- [健康检查](../src/utils/health_check.py) - 系统健康诊断

---

**文档版本**: 1.0  
**最后更新**: 2026-04-24
