@echo off
chcp 65001 >nul
title 忍者必须死自动化脚本

echo ========================================
echo 忍者必须死智能悬赏令自动化脚本
echo ========================================
echo.
echo 请选择要运行的程序:
echo.
echo 1. 智能悬赏令自动化 (auto_click_advanced.py)
echo 2. 仓库自动化 (warehouse_automation.py)
echo.
set /p choice="请输入选项 (1 或 2): "

if "%choice%"=="1" (
    set script=auto_click_advanced.py
    echo.
    echo 正在启动智能悬赏令自动化...
) else if "%choice%"=="2" (
    set script=warehouse_automation.py
    echo.
    echo 正在启动仓库自动化...
) else (
    echo.
    echo [错误] 无效选项，请输入 1 或 2
    pause
    exit /b 1
)

echo.
echo ========================================
echo.

REM 激活虚拟环境并运行程序
call .venv\Scripts\activate.bat
python %script%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo [错误] 程序运行出错
    echo ========================================
    pause
)

deactivate
