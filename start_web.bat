@echo off
chcp 65001 >nul
echo ==============================================================================
echo        Iris (鸢尾) · 个人消费购买时机量化决策引擎
echo ==============================================================================
echo [1/3] 检查 Python 环境依赖...
python -c "import fastapi, uvicorn" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 正在安装必要 Web 依赖 (fastapi, uvicorn)...
    pip install -r requirements.txt --quiet
)
python scripts/seed_demo_user.py
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 自动播种测试账号失败，继续启动...
)
echo [2/3] 启动 Web 终端服务 (http://127.0.0.1:8123)...
echo   * 评委测试账号: reviewer / 密码: iris2026 (或直接匿名体验)
echo   * 正在启动浏览器...
start http://127.0.0.1:8123
echo [3/3] 服务运行中，按 Ctrl+C 可停止服务
python scripts/serve_web.py
pause
