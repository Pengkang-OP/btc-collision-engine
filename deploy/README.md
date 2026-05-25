# 生产部署文件清单

## 📁 文件结构

```
btc-collision-engine/
├── # ===== Docker容器化部署 =====
├── Dockerfile                              # 主Dockerfile（CPU/NVIDIA GPU）
├── Dockerfile.amd                          # AMD GPU专用Dockerfile
├── docker-compose.yml                      # Docker Compose配置
├── .dockerignore                           # Docker构建排除文件
├── config.production.json                  # 生产环境配置
│
├── # ===== systemd服务部署 =====
├── deploy/
│   ├── systemd/
│   │   └── btc-collision-engine.service   # systemd服务文件
│   ├── install-systemd.sh                 # systemd自动化安装脚本
│   ├── docker-deploy.sh                   # Docker自动化部署脚本
│   └── QUICK_START.md                     # 快速部署指南
│
├── # ===== 监控配置 =====
├── deploy/
│   ├── prometheus/
│   │   └── prometheus.yml                 # Prometheus配置
│   └── grafana/
│       └── datasources/
│           └── datasource.yml             # Grafana数据源配置
│
└── # ===== 部署文档 =====
    └── docs/
        ├── PRODUCTION_DEPLOYMENT.md        # 生产部署方案总结
        ├── SYSTEMD_DEPLOYMENT.md           # systemd详细部署指南
        └── DOCKER_DEPLOYMENT.md            # Docker详细部署指南
```

---

## 📦 文件说明

### Docker相关文件（11个文件）

| 文件 | 行数 | 说明 |
|------|------|------|
| `Dockerfile` | 117 | 多阶段构建，生产优化，支持CPU和NVIDIA GPU |
| `Dockerfile.amd` | 90 | AMD GPU专用，集成ROCm OpenCL运行时 |
| `docker-compose.yml` | 290 | 完整编排配置，支持CPU/GPU/多GPU/监控栈 |
| `.dockerignore` | 48 | 构建优化，排除不必要的文件 |
| `config.production.json` | 78 | 生产参数优化，日志轮转配置 |
| `deploy/prometheus/prometheus.yml` | 46 | Prometheus抓取和告警配置 |
| `deploy/grafana/datasources/datasource.yml` | 15 | Grafana数据源自动配置 |
| `deploy/docker-deploy.sh` | 270 | 一键部署脚本，支持多种模式 |
| `docs/DOCKER_DEPLOYMENT.md` | 521 | 完整Docker部署文档 |
| `docs/PRODUCTION_DEPLOYMENT.md` | 417 | 生产部署方案对比和总结 |
| `deploy/QUICK_START.md` | 348 | 30秒快速启动指南 |

**总计：约 2,240 行配置和文档**

### systemd相关文件（4个文件）

| 文件 | 行数 | 说明 |
|------|------|------|
| `deploy/systemd/btc-collision-engine.service` | 97 | 完整服务配置，包含安全加固 |
| `deploy/install-systemd.sh` | 148 | 自动化安装脚本 |
| `docs/SYSTEMD_DEPLOYMENT.md` | 613 | 完整systemd部署文档 |
| `deploy/QUICK_START.md` | 348 | （与Docker共享） |

**总计：约 1,206 行配置和文档**

---

## ✨ 核心特性

### 1. systemd服务特性

- ✅ 自动重启和开机自启
- ✅ 系统级资源控制（CPU、内存、I/O）
- ✅ 安全加固（NoNewPrivileges、ProtectSystem）
- ✅ 日志集成（journal）
- ✅ 健康检查（Watchdog）
- ✅ 非root用户运行
- ✅ 私有临时目录

### 2. Docker容器特性

- ✅ 多阶段构建（减小镜像体积）
- ✅ 非root用户运行
- ✅ 健康检查
- ✅ 数据卷持久化
- ✅ 日志轮转
- ✅ 资源限制
- ✅ 多厂商GPU支持（NVIDIA/AMD/Intel）
- ✅ 多GPU负载均衡
- ✅ 监控栈集成（Prometheus + Grafana）
- ✅ Profile管理（按需启动服务）

### 3. 监控能力

- ✅ 系统级监控（systemd journal）
- ✅ 应用级监控（health_check）
- ✅ 指标收集（Prometheus）
- ✅ 可视化（Grafana）
- ✅ 告警配置（Alertmanager）
- ✅ 性能追踪（slow operations）

### 4. 安全特性

- ✅ 非特权用户运行
- ✅ 文件系统保护
- ✅ 网络隔离（可选）
- ✅ 资源限制
- ✅ 配置文件权限（600）
- ✅ 数据目录权限（750）

---

## 🚀 使用方式

### systemd部署（3步）

```bash
# 1. 运行安装脚本
sudo bash deploy/install-systemd.sh

# 2. 编辑配置（可选）
nano /opt/btc-collision-engine/config.production.json

# 3. 查看状态
systemctl status btc-collision-engine
```

### Docker部署（2步）

```bash
# 1. 启动服务
docker-compose --profile gpu --profile nvidia up -d

# 2. 查看日志
docker-compose logs -f
```

---

## 📊 部署方案对比

| 特性 | systemd | Docker |
|------|---------|--------|
| **安装时间** | 5-10分钟 | 2-5分钟 |
| **配置复杂度** | 中等 | 简单 |
| **性能开销** | ~0% | ~2-5% |
| **环境隔离** | 部分 | 完全 |
| **迁移难度** | 较高 | 极低 |
| **多版本共存** | 困难 | 简单 |
| **监控集成** | journal | Prometheus/Grafana |
| **适用场景** | 专用服务器 | 灵活部署/团队开发 |

---

## 🎯 推荐场景

### 选择systemd，如果

- ✅ 使用专用Linux服务器
- ✅ 需要最大性能（无容器开销）
- ✅ 已有运维基础设施
- ✅ 长期稳定运行
- ✅ 需要精细资源控制

### 选择Docker，如果

- ✅ 需要快速部署和迁移
- ✅ 多环境部署（开发/测试/生产）
- ✅ 团队共享环境
- ✅ 需要环境一致性
- ✅ 容器化基础设施

---

## 📝 配置示例

### 单GPU配置（config.production.json）

```json
{
  "gpu": {
    "use_gpu": true,
    "device_index": 0,
    "batch_size": 65536,
    "memory_usage_ratio": 0.7
  },
  "collision": {
    "max_workers": null,
    "checkpoint_interval": 60
  }
}
```

### 多GPU配置

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

---

## 🔍 验证部署

### 健康检查

```bash
# systemd
/opt/btc-collision-engine/venv/bin/python -m src.utils.health_check --gpu

# Docker
docker exec btc-collision-gpu python -m src.utils.health_check --gpu
```

### 性能测试

```bash
# 查看当前性能
cat data_logs/current_data.json | jq '.performance'

# 运行基准测试
python benchmarks/benchmark_optimizations.py
```

---

## 🛠 维护操作

### 日常检查

```bash
# systemd
systemctl status btc-collision-engine
journalctl -u btc-collision-engine -f

# Docker
docker-compose ps
docker-compose logs -f
```

### 数据备份

```bash
# 备份数据
tar czf /backup/btc-engine-$(date +%Y%m%d).tar.gz \
    data_logs/ logs/ monitoring_data/ config.production.json
```

### 清理数据

```bash
# 清理过期数据
python -m src.utils.data_cleanup --temp-days 14 --data-days 30
```

---

## 📚 文档索引

### 快速入门

- [快速部署指南](deploy/QUICK_START.md) - 30秒启动
- [生产部署总结](docs/PRODUCTION_DEPLOYMENT.md) - 方案对比

### 详细文档

- [systemd部署指南](docs/SYSTEMD_DEPLOYMENT.md) - 完整安装和管理
- [Docker部署指南](docs/DOCKER_DEPLOYMENT.md) - 容器化部署

### 配置参考

- [配置说明](docs/CONFIG.md) - 所有配置项详解
- [config.production.json](config.production.json) - 生产配置示例

### 项目文档

- [README](README.md) - 项目介绍
- [CHANGELOG](CHANGELOG.md) - 版本历史

---

## ✅ 部署检查清单

### 部署前

- [ ] 检查系统要求（Python 3.9+、内存、磁盘）
- [ ] 安装依赖（Docker或systemd）
- [ ] 准备GPU驱动（如使用GPU）
- [ ] 克隆仓库

### 部署中

- [ ] 运行安装脚本或docker-compose
- [ ] 配置生产参数
- [ ] 添加目标地址
- [ ] 设置文件权限

### 部署后

- [ ] 运行健康检查
- [ ] 验证GPU识别（如使用）
- [ ] 查看性能指标
- [ ] 配置监控告警
- [ ] 设置备份策略

---

## 📞 技术支持

- **GitHub Issues**: 报告问题和功能请求
- **文档**: docs/目录
- **示例**: config.*.json
- **脚本**: deploy/目录

---

## 🎓 最佳实践

1. **始终使用config.production.json**，不要使用config.example.json
2. **定期备份数据**，至少每周一次
3. **监控资源使用**，设置告警阈值
4. **配置日志轮转**，避免磁盘耗尽
5. **使用非root用户**，遵循最小权限原则
6. **定期更新依赖**，保持安全性
7. **记录运维操作**，便于问题追踪
8. **测试配置变更**，先在测试环境验证

---

**文件清单版本**: 5.0.0  
**创建日期**: 2026-04-24  
**文件总数**: 15个  
**代码行数**: 约3,446行  

---

## 🎉 总结

已创建完整的生产部署方案，包括：

- ✅ **systemd服务**：适合专用服务器，性能最优
- ✅ **Docker容器**：适合灵活部署，环境一致
- ✅ **监控栈**：Prometheus + Grafana，可视化监控
- ✅ **自动化脚本**：一键部署，简化运维
- ✅ **完整文档**：详细指南，快速上手

**项目现已满足生产运行条件！** 🚀
