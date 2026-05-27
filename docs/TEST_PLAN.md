# BTC Collision Engine 完整测试计划

> 版本: v5.0.0 | 更新: 2026-05-27

## 1. 测试概述

### 1.1 测试目标

- 验证软件功能符合需求规格说明书

- 确保代码质量和稳定性

- 达到预期的覆盖率指标

- 构建完整的测试闭环流程

### 1.2 测试范围

#### 白盒测试范围

- **核心加密模块** (`src/core/`)：密钥生成、地址转换、secp256k1

- **碰撞引擎** (`src/collision/`)：主引擎逻辑、GPU引擎、目标管理

- **配置管理** (`src/config/`)：配置加载、验证、热重载

- **监控系统** (`src/monitoring/`)：性能监控、告警系统

- **工具模块** (`src/utils/`)：通用工具函数

#### 黑盒测试范围

- CLI 功能验证

- GPU 加速功能

- 多格式地址支持

- 断点续传

- 安全特性

### 1.3 覆盖率目标

| 模块 | 目标语句覆盖率 | 目标分支覆盖率 | 优先级 |
|------|--------------|--------------|--------|
| `src/core/` | ≥90% | ≥85% | P0 |
| `src/collision/` | ≥85% | ≥80% | P0 |
| `src/cli/` | ≥80% | ≥75% | P1 |
| `src/config/` | ≥80% | ≥75% | P1 |
| `src/utils/` | ≥80% | ≥75% | P1 |
| `src/monitoring/` | ≥75% | ≥70% | P2 |
| `src/gpu/` | ≥75% | ≥70% | P1 |

---

## 2. 白盒测试策略

### 2.1 测试方法

- 使用 pytest 框架进行单元测试

- 配合 pytest-cov 进行覆盖率分析

- 使用 Mock 隔离外部依赖

- 参数化测试覆盖边界条件

### 2.2 关键测试点

- 代码逻辑分支覆盖

- 边界条件验证

- 异常路径处理

- 数据结构验证

### 2.3 多模式路径覆盖

#### 2.3.1 碰撞模式切换

| 模式 | 组合参数 | 路径数 | 测试方法 |
|------|---------|--------|---------|
| `random` + 默认配置 | 无额外参数 | 1 | 基本路径 |
| `random` + checkpoint | `--checkpoint` | 2 | 断点读写路径 |
| `random` + dedup | `--dedup` | 2 | 去重过滤器路径 |
| `random` + checkpoint + dedup | `--checkpoint --dedup` | 4 | 组合路径 |
| `range` + start/end | `--start 1 --end FFFF` | 2 | 范围边界 |
| `range` + start > end | `--start F --end 1` | 1 | 异常路径 |
| `range` + start < 1 | `--start 0 --end F` | 1 | 下限边界 |
| `range` + total_range > 2^64 | `--start 1 --end 2^65` | 1 | 大范围警告 |
| `brute_force` + start | `--start 1` | 1 | 基本路径 |
| `brute_force` + 无 start | 无 `--start` | 1 | 缺失参数 |

#### 2.3.2 GPU 引擎状态机覆盖

```

状态转移图:
  IDLE → INITIALIZING → RUNNING → STOPPING → IDLE
  IDLE → INITIALIZING → ERROR → IDLE
  RUNNING → PAUSED → RUNNING
  RUNNING → ERROR → IDLE

```

| 状态转移 | 触发条件 | 验证点 |
|---------|---------|--------|
| IDLE → INITIALIZING | `engine.__init__()` | 资源分配正确 |
| INITIALIZING → RUNNING | `engine.start()` | 线程启动 |
| RUNNING → STOPPING | `engine.stop()` | 线程停止、资源释放 |
| RUNNING → IDLE | Context manager `__exit__` | 自动 cleanup |
| 任意 → ERROR | GPU 驱动异常 | 优雅降级到 CPU |
| 并发 IDLE → RUNNING | 两次 `start()` | 幂等保护 |
| 并发 RUNNING → STOPPING | 两次 `stop()` | 幂等保护 |

#### 2.3.3 GPU 设备选择模式

| 模式 | device_index | 预期行为 |
|------|-------------|---------|
| 自动选择 | `-1` | 评分最高设备 |
| 指定 NVIDIA | `0` | NVIDIA GTX 1660 Ti |
| 指定 Intel | `1` | Intel Arc A770 |
| 无效索引 | `99` | 降级/错误提示 |
| 单 GPU 环境 | `-1` | 唯一设备 |

---

## 3. 黑盒测试策略

### 3.1 测试用例设计方法

- 等价类划分

- 边界值分析

- 错误推测法

- 状态转换测试

- 组合测试

### 3.2 多参数组合测试

#### 3.2.1 CLI 参数配对矩阵

```

主要参数: -t(目标), -f(文件), -m(模式), --start, --end, --duration, --workers, --checkpoint, --dedup, -g(GPU)
有效组合数: 3(目标来源) × 3(碰撞模式) × 2(checkpoint开关) × 2(dedup开关) × 2(GPU/CPU) = 72
核心场景: 12 组（覆盖 80% 用户场景）

```

| 场景 | 参数组合 | 优先级 |
|------|---------|--------|
| 最简随机 | `-t <addr> -m random` | P0 |
| 随机+持久化 | `-t <addr> -m random --checkpoint --dedup` | P0 |
| 范围扫描 | `-t <addr> -m range --start 1 --end 1000` | P0 |
| 限时运行 | `-t <addr> -m random --duration 60` | P0 |
| GPU 加速 | `-t <addr> -m random -g` | P0 |
| 文件输入 | `-f targets.txt -m random` | P1 |
| 多附件 | `-f addr.txt -m random --checkpoint --dedup -g` | P1 |
| 详细输出 | `-t <addr> -m random -v` | P1 |
| 安静模式 | `-t <addr> -m random -q` | P1 |
| 自定义线程 | `-t <addr> -m random --workers 8` | P1 |
| 大范围 | `-t <addr> -m range --start 1 --end FFFFFFFF` | P2 |
| 敏感模式 | `-t <addr> -m random --sensitive-mode full` | P2 |

#### 3.2.2 等价类划分

**batch_size 参数:**

| 类 | 值 | 预期 |
|----|-----|------|
| 有效 | 1024 ~ 4,194,304 | 引擎接受 |
| 下限无效 | 0 ~ 1023 | 拒绝/降级 |
| 上限无效 | >4,194,304 | 警告/降级 |
| 非数字 | `abc` | argparse 拒绝 |
| 负值 | -1 | 拒绝 |

**duration 参数:**

| 类 | 值 | 预期 |
|----|-----|------|
| 无限 | 0 | 持续运行直到 Ctrl+C |
| 有效 | 1 ~ 604,800 | 到时自动停止 |
| 无效 | -1 | 拒绝 |
| 超长 | >604,800 | 警告但允许 |

**workers 参数:**

| 类 | 值 | 预期 |
|----|-----|------|
| 有效 | 1 ~ CPU×2 | 引擎接受 |
| 无效 | 0, -1 | 拒绝 |
| 默认 | None/cpu_count | 自动设置 |

#### 3.2.3 边界值分析表

| 参数 | 边界 | 测试值 |
|------|------|--------|
| `--workers` | [1, ∞) | 0, 1, 2, CPU_count, CPU_count×2 |
| `--window-size` | [4, 8] | 3, 4, 5, 7, 8, 9 |
| `--checkpoint-interval` | [5, 3600] | 4, 5, 1800, 3600, 3601 |
| `--dedup-max-size` | [1000, ∞) | 0, 999, 1000, 10_000, 100_000 |
| `--batch-size` | [1024, 4M] | 0, 1023, 1024, 1M, 4M, 4M+1 |
| `--duration` | [0, 7天] | -1, 0, 1, 3600, 604800, 604801 |
| `--gpu-device` | [-1, N-1] | -2, -1, 0, N-1, N |
| start 私钥 | [1, N-1] | 0, 1, 2, N-2, N-1, N |
| end 私钥 | [start, N-1] | start-1, start, start+1 |

#### 3.2.4 组合爆炸控制

```

参数: A(mode) × B(duration) × C(checkpoint) × D(dedup) × E(gpu)
组合数: 3 × 5 × 2 × 2 × 2 = 120
控制策略: Pairwise 缩减 → 24 组核心组合

```

### 3.3 多状态测试

#### 3.3.1 CLI 状态转换

```

START → CONFIG_LOAD → TARGET_LOAD → ENGINE_INIT → RUNNING → STOP → REPORT
START → CONFIG_LOAD → [失败] → ERROR_EXIT
START → TARGET_LOAD → [空目标] → EXIT
RUNNING → [Ctrl+C] → STOP → REPORT
RUNNING → [超时] → STOP → REPORT
RUNNING → [GPU错误] → CPU_FALLBACK → RUNNING

```

| 状态 | 验证点 | 异常处理 |
|------|--------|---------|
| config.json 不存在 | 警告+默认配置 | 不中断启动 |
| config.json 格式错误 | 错误提示 | 退出/重试 |
| 目标文件不存在 | 错误提示 | 退出 |
| 目标文件空 | 错误提示 | 退出 |
| GPU 初始化失败 | 自动降级 CPU | 继续运行 |
| 引擎运行中 Ctrl+C | 优雅停止 | 显示最终统计 |
| duration 到期 | 自动停止 | 显示最终统计 |
| 引擎 start 异常 | 错误信息 | 退出 |

#### 3.3.2 断点状态转换

```

NO_CHECKPOINT → [第一次运行] → CHECKPOINT_CREATED
CHECKPOINT_CREATED → [继续运行] → CHECKPOINT_UPDATED
CHECKPOINT_CREATED → [重启] → RESUMED_FROM_CHECKPOINT
CHECKPOINT_CREATED → [文件损坏] → CRC_MISMATCH → WARNING + FRESH_START
CHECKPOINT_CREATED → [版本不匹配] → VERSION_MISMATCH → WARNING + FRESH_START

```

### 3.4 多格式地址测试

#### 3.4.1 地址格式覆盖矩阵

| 格式 | 前缀 | 长度 | 有效样本 | 无效样本 |
|------|------|------|---------|---------|
| P2PKH | `1` | 25-34 | `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` | 含非法 Base58 字符 |
| P2SH | `3` | 25-34 | `3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy` | 以 `1` 开头的 3 系列 |
| Bech32 | `bc1q` | 42/62 | `bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4` | 含 `1`/`b`/`i`/`o` 字符 |
| Taproot | `bc1p` | 62 | `bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8qt2acpp2yx7tq9pfj3` | Bech32 变体错误 |
| WIF 压缩 | `K/L` | 52 | `L5EZftfULZ5cFHMLUHKCbScne29MZtEeZa4tP6gPqT3iSoC8BKFq` | 校验和错误 |
| WIF 非压缩 | `5` | 51 | `5HueCGU8rMjxEX6JmN6KGVPGJCQk3cYPM9KQgMX7R7B8MkNLc7` | 前缀错误 |

#### 3.4.2 格式感知匹配测试

| 测试 | 目标格式 | 生成地址 | 预期匹配 |
|------|---------|---------|---------|
| 格式隔离 P2PKH → P2PKH | P2PKH | P2PKH | ✅ |
| 格式隔离 P2PKH → Bech32 | P2PKH | Bech32 | ❌ |
| 格式隔离 Bech32 → P2PKH | Bech32 | P2PKH | ❌ |
| 全格式检查 | P2PKH+P2SH+Bech32+Taproot | 4 种格式 | ✅ 仅对应格式 |
| 大写地址 | `BC1Q...` | Bech32 | ✅ 大小写不敏感 |
| 混合目标集 | 2 P2PKH + 1 Bech32 | P2PKH | ✅ 只匹配 P2PKH |

### 3.5 多 GPU 配置测试

#### 3.5.1 设备拓扑测试矩阵

| 拓扑 | NVIDIA | Intel Arc | AMD | CPU | 预期选择 |
|------|--------|-----------|-----|-----|---------|
| 单 NVIDIA | 1 | 0 | 0 | 0 | NVIDIA |
| 单 Intel | 0 | 1 | 0 | 0 | Intel |
| NVIDIA + Intel | 1 | 1 | 0 | 0 | Intel(评分更高) |
| NVIDIA + Intel + CPU | 1 | 1 | 0 | 1 | Intel(过滤CPU) |
| 无 GPU | 0 | 0 | 0 | 1 | 降级 CPU |
| 多 NVIDIA | 2 | 0 | 0 | 0 | 评分最高 |

---

## 4. 测试执行计划

### 4.1 执行顺序

1. 冒烟测试

2. 单元测试（白盒）

3. 功能测试（黑盒）

4. 集成测试

5. E2E 测试

6. 性能测试

7. 安全测试

### 4.2 分层执行

| 层 | 命令 | 频率 | 耗时 |
|----|------|------|------|
| L1 冒烟 | `pytest tests/ -m "smoke" -x --timeout=60` | 每次提交 | <1m |
| L2 单元 | `pytest tests/ -m "unit" --cov=src` | 每日 | <5m |
| L3 集成 | `pytest tests/ -m "integration" --timeout=300` | 每日 | <5m |
| L4 GPU | `pytest tests/ -m "gpu" --timeout=600` | 发布前 | <10m |
| L5 E2E | `pytest tests/ -m "e2e" --timeout=600` | 发布前 | <10m |

### 4.3 缺陷管理

- 缺陷分类：P0（阻断）、P1（高）、P2（中）、P3（低）

- 缺陷生命周期：发现 → 记录 → 修复 → 回归测试 → 关闭

### 4.4 pytest markers

```python

# pytest.ini 中注册

markers = {
    "unit": "Unit tests (no external deps)",
    "integration": "Module integration tests",
    "e2e": "End-to-end user scenario",
    "gpu": "GPU-related tests",
    "gpu_hardware": "Tests requiring real GPU hardware",
    "security": "Security-related tests",
    "performance": "Performance benchmark tests",
    "smoke": "Quick smoke tests for CI",
    "multi_gpu": "Multi-GPU topology tests",
    "multi_format": "Multi-format address tests",
    "state_machine": "State machine transition tests",
    "combinatorial": "Combinatorial parameter tests",
}

```

---

## 5. 测试报告

### 5.1 报告内容

- 测试执行摘要

- 覆盖率分析

- 缺陷统计

- 风险评估

- 改进建议

### 5.2 测试覆盖率追踪

| 模块 | 当前覆盖率 | 目标 | 差距 | 行动项 |
|------|-----------|------|------|--------|
| `src/core/` | - | 90% | - | 补充新测试 |
| `src/collision/` | - | 85% | - | 补充新测试 |
| `src/cli/` | - | 80% | - | 补充新测试 |
| `src/utils/` | - | 80% | - | 补充新测试 |
| `src/gpu/` | - | 75% | - | 补充新测试 |
| `src/monitoring/` | - | 75% | - | 补充新测试 |

---

*文档版本：v2.0 | 创建日期：2026-05-19 | 更新日期：2026-05-21*
