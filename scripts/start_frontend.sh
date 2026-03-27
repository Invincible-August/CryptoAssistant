#!/bin/bash
echo "========================================"
echo "  CryptoAssistant 前端启动脚本"
echo "========================================"
echo

cd "$(dirname "$0")/../frontend"

echo "[1/2] 检查Node.js环境..."
node --version 2>/dev/null || { echo "[错误] 未找到Node.js"; exit 1; }

echo "[2/2] 启动前端开发服务器..."
echo
echo "访问前端界面: http://localhost:5173"
echo "按 Ctrl+C 停止服务"
echo

npm run dev
