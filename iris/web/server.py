# -*- coding: utf-8 -*-
"""M6.2/M6.3 Web 服务：本地 127.0.0.1:8123（demo 全链路）。

启动：python scripts/serve_web.py（或 uvicorn iris.web.server:app --port 8123）

API：
  GET  /                  前端页面（离线静态，无 CDN）
  GET  /api/catalog       库内商品/SKU 与现价
  POST /api/resolve       文本/手动确认 -> {product, sku_id, questions, flow, message}
  POST /api/answer        画像答案 -> profile + 全字段决策卡（登记 session）
  POST /api/recompute     {session_id, overrides} 假设编辑重算；历史可回看
  GET  /api/kline?sku_id= 自绘 SVG 周 K 线（无外网依赖）

口径/数据与 CLI 同一管线（iris/agent/pipeline.py）；会话仅内存，TTL 2 小时。
"""
from __future__ import annotations
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from iris.agent import pipeline
from iris.agent.needs import ENUMS, build_questions, run_questionnaire, validate_profile
from iris.core.prices import resample_ohlc
from iris.core.svgk import kline_svg

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(APP_DIR, "static")
ROOT = os.path.dirname(os.path.dirname(APP_DIR))

SESSION_TTL_SEC = 2 * 3600
SESSION_MAX = 64
# 可编辑重算的画像字段（M6.3 假设编辑器白名单）
EDITABLE = ["deadline", "usage_intensity", "hedonic", "wait_tier",
            "budget_tier", "price_view", "supply_news", "alt_acceptable",
            "purpose"]

app = FastAPI(title="Iris 鸢尾 · 购买时机决策卡", version="0.3.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_sessions: Dict[str, dict] = {}


def _prune() -> None:
    now = time.time()
    stale = [k for k, v in _sessions.items()
             if now - v["created"] > SESSION_TTL_SEC]
    for k in stale:
        _sessions.pop(k, None)
    while len(_sessions) > SESSION_MAX:
        _sessions.pop(next(iter(_sessions)), None)


class ResolveBody(BaseModel):
    text: str = ""
    name: Optional[str] = None          # 手动确认商品名
    category: Optional[str] = None      # 手动确认品类


class AnswerBody(BaseModel):
    product: Dict
    sku_id: Optional[str] = None
    answers: Dict = Field(default_factory=dict)


class RecomputeBody(BaseModel):
    session_id: str
    overrides: Dict = Field(default_factory=dict)


def _answer_fn(answers: Dict):
    def fn(q):
        return answers.get(q["id"]) or "none"
    return fn


def _validate_overrides(overrides: Dict) -> List[str]:
    errs = []
    for k, v in overrides.items():
        if k not in EDITABLE:
            errs.append("不可编辑字段: %s" % k)
            continue
        if k == "purpose":
            if not isinstance(v, str) or not v:
                errs.append("purpose 非法: %r" % v)
        elif v not in ENUMS.get(k, ()):
            errs.append("%s 非法值: %r" % (k, v))
    return errs


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/catalog")
def catalog():
    d = pipeline.load_demo()
    out = []
    for pid, p in d["products"].items():
        skus = []
        for sid, s in d["skus"].items():
            if s.product_id != pid:
                continue
            price = d["price_map"].get(sid)
            if price is None:
                continue
            skus.append({"sku_id": sid, "brand": s.brand, "tier": s.tier,
                         "channel": s.channel, "price": price})
        out.append({"product_id": pid, "name": p.name, "launch_date": p.launch_date,
                    "skus": skus})
    return {"products": out,
            "note": "demo 库（合成数据，截至 2026-09-03）：仅显卡场景"}


@app.post("/api/resolve")
def resolve(b: ResolveBody):
    text = (b.text or "").strip()
    if b.category:                                   # 手动确认路径
        product = {"name": (b.name or text or "未命名商品")[:40],
                   "category": b.category, "source": "manual"}
        sku_id = pipeline.match_sku((b.name or text)) if b.category == "显卡" else None
        message = ""
    else:
        if not text:
            raise HTTPException(400, "text 为空：请粘贴商品链接或描述")
        res = pipeline.resolve_product(text)
        product, sku_id, message = res["product"], res["sku_id"], res["message"]
    if not product.get("category"):
        return {"product": product, "sku_id": None, "questions": [],
                "flow": None, "message": message or "请手动确认商品名与品类"}
    qs, flow = build_questions(product)
    return {"product": product, "sku_id": sku_id, "questions": qs,
            "flow": flow, "message": message}


@app.post("/api/answer")
def answer(b: AnswerBody):
    product = b.product or {}
    if not product.get("category"):
        raise HTTPException(400, "缺少品类（先 /api/resolve 或手动确认）")
    profile = run_questionnaire(product, _answer_fn(b.answers or {}))
    errs = validate_profile(profile)
    if errs:
        raise HTTPException(400, "画像校验失败: %s" % "; ".join(errs))
    pd = profile.to_dict()
    sid = None
    card = None
    if b.sku_id:
        sid = uuid.uuid4().hex[:12]
        _prune()
        _sessions[sid] = {"created": time.time(), "product": product,
                          "sku_id": b.sku_id, "base_profile": dict(pd),
                          "profile": dict(pd), "history": []}
        card = pipeline.build_card(pd, b.sku_id)
    return {"session_id": sid, "profile": pd, "card": card,
            "no_data": b.sku_id is None,
            "note": ("" if b.sku_id
                     else ("必需品类：时点不重要，只做渠道比价（R05 §1）。"
                            "demo 库暂无该品类渠道价，出不了量化卡。"
                            if profile.necessity == "essential"
                            else "demo 库暂无该型号价格数据，出不了量化卡。"))}


@app.post("/api/recompute")
def recompute(b: RecomputeBody):
    sess = _sessions.get(b.session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期：请重新走一遍流程")
    overrides = dict(b.overrides or {})
    errs = _validate_overrides(overrides)
    if errs:
        raise HTTPException(400, "; ".join(errs))
    profile = dict(sess["base_profile"])
    profile.update(overrides)
    sess["profile"] = profile
    card = pipeline.build_card(profile, sess["sku_id"])
    d = card["decision"]
    comp = d.get("decomposition") or {}
    sess["history"].append({
        "at": datetime.now().isoformat(timespec="seconds"),
        "overrides": dict(overrides),
        "recommendation": d["recommendation"],
        "traffic_light": d["traffic_light"],
        "p2": d["p2"]["probability"],
        "net_pct": comp.get("net_pct"),
    })
    return {"card": card, "profile": profile,
            "history": list(sess["history"])}


@app.get("/api/kline")
def kline(sku_id: str, weeks: int = 0):
    d = pipeline.load_demo()
    if sku_id not in d["skus"]:
        raise HTTPException(404, "未知 SKU: %s" % sku_id)
    ser = d["series"][sku_id]
    ohlc = resample_ohlc(ser.points, freq_days=7)
    if weeks > 0:
        ohlc = ohlc[-weeks:]
    sku = d["skus"][sku_id]
    title = "%s %s %s · 周线（合成演示数据）" % (sku.brand.upper(),
                                             sku.product_id.upper(), sku.tier)
    svg = kline_svg(title, ohlc, None)
    return Response(content=svg, media_type="image/svg+xml; charset=utf-8")
