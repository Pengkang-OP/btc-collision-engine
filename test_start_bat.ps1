# 测试start.bat脚本
Write-Host "测试start.bat脚本..."

# 模拟用户输入1
$testInput = "1"

# 运行start.bat并提供输入
Write-Host "模拟用户输入: $testInput"
$testInput | .\start.bat

Write-Host "测试完成!"
