@echo off
chcp 65001 > nul
echo ========================================
echo BTC 碰撞引擎 - 命令行模式
echo ========================================
echo.
echo 用法示例:
echo.
echo   随机碰撞:
echo     python key_collision_cli.py -t 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -m random
echo.
echo   范围扫描:
echo     python key_collision_cli.py -f targets.txt -m range --start 1 --end FFFFFFFF
echo.
echo   查看全部选项:
echo     python key_collision_cli.py --help
echo.
python key_collision_cli.py %*
pause
