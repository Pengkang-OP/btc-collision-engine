# Windows UTF-8 编码问题解决方案

## 问题描述

在Windows系统中运行Python工具脚本时，遇到以下问题：

1. **直接运行**：中文和emoji字符可能显示为乱码
2. **使用管道**：PowerShell/CMD管道会破坏UTF-8输出，导致乱码

## 解决方案

### 1. Python脚本内置修复（[OK_CHECK] 已完成）

所有工具脚本已内置Windows UTF-8编码支持：

```python
import ctypes

if sys.platform == 'win32':
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (OSError, AttributeError):
        pass
    
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

**修复的文件**：
- [OK_CHECK] `tools/check_document_quality.py`
- [OK_CHECK] `tools/fix_heading_levels.py`
- [OK_CHECK] `tools/fix_code_blocks.py`
- [OK_CHECK] `tools/check_broken_links.py`
- [OK_CHECK] `tools/add_version_info.py`
- [OK_CHECK] `tools/add_table_of_contents.py`
- [OK_CHECK] `audit_resource_cleanup.py`
- [OK_CHECK] `check_pr_status.py`

### 2. 管道问题解决方案

#### 方案A：使用PowerShell包装器（推荐）

**文件**：`tools/run_utf8.ps1`

**使用方法**：

```powershell
# 基础使用
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py"

# 配合管道使用
.\tools\run_utf8.ps1 -Script "python tools/add_version_info.py --dry-run" | Select-Object -First 20

# 检查文档质量并过滤输出
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-String "需改进"
```

**原理**：
- 设置PowerShell的 `[Console]::OutputEncoding` 为UTF-8
- 设置 `$OutputEncoding` 为UTF-8
- 确保管道传递的数据保持UTF-8编码

#### 方案B：使用批处理包装器

**文件**：`tools/run_utf8.bat`

**使用方法**：

```cmd
REM 基础使用
tools\run_utf8.bat python tools\check_document_quality.py

REM 配合管道使用
tools\run_utf8.bat python tools\add_version_info.py --dry-run | more
```

**原理**：
- 使用 `chcp 65001` 设置CMD代码页为UTF-8
- 执行传入的命令

#### 方案C：避免使用管道（最简单）

如果只需要查看完整输出，不使用管道：

```powershell
# [OK_CHECK] 推荐：直接运行
python tools/check_document_quality.py

# [CROSS] 避免：使用管道
python tools/check_document_quality.py | Select-Object -First 20
```

### 3. 一次性设置（全局方案）

如果经常使用管道，可以在PowerShell配置文件中设置：

**编辑PowerShell配置文件**：
```powershell
notepad $PROFILE
```

**添加以下内容**：
```powershell
# 设置UTF-8编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

**保存后重启PowerShell**，所有命令都将使用UTF-8编码。

## 使用示例

### 检查文档质量

```powershell
# 方法1：直接运行（推荐）
python tools/check_document_quality.py

# 方法2：使用包装器+管道
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-Object -First 30

# 方法3：使用批处理
tools\run_utf8.bat python tools\check_document_quality.py
```

### 添加版本信息

```powershell
# 模拟运行
.\tools\run_utf8.ps1 -Script "python tools/add_version_info.py --dry-run"

# 实际运行
.\tools\run_utf8.ps1 -Script "python tools/add_version_info.py"
```

### 检查断裂链接

```powershell
# 直接运行
python tools/check_broken_links.py

# 过滤错误
.\tools\run_utf8.ps1 -Script "python tools/check_broken_links.py" | Select-String "断裂"
```

## 技术细节

### 为什么管道会破坏UTF-8？

1. **PowerShell默认编码**：Windows PowerShell默认使用系统代码页（通常是GBK/CP936）
2. **管道重编码**：当使用 `|` 管道符时，PowerShell会重新编码输出流
3. **编码不匹配**：Python输出UTF-8，但PowerShell用GBK解码，导致乱码

### 解决方案原理

1. **Python端**：
   - 设置Windows控制台代码页为65001（UTF-8）
   - 重新包装stdout/stderr使用UTF-8编码
   - 添加 `errors='replace'` 处理无法编码的字符

2. **PowerShell端**：
   - 设置 `[Console]::OutputEncoding` 为UTF-8
   - 设置 `$OutputEncoding` 为UTF-8
   - 确保管道传递时不重新编码

3. **CMD端**：
   - 使用 `chcp 65001` 切换代码页到UTF-8

## 常见问题

### Q1: 为什么不用全局设置？

**A**: 全局设置可能影响其他程序的行为。我们采用**最小影响原则**：
- Python脚本自身处理编码（最可靠）
- 需要管道时使用包装器（按需启用）

### Q2: Linux/Mac需要这些修复吗？

**A**: 不需要。Linux/Mac默认使用UTF-8，不存在这个问题。代码中的 `if sys.platform == 'win32'` 确保只在Windows上应用修复。

### Q3: 能否让管道直接工作？

**A**: 可以，通过方案C的一次性设置。但这会改变PowerShell的全局行为，可能影响其他工具。

### Q4: 包装器脚本会影响性能吗？

**A**: 几乎不会。包装器只设置编码变量，开销可以忽略不计。

## 最佳实践

1. **日常使用**：直接运行Python脚本，不使用管道
2. **需要过滤**：使用 `run_utf8.ps1` 包装器
3. **批量处理**：在脚本开头设置编码（已自动完成）
4. **团队协作**：将此文档分享给团队成员

## 验证修复

运行以下命令验证UTF-8输出是否正常：

```powershell
# 测试emoji和中文字符
.\tools\run_utf8.ps1 -Script "python -c \"print('[OK_CHECK] 中文测试：文档质量检查')\""

# 应该看到：[OK_CHECK] 中文测试：文档质量检查
# 而不是：馃敡 涓枃娴嬭瘯锛氭枃妗ｈ川閲忔鏌?
```

## 更新历史

- **2026-04-21**: 初始版本，修复8个Python脚本，创建包装器
- **后续**: 新脚本添加中文/emoji输出时，自动应用相同的编码修复

## 参考资源

- [Python Unicode HOWTO](https://docs.python.org/3/howto/unicode.html)
- [Windows Console Code Pages](https://docs.microsoft.com/en-us/windows/console/console-code-pages)
- [PowerShell Encoding](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
