@echo off
chcp 65001 >nul
echo ================================================================================
echo   GPU碰撞引擎 - 异步优化版本启动
echo ================================================================================
echo.
echo 配置: config.intel_arc.json
echo  - Batch Size: 1,000,000
echo  - 异步执行: 已启用(双缓冲)
echo  - GPU: Intel Arc A770
echo.
echo 正在启动...
echo.

python key_collision_cli.py --config config.intel_arc.json -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

pause
