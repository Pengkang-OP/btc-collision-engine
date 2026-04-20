# ============================================
# GPU监控依赖检查和安装脚本
# ============================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "GPU监控依赖检查和安装" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python
Write-Host "[1/4] 检查Python环境..." -ForegroundColor Yellow
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "✓ Python已找到: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python未找到，请先安装Python 3.7+" -ForegroundColor Red
    exit 1
}

# 检查PyOpenCL
Write-Host ""
Write-Host "[2/4] 检查PyOpenCL..." -ForegroundColor Yellow
try {
    & python -c "import pyopencl; print('PyOpenCL版本:', pyopencl.VERSION_TEXT)" 2>$null
    Write-Host "✓ PyOpenCL已安装" -ForegroundColor Green
    $pyopencl_installed = $true
} catch {
    Write-Host "✗ PyOpenCL未安装" -ForegroundColor Red
    $pyopencl_installed = $false
}

# 检查OpenCL驱动
Write-Host ""
Write-Host "[3/4] 检查OpenCL驱动..." -ForegroundColor Yellow

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
    Write-Host "✓ OpenCL驱动正常" -ForegroundColor Green
    Write-Host $gpu_info
} else {
    Write-Host "⚠ 无法检测OpenCL驱动" -ForegroundColor Yellow
}

# 安装建议
Write-Host ""
Write-Host "[4/4] 安装建议" -ForegroundColor Yellow
Write-Host ""

if ($pyopencl_installed) {
    Write-Host "✓ PyOpenCL已安装，GPU监控可以直接使用！" -ForegroundColor Green
    Write-Host ""
    Write-Host "测试GPU监控：" -ForegroundColor Cyan
    Write-Host "  python src\monitoring\gpu_monitor.py" -ForegroundColor Gray
} else {
    Write-Host "PyOpenCL未安装，需要安装才能启用GPU监控" -ForegroundColor Red
    Write-Host ""
    Write-Host "安装步骤：" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "方法1: 使用pip安装（推荐）" -ForegroundColor Yellow
    Write-Host "  pip install pyopencl" -ForegroundColor Gray
    Write-Host ""
    Write-Host "方法2: 如果方法1失败，尝试预编译版本" -ForegroundColor Yellow
    Write-Host "  pip install pyopencl-wheel" -ForegroundColor Gray
    Write-Host ""
    Write-Host "方法3: 从源码编译（需要Visual Studio Build Tools）" -ForegroundColor Yellow
    Write-Host "  1. 安装Visual Studio Build Tools 2019+" -ForegroundColor Gray
    Write-Host "  2. pip install pyopencl" -ForegroundColor Gray
    Write-Host ""
    Write-Host "注意: PyOpenCL需要OpenCL驱动支持" -ForegroundColor Yellow
    Write-Host "  - Intel GPU: 通常已预装OpenCL驱动" -ForegroundColor Gray
    Write-Host "  - NVIDIA GPU: 安装NVIDIA显卡驱动即可" -ForegroundColor Gray
    Write-Host "  - AMD GPU: 安装AMD显卡驱动即可" -ForegroundColor Gray
    Write-Host ""
    
    $install = Read-Host "是否现在安装PyOpenCL？(Y/N)"
    if ($install -eq 'Y' -or $install -eq 'y') {
        Write-Host ""
        Write-Host "正在安装PyOpenCL..." -ForegroundColor Yellow
        & python -m pip install pyopencl
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✓ PyOpenCL安装成功！" -ForegroundColor Green
            Write-Host ""
            Write-Host "测试GPU监控：" -ForegroundColor Cyan
            Write-Host "  python src\monitoring\gpu_monitor.py" -ForegroundColor Gray
        } else {
            Write-Host ""
            Write-Host "✗ PyOpenCL安装失败" -ForegroundColor Red
            Write-Host ""
            Write-Host "请尝试上述其他安装方法" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "完成" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
