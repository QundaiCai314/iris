# -*- coding: utf-8 -*-
"""M6.2 本地启动：python scripts/serve_web.py  ->  http://127.0.0.1:8123
（FastAPI + uvicorn；纯本地、静态前端无外网依赖。）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

if __name__ == "__main__":
    print("Iris Web 启动：http://127.0.0.1:8123  （Ctrl+C 停止）")
    uvicorn.run("iris.web.server:app", host="127.0.0.1", port=8123,
                log_level="warning")
