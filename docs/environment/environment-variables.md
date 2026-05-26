# 环境变量配置

> **版本**: v4.5.1 | **最后更新**: 2026-05-22

## 概述

本项目支持通过环境变量进行运行时配置。将以下内容复制到 `.env` 文件中进行配置。

## 环境变量列表

### 通用配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BTC_ENGINE_LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `BTC_ENGINE_DATA_DIR` | `./data` | 数据存储目录 |
| `BTC_ENGINE_LOG_DIR` | `./logs` | 日志存储目录 |
| `BTC_ENGINE_MONITOR_DIR` | `./monitoring` | 监控数据目录 |
| `BTC_ENGINE_CONFIG_FILE` | `config.json` | 配置文件路径 |

### GPU 配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BTC_ENGINE_GPU_ENABLE` | `true` | 是否启用 GPU 加速 |
| `BTC_ENGINE_GPU_DEVICE_INDEX` | `0` | GPU 设备索引 |
| `BTC_ENGINE_GPU_BATCH_SIZE` | `1048576` | GPU 批处理大小 |
| `BTC_ENGINE_GPU_QUEUE_DEPTH` | `4` | 异步队列深度 |
| `NVIDIA_VISIBLE_DEVICES` | `all` | Docker NVIDIA 可见设备 |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | Docker NVIDIA 驱动能力 |

### 监控配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BTC_ENGINE_MONITOR_INTERVAL` | `5` | 监控采样间隔 (秒) |
| `BTC_ENGINE_MONITOR_ENABLED` | `true` | 是否启用监控 |

### 安全配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BTC_ENGINE_SECURE_MEMORY` | `true` | 是否启用安全内存管理 |
| `BTC_ENGINE_CRYPTO_BACKEND` | `auto` | 加密后端选择 (auto/coincurve/cryptography/ecdsa/pure) |

## 使用方法

### 方式一：直接导出环境变量

```bash
# Linux/macOS
export BTC_ENGINE_LOG_LEVEL=DEBUG

# Windows (PowerShell)
$env:BTC_ENGINE_LOG_LEVEL = "DEBUG"

# Windows (CMD)
set BTC_ENGINE_LOG_LEVEL=DEBUG

```

### 方式二：使用 .env 文件

复制 `.env.example` 为 `.env`，然后按需修改：

```bash
# Windows (CMD)
copy .env.example .env

# Linux/macOS
cp .env.example .env

```

## 注意事项

1. 环境变量优先级高于配置文件（`config.json`）

2. 修改环境变量后需要重新启动程序才能生效

3. 不要在 `.env` 文件中存储敏感信息（如私钥）

4. `.env` 文件不应提交到版本控制系统

## 相关文档

- [配置示例](../../config.example.json)

- [部署指南](../docker-deployment-guide.md)
