# 环境诊断: 检测当前使用的Shell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "环境诊断: 检测Shell类型" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检测当前Shell
if ($PSVersionTable.PSVersion) {
    Write-Host "[OK] 当前环境: PowerShell" -ForegroundColor Green
    Write-Host "  版本: $($PSVersionTable.PSVersion)" -ForegroundColor White
    Write-Host "  这是Windows默认的终端环境" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "重要信息:" -ForegroundColor Cyan
    Write-Host "  - PowerShell可以直接运行 .bat 文件" -ForegroundColor White
    Write-Host "  - 但.bat文件内部使用的是CMD语法" -ForegroundColor White
    Write-Host "  - start.bat 使用CMD语法，在PowerShell中也能运行" -ForegroundColor White
    Write-Host ""
    Write-Host "双击start.bat时:" -ForegroundColor Yellow
    Write-Host "  - Windows会使用 CMD.exe 来执行 .bat 文件" -ForegroundColor White
    Write-Host "  - 不是使用 PowerShell" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "[INFO] 当前环境: CMD" -ForegroundColor Green
    Write-Host "  这是Windows传统命令行" -ForegroundColor Yellow
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "start.bat 的执行方式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "方式1: 双击运行 (推荐)" -ForegroundColor White
Write-Host "  - Windows自动使用 CMD.exe 执行" -ForegroundColor Gray
Write-Host "  - 应该显示'启动选择'菜单" -ForegroundColor Gray
Write-Host ""

Write-Host "方式2: 在PowerShell中运行" -ForegroundColor White
Write-Host "  - 命令: .\start.bat" -ForegroundColor Gray
Write-Host "  - PowerShell调用CMD来执行" -ForegroundColor Gray
Write-Host "  - 应该显示'启动选择'菜单" -ForegroundColor Gray
Write-Host ""

Write-Host "方式3: 在CMD中运行" -ForegroundColor White
Write-Host "  - 命令: start.bat" -ForegroundColor Gray
Write-Host "  - 直接使用CMD执行" -ForegroundColor Gray
Write-Host "  - 应该显示'启动选择'菜单" -ForegroundColor Gray
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "如果菜单不显示的排查步骤" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. 检查start.bat文件编码" -ForegroundColor White
Write-Host "   - 应该是 ANSI 或 UTF-8 without BOM" -ForegroundColor Gray
$file = Get-Item "F:\Qoder\btc-collision-engine\start.bat"
Write-Host "   - 文件大小: $($file.Length) 字节" -ForegroundColor Gray
Write-Host ""

Write-Host "2. 检查是否有语法错误" -ForegroundColor White
Write-Host "   - 运行: cmd /c F:\Qoder\btc-collision-engine\start.bat --help" -ForegroundColor Gray
Write-Host ""

Write-Host "3. 查看DEBUG输出" -ForegroundColor White
Write-Host "   - start.bat中已添加DEBUG信息" -ForegroundColor Gray
Write-Host "   - 应该看到: [DEBUG] SHOW_START_CHOICE set to 1" -ForegroundColor Gray
Write-Host ""

Write-Host "4. 手动测试关键逻辑" -ForegroundColor White
Write-Host "   - 运行: .\test_cmd_environment.bat (在CMD中)" -ForegroundColor Gray
Write-Host "   - 运行: .\test_powershell_environment.ps1 (在PowerShell中)" -ForegroundColor Gray
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "快速测试" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$choice = Read-Host "是否现在测试 start.bat? (y/n)"
if ($choice -eq 'y' -or $choice -eq 'Y') {
    Write-Host ""
    Write-Host "正在执行 start.bat..." -ForegroundColor Yellow
    Write-Host "观察是否显示'启动选择'菜单" -ForegroundColor Yellow
    Write-Host ""
    
    # 使用cmd.exe执行，模拟双击行为
    & cmd.exe /c "cd /d F:\Qoder\btc-collision-engine && start.bat"
} else {
    Write-Host ""
    Write-Host "已跳过测试" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
pause
