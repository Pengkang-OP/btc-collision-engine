# ============================================
# Windows PowerShell UTF-8编码设置脚本
# 解决Python脚本中文乱码问题
# ============================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  设置Windows控制台UTF-8编码" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. 设置代码页为UTF-8
Write-Host "[1/4] 设置代码页为UTF-8 (65001)..." -ForegroundColor Yellow
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
Write-Host "  [PASS] 代码页设置成功" -ForegroundColor Green
Write-Host ""

# 2. 设置Python环境变量
Write-Host "[2/4] 设置Python UTF-8环境变量..." -ForegroundColor Yellow
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
Write-Host "  [PASS] PYTHONIOENCODING=utf-8" -ForegroundColor Green
Write-Host "  [PASS] PYTHONUTF8=1" -ForegroundColor Green
Write-Host ""

# 3. 设置PowerShell输出编码
Write-Host "[3/4] 设置PowerShell输出编码..." -ForegroundColor Yellow
$OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "  [PASS] PowerShell输出编码已设置" -ForegroundColor Green
Write-Host ""

# 4. 验证编码设置
Write-Host "[4/4] 验证编码设置..." -ForegroundColor Yellow
python -c "import sys; print(f'  默认编码: {sys.getdefaultencoding()}'); print(f'  文件系统编码: {sys.getfilesystemencoding()}'); print(f'  标准输出编码: {sys.stdout.encoding}')"
Write-Host ""

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  编码设置完成!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "现在可以运行Python脚本而不会出现乱码:" -ForegroundColor White
Write-Host "  python your_script.py" -ForegroundColor Gray
Write-Host ""
Write-Host "或者直接运行:" -ForegroundColor White
Write-Host "  .\run_gpu_diagnostic.bat" -ForegroundColor Gray
Write-Host ""
