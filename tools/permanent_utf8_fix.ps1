# ============================================
# 永久修复Windows控制台UTF-8编码
# 修改注册表使所有控制台默认使用UTF-8
# ============================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  永久修复Windows控制台UTF-8编码" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] 需要管理员权限!" -ForegroundColor Red
    Write-Host ""
    Write-Host "请以管理员身份运行此脚本:" -ForegroundColor Yellow
    Write-Host "  1. 右键点击PowerShell" -ForegroundColor Yellow
    Write-Host "  2. 选择'以管理员身份运行'" -ForegroundColor Yellow
    Write-Host "  3. 重新运行此脚本" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[INFO] 检测到管理员权限" -ForegroundColor Green
Write-Host ""

# 1. 修改注册表 - 启用UTF-8支持
Write-Host "[1/3] 修改注册表启用UTF-8..." -ForegroundColor Yellow

try {
    $registryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage"
    
    # 备份当前设置
    $currentOEMCP = Get-ItemProperty -Path $registryPath -Name "OEMCP" -ErrorAction SilentlyContinue
    $currentACP = Get-ItemProperty -Path $registryPath -Name "ACP" -ErrorAction SilentlyContinue
    
    if ($currentOEMCP -and $currentACP) {
        Write-Host "  当前设置:" -ForegroundColor Gray
        Write-Host "    OEMCP (控制台代码页): $($currentOEMCP.OEMCP)" -ForegroundColor Gray
        Write-Host "    ACP (ANSI代码页): $($currentACP.ACP)" -ForegroundColor Gray
        Write-Host ""
    }
    
    # 设置为UTF-8 (65001)
    Set-ItemProperty -Path $registryPath -Name "OEMCP" -Value "65001"
    Set-ItemProperty -Path $registryPath -Name "ACP" -Value "65001"
    
    Write-Host "  [PASS] 注册表修改成功" -ForegroundColor Green
    Write-Host "  OEMCP: 65001 (UTF-8)" -ForegroundColor Green
    Write-Host "  ACP: 65001 (UTF-8)" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-Host "  [FAIL] 注册表修改失败: $_" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

# 2. 启用Beta版UTF-8支持 (Windows 10 1903+)
Write-Host "[2/3] 启用Beta版UTF-8全局支持..." -ForegroundColor Yellow

try {
    $betaPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage"
    
    # 检查是否已启用
    $betaValue = Get-ItemProperty -Path $betaPath -Name "UseUTF8ActiveCodePage" -ErrorAction SilentlyContinue
    
    if ($betaValue -and $betaValue.UseUTF8ActiveCodePage -eq 1) {
        Write-Host "  [INFO] Beta版UTF-8已启用" -ForegroundColor Yellow
    } else {
        # 启用Beta UTF-8
        Set-ItemProperty -Path $registryPath -Name "UseUTF8ActiveCodePage" -Value "1"
        Write-Host "  [PASS] Beta版UTF-8已启用" -ForegroundColor Green
    }
    Write-Host ""
    
} catch {
    Write-Host "  [WARN] Beta版UTF-8启用失败(可能不支持): $_" -ForegroundColor Yellow
    Write-Host ""
}

# 3. 设置系统环境变量
Write-Host "[3/3] 设置系统环境变量..." -ForegroundColor Yellow

try {
    # 设置用户级别环境变量
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
    
    # 设置系统级别环境变量(需要管理员)
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Machine")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Machine")
    
    Write-Host "  [PASS] 用户环境变量已设置" -ForegroundColor Green
    Write-Host "  [PASS] 系统环境变量已设置" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-Host "  [WARN] 环境变量设置失败: $_" -ForegroundColor Yellow
    Write-Host ""
}

# 总结
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  永久修复完成!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "需要重启计算机使设置生效:" -ForegroundColor Yellow
Write-Host ""

$restart = Read-Host "是否立即重启计算机? (y/n)"

if ($restart -eq "y" -or $restart -eq "Y") {
    Write-Host ""
    Write-Host "正在重启计算机..." -ForegroundColor Yellow
    Restart-Computer -Force
} else {
    Write-Host ""
    Write-Host "请手动重启计算机使设置生效。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "重启后,所有Python脚本将正确显示中文,不会出现乱码。" -ForegroundColor White
    Write-Host ""
}

pause
