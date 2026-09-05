# -*- coding: utf-8 -*-
"""M6.2 冒烟：进程内起服务 -> 走通 解析/答卷/出卡/重算/历史/K线/必需闸门/目录/页面。
运行：python scripts/smoke_web_api.py
"""
import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from iris.web.server import app

PORT = 8123
BASE = "http://127.0.0.1:%d" % PORT


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> None:
    cfg = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(cfg)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    ok = []
    try:
        for _ in range(60):
            try:
                get("/api/health")
                break
            except Exception:
                time.sleep(0.2)

        # 页面与静态
        idx = get("/")
        assert "Iris" in idx, "首页缺少标题"
        ok.append("GET / 页面(%d 字符)" % len(idx))
        assert get("/static/app.js").startswith("/* Iris"), "app.js 缺失"
        assert len(get("/static/style.css")) > 500, "style.css 缺失"
        ok.append("静态资源离线可用")

        # 解析（自动）
        r1 = post("/api/resolve", {"text": "https://item.jd.com/10086.html 华硕 RTX 5080 TUF 显卡 16G"})
        assert r1["sku_id"] == "rtx5080-asus-tuf-mid", r1
        assert r1["flow"] == "optional" and len(r1["questions"]) == 9
        ok.append("resolve: sku=%s 9 屏" % r1["sku_id"])

        # 答卷出卡（GPU 剧本）
        ans = {"purpose": "游戏", "deadline": "none", "usage": "high",
               "budget": "flexible", "alt": "yes", "want_need": "hedonic",
               "price_view": "up", "supply": "yes",
               "dq1": "wait", "dq2": "now", "dq3": "wait"}
        r2 = post("/api/answer", {"product": {"name": "RTX 5080", "category": "显卡",
                                              "source": "text"},
                                  "sku_id": "rtx5080-asus-tuf-mid", "answers": ans})
        sid = r2["session_id"]
        card = r2["card"]
        assert sid and card
        d = card["decision"]
        assert d["p2"]["n_scenarios"] > 0 and card["alternatives"]["rows"]
        assert card["evidence"] and card["kline"]
        ok.append("answer: rec=%s light=%s p2=%.2f evidence=%d kline=%d根"
                  % (d["recommendation"], d["traffic_light"],
                     d["p2"]["probability"], len(card["evidence"]),
                     len(card["kline"])))

        # 假设编辑重算 + 历史回看
        r3 = post("/api/recompute", {"session_id": sid,
                                     "overrides": {"deadline": "within_30",
                                                   "wait_tier": "low"}})
        assert len(r3["history"]) == 1
        h = r3["history"][0]
        assert h["overrides"]["deadline"] == "within_30"
        assert r3["card"]["decision"]["window_days"] == 30
        ok.append("recompute: rec=%s p2=%.2f 历史=%d 条（window=%d）"
                  % (r3["card"]["decision"]["recommendation"],
                     r3["card"]["decision"]["p2"]["probability"],
                     len(r3["history"]),
                     r3["card"]["decision"]["window_days"]))
        # 非法覆盖被拒
        try:
            post("/api/recompute", {"session_id": sid, "overrides": {"deadline": "bogus"}})
            raise AssertionError("非法值未被拒绝")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            ok.append("非法覆盖 -> HTTP 400")

        # 重置回问卷原答案
        r5 = post("/api/recompute", {"session_id": sid, "overrides": {}})
        assert r5["profile"]["deadline"] == "none"
        assert len(r5["history"]) == 2
        ok.append("重置回问卷原参数（历史 %d 条）" % len(r5["history"]))

        # K 线 svg
        k = get("/api/kline?sku_id=rtx5080-asus-tuf-mid")
        assert k.lstrip().startswith("<svg")
        ok.append("kline svg %.1f KB" % (len(k) / 1024))

        # 必需闸门（无价格数据路径）
        d1 = post("/api/resolve", {"text": "布洛芬缓释胶囊 退烧止痛药"})
        assert d1["sku_id"] is None and d1["flow"] == "essential"
        ok.append("resolve 药品 -> 必需闸门 3 题")
        d2 = post("/api/answer", {"product": d1["product"], "sku_id": None,
                                  "answers": {"purpose": "急用", "urgency": "now",
                                              "budget": "mid"}})
        assert d2["no_data"] is True and d2["card"] is None
        assert "必需" in d2["note"]
        ok.append("药品无价格库 -> 明确空态与闸门结论")

        # catalog
        c = json.loads(get("/api/health"))
        ok.append("health: %s" % c["ok"])
    finally:
        server.should_exit = True
        time.sleep(0.3)
    print("\n".join("✓ " + s for s in ok))
    print("SMOKE PASS (%d)" % len(ok))


if __name__ == "__main__":
    main()
