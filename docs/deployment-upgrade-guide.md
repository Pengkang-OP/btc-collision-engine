# BTC碰撞引擎部署与升级指南

**版本**: v2.2.0  
**更新日期**: 2026-04-21

---

## 📋 目录

1. [系统要求](#1-系统要求)
2. [快速安装](#2-快速安装)
3. [从v2.1.0升级到v2.2.0](#3-从v210升级到v220)
4. [配置优化](#4-配置优化)
5. [性能验证](#5-性能验证)
6. [生产环境部署](#6-生产环境部署)
7. [故障恢复](#7-故障恢复)

---

## 1. 系统要求

### 1.1 最低要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10+ / Linux / macOS |
| Python | 3.8+ |
| CPU | 4核心+ |
| 内存 | 8GB RAM |
| 磁盘 | 2GB可用空间 |

### 1.2 GPU要求 (可选但推荐)

**Intel Arc**:

- 驱动版本: 31.0.101.4972+
- 显存: 8GB+ (推荐16GB)
- OpenCL: 3.0+

**NVIDIA**:

- 驱动版本: 520.00+
- CUDA: 12.0+
- 显存: 8GB+ (推荐12GB+)

**AMD**:

- 驱动版本: 22.40+
- ROCm: 5.0+ (Linux) / OpenCL: 2.0+ (Windows)
- 显存: 8GB+ (推荐12GB+)

### 1.3 推荐配置

```
CPU: AMD Ryzen 7 5700X / Intel i7-12700K
GPU: Intel Arc A770 16GB / RTX 4070 / RX 7800 XT
内存: 32GB DDR4
磁盘: NVMe SSD 500GB+
网络: 100Mbps+ (用于地址导入)
```

---

## 2. 快速安装

### 2.1 Windows安装

```powershell
# 1. 下载项目
git clone https://github.com/your-org/btc-collision-engine.git
cd btc-collision-engine

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 验证安装
python -m pytest tests/ -v --tb=short

# 5. 运行测试
python key_collision_cli.py --test
```

### 2.2 Linux安装

```bash
# 1. 下载项目
git clone https://github.com/your-org/btc-collision-engine.git
cd btc-collision-engine

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装GPU驱动 (Intel Arc示例)
sudo apt update
sudo apt install intel-opencl-icd

# 5. 验证安装
python -m pytest tests/ -v --tb=short

# 6. 运行测试
python key_collision_cli.py --test
```

### 2.3 验证GPU可用性

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine

# 检查GPU是否可用
if GPUCollisionEngine.is_gpu_available():
    print("✅ GPU可用")
else:
    print("❌ GPU不可用,将使用CPU模式")
```

---

## 3. 从v2.1.0升级到v2.2.0

### 3.1 升级步骤

```powershell
# 1. 备份当前配置
cp config.json config.json.bak
cp config.example.json config.example.json.bak

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 运行测试验证
python -m pytest tests/ -v --tb=short

# 5. 对比配置文件
diff config.json config.example.json
```

### 3.2 新功能说明

**v2.2.0新增功能**:

1. **GPU性能监控增强**
   - 实时监控吞吐量、错误率、显存使用
   - 自动性能报告生成
   - 性能趋势分析

2. **Intel Arc深度优化**
   - uint32 workaround (避免hang bug)
   - 自适应超时管理
   - 显存监控与保护

3. **集成测试框架**
   - 7项GPU集成测试
   - 自动化性能验证
   - 基准对比(v2.1.0 vs v2.2.0)

### 3.3 性能提升

| 指标 | v2.1.0基准 | v2.2.0当前 | 提升 |
|------|--------|--------|------|
| 平均吞吐量 | ~150k keys/s | ~200k keys/s | +33% |
| 峰值吞吐量 | ~180k keys/s | ~240k keys/s | +33% |
| 执行时间 | ~65ms | ~45ms | -31% |
| 显存估算 | ~70%准确 | ~95%准确 | +36% |

---

## 4. 配置优化

### 4.1 基础配置

```json
{
    "engine": {
        "mode": "random",
        "batch_size": 262144,
        "max_threads": 8,
        "checkpoint_interval": 300
    },
    "gpu": {
        "use_gpu": true,
        "device_index": 0,
        "gpu_memory_pool": true,
        "max_buffers": 100,
        "max_memory_mb": 512
    },
    "monitoring": {
        "enable_performance_monitor": true,
        "report_interval": 60,
        "log_level": "INFO"
    }
}
```

### 4.2 根据GPU型号优化

**Intel Arc A770**:

```json
{
    "gpu": {
        "use_gpu": true,
        "batch_size": 262144,
        "gpu_memory_pool": true,
        "max_buffers": 100,
        "max_memory_mb": 512
    }
}
```

**NVIDIA RTX 4090**:

```json
{
    "gpu": {
        "use_gpu": true,
        "batch_size": 524288,
        "gpu_memory_pool": true,
        "max_buffers": 200,
        "max_memory_mb": 1024
    }
}
```

**小显存GPU (8GB)**:

```json
{
    "gpu": {
        "use_gpu": true,
        "batch_size": 65536,
        "gpu_memory_pool": true,
        "max_buffers": 50,
        "max_memory_mb": 256
    }
}
```

### 4.3 配置文件验证

```python
from src.config.config_manager import ConfigManager

config = ConfigManager("config.json")
errors = config.validate()

if errors:
    print("配置错误:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✅ 配置验证通过")
```

---

## 5. 性能验证

### 5.1 运行集成测试

```powershell
# 运行GPU集成测试
python tests/test_gpu_integration_validation.py

# 预期输出:
# 总测试数: 7
# 通过: 5+
# 通过率: 71.4%+
```

### 5.2 性能基准测试

```python
from src.collision.gpu_collision_engine import GPUCollisionEngine
import time

# 创建引擎
engine = GPUCollisionEngine(
    targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
    batch_size=262144,
    use_gpu_memory_pool=True
)

# 运行10秒
import threading
def run():
    engine.start()

thread = threading.Thread(target=run, daemon=True)
thread.start()
time.sleep(10)
engine.stop()

# 获取性能报告
monitor = engine.gpu_performance_monitor
report = monitor.get_performance_report()

print(f"吞吐量: {report.avg_throughput_keys_per_sec:,.0f} keys/s")
print(f"错误率: {report.error_rate_percent:.2f}%")
print(f"显存使用: {report.memory_usage_avg_mb:.2f} MB")
```

### 5.3 性能达标检查

| 检查项 | 达标标准 | 验证方法 |
|--------|---------|---------|
| 吞吐量 | >150k keys/s | `report.avg_throughput_keys_per_sec > 150000` |
| 错误率 | 0.00% | `report.error_rate_percent == 0.0` |
| 显存使用 | <85% | `report.memory_usage_avg_mb < 显存总量*0.85` |
| 执行时间 | <50ms | `report.avg_execution_time_ms < 50` |

---

## 6. 生产环境部署

### 6.1 系统服务部署 (Linux)

```bash
# 创建服务文件
sudo nano /etc/systemd/system/btc-collision.service

# 添加以下内容:
[Unit]
Description=BTC Collision Engine
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/btc-collision-engine
ExecStart=/path/to/venv/bin/python key_collision_cli.py --config config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# 启用并启动服务
sudo systemctl enable btc-collision
sudo systemctl start btc-collision

# 查看状态
sudo systemctl status btc-collision

# 查看日志
sudo journalctl -u btc-collision -f
```

### 6.2 Docker部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "key_collision_cli.py", "--config", "config.json"]
```

```bash
# 构建镜像
docker build -t btc-collision-engine:latest .

# 运行容器
docker run -d \
  --name btc-collision \
  --gpus all \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/logs:/app/logs \
  btc-collision-engine:latest

# 查看日志
docker logs -f btc-collision
```

### 6.3 监控与告警

**性能监控脚本**:

```python
#!/usr/bin/env python3
"""性能监控脚本 - 每小时检查一次"""

from src.collision.gpu_collision_engine import GPUCollisionEngine
import requests

def check_performance():
    # 获取当前性能
    # ... (省略)
    
    # 检查是否达标
    if throughput < 150000:
        # 发送告警
        requests.post("https://your-webhook.com/alert", json={
            "message": f"性能下降: {throughput} keys/s",
            "severity": "warning"
        })

if __name__ == "__main__":
    check_performance()
```

**Cron定时任务**:

```bash
# 每小时检查一次
0 * * * * /path/to/monitor.py >> /var/log/btc-collision-monitor.log 2>&1
```

---

## 7. 故障恢复

### 7.1 常见问题

**问题1: GPU不可用**

```bash
# 检查GPU驱动
nvidia-smi  # NVIDIA
intel_gpu_top  # Intel
rocm-smi  # AMD

# 重新安装驱动
# ... (根据GPU厂商)
```

**问题2: 性能下降**

```python
# 检查配置
from src.config.config_manager import ConfigManager
config = ConfigManager("config.json")
print(config.get_all())

# 重置为默认配置
config.reset_to_defaults()
config.save()
```

**问题3: 内存泄漏**

```bash
# 监控显存使用
watch -n 1 'nvidia-smi'  # NVIDIA

# 重启服务
sudo systemctl restart btc-collision
```

### 7.2 断点恢复

```python
from src.collision.checkpoint_manager import CheckpointManager

# 自动恢复
checkpoint = CheckpointManager("checkpoint.json")
if checkpoint.exists():
    print("发现断点,正在恢复...")
    checkpoint.restore()
else:
    print("无断点,从头开始")
```

### 7.3 日志分析

```bash
# 查看错误日志
tail -f logs/collision.log | grep ERROR

# 查看性能日志
tail -f logs/collision.log | grep "性能报告"

# 统计错误率
grep -c "ERROR" logs/collision.log
```

---

## 📚 相关文档

- [性能调优最佳实践](performance-tuning-best-practices.md)
- [Intel Arc兼容性指南](intel-arc-integration-guide.md)
- [故障排查指南](troubleshooting.md)
- [贡献指南](CONTRIBUTING.md)

---

**文档版本**: v1.0  
**最后更新**: 2026-04-21  
**维护者**: BTC碰撞引擎团队
