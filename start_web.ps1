# Iris Web 服务一键启动脚本 (PowerShell)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Iris 量化时机决策引擎"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "       Iris (鸢尾) · 个人消费购买时机量化决策引擎" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "[1/3] 初始化评委体验账号..." -ForegroundColor Yellow
python scripts/seed_demo_user.py

Write-Host "[2/3] 打开默认浏览器 (http://127.0.0.1:8123)..." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:8123"

Write-Host "[3/3] 启动服务中... (评委账号: reviewer / 密码: iris2026)" -ForegroundColor Green
python scripts/serve_web.py
