# PowerShell UTF-8输出包装器
# 解决PowerShell管道破坏Python UTF-8输出的问题
#
# 使用方法:
#   .\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py"
#   .\tools\run_utf8.ps1 -Script "python tools/add_version_info.py --dry-run" | Select-Object -First 20

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Script
)

# 设置PowerShell输出编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 执行脚本
Invoke-Expression $Script
