@echo off
chcp 65001 >nul
echo ========================================
echo   CryptoAssistant 后端启动脚本
echo ========================================
echo.

cd /d "%~dp0\..\backend"

echo [1/2] 检查Python环境...
python --version 2>nul
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.12+
    pause
    exit /b 1
)

echo [2/2] 启动后端服务...
echo.
echo 访问 API 文档: http://localhost:8000/docs
echo 按 Ctrl+C 停止服务
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
