# ⚡ GPU配置最佳实践

> **版本**: v3.3.1 | **最后更新**: 2026-04-28  
> **相关文档**: [GPU引擎指南](gpu-engine-guide.md) | [CLI快速参考](CLI_QUICK_REFERENCE.md) | [配置说明](CONFIG.md)

---

## 📋 目录

1. [GPU配置快速指南](#gpu配置快速指南)
2. [批次大小调优](#批次大小调优)
3. [配置模板对比](#配置模板对比)
4. [--sensitive-mode 使用指南](#--sensitive-mode-使用指南)
5. [性能优化参数](#性能优化参数)
6. [常见问题](#常见问题)

---

## 🧭 GPU配置快速指南

使用以下决策树快速确定适合您场景的GPU配置策略：

```
开始
│
├─ 您有几块独立GPU？
│   │
│   ├─ 1块 ──→ 显存大小？
│   │           ├─ < 4GB  ──→ 单GPU + 小批次（gpu-performance 模板，减小 batch_size）
│   │           ├─ 4~8GB  ──→ 单GPU 标准配置（gpu-performance 模板，默认参数）
│   │           └─ > 8GB  ──→ 单GPU 高性能配置（gpu-performance 模板，增大 batch_size）
│   │
│   └─ 2块以上 ──→ 是否需要7×24小时持续运行？
│                   ├─ 是 ──→ 多GPU + 长时间运行（gpu-multi + long-running 组合）
│                   └─ 否 ──→ 多GPU 标准配置（gpu-multi 模板）
│
└─ 无独立GPU 或 仅集成显卡？
    └─ 使用CPU模式（无需GPU参数，配合 long-running 模板）
```

### 快速启动命令对照

| 场景 | 推荐命令 |
|------|---------|
| 单GPU 快速测试 | `python key_collision_cli.py -t <地址> -m random --use-gpu` |
| 单GPU 性能优化 | `python key_collision_cli.py -t <地址> -m random --use-gpu --template gpu-performance` |
| 多GPU 并行 | `python key_collision_cli.py -f targets.txt -m random --multi-gpu --template gpu-multi` |
| 长时间运行 | `python key_collision_cli.py -f targets.txt -m random --use-gpu --template long-running --checkpoint` |
| 功能验证 | `python key_collision_cli.py -t <地址> -m random --use-gpu --template quick-test --duration 60` |

---

## 📐 批次大小调优

`batch_size`（`--gpu-batch-size`）是影响GPU性能的最关键参数，直接决定每次GPU并行计算的私钥数量。

### 显存 × 批次大小 × 预期性能对照表

| GPU显存 | 推荐 `--gpu-batch-size` | 预期速度范围 | 适用GPU示例 |
|---------|------------------------|-------------|------------|
| < 2GB | `10000` ~ `30000` | 10K ~ 30K 次/秒 | 低端移动GPU |
| 2~4GB | `50000` ~ `100000` | 30K ~ 100K 次/秒 | GTX 1050, RX 560 |
| 4~8GB | `100000` ~ `300000` | 80K ~ 300K 次/秒 | GTX 1060/1070, RX 580 |
| 8~12GB | `300000` ~ `600000` | 250K ~ 600K 次/秒 | RTX 2080, RX 6700 XT |
| 16GB+ | `1048576` ~ `2000000` | **3.07M 次/秒**（Intel Arc A770 v3.2.0） | RTX 3090, Intel Arc A770, A100 |

> 💡 **推荐做法**：首次运行不指定 `--gpu-batch-size`，系统会根据显存自动计算最优值。若出现显存不足错误，再手动减小该参数。

### 调优步骤

```bash
# 步骤1：让系统自动检测显存并选择批次大小
python key_collision_cli.py -t <地址> -m random --use-gpu --duration 30

# 步骤2：如出现 cl_out_of_resources 错误，手动减半
python key_collision_cli.py -t <地址> -m random --use-gpu --gpu-batch-size 50000

# 步骤3：如性能未达预期，可适当增大（不超过显存80%）
python key_collision_cli.py -t <地址> -m random --use-gpu --gpu-batch-size 200000
```

### 配置文件方式（持久化）

```json
{
  "gpu": {
    "gpu_batch_size": 200000
  }
}
```

> ⚠️ 值设为 `-1` 表示自动计算（默认）。

---

## 📦 配置模板对比

使用 `--template` 参数可以一键应用预设配置，避免手动修改 `config.json`。

```bash
# 应用模板（修改 config.json 并立即生效）
python key_collision_cli.py --template gpu-performance
```

### 四个模板详细对比

| 对比项 | `gpu-performance` | `gpu-multi` | `long-running` | `quick-test` |
|--------|------------------|-------------|---------------|--------------|
| **中文名** | GPU性能优化 | 多GPU负载均衡 | 长时间运行 | 快速测试 |
| **适用场景** | 单GPU高性能碰撞 | 多GPU并行碰撞 | 7×24小时持续运行 | 功能测试与验证 |
| **GPU模式** | `single` | `multi` | 不设定 | 不设定 |
| **性能优化** | ✅ 开启 | ✅ 开启 | ✅ 开启 | ❌ 关闭 |
| **SIMD哈希** | ✅ 开启 | ✅ 开启 | 不设定 | 不设定 |
| **内存池** | ✅ 开启 | ✅ 开启 | 不设定 | 不设定 |
| **window_size** | 8 | 8 | 不设定 | 不设定 |
| **自动调优** | ✅ 开启 | ✅ 开启 | 不设定 | 不设定 |
| **厂商优化** | ✅ 开启 | ✅ 开启 | 不设定 | 不设定 |
| **负载均衡策略** | 不设定 | `performance` | 不设定 | 不设定 |
| **断点续传间隔** | 不设定 | 不设定 | 每60秒 | 每10秒 |
| **监控系统** | 不设定 | 不设定 | ✅ 开启（10s采样） | ❌ 关闭 |
| **日志级别** | 不设定 | 不设定 | `INFO` | `DEBUG` |
| **日志轮转** | 不设定 | 不设定 | 50MB/10份 | 不设定 |
| **自动清理** | 不设定 | 不设定 | 7天后清理 | 不设定 |
| **最大工作线程** | 1 | 不设定 | 不设定 | 2 |

### 模板使用建议

```bash
# 单GPU最高性能（日常使用推荐）
python key_collision_cli.py -f targets.txt -m random \
  --use-gpu \
  --template gpu-performance

# 多GPU并行（充分利用多卡算力）
python key_collision_cli.py -f targets.txt -m random \
  --multi-gpu \
  --template gpu-multi

# 服务器长期运行（7×24小时，含自动监控和日志管理）
python key_collision_cli.py -f targets.txt -m random \
  --use-gpu \
  --template long-running \
  --checkpoint \
  --dedup

# 开发调试（详细日志，快速验证逻辑）
python key_collision_cli.py -t <地址> -m random \
  --use-gpu \
  --template quick-test \
  --duration 60
```

---

## 🔒 `--sensitive-mode` 使用指南

`--sensitive-mode` 参数控制匹配结果中私钥信息的显示和导出方式，适用于多人协作、截图分享、日志留存等需要保护敏感数据的场景。

### 三种模式说明

| 模式 | 参数值 | 私钥显示 | WIF显示 | 适用场景 |
|------|--------|---------|---------|---------|
| **完整模式**（默认） | `full` | 完整64位十六进制 | 完整WIF字符串 | 本地个人使用，需立即使用私钥 |
| **掩码模式** | `masked` | 首尾各8位，中间用 `*` 掩盖 | 首4位 + `*` + 末4位 | 截图分享、多人协作、审计留档 |
| **仅哈希模式** | `hash_only` | `[SHA256:xxxx...]` 摘要 | `[已隐藏]` | 最高安全级别，仅确认碰撞存在 |

### 各模式输出示例

```
# full 模式（默认）
🎯 发现匹配!
  地址     : 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
  私钥 Hex : 0000000000000000000000000000000000000000000000000000000000000001
  WIF      : KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn

# masked 模式
🎯 发现匹配!
  地址     : 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
  私钥 Hex : 00000000********************************00000001
  WIF      : KwDi****************************oWn

# hash_only 模式
🎯 发现匹配!
  地址     : 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
  私钥 Hex : [SHA256:5feceb66ffc86f38...]
  WIF      : [已隐藏]
```

### 安全建议

- 🟢 **本地单人使用**：使用默认 `full` 模式，确保找到碰撞后可立即获取完整私钥。
- 🟡 **团队协作 / 截图留存**：使用 `masked` 模式，防止私钥在通讯记录中泄露。
- 🔴 **高安全合规场景**：使用 `hash_only` 模式，仅记录碰撞存在的证据，不保存私钥。

```bash
# 配合导出使用（保护导出文件中的私钥）
python key_collision_cli.py -f targets.txt -m random \
  --use-gpu \
  --sensitive-mode masked \
  --export-matches matches_masked.json \
  --export-progress progress.json
```

> ⚠️ **重要**：`hash_only` 模式下，匹配到的私钥将**无法恢复**。如果您需要实际使用发现的私钥，请勿使用此模式，或在验证后改回 `full` 模式重新运行。

---

## 🔧 性能优化参数

以下参数允许对CPU端性能优化策略进行精细控制，在特殊硬件或调试场景下使用。

### 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--window-size N` | `8` | 预计算窗口大小，影响椭圆曲线批量运算效率 |
| `--no-simd` | 关闭（即默认开启SIMD） | 禁用SIMD哈希优化（适用于不支持SIMD的老旧CPU） |
| `--no-memory-pool` | 关闭（即默认使用内存池） | 禁用内存池复用（适用于调试内存问题） |

### 推荐配置组合

| 场景 | `--window-size` | `--no-simd` | `--no-memory-pool` | 说明 |
|------|-----------------|-------------|-------------------|------|
| **生产高性能**（默认） | `8` | 不加 | 不加 | 全开优化，适合现代CPU+GPU |
| **低端CPU辅助** | `4` | 加上 | 不加 | 减小CPU计算量，GPU主导 |
| **内存受限环境** | `8` | 不加 | 加上 | 避免内存池占用，降低RSS |
| **调试/问题排查** | `4` | 加上 | 加上 | 关闭所有优化，便于定位问题 |
| **Intel Arc专项** | `8` | 不加 | 不加 | 保持默认，驱动已处理兼容性 |

### 组合使用示例

```bash
# 生产环境最优配置（默认参数即可）
python key_collision_cli.py -f targets.txt -m random \
  --use-gpu \
  --template gpu-performance

# 调试模式：关闭所有CPU优化，便于排查问题
python key_collision_cli.py -t <地址> -m random \
  --use-gpu \
  --no-simd \
  --no-memory-pool \
  --window-size 4 \
  --duration 30

# 内存受限服务器（16GB以下RAM）
python key_collision_cli.py -f targets.txt -m random \
  --use-gpu \
  --no-memory-pool \
  --duration 3600
```

### `--window-size` 调优说明

`window_size` 决定预计算椭圆曲线点的数量（`2^window_size` 个）：

- 值越大 → 预计算表越大 → 单次查表更快 → 但初始化时间和内存占用更高
- 推荐范围：`4` ~ `16`，默认 `8` 在大多数场景下效果最佳
- GPU模式下CPU端计算占比较小，调整此值对整体性能影响有限

---

## ❓ 常见问题

### Q1: GPU不可用 / 初始化失败

**症状**：运行时提示 `GPU模式需要安装 pyopencl` 或 `GPU初始化失败`

**排查步骤**：

```bash
# 步骤1：检查 pyopencl 安装
python -c "import pyopencl; print('pyopencl 版本:', pyopencl.__version__)"

# 步骤2：列出可用OpenCL平台
python -c "import pyopencl as cl; [print(p) for p in cl.get_platforms()]"

# 步骤3：使用内置健康检查
python key_collision_cli.py --health-check
```

**解决方案**：

```bash
# 安装 pyopencl
pip install pyopencl

# NVIDIA GPU：确保已安装 CUDA Toolkit
# AMD GPU：安装 ROCm 或 AMD 驱动
# Intel Arc：更新至最新 Intel Graphics 驱动
```

---

### Q2: 显存不足 (`cl_out_of_resources` / `memory allocation failed`)

**症状**：运行开始后立即报错或性能急剧下降

**解决方案**：

```bash
# 方法1：减小批次大小
python key_collision_cli.py -t <地址> -m random \
  --use-gpu \
  --gpu-batch-size 50000

# 方法2：持久化到配置文件
python key_collision_cli.py --template gpu-performance
# 然后编辑 config.json，将 gpu.gpu_batch_size 设为 50000

# 方法3：关闭其他占用显存的程序（游戏、浏览器WebGL等）
```

---

### Q3: 多GPU负载不均

**症状**：监控显示某块GPU利用率远低于其他GPU

**解决方案**：

```bash
# 查看GPU设备列表
python key_collision_cli.py --health-check

# 方法1：指定参与的GPU索引（排除问题设备）
python key_collision_cli.py -f targets.txt -m random \
  --multi-gpu \
  --gpu-indices 0 1

# 方法2：使用性能均衡策略（已内置于 gpu-multi 模板）
python key_collision_cli.py --template gpu-multi
```

---

### Q4: Intel Arc GPU 性能低 / GPU Hang

**症状**：速度远低于预期，或出现程序无响应

**解决方案**：

```bash
# 步骤1：确认驱动版本（建议31.0.101.5522+）
# 在设备管理器中查看 Intel Arc 驱动版本

# 步骤2：减小批次大小（Intel Arc 建议从 65536 开始）
python key_collision_cli.py -t <地址> -m random \
  --use-gpu \
  --gpu-batch-size 65536

# 步骤3：使用 Intel Arc 专用配置文件
python key_collision_cli.py -t <地址> -m random \
  --use-gpu \
  --config config.intel_arc.json
```

> 💡 引擎已内置30秒超时保护机制，GPU Hang会被自动检测并恢复，无需手动干预。

---

### Q5: 驱动兼容性问题

**症状**：OpenCL内核编译失败或计算结果异常

| GPU厂商 | 推荐驱动/运行时 | 注意事项 |
|---------|--------------|---------|
| NVIDIA | CUDA Toolkit 11.x+ | 确保 `nvidia-opencl-icd` 已安装 |
| AMD | ROCm 5.x+ 或 AMDGPU-PRO | Windows 使用 AMD Software 驱动 |
| Intel Arc | Intel Graphics Driver 31.0.101.4502+ | 旧版驱动存在 uint8 全局指针 hang bug |

```bash
# 验证OpenCL内核可正常编译
python -c "
import pyopencl as cl
platforms = cl.get_platforms()
for p in platforms:
    for d in p.get_devices(cl.device_type.GPU):
        ctx = cl.Context([d])
        print(f'✅ {d.name} 上下文创建成功')
"
```

---

## 📚 相关参考

- GPU引擎详细说明：[gpu-engine-guide.md](gpu-engine-guide.md)
- Intel Arc专项指南：[intel-arc-integration-guide.md](intel-arc-integration-guide.md)
- 多GPU配置：[MULTI_GPU.md](MULTI_GPU.md)
- 性能优化：[performance-optimization.md](performance-optimization.md)
- 配置文件说明：[CONFIG.md](CONFIG.md)

---

**更新日期**: 2026-04-25  
**版本**: v3.0+
