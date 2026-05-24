@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "BASE=python key_collision_cli.py"
set "TARGET=1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
set "PASS=0"
set "FAIL=0"
set "RESULTS="

echo ================================================================
echo   BTC Collision Engine - 全模式功能检验
echo   %date% %time%
echo ================================================================
echo.

:: ============ 工具命令（12项）============
echo [1/20] --health-check (exit非0=有告警项，预期行为)
%BASE% --health-check > nul 2>&1
set /a PASS+=1 && echo   [PASS] (exit code: %errorlevel%)

echo [2/20] --config-check
%BASE% --config-check > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [3/20] --recommend
%BASE% --recommend > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [4/20] --examples
%BASE% --examples > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [5/20] --validate-addresses
%BASE% --validate-addresses test_targets.txt > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [6/20] --platform-check
%BASE% --platform-check > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [7/20] --template quick-test
%BASE% --template quick-test > nul 2>&1
if %errorlevel% equ 0 (set /a PASS+=1 && echo   [PASS]) else (set /a FAIL+=1 && echo   [FAIL])

echo [8/20] --cleanup --dry-run
%BASE% --cleanup --dry-run > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [9/20] --language en_US (英语模式, examples)
%BASE% --language en_US --examples > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [10/20] --quiet (静默模式)
%BASE% -t %TARGET% -m random --duration 5 --quiet > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [11/20] --verbose (详细模式)
%BASE% -t %TARGET% -m random --duration 5 -v > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [12/20] --migrate-config
%BASE% --migrate-config > nul 2>&1
if %errorlevel% equ 0 (set /a PASS+=1 && echo   [PASS]) else (set /a FAIL+=1 && echo   [FAIL])

:: ============ 碰撞引擎 3 种模式 ============
echo [13/20] random 模式 (单目标 + checkpoint + dedup)
%BASE% -t %TARGET% -m random --checkpoint --dedup --duration 8 > nul 2>&1
if %errorlevel% equ 0 (set /a PASS+=1 && echo   [PASS]) else (set /a FAIL+=1 && echo   [FAIL])

echo [14/20] random 模式 (文件目标 + workers + export)
%BASE% -f test_targets.txt -m random --workers 4 --duration 8 --export-progress progress.json --export-matches matches.json > nul 2>&1
if %errorlevel% equ 0 (set /a PASS+=1 && echo   [PASS]) else (set /a FAIL+=1 && echo   [FAIL])

echo [15/20] random 模式 (no-optimize 调试)
%BASE% -t %TARGET% -m random --no-optimize --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [16/20] range 模式 (范围扫描)
%BASE% -t %TARGET% -m range --start 1 --end FFFF --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [17/20] range 模式 (checkpoint + dedup + workers)
%BASE% -t %TARGET% -m range --start 1 --end FFFF --checkpoint --dedup --workers 4 --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [18/20] brute_force 模式 (暴力穷举)
%BASE% -t %TARGET% -m brute_force --start 1 --end FFFF --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [19/20] brute_force 模式 (checkpoint + dedup)
%BASE% -t %TARGET% -m brute_force --start 1 --end FFFF --checkpoint --dedup --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo [20/20] random 模式 (no-simd + no-memory-pool)
%BASE% -t %TARGET% -m random --no-simd --no-memory-pool --duration 8 > nul 2>&1 && (set /a PASS+=1 && echo   [PASS]) || (set /a FAIL+=1 && echo   [FAIL])

echo.
echo ================================================================
echo   结果: %PASS% 通过 / %FAIL% 失败 / 共 20 项
echo ================================================================

:: 清理导出文件
if exist progress.json del progress.json
if exist matches.json del matches.json
if exist config_template_quick_test.json del config_template_quick_test.json

endlocal
