@echo off
chcp 65001 > nul
title 清理卡住的Python进程

echo.
echo ========================================
echo   清理卡住的Python进程
echo ========================================
echo.

echo 🔍 查找Python进程...
tasklist | findstr python.exe

echo.
echo ⚠️  即将终止所有Python进程
echo 📝 这将关闭所有正在运行的Python程序
echo.
pause

echo.
echo 🔄 正在终止Python进程...
taskkill /f /im python.exe

echo.
echo ✅ 清理完成
echo 💡 现在可以重新启动程序
echo.
pause 