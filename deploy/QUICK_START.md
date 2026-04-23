# BTC碰撞引擎 - 快速部署指南

## 🚀 30秒快速启动

### systemd方式（Linux服务器）

```bash
# 一键安装
sudo bash deploy/install-systemd.sh

# 查看状态
systemctl status btc-collision-engine
```

### Docker方式（任意平台）

```bash
# CPU模式
docker-compose --profile cpu up -d

# GPU模式（NVIDIA）
docker-compose --profile gpu --profile nvidia up -d
```

---

## 📋 部署前准备

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2核 | 8核+ |
| 内存 | 4GB | 16GB+ |
| 磁盘 | 20GB | 100GB+ SSD |
| Python | 3.9+ | 3.11 |
| GPU（可选） | OpenCL 1.2 | NVIDIA RTX 3060+ |

### 依赖安装

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv git curl

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

---

## 🔧 配置步骤

### 1. 创建生产配置

```bash
cp config.example.json config.production.json
nano config.production.json
```

### 2. 关键配置项

```json
{
  "collision": {
    "max_workers": 8,              // CPU核心数
    "checkpoint_interval": 60      // 断点保存间隔（秒）
  },
  "gpu": {
    "use_gpu": true,               // 启用GPU
    "batch_size": 65536,           // 批次大小
    "memory_usage_ratio": 0.7      // 显存使用比例
  },
  "logging": {
    "level": "INFO",               // 日志级别
    "max_bytes": 52428800,         // 50MB
    "backup_count": 10             // 保留10个
  }
}
```

### 3. 添加目标地址

```bash
# 单个目标
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > targets.txt

# 多个目标
cat >> targets.txt << EOF
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2
12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX
EOF
```

---

## 📊 运行模式

### CPU模式

```bash
# systemd
ExecStart=... --mode random --workers 8

# Docker
docker-compose --profile cpu up -d
```

**性能：** ~5,000-10,000 keys/s（8核）

### GPU模式

```bash
# systemd（需配置NVIDIA环境变量）
Environment="NVIDIA_VISIBLE_DEVICES=all"

# Docker
docker-compose --profile gpu --profile nvidia up -d
```

**性能：** ~200,000-500,000 keys/s（RTX 3080）

### 多GPU模式

```json
{
  "gpu": {
    "mode": "multi",
    "device_indices": [0, 1, 2],
    "load_balancing": "performance"
  }
}
```

**性能：** ~1,000,000+ keys/s（3x RTX 3080）

---

## 🔍 监控和日志

### 查看状态

```bash
# systemd
systemctl status btc-collision-engine

# Docker
docker-compose ps
docker-compose logs -f
```

### 查看性能

```bash
# 实时性能
watch -n 5 'cat data_logs/current_data.json | jq ".performance"'

# 健康检查
python -m src.utils.health_check --gpu
```

### 查看日志

```bash
# systemd
journalctl -u btc-collision-engine -f

# Docker
docker-compose logs -f btc-engine-gpu
```

---

## 🛠 常用命令

### systemd管理

```bash
# 启动/停止/重启
sudo systemctl start|stop|restart btc-collision-engine

# 查看状态
sudo systemctl status btc-collision-engine

# 查看日志
sudo journalctl -u btc-collision-engine -f

# 重新加载配置
sudo systemctl reload btc-collision-engine
```

### Docker管理

```bash
# 启动/停止
docker-compose up -d
docker-compose down

# 重启
docker-compose restart

# 查看日志
docker-compose logs -f

# 进入容器
docker exec -it btc-collision-gpu bash
```

---

## 📈 性能优化

### CPU优化

```json
{
  "collision": {
    "max_workers": 16,              // 增加工作线程
    "use_performance_optimization": true
  }
}
```

### GPU优化

```json
{
  "gpu": {
    "batch_size": 131072,           // 增大批次
    "memory_usage_ratio": 0.8,      // 使用更多显存
    "auto_tuning": true             // 自动调优
  }
}
```

### 安装性能库

```bash
# gmpy2（大整数运算 +1455%）
pip install gmpy2>=2.1.5

# coincurve（标量乘法 +46%）
pip install coincurve>=13.0.0

# pycryptodome（SIMD哈希）
pip install pycryptodome>=3.19.0
```

---

## 🔒 安全建议

### 文件权限

```bash
# 配置文件
chmod 600 config.production.json

# 数据目录
chmod 750 data_logs/ logs/ monitoring_data/
```

### 系统加固

```bash
# 创建专用用户
sudo useradd -r -m btc-engine

# 限制资源
sudo systemctl edit btc-collision-engine
# 添加: MemoryMax=16G, CPUQuota=800%
```

---

## 🐛 故障排除

### 服务无法启动

```bash
# 查看详细错误
sudo journalctl -u btc-collision-engine -n 50

# 检查配置
python -c "import json; json.load(open('config.production.json'))"

# 手动测试
python key_collision_cli.py --help
```

### GPU不可用

```bash
# 检查驱动
nvidia-smi

# 检查OpenCL
python -c "import pyopencl; print(pyopencl.get_platforms())"

# 重新安装
pip install pyopencl
```

### 性能低下

```bash
# 检查配置
cat config.production.json | jq '.gpu'

# 运行基准测试
python benchmarks/benchmark_optimizations.py

# 查看GPU状态
nvidia-smi --query-gpu=utilization.gpu --format=csv -l 5
```

---

## 📚 完整文档

- [生产部署总结](./PRODUCTION_DEPLOYMENT.md)
- [systemd部署指南](./SYSTEMD_DEPLOYMENT.md)
- [Docker部署指南](./DOCKER_DEPLOYMENT.md)
- [配置说明](./CONFIG.md)
- [README](../README.md)

---

## 💡 快速参考

| 任务 | 命令 |
|------|------|
| 安装服务 | `sudo bash deploy/install-systemd.sh` |
| 启动服务 | `sudo systemctl start btc-collision-engine` |
| 查看日志 | `journalctl -u btc-collision-engine -f` |
| Docker启动 | `docker-compose --profile gpu up -d` |
| 健康检查 | `python -m src.utils.health_check --gpu` |
| 查看性能 | `cat data_logs/current_data.json \| jq '.performance'` |
| 清理数据 | `python -m src.utils.data_cleanup` |
| 备份数据 | `tar czf backup.tar.gz data_logs/` |

---

**快速指南版本**: 1.0  
**最后更新**: 2026-04-24
