# 跨平台兼容性指南

> **版本**: v4.2.2 | **最后更新**: 2026-05-15

## 概述

BTC 碰撞引擎支持 **Windows、Linux、macOS** 三大平台，通过 `PlatformUtils` 和 `PlatformChecker` 两个核心工具类提供统一的跨平台能力。引擎在各平台上均可运行 CPU 碰撞核心、CLI 界面、监控系统和断点续传；GPU 加速功能在 macOS 上受硬件支持限制，详见[第 6 节已知限制](#6-已知限制)。

---

## 1. 平台支持矩阵

| 功能 | Windows | Linux | macOS | 备注 |
|------|:-------:|:-----:|:-----:|------|
| 核心碰撞引擎 | [OK] | [OK] | [OK] | 纯 Python/coincurve 实现 |
| GPU 加速 (NVIDIA) | [OK] | [OK] | [WARN] | macOS 通过 `nvidia-smi` 检测，Apple Silicon 不支持 CUDA |
| GPU 加速 (AMD) | [OK] | [OK] | [WARN] | macOS 通过 `system_profiler SPDisplaysDataType` 检测 |
| GPU 加速 (Intel) | [OK] | [OK] | [WARN] | macOS 通过 `system_profiler SPDisplaysDataType` 检测 |
| CLI 界面 | [OK] | [OK] | [OK] | 统一入口 `key_collision_cli.py` |
| GUI 教程界面 | [OK] | [OK] | [OK] | 跨平台字体自动适配（见 §4.3） |
| 自动安装脚本 | [OK] `.bat` | [OK] `.sh` | [OK] `.sh` | |
| 内存锁定 | [FAIL] | [OK] | [FAIL] | 仅 Linux 支持 `mlockall` |
| 断点续传 | [OK] | [OK] | [OK] | 原子文件操作跨平台适配 |
| 监控系统 | [OK] | [OK] | [OK] | Prometheus + 本地 JSON |
| 健康检查工具 | [OK] | [OK] | [OK] | `python -m src.utils.health_check` |
| 平台兼容性检查 | [OK] | [OK] | [OK] | `python -m src.utils.platform_check` |
| 配置目录管理 | [OK] | [OK] | [OK] | `PlatformUtils.get_config_dir()` |
| 符号链接 | [WARN] | [OK] | [OK] | Windows 需开发者模式或管理员权限 |

---

## 2. 系统要求

### 2.1 最低要求

| 项目 | 最低版本/规格 |
|------|-------------|
| Python | >= 3.9 |
| 磁盘空间 | >= 200 MB |
| 内存 | >= 512 MB（推荐 2 GB+） |
| 操作系统 | Windows 10+、Ubuntu 18.04+、macOS 10.15+ |

### 2.2 各平台特殊要求

**Windows**

- 推荐启用长路径支持，避免 MAX_PATH（260 字符）限制触发构建失败（见 §6.2）

- PowerShell 执行 `chcp 65001` 或系统区域设置为 UTF-8，避免中文乱码

- 符号链接功能需要开启「开发者模式」或以管理员权限运行

**Linux**

- 建议具备 `/proc` 文件系统（用于 GPU 驱动检测）

- `mlockall` 内存锁定需要 `CAP_IPC_LOCK` 能力，或运行 `ulimit -l unlimited`

- 中文 GUI 需要安装 CJK 字体（见 §7.2）

**macOS**

- 需要安装 Xcode Command Line Tools：`xcode-select --install`

- Apple Silicon (M1/M2/M3) 不支持 CUDA，GPU 模式不可用

- macOS 已弃用 OpenCL，GPU 加速功能受限，建议使用 CPU 模式

---

## 3. 安装指南

### 3.1 Windows 安装

```cmd
scripts/install/install.bat

```

安装脚本特性：

- 自动设置 UTF-8 编码环境（`chcp 65001`）

- 检测 Python 版本（>= 3.9）

- 若 `coincurve` 二进制安装失败，自动切换到源码编译降级策略

- 安装至项目本地 `venv` 虚拟环境，不污染系统 Python

### 3.2 Linux / macOS 安装

```bash
bash scripts/install/install.sh

```

安装脚本特性：

- 自动检测 `python3` 可执行路径

- `coincurve` 安装失败时自动尝试源码编译降级

- macOS 上自动检查 Xcode Command Line Tools

### 3.3 验证安装

安装完成后，运行平台兼容性检查：

```bash
# 命令行（交互式报告）
python -m src.utils.platform_check

# JSON 格式输出，方便脚本解析
python -m src.utils.platform_check --json

# 系统健康检查
python -m src.utils.health_check

```

检查器会逐项验证：操作系统、Python 版本、路径长度、终端编码、目录权限、磁盘空间、长路径支持（Windows）、符号链接支持。

---

## 4. 平台适配技术细节

### 4.1 编码处理

Windows 旧版控制台默认使用 GBK（CP936）编码，引擎在启动时自动调用 `PlatformUtils.ensure_utf8_output()` 将 `stdout`/`stderr` 重新包装为 UTF-8：

```python
from src.utils.platform_utils import PlatformUtils

# 在主入口处调用，确保中文正常输出
PlatformUtils.ensure_utf8_output()

```

底层实现：

```python
# 仅在 Windows 上生效，其他平台为空操作
if platform.system() == 'Windows':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

```

`PlatformChecker.check_encoding()` 可检测当前终端编码状态，若非 UTF-8 会给出修复提示。

### 4.2 文件操作与路径

**原子文件写入**

- Windows：使用 `os.replace()` 实现原子替换（避免写入失败留下损坏文件）

- Unix/Linux/macOS：使用 `os.rename()` + `chmod` 权限设置

**路径规范化**

```python
from src.utils.platform_utils import PlatformUtils

# 跨平台路径规范化（消除 \\ 和 / 不一致问题）
normalized = PlatformUtils.normalize_path(path)

```

底层调用 `os.path.normpath()`，在各平台上正确处理路径分隔符。

**配置目录**

```python
# Windows: %APPDATA%/btc-collision-engine
# Linux/macOS: ~/.config/btc-collision-engine
config_dir = PlatformUtils.get_config_dir("btc-collision-engine")

```

**断点文件存储**
断点文件存储于 `data_logs/collision_checkpoint.json`（已验证 Windows 具备写入权限），而非 `src/collision/` 下。

### 4.3 GUI 字体适配

GUI 教程界面通过 `PlatformUtils.get_ui_font()` 和 `PlatformUtils.get_mono_font()` 自动选择最佳字体：

| 平台 | UI 字体 | 等宽字体 |
|------|--------|---------|
| Windows | Microsoft YaHei（微软雅黑） | Consolas |
| macOS | PingFang SC（苹方） | Menlo |
| Linux | Noto Sans CJK SC（思源黑体） | DejaVu Sans Mono |
| 其他 | Arial | Courier New |

获取完整字体配置（含 DPI 缩放）：

```python
from src.utils.platform_utils import PlatformUtils

font_config = PlatformUtils.get_font_config()
# 返回示例:
# {
#   "title": ("Microsoft YaHei", 16, "bold"),
#   "label": ("Microsoft YaHei", 10),
#   "monospace": ("Consolas", 10),
#   ...
# }

```

### 4.4 DPI 缩放

- 基准值：96 DPI = 缩放比例 1.0

- 仅当 DPI 缩放 >= 1.5 时才等比放大字体，避免小屏幕字体过大

- 支持 `BTC_DPI_SCALE` 环境变量手动覆盖：

```bash
# 强制使用 2.0 缩放（4K 高分屏）
set BTC_DPI_SCALE=2.0    # Windows
export BTC_DPI_SCALE=2.0 # Linux/macOS

```

- 无 GUI 环境（如 headless 服务器）检测失败时自动回退到 1.0

```python
scale = PlatformUtils.get_dpi_scale()
scaled_font_size = PlatformUtils.scale_font_size(12)  # DPI >= 1.5 时才缩放
window_w, window_h = PlatformUtils.get_optimal_window_size()
# 窗口尺寸策略: 屏幕 75% 宽 x 80% 高，范围限制 [600x900, 1920x1200]

```

### 4.5 GPU 驱动检测

`DriverManager` 根据平台选择不同检测命令：

| 平台 | NVIDIA | AMD | Intel |
|------|--------|-----|-------|
| Windows | `nvidia-smi` / PowerShell WMI | WMI 查询 | WMI 查询 |
| Linux | `nvidia-smi` / `/proc/driver` / `rocm-smi` | `rocm-smi` | `clinfo` |
| macOS | `nvidia-smi`（CUDA toolkit） | `system_profiler SPDisplaysDataType` | `system_profiler SPDisplaysDataType` |

### 4.6 换行符与临时目录

```python
# 获取当前平台换行符（Windows: \r\n, Unix: \n）
line_ending = PlatformUtils.get_line_ending()

# 获取跨平台临时目录（Windows: %TEMP%, Unix: /tmp）
temp_dir = PlatformUtils.get_temp_dir()

```

---

## 5. 开发者跨平台编码规范

### 5.1 平台检测

**规范做法**：统一使用 `PlatformUtils` 类方法：

```python
from src.utils.platform_utils import PlatformUtils

if PlatformUtils.is_windows():
    # Windows 特定逻辑
elif PlatformUtils.is_macos():
    # macOS 特定逻辑
elif PlatformUtils.is_linux():
    # Linux 特定逻辑

```

**禁止**混用原始 API，避免逻辑分散和表达不一致：

```python
# [FAIL] 禁止
import sys, os, platform
if sys.platform == 'win32': ...
if os.name == 'nt': ...
if platform.system() == 'Windows': ...

# [OK] 正确
from src.utils.platform_utils import PlatformUtils
if PlatformUtils.is_windows(): ...

```

### 5.2 文件编码

- 所有文件读写操作**必须**显式指定 `encoding='utf-8'`

- 处理外部输入的未知编码文件时，使用 `errors='replace'` 或 `errors='ignore'` 防止崩溃

```python
# [OK] 正确
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# [FAIL] 禁止（依赖系统默认编码）
with open(path, 'r') as f:
    content = f.read()

```

### 5.3 路径处理

```python
import os
from src.utils.platform_utils import PlatformUtils

# [OK] 正确：使用 os.path.join 构建路径
log_path = os.path.join("data_logs", "collision.log")

# [OK] 正确：使用 normalize_path 规范化路径
clean_path = PlatformUtils.normalize_path(raw_path)

# [FAIL] 禁止：硬编码路径分隔符
log_path = "data_logs\\collision.log"   # Windows 专用
log_path = "data_logs/collision.log"    # Unix 专用

```

### 5.4 平台兼容性自测

开发新功能后，使用 `PlatformChecker` 验证兼容性：

```python
from src.utils.platform_check import PlatformChecker

checker = PlatformChecker()
all_passed, issues = checker.run_all_checks()
if not all_passed:
    for issue in issues:
        print(f"[兼容性问题] {issue}")

```

---

## 6. 已知限制

### 6.1 macOS GPU 限制

- **Apple Silicon (M1/M2/M3)**：不支持 CUDA，NVIDIA GPU 加速完全不可用

- **OpenCL**：Apple 已在 macOS 12+ 中弃用 OpenCL，支持有限且可能产生警告

- **建议**：macOS 用户优先使用 CPU 模式，可获得稳定的完整功能

```bash
# macOS 推荐启动方式（CPU 模式）
python key_collision_cli.py --mode cpu

```

### 6.2 Windows 路径长度限制

- 默认 MAX_PATH = 260 字符，嵌套深的路径可能触发 `[WinError 3]` 或 `[WinError 206]`

- `PlatformChecker.check_path_length()` 会在检测到路径过长（> 200 字符）时发出警告

**启用长路径支持（需管理员权限）**：

```powershell
# 方法 1：注册表（推荐）
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1

# 方法 2：组策略
# 计算机配置 > 管理模板 > 系统 > 文件系统 > 启用 Win32 长路径

```

### 6.3 Linux 内存安全（mlockall）

- 仅 Linux 支持 `mlockall` 内存锁定，可防止私钥被系统交换到磁盘（swap）

- Windows 和 macOS 上 `SecureKeyManager` 的内存锁定功能降级为空操作

- 如在 Windows/macOS 上有高安全要求，建议关闭系统交换分区/文件，或使用全盘加密

### 6.4 Windows 符号链接

- 符号链接需要开发者模式或管理员权限，普通用户环境下创建符号链接会失败

- 项目核心功能不依赖符号链接，此限制不影响正常使用

---

## 7. 故障排除

### 7.1 Windows 中文乱码（UTF-8）

**现象**：终端输出中文显示为乱码（如 `?????` 或 `锟斤拷`）

**解决方案**：

```powershell
# 方法 1：临时切换（当前会话有效）
chcp 65001

# 方法 2：永久设置（推荐）
# 控制面板 > 区域 > 管理 > 更改系统区域设置 > 勾选 Beta: 使用 Unicode UTF-8

```

代码层面引擎已自动调用 `PlatformUtils.ensure_utf8_output()` 处理，若仍出现乱码，请检查终端字体是否支持中文（推荐 `Windows Terminal` + `Cascadia Code`）。

### 7.2 Linux 中文字体缺失

**现象**：GUI 界面中文显示为方块或乱码

**解决方案**：

```bash
# Ubuntu / Debian
sudo apt install fonts-noto-cjk

# CentOS / RHEL / Fedora
sudo dnf install google-noto-cjk-fonts

# Arch Linux
sudo pacman -S noto-fonts-cjk

```

安装后刷新字体缓存：`fc-cache -fv`

验证字体是否可用：

```bash
fc-list | grep -i "Noto Sans CJK"

```

### 7.3 macOS GPU 不可用

**现象**：启动时提示 `GPU 不可用，回退到 CPU 模式`

**排查步骤**：

1. 确认已安装 Xcode Command Line Tools：

   ```bash
   xcode-select --version
   # 若未安装：xcode-select --install

   ```

2. 确认 GPU 类型：

   ```bash
   system_profiler SPDisplaysDataType | grep "Chipset Model"

   ```

3. Apple Silicon 用户 GPU 加速不可用，这是正常现象。建议使用 CPU 模式。

### 7.4 Windows 路径权限错误

**现象**：`[WinError 5] 拒绝访问` 或 `[WinError 3] 系统找不到指定的路径`

**解决方案**：

- 断点文件请确保写入 `data_logs/` 目录（已验证有写入权限），**不要**使用 `src/collision/` 下的路径

- 以管理员权限运行 PowerShell，或将项目迁移至用户主目录下（如 `C:\Users\<用户名>\btc-collision-engine`）

### 7.5 运行平台诊断

遇到任何不明原因的启动问题，首先运行完整的兼容性检查：

```bash
# 详细检查报告
python -m src.utils.platform_check

# JSON 格式（方便保存后提 Issue）
python -m src.utils.platform_check --json > platform_report.json

# 系统健康检查
python -m src.utils.health_check

```

检查项目包括：操作系统识别、Python 版本、路径长度（Windows）、终端编码、关键目录读写权限（`data_logs/`、`logs/`）、磁盘可用空间（>= 200 MB）、长路径支持（Windows）、符号链接支持。

---

## 相关文档

- [getting-started.md](getting-started.md) — 安装与快速开始

- [troubleshooting.md](troubleshooting.md) — 常见问题汇总

- [gpu-engine-guide.md](gpu-engine-guide.md) — GPU 引擎使用指南

- [secure-key-management.md](secure-key-management.md) — 安全密钥管理（含 mlockall 说明）

- [config-usage-examples.md](config-usage-examples.md) — 配置示例
