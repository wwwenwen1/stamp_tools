@echo off
chcp 65001 >nul
cd /d "D:\stamp_tool"
echo.
echo ============================================
echo   正在启动 合同批量盖章工具...
echo ============================================
echo.
python main.py
pause
