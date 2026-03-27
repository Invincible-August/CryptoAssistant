@echo off
chcp 65001 >nul
echo ========================================
echo   CryptoAssistant 项目初始化脚本
echo ========================================
echo.
echo 此脚本将：
echo   1. 安装后端Python依赖
echo   2. 安装前端Node.js依赖
echo   3. 创建管理员账户
echo   4. 导入示例数据
echo.
echo 前提条件：
echo   - 已安装 Python 3.12+
echo   - 已安装 Node.js 20+
echo   - 已安装并启动 PostgreSQL
echo   - 已创建数据库 crypto_assistant
echo   - 已配置 .env 文件
echo.
pause

echo.
echo [1/4] 安装后端依赖...
cd /d "%~dp0\..\backend"
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/4] 安装前端依赖...
cd /d "%~dp0\..\frontend"
call npm install
if errorlevel 1 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/4] 创建管理员账户...
cd /d "%~dp0\.."
python scripts/create_admin.py

echo.
echo [4/4] 导入示例数据...
python scripts/seed_demo_data.py

echo.
echo ========================================
echo   初始化完成！
echo ========================================
echo.
echo 启动方式：
echo   后端: 运行 scripts\start_backend.bat
echo   前端: 运行 scripts\start_frontend.bat（新终端）
echo.
echo 访问地址：
echo   前端: http://localhost:5173
echo   API:  http://localhost:8000/docs
echo   账号: admin / admin123456
echo.
pause
