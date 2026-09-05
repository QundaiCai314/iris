# -*- coding: utf-8 -*-
"""SVG K 线渲染（无第三方依赖；A 股习惯：红涨绿跌）。M1 提供，M6 前端复用。"""
from __future__ import annotations
from typing import List, Optional

RED = "#d93a3a"
GREEN = "#21a366"
GRID = "#e2e2e2"
AXIS = "#666666"

def _fmt(v: float) -> str:
    return ("%d" % round(v)) if abs(v) >= 100 else ("%.1f" % v)

def kline_svg(title: str, ohlc: List[dict], out_path: Optional[str] = None,
              width: int = 960, height: int = 360, show_ma: bool = False) -> Optional[str]:
    """ohlc: [{date, open, high, low, close}]，按时间升序。"""
    if not ohlc:
        raise ValueError("无数据可画")
    pad_l, pad_r, pad_t, pad_b = 70, 24, 46, 30
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(ohlc)
    lo = min(x["low"] for x in ohlc)
    hi = max(x["high"] for x in ohlc)
    if hi - lo < 1e-9:
        hi, lo = lo + 1, lo - 1
    span = hi - lo
    lo -= span * 0.06
    hi += span * 0.06

    def y(price: float) -> float:
        return pad_t + plot_h * (1 - (price - lo) / (hi - lo))

    def x(i: int) -> float:
        return pad_l + plot_w * (i + 0.5) / n

    parts = []
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
                 % (width, height, width, height))
    parts.append('<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (width, height))
    parts.append('<text x="%d" y="26" font-size="15" font-family="sans-serif" fill="#222">%s</text>'
                 % (pad_l, _escape(title)))
    # 网格与 Y 轴
    for g in range(6):
        gy = pad_t + plot_h * g / 5.0
        price = hi - (hi - lo) * g / 5.0
        parts.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="1"/>'
                     % (pad_l, gy, pad_l + plot_w, gy, GRID))
        parts.append('<text x="%d" y="%.1f" font-size="11" fill="%s" text-anchor="end">%s</text>'
                     % (pad_l - 8, gy + 4, AXIS, _fmt(price)))
    # 蜡烛
    cw = max(2.0, plot_w / n * 0.55)
    for i, k in enumerate(ohlc):
        up = k["close"] >= k["open"]
        color = RED if up else GREEN
        cx = x(i)
        oy, cy = y(k["open"]), y(k["close"])
        hy, ly = y(k["high"]), y(k["low"])
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                     % (cx, hy, cx, ly, color))
        top, bot = min(oy, cy), max(oy, cy)
        if bot - top < 1:
            bot = top + 1
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                     % (cx - cw / 2, top, cw, max(1.0, bot - top), color))
    # X 轴日期标签（首中尾）
    for idx in (0, n // 2, n - 1):
        parts.append('<text x="%.1f" y="%d" font-size="10" fill="%s" text-anchor="middle">%s</text>'
                     % (x(idx), height - 8, AXIS, ohlc[idx]["date"]))
    parts.append('</svg>')
    svg_text = "\n".join(parts)
    if out_path is None:
        return svg_text
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_text)
    return None

def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
