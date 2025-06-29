@echo off
chcp 65001 > nul
title 屏幕智能助手 - 完整版

:menu
cls
echo.
echo ========================================
echo        屏幕智能助手 - 完整版
echo ========================================
echo.
echo 请选择操作：
echo.
echo [1] 🚀 启动智能助手 - 现代化界面，完整功能
echo [2] 🔧 清理进程 - 清理卡住的Python进程  
echo [3] ❌ 退出
echo.
set /p choice=请输入选择 (1-3): 

if "%choice%"=="1" goto start_app
if "%choice%"=="2" goto kill_processes
if "%choice%"=="3" goto exit
goto menu

:start_app
echo.
echo 🚀 启动屏幕智能助手...
echo ✨ 特色：现代化界面、简约设计、完整功能
python start_modern_gui.py
pause
goto menu

:kill_processes
echo.
echo 🔧 清理卡住的Python进程...
tasklist | findstr python.exe
echo.
echo 即将终止所有Python进程...
pause
taskkill /f /im python.exe
echo 清理完成！
pause
goto menu

:exit
echo.
echo 👋 感谢使用屏幕智能助手！
timeout /t 2 > nul
exit 