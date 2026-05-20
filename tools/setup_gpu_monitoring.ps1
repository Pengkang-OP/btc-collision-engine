# ============================================
# GPU监控依赖检查和安装脚本
# ============================================

Write-Output "============================================"
Write-Output "GPU监控依赖检查和安装"
Write-Output "============================================"
Write-Output ""

# 检查Python
Write-Output "[1/4] 检查Python环境..."
try {
    $pythonVersion = & python --version 2>&1
    Write-Output "✓ Python已找到: $pythonVersion"
} catch {
    Write-Output "✗ Python未找到，请先安装Python 3.7+"
    exit 1
}

# 检查PyOpenCL
Write-Output ""
Write-Output "[2/4] 检查PyOpenCL..."
try {
    & python -c "import pyopencl; print('PyOpenCL版本:', pyopencl.VERSION_TEXT)" 2>$null
    Write-Output "✓ PyOpenCL已安装"
    $pyopencl_installed = $true
} catch {
    Write-Output "✗ PyOpenCL未安装"
    $pyopencl_installed = $false
}

# 检查OpenCL驱动
Write-Output ""
Write-Output "[3/4] 检查OpenCL驱动..."

# 尝试获取GPU信息
$gpu_info = & python -c "
try:
    import pyopencl as cl
    platforms = cl.get_platforms()
    gpu_count = 0
    for platform in platforms:
        devices = platform.get_devices(device_type=cl.device_type.GPU)
        gpu_count += len(devices)
        for device in devices:
            print(f'  GPU: {device.name}')
            print(f'  厂商: {device.vendor}')
            print(f'  显存: {device.global_mem_size / (1024**3):.1f} GB')
    if gpu_count == 0:
        print('  未找到GPU设备')
except Exception as e:
    print(f'  错误: {e}')
" 2>&1

if ($gpu_info) {
    Write-Output "✓ OpenCL驱动正常"
    Write-Output $gpu_info
} else {
    Write-Output "⚠ 无法检测OpenCL驱动"
}

# 安装建议
Write-Output ""
Write-Output "[4/4] 安装建议"
Write-Output ""

if ($pyopencl_installed) {
    Write-Output "✓ PyOpenCL已安装，GPU监控可以直接使用！"
    Write-Output ""
    Write-Output "测试GPU监控："
    Write-Output "  python src\monitoring\gpu_monitor.py"
} else {
    Write-Output "PyOpenCL未安装，需要安装才能启用GPU监控"
    Write-Output ""
    Write-Output "安装步骤："
    Write-Output ""
    Write-Output "方法1: 使用pip安装（推荐）"
    Write-Output "  pip install pyopencl"
    Write-Output ""
    Write-Output "方法2: 如果方法1失败，尝试预编译版本"
    Write-Output "  pip install pyopencl-wheel"
    Write-Output ""
    Write-Output "方法3: 从源码编译（需要Visual Studio Build Tools）"
    Write-Output "  1. 安装Visual Studio Build Tools 2019+"
    Write-Output "  2. pip install pyopencl"
    Write-Output ""
    Write-Output "注意: PyOpenCL需要OpenCL驱动支持"
    Write-Output "  - Intel GPU: 通常已预装OpenCL驱动"
    Write-Output "  - NVIDIA GPU: 安装NVIDIA显卡驱动即可"
    Write-Output "  - AMD GPU: 安装AMD显卡驱动即可"
    Write-Output ""
    
    $install = Read-Host "是否现在安装PyOpenCL？(Y/N)"
    if ($install -eq 'Y' -or $install -eq 'y') {
        Write-Output ""
        Write-Output "正在安装PyOpenCL..."
        & python -m pip install pyopencl
        if ($LASTEXITCODE -eq 0) {
            Write-Output ""
            Write-Output "✓ PyOpenCL安装成功！"
            Write-Output ""
            Write-Output "测试GPU监控："
            Write-Output "  python src\monitoring\gpu_monitor.py"
        } else {
            Write-Output ""
            Write-Output "✗ PyOpenCL安装失败"
            Write-Output ""
            Write-Output "请尝试上述其他安装方法"
        }
    }
}

Write-Output ""
Write-Output "============================================"
Write-Output "完成"
Write-Output "============================================"
Write-Output ""
