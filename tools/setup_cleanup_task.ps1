# ============================================
# 监控数据自动清理 - Windows任务计划配置脚本
# 创建每周自动清理任务
# ============================================

$TaskName = "BTC监控数据清理"
$TaskDescription = "每周清理30天前的BTC监控数据，防止磁盘空间占用过多"
# 自动检测脚本所在目录作为工作目录
$WorkingDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $WorkingDirectory "cleanup_monitoring_data.py"
$PythonPath = "python"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "配置Windows任务计划 - 监控数据自动清理" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python是否可用
try {
    $pythonVersion = & $PythonPath --version 2>&1
    Write-Host "✓ Python已找到: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 错误: 找不到Python，请先安装Python或修改PythonPath" -ForegroundColor Red
    exit 1
}

# 检查清理脚本是否存在
if (Test-Path $ScriptPath) {
    Write-Host "✓ 清理脚本已找到: $ScriptPath" -ForegroundColor Green
} else {
    Write-Host "✗ 错误: 清理脚本不存在: $ScriptPath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "即将创建以下任务计划：" -ForegroundColor Yellow
Write-Host "  任务名称: $TaskName" -ForegroundColor White
Write-Host "  执行频率: 每周一次（周日凌晨2点）" -ForegroundColor White
Write-Host "  清理策略: 删除30天前的数据" -ForegroundColor White
Write-Host "  试运行模式: 否（将实际删除文件）" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "是否继续创建任务计划？(Y/N)"

if ($confirm -ne 'Y' -and $confirm -ne 'y') {
    Write-Host "已取消操作" -ForegroundColor Yellow
    exit 0
}

# 创建任务计划
try {
    # 创建触发器：每周日凌晨2点
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2:00AM

    # 创建操作：运行Python清理脚本
    $Action = New-ScheduledTaskAction -Execute $PythonPath `
        -Argument "$ScriptPath --max-age 30" `
        -WorkingDirectory $WorkingDirectory

    # 创建设置
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false

    # 注册任务
    Register-ScheduledTask -TaskName $TaskName `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -Description $TaskDescription `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "✓ 任务计划创建成功！" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "任务详情：" -ForegroundColor Cyan
    Write-Host "  任务名称: $TaskName" -ForegroundColor White
    Write-Host "  执行时间: 每周日凌晨2:00" -ForegroundColor White
    Write-Host "  清理策略: 30天前的数据" -ForegroundColor White
    Write-Host ""
    Write-Host "管理任务：" -ForegroundColor Cyan
    Write-Host "  查看任务: schtasks /query /tn '$TaskName'" -ForegroundColor Gray
    Write-Host "  手动运行: schtasks /run /tn '$TaskName'" -ForegroundColor Gray
    Write-Host "  删除任务: schtasks /delete /tn '$TaskName' /f" -ForegroundColor Gray
    Write-Host "  打开任务计划程序: taskschd.msc" -ForegroundColor Gray
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "✗ 创建任务计划失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "提示: 请以管理员权限运行此脚本" -ForegroundColor Yellow
    exit 1
}
