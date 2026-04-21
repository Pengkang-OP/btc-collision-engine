@echo off
REM UTF-8编码设置批处理文件
REM 解决Windows CMD管道破坏Python UTF-8输出的问题
REM
REM 使用方法:
REM   tools\run_utf8.bat python tools\check_document_quality.py
REM   tools\run_utf8.bat python tools\add_version_info.py --dry-run

REM 设置控制台代码页为UTF-8
chcp 65001 >nul 2>&1

REM 执行命令
%*
