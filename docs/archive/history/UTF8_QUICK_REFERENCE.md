# UTF-8 编码问题 - 快速参考

## [QUICK] 快速解决

### 场景1：直接查看输出
```powershell
python tools/check_document_quality.py
```

### 场景2：使用管道过滤
```powershell
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-Object -First 20
```

### 场景3：批处理环境
```cmd
tools\run_utf8.bat python tools\check_document_quality.py
```

## [CHECKLIST] 常用命令

### 文档质量检查
```powershell
# 完整输出
python tools/check_document_quality.py

# 只看需改进的文档
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-String "需改进"

# 只看评分
.\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-String "质量评分"
```

### 版本信息管理
```powershell
# 模拟运行
.\tools\run_utf8.ps1 -Script "python tools/add_version_info.py --dry-run"

# 实际添加
.\tools\run_utf8.ps1 -Script "python tools/add_version_info.py"
```

### 链接检查
```powershell
# 检查所有链接
python tools/check_broken_links.py

# 只看断裂链接
.\tools\run_utf8.ps1 -Script "python tools/check_broken_links.py" | Select-String "断裂"
```

### 标题修复
```powershell
# 分析报告
.\tools\run_utf8.ps1 -Script "python tools/fix_heading_levels.py --dry-run"

# 自动修复
.\tools\run_utf8.ps1 -Script "python tools/fix_heading_levels.py"
```

### 代码块修复
```powershell
# 模拟运行
.\tools\run_utf8.ps1 -Script "python tools/fix_code_blocks.py --dry-run"

# 自动修复
.\tools\run_utf8.ps1 -Script "python tools/fix_code_blocks.py"
```

## [BOLT] 别名设置（可选）

在PowerShell配置文件中添加别名：

```powershell
# 编辑配置文件
notepad $PROFILE

# 添加别名
function Run-UTF8 {
    param([string]$Script)
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    Invoke-Expression $Script
}

Set-Alias utf8 Run-UTF8
```

**使用方式**：
```powershell
utf8 "python tools/check_document_quality.py" | Select-Object -First 20
```

## [DEBUG] 问题排查

### 输出仍然是乱码？

**检查1**：PowerShell执行策略
```powershell
Get-ExecutionPolicy
# 如果是 Restricted，需要：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**检查2**：直接测试UTF-8
```powershell
python -c "print('[OK_CHECK] 中文测试')"
# 如果正常，说明脚本编码修复有效
# 如果乱码，使用包装器
```

**检查3**：包装器是否工作
```powershell
.\tools\run_utf8.ps1 -Script "python -c \"print('[OK_CHECK] UTF-8测试')\""
# 应该显示：[OK_CHECK] UTF-8测试
```

### 包装器脚本报错？

**错误**：无法加载文件，因为在此系统上禁止运行脚本

**解决**：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### CMD中使用管道？

使用批处理包装器：
```cmd
tools\run_utf8.bat python tools\check_document_quality.py | more
```

## [CHART] 工具脚本清单

| 脚本 | 功能 | 管道支持 |
|------|------|----------|
| `check_document_quality.py` | 文档质量检查 | [OK_CHECK] 使用包装器 |
| `add_version_info.py` | 添加版本信息 | [OK_CHECK] 使用包装器 |
| `check_broken_links.py` | 链接检查 | [OK_CHECK] 使用包装器 |
| `fix_heading_levels.py` | 标题层级修复 | [OK_CHECK] 使用包装器 |
| `fix_code_blocks.py` | 代码块修复 | [OK_CHECK] 使用包装器 |
| `add_table_of_contents.py` | 添加目录 | [OK_CHECK] 使用包装器 |
| `audit_resource_cleanup.py` | 资源审计 | [OK_CHECK] 使用包装器 |
| `check_pr_status.py` | PR状态检查 | [OK_CHECK] 使用包装器 |

## [TIP] 最佳实践

1. **不需要过滤** → 直接运行
2. **需要管道** → 使用 `run_utf8.ps1`
3. **批处理环境** → 使用 `run_utf8.bat`
4. **频繁使用** → 设置别名或全局编码

## [LINK] 详细文档

完整技术说明和原理分析：[UTF8_ENCODING_GUIDE.md](UTF8_ENCODING_GUIDE.md)
