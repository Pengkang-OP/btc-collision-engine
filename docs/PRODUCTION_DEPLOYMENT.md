# 生产部署方案总结

本文档总结BTC碰撞引擎的完整生产部署方案，包括systemd服务和Docker容器化两种部署方式。

---

## 📦 已创建的文件

### 1. systemd服务部署

| 文件 | 说明 | 用途 |
|------|------|------|
| `deploy/systemd/btc-collision-engine.service` | systemd服务文件 | 定义服务配置、资源限制、安全加固 |
| `deploy/install-systemd.sh` | 自动化安装脚本 | 一键部署到Linux服务器 |
| `docs/SYSTEMD_DEPLOYMENT.md` | 部署文档 | 详细的安装、配置、管理指南 |

### 2. Docker容器化部署

| 文件 | 说明 | 用途 |
|------|------|------|
| `Dockerfile` | 主Dockerfile（CPU/NVIDIA GPU） | 多阶段构建，生产优化 |
| `Dockerfile.amd` | AMD GPU专用Dockerfile | AMD ROCm支持 |
| `docker-compose.yml` | Docker Compose配置 | 支持CPU、GPU、多GPU、监控栈 |
| `config.production.json` | 生产环境配置 | 优化的生产参数 |
| `.dockerignore` | Docker构建排除文件 | 减小镜像体积 |
| `docs/DOCKER_DEPLOYMENT.md` | 部署文档 | 详细的Docker使用指南 |

### 3. 监控配置

| 文件 | 说明 | 用途 |
|------|------|------|
| `deploy/prometheus/prometheus.yml` | Prometheus配置 | 指标收集和告警 |
| `deploy/prometheus/rules/btc-collision-alerts.yml` | 告警规则 | 异常检测和告警通知 |
| `deploy/grafana/datasources/datasource.yml` | Grafana数据源 | 可视化监控 |
| `deploy/grafana/dashboards/btc-collision-dashboard.json` | Grafana仪表盘 | 实时监控面板 |
| `deploy/docker-deploy.sh` | Docker部署脚本 | 一键启动Docker环境 |

### 4. 备份与维护

| 文件 | 说明 | 用途 |
|------|------|------|
| `scripts/backup_manager.py` | 备份管理器 | 创建、恢复、管理备份 |
| `scripts/schedule_backup.py` | 定时备份调度器 | 设置自动备份任务 |

---

## 🚀 快速部署

### 方式1：systemd服务（推荐用于专用服务器）

```bash
# 1. 克隆仓库
git clone https://github.com/your-repo/btc-collision-engine.git
cd btc-collision-engine

# 2. 运行安装脚本
sudo bash deploy/install-systemd.sh

# 3. 查看状态
systemctl status btc-collision-engine
journalctl -u btc-collision-engine -f
```

**优势：**

- ✅ 原生Linux服务管理
- ✅ 自动重启和开机自启
- ✅ 系统级资源控制
- ✅ 与系统集成度高
- ✅ 性能开销最小

**适用场景：**

- 专用服务器或VPS
- 长期运行的生产环境
- 需要精细资源控制
- 已有运维基础设施

---

### 方式2：Docker容器（推荐用于灵活部署）

```bash
# CPU模式
docker-compose --profile cpu up -d

# NVIDIA GPU模式
docker-compose --profile gpu --profile nvidia up -d

# AMD GPU模式
docker-compose --profile gpu --profile amd up -d

# 带监控
docker-compose --profile gpu --profile nvidia --profile monitoring up -d
```

**优势：**

- ✅ 环境隔离
- ✅ 快速部署和迁移
- ✅ 版本控制
- ✅ 易于扩展
- ✅ 一键监控栈

**适用场景：**

- 多环境部署（开发/测试/生产）
- 容器化基础设施
- 需要快速扩缩容
- 团队共享环境

---

## 📊 功能对比

| 特性 | systemd | Docker |
|------|---------|--------|
| **安装复杂度** | 中等（需手动配置） | 简单（一键启动） |
| **资源隔离** | 系统级（cgroups） | 容器级（namespace） |
| **性能开销** | 几乎无 | 2-5% |
| **环境一致性** | 依赖系统环境 | 完全一致 |
| **迁移难度** | 较高 | 极低 |
| **多版本共存** | 困难 | 简单 |
| **监控集成** | journal | Prometheus/Grafana |
| **自动重启** | ✅ | ✅ |
| **日志管理** | journalctl | docker logs |
| **GPU支持** | 需配置 | 内置支持 |

---

## ✅ 验收测试

### 生产验收测试状态

<<<<<<< Updated upstream
**测试版本**: v4.4.0
=======
**测试版本**: v4.2.1
>>>>>>> Stashed changes
**测试时间**: 2026-04-28
**测试结果**: ✅ PASSED (18/18, 100%)

### 测试覆盖

| 测试类别 | 测试数 | 通过 | 状态 |
|----------|--------|------|------|
| 关键功能测试 | 10 | 10 | ✅ |
| 扩展功能测试 | 8 | 8 | ✅ |
| **总计** | **18** | **18** | ✅ |

### 关键验证项

| 验证项 | 状态 | 说明 |
|--------|------|------|
| 核心加密功能 | ✅ | Bitcoin密钥生成和验证 |
| 配置管理系统 | ✅ | 配置读写和持久化 |
| 日志和安全 | ✅ | 安全日志过滤 |
| 检查点功能 | ✅ | 状态保存和恢复 |
| 碰撞引擎 | ✅ | 核心碰撞计算 |
| 安全功能 | ✅ | 密钥安全处理 |
| 真实碰撞运行 | ✅ | 315 keys / 3.17s |
| 性能压力测试 | ✅ | 1,387 keys / 10.5s |

### 运行验收测试

```bash
# 运行完整测试套件
python run_all_tests.py

# 或直接使用 pytest
pytest tests/ -v

# 查看测试报告
cat data_logs/acceptance_test/acceptance_test_summary.md
```

### 验收报告位置

- **JSON报告**: `data_logs/acceptance_test/acceptance_test_report.json`
- **Markdown摘要**: `data_logs/acceptance_test/acceptance_test_summary.md`
- **测试日志**: `data_logs/acceptance_test/acceptance_test.log`

---

## 🔧 配置说明

### 生产配置优化（config.production.json）

```json
{
  "collision": {
    "checkpoint_interval": 60,        // 断点保存间隔（秒）
    "dedup_max_size": 5000000         // 去重容量
  },
  "logging": {
    "max_bytes": 52428800,            // 50MB单文件
    "backup_count": 10,               // 保留10个备份
    "compress_backups": true          // 压缩备份
  },
  "gpu": {
    "memory_usage_ratio": 0.7,        // 使用70%显存
    "auto_tuning": true               // 自动调优
  },
  "monitoring": {
    "collection_interval": 10,        // 10秒采集一次
    "history_max_size": 5000          // 保留5000条历史
  }
}
```

---

## 📈 监控方案

### 1. 系统级监控（systemd）

```bash
# 查看服务状态
systemctl status btc-collision-engine

# 查看资源使用
systemd-cgtop

# 查看日志
journalctl -u btc-collision-engine -f

# 查看资源限制状态
systemctl show btc-collision-engine | grep Memory
```

### 2. 应用级监控

```bash
# 健康检查（基础）
python -m src.utils.health_check

# 健康检查（含GPU）
python -m src.utils.health_check --gpu

# 健康检查（含网络）
python -m src.utils.health_check --network

# 生成健康检查报告
python -m src.utils.health_check --gpu --report health_report.txt

# 查看当前性能
cat data_logs/current_data.json | jq '.performance'

# 查看统计数据
cat data_logs/current_data.json | jq '.stats'
```

### 3. 监控栈（Docker）

```bash
# 启动监控
docker-compose --profile monitoring up -d

# 访问Grafana
# URL: http://localhost:3000
# 用户名: admin
# 密码: changeme (可通过环境变量 GF_ADMIN_PASSWORD 设置)

# 访问Prometheus
# URL: http://localhost:9090

# 查看告警规则
cat deploy/prometheus/rules/btc-collision-alerts.yml
```

### 4. 告警规则

系统已配置以下告警规则：

| 告警名称 | 触发条件 | 严重级别 |
|----------|----------|----------|
| BTCEngineDown | 服务离线超过1分钟 | critical |
| BTCHighCPUUsage | CPU使用率>90%持续5分钟 | warning |
| BTCHighMemoryUsage | 内存使用率>90%持续5分钟 | warning |
| BTCLowDiskSpace | 磁盘空间<10% | critical |
| BTCThroughputDrop | 检测速率<1000 keys/s持续2分钟 | warning |
| BTCErrorRateHigh | 错误率>5%持续1分钟 | critical |
| BTCGPUMemoryHigh | GPU显存>80%持续3分钟 | warning |
| BTCGPUTemperatureHigh | GPU温度>85°C持续1分钟 | critical |

---

## 🔒 安全加固

### systemd安全选项

```ini
[Service]
NoNewPrivileges=true          # 禁止提权
ProtectSystem=strict          # 保护系统目录
ProtectHome=true              # 保护家目录
PrivateTmp=true               # 私有临时目录
ReadWritePaths=...            # 限定可写路径
```

### Docker安全选项

```dockerfile
# 非root用户
RUN useradd -r btc-engine
USER btc-engine

# 健康检查
HEALTHCHECK CMD python -m src.utils.health_check

# 资源限制
docker-compose.yml:
  deploy:
    resources:
      limits:
        memory: 16G
```

### 文件权限

```bash
# 配置文件（600）
chmod 600 config.production.json

# 数据目录（750）
chmod 750 data_logs/ logs/ monitoring_data/

# 应用文件（644/755）
chmod 644 *.py
chmod 755 src/
```

---

## 🎯 推荐部署方案

### 场景1：个人研究（单机）

**推荐：** systemd服务

```bash
# 简单部署
sudo bash deploy/install-systemd.sh

# 配置单GPU
nano /opt/btc-collision-engine/config.production.json
# 设置: "gpu": {"device_index": 0}

# 启动
sudo systemctl start btc-collision-engine
```

### 场景2：团队开发（多环境）

**推荐：** Docker Compose

```bash
# 开发环境
docker-compose --profile cpu up -d

# 测试环境
docker-compose --profile gpu up -d

# 生产环境
docker-compose -f docker-compose.prod.yml up -d
```

### 场景3：大规模生产（多节点）

**推荐：** Docker Swarm / Kubernetes

```bash
# Docker Swarm
docker swarm init
docker stack deploy -c docker-compose.yml btc-engine

# Kubernetes（需要额外配置）
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 场景4：云平台部署

**推荐：** Docker + 云服务

```bash
# AWS ECS
ecs-cli compose up

# Google Cloud Run
gcloud run deploy btc-engine --source .

# Azure Container Instances
az container create --resource-group myRG --name btc-engine --image btc-engine:latest
```

---

## 📝 运维手册

### 日常检查

```bash
# 1. 检查服务状态
systemctl status btc-collision-engine

# 2. 查看性能指标
cat data_logs/current_data.json | jq '.performance.speed'

# 3. 检查磁盘空间
df -h /opt/btc-collision-engine

# 4. 查看错误日志
journalctl -u btc-collision-engine -p err --since today

# 5. 运行健康检查
python -m src.utils.health_check --gpu
```

### 定期维护

```bash
# 每周：清理日志
sudo journalctl --vacuum-time=7d

# 每月：清理数据
python -m src.utils.data_cleanup --temp-days 14 --data-days 30

# 定期：备份数据
python scripts/backup_manager.py create --desc "定期备份"

# 查看备份列表
python scripts/backup_manager.py list

# 恢复备份
python scripts/backup_manager.py restore btc-collision-backup_20240101_120000.tar.gz
```

### 自动备份配置

```bash
# 安装定时备份任务
python scripts/schedule_backup.py install

# 查看当前定时任务
python scripts/schedule_backup.py show

# 移除定时备份任务
python scripts/schedule_backup.py remove
```

### 故障处理

```bash
# 1. 服务停止
sudo systemctl restart btc-collision-engine

# 2. 查看断点
cat data_logs/checkpoint.json | jq '.'

# 3. 重新加载配置
sudo systemctl reload btc-collision-engine

# 4. 查看完整日志
journalctl -u btc-collision-engine --since "1 hour ago"

# 5. 检查资源限制
systemctl show btc-collision-engine | grep -E '(Memory|CPU)'
```

### 资源限制配置

systemd服务已配置以下资源限制：

| 限制项 | 值 | 说明 |
|--------|-----|------|
| CPUQuota | 800% | CPU使用上限（8核） |
| MemoryMax | 16G | 最大内存 |
| MemoryHigh | 14G | 内存高压阈值 |
| MemorySwapMax | 2G | 最大交换内存 |
| LimitNOFILE | 65536 | 最大文件描述符 |
| LimitNPROC | 4096 | 最大进程数 |
| Nice | 10 | 进程优先级 |

---

## 📚 相关文档

- [README.md](../README.md) - 项目主文档
- [SYSTEMD_DEPLOYMENT.md](./SYSTEMD_DEPLOYMENT.md) - systemd详细指南
- [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) - Docker详细指南
- [CONFIG.md](./CONFIG.md) - 配置说明
- [health_check.py](../src/utils/health_check.py) - 健康检查工具

---

## ✅ 部署检查清单

### systemd部署

- [ ] 创建btc-engine用户
- [ ] 安装应用到`/opt/btc-collision-engine`
- [ ] 创建虚拟环境并安装依赖
- [ ] 配置生产参数（config.production.json）
- [ ] 安装systemd服务文件
- [ ] 设置文件权限
- [ ] 启用并启动服务
- [ ] 验证健康检查
- [ ] 配置日志轮转
- [ ] 设置监控告警

### Docker部署

- [ ] 安装Docker和Docker Compose
- [ ] 安装NVIDIA Container Toolkit（GPU模式）
- [ ] 准备生产配置
- [ ] 构建Docker镜像
- [ ] 启动服务
- [ ] 验证GPU识别（GPU模式）
- [ ] 配置数据卷
- [ ] 启动监控栈（可选）
- [ ] 验证健康检查
- [ ] 配置备份策略

---

## 🎓 最佳实践

1. **始终使用生产配置**：不要使用config.example.json直接运行
2. **定期备份数据**：至少每周备份一次断点和历史数据
3. **监控资源使用**：设置CPU和内存告警阈值
4. **日志管理**：配置日志轮转，避免磁盘耗尽
5. **安全加固**：最小权限原则，定期更新依赖
6. **性能调优**：根据硬件调整batch_size和workers
7. **健康检查**：定期检查服务状态和数据完整性
8. **文档更新**：记录所有配置变更和运维操作

---

## 📞 技术支持

- **问题反馈**：GitHub Issues
- **文档**：docs/目录
- **示例配置**：config.*.json
- **部署脚本**：deploy/目录

---

<<<<<<< Updated upstream
**文档版本**: v4.4.0
=======
**文档版本**: v4.2.2
>>>>>>> Stashed changes
**创建日期**: 2026-04-24
**更新日期**: 2026-05-18
