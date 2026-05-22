# systemd服务部署指南

**版本**: v4.5.1



本文档提供BTC碰撞引擎的systemd服务部署详细说明。

## 📋 目录

- [快速开始](#快速开始)
- [自动化安装](#自动化安装)
- [手动安装](#手动安装)
- [服务管理](#服务管理)
- [日志管理](#日志管理)
- [性能调优](#性能调优)
- [故障排除](#故障排除)
- [安全加固](#安全加固)

---

## 快速开始

### 前置要求

- Linux系统（Ubuntu 20.04+, Debian 11+, CentOS 8+）
- Python 3.9+
- systemd 239+
- root或sudo权限

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/btc-collision-engine.git
cd btc-collision-engine

# 运行安装脚本
sudo bash deploy/install-systemd.sh
```

---

## 自动化安装

### 安装步骤

安装脚本会自动完成以下操作：

1. ✅ 创建`btc-engine`用户和组
2. ✅ 创建目录结构（`/opt/btc-collision-engine`）
3. ✅ 复制应用文件（排除开发和测试文件）
4. ✅ 创建Python虚拟环境
5. ✅ 安装依赖包
6. ✅ 安装systemd服务文件
7. ✅ 配置生产环境
8. ✅ 启用并启动服务

### 安装后验证

```bash
# 检查服务状态
systemctl status btc-collision-engine

# 查看服务日志
journalctl -u btc-collision-engine -f

# 运行健康检查
/opt/btc-collision-engine/venv/bin/python -m src.utils.health_check
```

---

## 手动安装

### 1. 创建用户和目录

```bash
# 创建系统用户
sudo useradd -r -m -d /opt/btc-collision-engine -s /bin/bash btc-engine

# 创建目录结构
sudo mkdir -p /opt/btc-collision-engine/{logs,data_logs,monitoring_data}
sudo chown -R btc-engine:btc-engine /opt/btc-collision-engine
sudo chmod 750 /opt/btc-collision-engine/{logs,data_logs,monitoring_data}
```

### 2. 部署应用

```bash
# 复制文件
sudo rsync -avz --exclude='venv' --exclude='.git' \
    ./ /opt/btc-collision-engine/

# 设置权限
sudo chown -R btc-engine:btc-engine /opt/btc-collision-engine
```

### 3. 创建虚拟环境

```bash
# 切换到btc-engine用户
sudo su - btc-engine

cd /opt/btc-collision-engine

# 创建虚拟环境
python3 -m venv venv

# 安装依赖
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements-base.txt

# 退出
exit
```

### 4. 安装systemd服务

```bash
# 复制服务文件
sudo cp deploy/systemd/btc-collision-engine.service /etc/systemd/system/

# 重新加载systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable btc-collision-engine
```

### 5. 配置生产环境

```bash
# 创建生产配置
sudo cp /opt/btc-collision-engine/config.example.json \
    /opt/btc-collision-engine/config.production.json

# 设置权限
sudo chown btc-engine:btc-engine /opt/btc-collision-engine/config.production.json
sudo chmod 600 /opt/btc-collision-engine/config.production.json

# 编辑配置
sudo nano /opt/btc-collision-engine/config.production.json
```

### 6. 启动服务

```bash
# 启动服务
sudo systemctl start btc-collision-engine

# 检查状态
sudo systemctl status btc-collision-engine

# 查看日志
sudo journalctl -u btc-collision-engine -f
```

---

## 服务管理

### 基本命令

```bash
# 启动服务
sudo systemctl start btc-collision-engine

# 停止服务
sudo systemctl stop btc-collision-engine

# 重启服务
sudo systemctl restart btc-collision-engine

# 重新加载配置（不重启）
sudo systemctl reload btc-collision-engine

# 查看状态
sudo systemctl status btc-collision-engine

# 启用开机自启
sudo systemctl enable btc-collision-engine

# 禁用开机自启
sudo systemctl disable btc-collision-engine
```

### 查看日志

```bash
# 实时日志
sudo journalctl -u btc-collision-engine -f

# 最近100行
sudo journalctl -u btc-collision-engine -n 100

# 带时间戳
sudo journalctl -u btc-collision-engine -t

# 特定时间范围
sudo journalctl -u btc-collision-engine --since "2024-01-01 00:00:00" --until "2024-01-02 00:00:00"

# 错误日志
sudo journalctl -u btc-collision-engine -p err
```

### 性能监控

```bash
# 查看CPU使用率
systemd-cgtop

# 查看内存使用
sudo systemctl show btc-collision-engine -p MemoryCurrent

# 查看进程树
systemd-cgls
```

---

## 日志管理

### 日志轮转配置

创建 `/etc/logrotate.d/btc-collision-engine`:

```bash
/var/log/journal/*/system.journal {
    monthly
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root systemd-journal
}
```

### 导出日志

```bash
# 导出所有日志
sudo journalctl -u btc-collision-engine > btc-engine-$(date +%Y%m%d).log

# 导出JSON格式
sudo journalctl -u btc-collision-engine -o json > btc-engine.json

# 导出错误日志
sudo journalctl -u btc-collision-engine -p err > btc-engine-errors.log
```

### 清理日志

```bash
# 清理7天前的日志
sudo journalctl --vacuum-time=7d

# 限制日志大小为1GB
sudo journalctl --vacuum-size=1G
```

---

## 性能调优

### 资源限制

编辑服务文件 `/etc/systemd/system/btc-collision-engine.service`:

```ini
[Service]
# CPU限制（8核）
CPUQuota=800%

# 内存限制（16GB）
MemoryMax=16G
MemoryHigh=14G

# 文件描述符
LimitNOFILE=65536
LimitNPROC=4096

# 进程优先级
Nice=10
```

重新加载配置：

```bash
sudo systemctl daemon-reload
sudo systemctl restart btc-collision-engine
```

### GPU支持

如果使用GPU，需要添加NVIDIA支持：

```ini
[Service]
# NVIDIA GPU环境变量
Environment="NVIDIA_VISIBLE_DEVICES=all"
Environment="NVIDIA_DRIVER_CAPABILITIES=compute,utility"

# 如果需要nvidia-persistenced服务
After=network.target nvidia-persistenced.service
Wants=nvidia-persistenced.service
```

### I/O优化

```ini
[Service]
# 限制磁盘I/O
IOWeight=500
IODeviceWeight=/dev/sda 500

# 限制读写速率
IOReadBandwidthMax=/dev/sda 100M
IOWriteBandwidthMax=/dev/sda 50M
```

---

## 故障排除

### 服务无法启动

```bash
# 查看详细错误
sudo journalctl -u btc-collision-engine -n 50 --no-pager

# 检查配置文件语法
sudo -u btc-engine /opt/btc-collision-engine/venv/bin/python -c \
    "import json; json.load(open('/opt/btc-collision-engine/config.production.json'))"

# 检查目录权限
ls -la /opt/btc-collision-engine/

# 手动运行测试
sudo -u btc-engine /opt/btc-collision-engine/venv/bin/python \
    /opt/btc-collision-engine/key_collision_cli.py --help
```

### 性能低下

```bash
# 检查资源限制
sudo systemctl show btc-collision-engine | grep -E 'CPUQuota|MemoryMax'

# 查看实际使用率
sudo systemd-cgtop

# 检查GPU状态
nvidia-smi

# 查看碰撞引擎状态
cat /opt/btc-collision-engine/data_logs/current_data.json | jq '.performance'
```

### 内存泄漏

```bash
# 监控内存使用
watch -n 5 'systemctl show btc-collision-engine -p MemoryCurrent'

# 如果发现内存持续增长，重启服务
sudo systemctl restart btc-collision-engine

# 设置内存限制（自动重启）
# 在服务文件中添加:
# MemoryMax=16G
```

### 断点恢复

```bash
# 检查断点文件
ls -lh /opt/btc-collision-engine/data_logs/checkpoint.json

# 查看断点信息
sudo -u btc-engine /opt/btc-collision-engine/venv/bin/python -c "
import json
with open('/opt/btc-collision-engine/data_logs/checkpoint.json') as f:
    cp = json.load(f)
    print(f\"已检测: {cp.get('total_checked', 0):,} 个密钥\")
    print(f\"运行时间: {cp.get('elapsed_time', 0):.2f} 秒\")
"

# 重启服务自动恢复
sudo systemctl restart btc-collision-engine
```

---

## 安全加固

### 文件权限

```bash
# 配置文件（仅所有者可读写）
sudo chmod 600 /opt/btc-collision-engine/config.production.json

# 数据目录（所有者可读写执行）
sudo chmod 750 /opt/btc-collision-engine/{data_logs,logs,monitoring_data}

# 应用文件（只读）
sudo chmod 644 /opt/btc-collision-engine/*.py
sudo chmod 755 /opt/btc-collision-engine/src/
```

### systemd安全选项

服务文件已包含以下安全加固：

```ini
[Service]
# 禁止获取新权限
NoNewPrivileges=true

# 保护系统目录
ProtectSystem=strict

# 保护家目录
ProtectHome=true

# 可写路径（仅限数据目录）
ReadWritePaths=/opt/btc-collision-engine/logs \
               /opt/btc-collision-engine/data_logs \
               /opt/btc-collision-engine/monitoring_data

# 私有临时目录
PrivateTmp=true
```

### 网络隔离

如果不需要网络访问，可以添加：

```ini
[Service]
# 禁止网络访问
PrivateNetwork=true

# 或者限制网络访问
IPAddressAllow=localhost
IPAddressDeny=any
```

---

## 备份和恢复

### 备份数据

```bash
# 创建备份
sudo tar czf /backup/btc-engine-$(date +%Y%m%d).tar.gz \
    /opt/btc-collision-engine/data_logs/ \
    /opt/btc-collision-engine/logs/ \
    /opt/btc-collision-engine/monitoring_data/ \
    /opt/btc-collision-engine/config.production.json

# 设置备份权限
sudo chmod 600 /backup/btc-engine-*.tar.gz
```

### 恢复数据

```bash
# 停止服务
sudo systemctl stop btc-collision-engine

# 恢复数据
sudo tar xzf /backup/btc-engine-20240101.tar.gz -C /

# 设置权限
sudo chown -R btc-engine:btc-engine /opt/btc-collision-engine

# 启动服务
sudo systemctl start btc-collision-engine
```

---

## 监控告警

### 创建systemd路径监控

创建 `/etc/systemd/system/btc-collision-monitor.path`:

```ini
[Unit]
Description=Monitor BTC Collision Engine Data

[Path]
PathModified=/opt/btc-collision-engine/data_logs/current_data.json

[Install]
WantedBy=multi-user.target
```

创建对应的服务 `/etc/systemd/system/btc-collision-monitor.service`:

```ini
[Unit]
Description=Check BTC Collision Engine Status

[Service]
Type=oneshot
ExecStart=/opt/btc-collision-engine/venv/bin/python -m src.utils.health_check --quiet
User=btc-engine
```

启用监控：

```bash
sudo systemctl enable --now btc-collision-monitor.path
```

---

## 常见问题

### Q: 如何修改碰撞模式？

A: 编辑服务文件中的 `ExecStart`:

```bash
sudo systemctl edit btc-collision-engine
```

修改为：

```ini
[Service]
ExecStart=
ExecStart=/opt/btc-collision-engine/venv/bin/python key_collision_cli.py \
    --config /opt/btc-collision-engine/config.production.json \
    --mode range \
    --start 1 \
    --end FFFFFFFF
```

### Q: 如何添加目标地址？

A:

```bash
# 创建目标文件
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" | sudo tee -a /opt/btc-collision-engine/targets.txt

# 设置权限
sudo chown btc-engine:btc-engine /opt/btc-collision-engine/targets.txt
sudo chmod 640 /opt/btc-collision-engine/targets.txt

# 修改服务文件使用文件模式
sudo systemctl edit btc-collision-engine
# 添加: --file /opt/btc-collision-engine/targets.txt
```

### Q: 如何升级应用？

A:

```bash
# 停止服务
sudo systemctl stop btc-collision-engine

# 备份当前版本
sudo cp -r /opt/btc-collision-engine /opt/btc-collision-engine.backup

# 更新代码
cd /opt/btc-collision-engine
sudo -u btc-engine git pull

# 更新依赖
sudo -u btc-engine ./venv/bin/pip install -r requirements-base.txt

# 重启服务
sudo systemctl start btc-collision-engine

# 验证运行
sudo systemctl status btc-collision-engine
```

### Q: 服务频繁重启怎么办？

A: 检查服务文件中的重启限制：

```ini
[Service]
# 5分钟内最多重启5次
StartLimitIntervalSec=300
StartLimitBurst=5
```

查看重启记录：

```bash
sudo journalctl -u btc-collision-engine | grep "Scheduled restart"
```

---

## 相关资源

- [README.md](../README.md) - 项目主文档
- [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) - Docker部署指南
- [config.example.json](../config.example.json) - 配置示例
- [健康检查](../src/utils/health_check.py) - 系统健康诊断

---

**文档版本**: 1.0  
**最后更新**: 2026-04-24
