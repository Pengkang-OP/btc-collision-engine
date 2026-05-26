# 配置参考文档

**版本**: v5.2.1


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
| `use_performance_optimization` | bool | `true` | `true` / `false` | 是否启用 v4.2.1 性能优化套件 |
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
| `device_index` | int | `-1` | `>= -1` | GPU 设备索引。`-1` 表示自动选择最佳设备 |
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

## `monitoring` — 监控系统配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `enabled` | bool | `true` | `true` / `false` | 是否启用监控系统 |
| `collection_interval` | int | `5` | `>= 1` | 数据采集间隔（秒） |
| `storage_dir` | string | `"monitoring_data"` | 任意路径 | 监控数据存储目录 |
| `history_max_size` | int | `1000` | `>= 1` | 历史数据最大条数 |
| `error_max_size` | int | `500` | `>= 1` | 错误日志最大条数 |
| `auto_cleanup.enabled` | bool | `true` | `true` / `false` | 是否启用自动清理 |
| `auto_cleanup.max_age_days` | int | `30` | `>= 1` | 数据最大保存天数 |

---

## `gpu` — GPU 高级配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `use_new_module` | bool | `true` | `true` / `false` | 是否使用新的 GPU 模块 |
| `auto_detect` | bool | `true` | `true` / `false` | 自动检测 GPU 设备 |
| `memory_usage_ratio` | float | `0.70` | `(0, 1]` | 显存使用比例（Intel Arc 建议 0.70） |
| `enable_vendor_optimizations` | bool | `true` | `true` / `false` | 启用厂商特定优化 |
| `gpu_memory_pool` | bool | `true` | `true` / `false` | 启用 GPU 内存池 |
| `max_buffers` | int | `100` | `>= 1` | GPU 内存池最大缓冲区数量 |
| `max_memory_mb` | int | `512` | `>= 1` | GPU 内存池最大内存（MB） |
| `async_execution` | bool | `true` | `true` / `false` | 启用 GPU 异步执行（双缓冲优化） |
| `queue_depth` | int | `4` | `1` ~ `64` | GPU 命令队列深度 |
| `timeout_protection` | bool | `true` | `true` / `false` | 启用 GPU 超时保护机制 |
| `base_timeout_seconds` | int | `60` | `>= 1` | GPU 内核执行基础超时（秒） |
| `mode` | string | `"auto"` | `auto` / `single` / `multi` | GPU 模式 |
| `device_indices` | array | `[-1]` | 整数数组（元素 >= -1） | GPU 设备索引列表，`-1` 表示自动选择 |
| `load_balancing` | string | `"performance"` | `performance` / `equal` | 负载均衡策略 |
| `auto_tuning` | bool | `true` | `true` / `false` | 自动根据设备型号调优参数 |
| `seed_prefetch_size` | int | `64` | `1` ~ `4096` | 种子预生成缓存深度。Intel Arc 等需要大预取的场景可设为 256~1024 |
| `driver_check.enabled` | bool | `true` | `true` / `false` | 是否启用 GPU 驱动检查 |
| `driver_check.require_minimum_version` | bool | `true` | `true` / `false` | 是否要求最低驱动版本 |
| `driver_check.warn_on_unstable` | bool | `true` | `true` / `false` | 不稳定驱动是否发出警告 |
| `driver_check.auto_fallback_conservative` | bool | `true` | `true` / `false` | 不稳定驱动是否自动降级为保守模式 |
| `per_device_config` | object | `{}` | 任意 JSON 对象 | 每设备独立配置（允许附加属性） |
| `key_generation_strategy` | string | `"PRNG_SEED"` | `PRNG_SEED` / `SEQUENTIAL_UINT32` / `PRNG_STREAM` | 私钥生成策略 |

---

## `optimization` — GPU 优化参数

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `uint32_workaround` | bool | `true` | `true` / `false` | Intel Arc 必须启用（避免 global char* hang bug） |
| `disable_async_transfer` | bool | `false` | `true` / `false` | 禁用异步传输（Intel Arc 建议 `false`） |
| `conservative_memory_policy` | bool | `false` | `true` / `false` | 保守内存策略 |
| `adaptive_timeout` | bool | `true` | `true` / `false` | 自适应超时（根据历史执行时间动态调整） |

---

## `performance_monitoring` — 性能监控配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `enabled` | bool | `true` | `true` / `false` | 是否启用性能监控系统 |
| `track_slow_operations` | bool | `true` | `true` / `false` | 记录慢操作（超过阈值的调用） |
| `slow_threshold_ms` | float | `30000` | `>= 0` | 慢操作阈值（毫秒），GPU编译通常需10-30秒 |
| `max_records` | int | `10000` | `>= 1` | 性能记录最大保存条数 |
| `log_level` | string | `"INFO"` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 性能日志输出级别 |

---

## `i18n` — 国际化配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `language` | string | `"auto"` | `auto` / `zh_CN` / `en_US` | 界面语言。`auto` 自动检测系统语言 |
| `fallback_language` | string | `"en_US"` | `zh_CN` / `en_US` | 回退语言（当指定语言翻译不存在时使用） |

---

## `security` — 安全配置

| 配置项 | 类型 | 默认值 | 有效值 / 范围 | 说明 |
|--------|------|--------|--------------|------|
| `enable_deduplication` | bool | `true` | `true` / `false` | 是否启用去重功能 |
| `enable_checkpoint` | bool | `true` | `true` / `false` | 是否启用断点保存功能 |
| `checkpoint_encryption` | bool | `true` | `true` / `false` | 是否加密断点文件（保护目标地址列表） |
| `enable_audit_log` | bool | `true` | `true` / `false` | 是否启用审计日志 |

---

## 配置优先级

配置加载顺序（后者覆盖前者）：

```text
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

### 生产环境模式

```json
{
  "logging": {
    "level": "INFO",
    "enable_console": true,
    "enable_file": true,
    "compress_backups": true
  },
  "collision": {
    "max_workers": null,
    "checkpoint_interval": 60
  },
  "security": {
    "enable_deduplication": true,
    "enable_checkpoint": true,
    "checkpoint_encryption": true,
    "enable_audit_log": true
  }
}
```

### 多 GPU 并行模式

```json
{
  "gpu": {
    "mode": "multi",
    "device_indices": [-1],
    "load_balancing": "performance",
    "auto_tuning": true
  }
}
```
