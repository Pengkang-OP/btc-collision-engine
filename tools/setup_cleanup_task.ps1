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

Write-Output "============================================"
Write-Output "配置Windows任务计划 - 监控数据自动清理"
Write-Output "============================================"
Write-Output ""

# 检查Python是否可用
try {
    $pythonVersion = & $PythonPath --version 2>&1
    Write-Output "✓ Python已找到: $pythonVersion"
} catch {
    Write-Output "✗ 错误: 找不到Python，请先安装Python或修改PythonPath"
    exit 1
}

# 检查清理脚本是否存在
if (Test-Path $ScriptPath) {
    Write-Output "✓ 清理脚本已找到: $ScriptPath"
} else {
    Write-Output "✗ 错误: 清理脚本不存在: $ScriptPath"
    exit 1
}

Write-Output ""
Write-Output "即将创建以下任务计划："
Write-Output "  任务名称: $TaskName"
Write-Output "  执行频率: 每周一次（周日凌晨2点）"
Write-Output "  清理策略: 删除30天前的数据"
Write-Output "  试运行模式: 否（将实际删除文件）"
Write-Output ""

$confirm = Read-Host "是否继续创建任务计划？(Y/N)"

if ($confirm -ne 'Y' -and $confirm -ne 'y') {
    Write-Output "已取消操作"
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

    Write-Output ""
    Write-Output "============================================"
    Write-Output "✓ 任务计划创建成功！"
    Write-Output "============================================"
    Write-Output ""
    Write-Output "任务详情："
    Write-Output "  任务名称: $TaskName"
    Write-Output "  执行时间: 每周日凌晨2:00"
    Write-Output "  清理策略: 30天前的数据"
    Write-Output ""
    Write-Output "管理任务："
    Write-Output "  查看任务: schtasks /query /tn '$TaskName'"
    Write-Output "  手动运行: schtasks /run /tn '$TaskName'"
    Write-Output "  删除任务: schtasks /delete /tn '$TaskName' /f"
    Write-Output "  打开任务计划程序: taskschd.msc"
    Write-Output ""

} catch {
    Write-Output ""
    Write-Output "✗ 创建任务计划失败: $_"
    Write-Output ""
    Write-Output "提示: 请以管理员权限运行此脚本"
    exit 1
}
