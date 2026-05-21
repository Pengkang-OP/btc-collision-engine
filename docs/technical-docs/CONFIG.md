# 配置参考文档

本文件说明 `config.json` 中所有配置项的类型、默认值、有效范围及用途。

> 首次使用请将 `config.example.json` 复制为 `config.json` 并按需修改：
>
> ```bash
> # Windows
> copy config.example.json config.json
> # Linux / macOS
> cp config.example.json config.json
> ```

---

## `crypto` — 加密后端配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `backend` | string | `"auto"` | `auto` / `pure_python` / `pure_python_const_time` / `openssl` / `coincurve` / `ecdsa` | 加密后端选择。`auto` 按性能自动选取最优后端（推荐） |
| `constant_time` | bool | `false` | `true` / `false` | 优先使用恒定时间算法（防御侧信道攻击），开启后性能略降 |
| `verify_checksums` | bool | `true` | `true` / `false` | 验证所有 Base58Check 校验和 |
| `strict_wif_validation` | bool | `true` | `true` / `false` | 严格 WIF 格式验证 |

---

## `collision` — 碰撞引擎配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `max_workers` | int / null | `null` | `1` ~ `1024` | 工作线程数。`null` 表示自动使用 CPU 核心数。超过 1024 会被拒绝 |
| `progress_interval` | int | `1000` | `>= 1` | 进度回调触发间隔（检测次数），越小刷新越频繁但开销越大 |
| `checkpoint_interval` | int | `30` | `>= 1` | 断点自动保存间隔（秒） |
| `dedup_max_size` | int | `1000000` | `>= 1` | Bloom 过滤器最大容量（仅 `random` 模式有效）。**注意**：Bloom 过滤器存在约 0.1% 的误报率（即极少数未检测过的私钥被误判为重复），这是概率型数据结构的固有特性，不影响碰撞准确性。`random` 模式下重复的概率本身极低，启用去重主要是防止极端巧合的重复计算。内存占用约为 `max_size × 1.44 bit`，100 万条约 180 KB。**不适用场景**：range/brute_force 模式（顺序遍历不会重复，无需去重） |
| `use_performance_optimization` | bool | `true` | `true` / `false` | 是否启用 v2.2.0 性能优化套件 |
| `precomputed_window_size` | int | `8` | `4` ~ `8` | 椭圆曲线预计算表窗口大小。越大越快，内存占用越多（window=8 约 50KB） |
| `use_simd_hash` | bool | `true` | `true` / `false` | 启用 SIMD 哈希优化（需安装 `pycryptodome`） |
| `use_memory_pool` | bool | `true` | `true` / `false` | 启用 ECPoint 内存池，减少 GC 压力 |
| `use_gpu_memory_pool` | bool | `true` | `true` / `false` | 启用 GPU 缓冲区内存池（需安装 `pyopencl`） |
| `gpu_pool_max_buffers` | int | `100` | `>= 1` | GPU 内存池最大缓冲区数量 |
| `gpu_pool_max_memory_mb` | int | `512` | `>= 1` | GPU 内存池最大占用内存（MB） |

---

## `gpu` — GPU 加速配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `use_gpu` | bool | `true` | `true` / `false` | 是否启用 GPU 加速。GPU 不可用时自动降级为 CPU |
| `device_index` | int | `0` | `>= 0` | GPU 设备索引，多卡时使用 |
| `batch_size` | int | `65536` | `1` ~ `16777216` (16M) | GPU 每批次处理的密钥数量。超过 16M 会被拒绝（防止显存耗尽） |
| `auto_detect` | bool | `true` | `true` / `false` | 自动检测并选择最优 GPU 设备 |
| `memory_usage_ratio` | float | `0.7` | `(0, 1]` | GPU 显存使用率上限（Intel Arc 建议 0.45） |
| `enable_vendor_optimizations` | bool | `true` | `true` / `false` | 启用厂商特定优化（Intel/NVIDIA/AMD 差异化配置） |

---

## `logging` — 日志配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `level` | string | `"INFO"` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 日志输出级别 |
| `format` | string | 见示例 | 任意字符串 | Python logging 格式字符串 |
| `file` | string | `"logs/collision.log"` | 任意路径 | 日志文件路径（目录不存在会自动创建） |
| `max_bytes` | int | `10485760` | `>= 1` | 单个日志文件最大字节数（默认 10MB） |
| `backup_count` | int | `5` | `>= 0` | 轮转保留的备份文件数量 |
| `enable_console` | bool | `true` | `true` / `false` | 是否输出到控制台 |
| `enable_file` | bool | `true` | `true` / `false` | 是否写入日志文件 |
| `rotation_type` | string | `"size"` | `size` / `time` | 日志轮转类型：按文件大小或按时间 |
| `rotation_when` | string | `"midnight"` | `S/M/H/D/midnight/W0-W6` | 时间轮转触发时机（仅 `rotation_type=time` 有效） |
| `rotation_interval` | int | `1` | `>= 1` | 时间轮转间隔（天） |
| `compress_backups` | bool | `false` | `true` / `false` | 是否压缩归档旧日志文件 |

---

## `performance_monitoring` — 性能监控配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `enabled` | bool | `true` | `true` / `false` | 是否启用性能监控系统 |
| `track_slow_operations` | bool | `true` | `true` / `false` | 记录慢操作（超过阈值的调用） |
| `slow_threshold_ms` | float | `100` | `>= 0` | 慢操作阈值（毫秒） |
| `max_records` | int | `1000` | `>= 1` | 性能记录最大保存条数 |
| `log_level` | string | `"DEBUG"` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 性能日志输出级别 |

---

## 配置优先级

配置加载顺序（后者覆盖前者）：

```
内置默认值  →  config.json  →  环境变量（如有）  →  命令行参数（--workers 等）
```

## 常见配置场景

### 高性能 CPU 模式（无 GPU）

```json
{
  "collision": { "max_workers": 16, "use_performance_optimization": true },
  "gpu": { "use_gpu": false }
}
```

### Intel Arc GPU 稳定模式

```json
{
  "gpu": {
    "use_gpu": true,
    "batch_size": 262144,
    "memory_usage_ratio": 0.45,
    "enable_vendor_optimizations": true
  }
}
```

### 调试模式

```json
{
  "logging": { "level": "DEBUG", "enable_console": true },
  "collision": { "max_workers": 1 }
}
```
