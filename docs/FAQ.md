# 常见问题与故障排除

## 安装问题

### Q: `pip install -r requirements.txt` 报错，缺少某些包？

**A:** 先确认 Python 版本 >= 3.7，然后使用虚拟环境：

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

如果仍然失败，尝试升级 pip：

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Q: 安装 `coincurve` 失败，提示缺少编译工具？

**A:** `coincurve` 需要 C 编译器。

- **Windows**：安装 [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，勾选"C++ 生成工具"
- **Ubuntu/Debian**：`sudo apt install build-essential libssl-dev`
- **macOS**：`xcode-select --install`

安装完成后重新运行 `pip install coincurve`。

> 如果不需要最高性能，可跳过 `coincurve`，系统会自动降级到纯 Python 后端。

---

### Q: 安装 `pyopencl` 失败？

**A:** `pyopencl` 依赖 OpenCL 运行时驱动：

- **NVIDIA**：安装 CUDA Toolkit >= 11.0
- **AMD**：安装 AMD 显卡驱动（版本 >= 21.x）
- **Intel**：安装 Intel Arc 客户端驱动（版本 >= 31.0.101.4146）

安装驱动后，执行：

```bash
pip install pyopencl
```

验证 OpenCL 是否可用：

```bash
python -c "import pyopencl; print([d.name for p in pyopencl.get_platforms() for d in p.get_devices()])"
```

---

## 启动问题

### Q: 运行 `python key_collision_cli.py --help` 提示 `ModuleNotFoundError`？

**A:** 确认已安装依赖，且在项目根目录下运行：

```bash
# 在项目根目录
cd btc-collision-engine
pip install -r requirements.txt
python key_collision_cli.py --help
```

---

### Q: 提示 `p2pkh_simulator 模块未找到`？

**A:** 这是旧版 GUI 依赖模块（已移除），不影响 CLI 正常运行，可忽略该警告。CLI 模式完全不依赖此模块。

---

### Q: `config.json` 不存在时启动报错？

**A:** 首次使用需初始化配置文件：

```bash
# Windows
copy config.example.json config.json

# Linux / macOS
cp config.example.json config.json
```

然后按需编辑 `config.json`（详见 [CONFIG.md](CONFIG.md)）。

---

## GPU 问题

### Q: GPU 不被识别，始终使用 CPU 模式？

**A:** 检查以下步骤：

1. 确认 `pyopencl` 已安装
2. 验证 GPU 驱动支持 OpenCL：

   ```bash
   python -c "import pyopencl; print(pyopencl.get_platforms())"
   ```

3. 检查 `config.json` 中 `gpu.use_gpu` 是否为 `true`
4. 尝试指定 `gpu.device_index` 为具体设备编号

---

### Q: Intel Arc GPU 运行不稳定或崩溃？

**A:** 使用 Intel Arc 优化配置（已包含在 `config.intel_arc.json`）：

```bash
# 复制 Intel Arc 专用配置
copy config.intel_arc.json config.json
```

或手动调整以下参数：

```json
{
  "gpu": {
    "batch_size": 262144,
    "memory_usage_ratio": 0.45,
    "enable_vendor_optimizations": true
  }
}
```

**注意**：Intel Arc 驱动版本需 >= 31.0.101.4146。

---

### Q: GPU 模式比 CPU 慢？

**A:** 常见原因：

1. `batch_size` 设置过小（建议 >= 65536）
2. 系统内存不足导致频繁页交换
3. GPU 驱动版本过低（需更新驱动）
4. 当前系统负载过高

建议先使用 CPU 模式基准测试，再对比 GPU 效果：

```bash
python key_collision_cli.py -t <地址> -m random --duration 10
```

---

### Q: 运行时出现大量 GPU 警告日志刷屏？

**A:** 调整日志级别过滤掉 DEBUG/WARNING：

```json
{
  "logging": {
    "level": "ERROR",
    "enable_console": true
  }
}
```

---

## 运行问题

### Q: 速度为 0 次/秒？

**A:** 常见原因及解决：

1. **未指定目标地址**：使用 `-t` 或 `-f` 参数

   ```bash
   python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
   ```

2. **目标文件为空**：检查 `targets.txt` 是否包含有效地址
3. **依赖库未安装**：重新运行 `pip install -r requirements.txt`

---

### Q: 程序意外中断，如何恢复？

**A:** 使用断点续传功能：

```bash
# 启用断点保存（每 30 秒自动保存一次）
python key_collision_cli.py -t <地址> -m random --checkpoint

# 恢复上次进度（range/brute_force 模式支持）
python key_collision_cli.py -t <地址> -m range --checkpoint --resume
```

---

### Q: 内存占用持续增长？

**A:**

1. 使用 `--dedup` 时，Bloom 过滤器会占用内存。可调小 `config.json` 中的 `dedup_max_size`
2. 确认未设置超大 `batch_size`（GPU 模式）
3. 尝试减少 `max_workers` 线程数

---

### Q: 如何设置多线程数量？

**A:** 两种方式：

```bash
# 命令行参数
python key_collision_cli.py -t <地址> -m random --workers 8

# 或修改 config.json
# "collision": { "max_workers": 8 }
```

> `max_workers` 上限为 1024，超过会报错。建议不超过 CPU 核心数 × 2。

---

## 日志与诊断

### Q: 如何开启详细调试日志？

```bash
# 临时开启（修改 config.json）
# "logging": { "level": "DEBUG" }

# 或查看 logs/ 目录下的日志文件
```

---

### Q: 日志文件过大？

**A:** 调整轮转策略：

```json
{
  "logging": {
    "max_bytes": 5242880,
    "backup_count": 3,
    "compress_backups": true
  }
}
```

---

## 其他

### Q: 支持哪些 Bitcoin 地址格式？

**A:** 目前支持：

- **P2PKH**：以 `1` 开头（如 `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`）
- **P2SH**：以 `3` 开头（部分支持）

**暂不支持**：Bech32 原生 SegWit（`bc1...`）地址。

---

### Q: 如何贡献代码或报告 Bug？

请阅读 [CONTRIBUTING.md](../CONTRIBUTING.md) 了解贡献指南，或在 GitHub Issues 页面提交 Bug 报告。

---

> 更多配置说明请参考 [CONFIG.md](CONFIG.md)。
