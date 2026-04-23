# Windows控制台UTF-8编码乱码修复指南

**问题**: Python脚本在Windows控制台输出中文时显示乱码  
**影响**: 所有包含中文输出的Python脚本  
**日期**: 2026-04-21

---

## 🔍 问题现象

运行Python脚本时,中文显示为乱码:

```
❌ 错误输出:
妫€娴嬪埌GPU璁惧: Intel(R) Arc(TM) A770 Graphics
搴旂敤Intel浼樺寲绛栫暐

✅ 正确输出:
检测到GPU设备: Intel(R) Arc(TM) A770 Graphics
应用Intel优化策略
```

---

## 🛠️ 解决方案

### 方案1: 临时修复(推荐用于单次运行) ⭐

#### 使用批处理脚本

```powershell
# 运行GPU诊断工具(已包含UTF-8设置)
.\run_gpu_diagnostic.bat
```

#### 手动设置(单次有效)

```powershell
# 1. 设置代码页
chcp 65001

# 2. 设置环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

# 3. 运行脚本
python tools/gpu_diagnostic.py
```

**优点**: 无需重启,立即生效  
**缺点**: 每次打开新控制台都需要重新设置

---

### 方案2: 会话级修复(推荐用于开发) ⭐⭐

#### PowerShell脚本

```powershell
# 运行编码修复脚本
.\tools\fix_console_encoding.ps1
```

**效果**:

- 设置当前会话的UTF-8编码
- 设置Python环境变量
- 验证编码设置

**优点**: 一次性设置,当前会话有效  
**缺点**: 关闭控制台后失效

---

### 方案3: 永久修复(推荐用于生产环境) ⭐⭐⭐

#### 修改注册表(需要管理员权限)

```powershell
# 以管理员身份运行PowerShell
# 右键PowerShell -> 以管理员身份运行

# 运行永久修复脚本
.\tools\permanent_utf8_fix.ps1
```

**效果**:

- 修改系统注册表
- 设置全局环境变量
- 所有控制台默认使用UTF-8

**优点**: 一次设置,永久生效  
**缺点**: 需要重启计算机,需要管理员权限

---

### 方案4: Python代码级修复

在Python脚本开头添加:

```python
import sys
import io

# 设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置默认编码
sys.setdefaultencoding('utf-8')
```

**优点**: 脚本级别控制  
**缺点**: 需要修改每个脚本

---

### 方案5: 使用Windows Terminal(最佳体验) ⭐⭐⭐⭐

Windows Terminal默认支持UTF-8,无需额外配置。

#### 安装Windows Terminal

```powershell
# 从Microsoft Store安装
# 或使用winget
winget install Microsoft.WindowsTerminal
```

#### 配置默认使用UTF-8

编辑Windows Terminal配置文件 (`%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`):

```json
{
    "profiles": {
        "defaults": {
            "font": {
                "face": "Cascadia Mono"
            },
            "colorScheme": "One Half Dark",
            "useAcrylic": true,
            "acrylicOpacity": 0.8
        }
    },
    "defaultProfile": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}"
}
```

**优点**: 现代化终端,完美支持UTF-8,美观  
**缺点**: 需要安装额外软件

---

## 📋 快速修复流程

### 立即可用(1分钟)

```powershell
# 步骤1: 运行编码修复脚本
.\tools\fix_console_encoding.ps1

# 步骤2: 运行GPU诊断
python tools/gpu_diagnostic.py
```

### 永久解决(5分钟+重启)

```powershell
# 步骤1: 以管理员身份打开PowerShell

# 步骤2: 运行永久修复脚本
.\tools\permanent_utf8_fix.ps1

# 步骤3: 重启计算机

# 步骤4: 验证
python tools/gpu_diagnostic.py
```

---

## 🔧 验证修复

### 方法1: 运行测试脚本

```powershell
python -c "print('测试中文输出: 你好世界! 🌍')"
```

**正确输出**:

```
测试中文输出: 你好世界! 🌍
```

**错误输出**:

```
娴嬭瘯涓枃杈撳嚭: 浣犲ソ涓栫晫! 馃寪
```

---

### 方法2: 检查编码设置

```powershell
python -c "import sys; print(f'默认编码: {sys.getdefaultencoding()}'); print(f'标准输出编码: {sys.stdout.encoding}')"
```

**正确输出**:

```
默认编码: utf-8
标准输出编码: utf-8
```

**错误输出**:

```
默认编码: utf-8
标准输出编码: gbk
```

---

### 方法3: 检查代码页

```powershell
chcp
```

**正确输出**:

```
活动代码页: 65001
```

**错误输出**:

```
活动代码页: 936
```

---

## 📊 方案对比

| 方案 | 难度 | 持久性 | 需要重启 | 推荐场景 |
|------|------|--------|---------|---------|
| 方案1: 批处理 | ⭐ | 临时 | 否 | 单次运行 |
| 方案2: 会话脚本 | ⭐⭐ | 会话 | 否 | 开发调试 |
| 方案3: 注册表 | ⭐⭐⭐ | 永久 | 是 | 生产环境 |
| 方案4: Python代码 | ⭐⭐⭐ | 脚本级 | 否 | 脚本分发 |
| 方案5: Windows Terminal | ⭐ | 永久 | 否 | 日常使用 |

---

## 🚨 常见问题

### Q1: 设置后仍然乱码?

**原因**: 控制台字体不支持中文

**解决方案**:

1. 右键控制台标题栏 -> 属性
2. 选择"字体"选项卡
3. 选择支持中文的字体:
   - 新宋体
   - 微软雅黑
   - Cascadia Mono
   - Consolas(部分中文)

---

### Q2: chcp 65001报错?

**原因**: 系统不支持UTF-8代码页

**解决方案**:

```powershell
# Windows 10 1903+ 才完全支持
# 检查Windows版本
winver

# 如果版本过低,使用方案5(Windows Terminal)
```

---

### Q3: PowerShell脚本报错?

**错误**: 无法加载文件,因为在此系统上禁止运行脚本

**解决方案**:

```powershell
# 以管理员身份运行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 然后重新运行脚本
.\tools\fix_console_encoding.ps1
```

---

### Q4: 永久修复后部分软件乱码?

**原因**: 某些老旧软件依赖GBK编码

**解决方案**:

```powershell
# 恢复默认编码(936 = GBK)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "OEMCP" -Value "936"
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "ACP" -Value "936"

# 重启计算机
Restart-Computer
```

---

### Q5: VS Code终端乱码?

**解决方案**:

编辑VS Code设置 (`settings.json`):

```json
{
    "terminal.integrated.profiles.windows": {
        "PowerShell": {
            "source": "PowerShell",
            "icon": "terminal-powershell",
            "args": ["-NoExit", "-Command", "chcp 65001"]
        }
    },
    "terminal.integrated.defaultProfile.windows": "PowerShell",
    "files.encoding": "utf8"
}
```

---

## 📝 已提供的工具

| 工具 | 路径 | 说明 |
|------|------|------|
| 编码修复脚本(CMD) | `tools/fix_console_encoding.bat` | 批处理版本 |
| 编码修复脚本(PS) | `tools/fix_console_encoding.ps1` | PowerShell版本 |
| 永久修复脚本 | `tools/permanent_utf8_fix.ps1` | 注册表修改 |
| GPU诊断工具 | `tools/gpu_diagnostic.py` | 已修复编码问题 |
| 快速运行脚本 | `run_gpu_diagnostic.bat` | 一键运行诊断 |

---

## 🎯 推荐工作流

### 开发人员

```
1. 安装Windows Terminal (永久解决)
2. 或使用 fix_console_encoding.ps1 (每次会话)
3. 开发测试
```

### 运维人员

```
1. 运行 permanent_utf8_fix.ps1 (一次设置)
2. 重启服务器
3. 所有脚本正常输出
```

### 临时使用

```
1. 运行 run_gpu_diagnostic.bat (自动设置)
2. 查看输出
3. 关闭窗口
```

---

## 📚 相关资源

- [Windows控制台代码页文档](https://docs.microsoft.com/en-us/windows/console/code-page-identifiers)
- [Python UTF-8模式](https://docs.python.org/3/using/windows.html#utf-8-mode)
- [Windows Terminal](https://aka.ms/terminal)

---

**文档版本**: v1.0  
**最后更新**: 2026-04-21  
**维护者**: BTC碰撞引擎团队
