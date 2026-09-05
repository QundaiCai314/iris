# -*- coding: utf-8 -*-
"""需求澄清问卷（M4.1/M4.2；出处：R05 + docs/needs-profile.md）。

- 确定性规则版：无 LLM、无随机，同一输入产出同一问题集（M4.4 验收：可复现）。
- 必需闸门：类目规则 + 关键词兜底；命中走 essential 分支（3 题，不问时机）。
- 等待贴现：3 道「现在价 vs 等 N 月省 X%」离散选择题（R05 §3），选等次数 -> wait_tier。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional

# ---------- 品类规则（可扩展；规则出处 R05 §1） ----------

CATEGORY_RULES: Dict[str, dict] = {
    "显卡":     {"necessary": False, "hedonic": "hedonic",
                "purpose": ["游戏", "AI / 跑模型", "3D / 视频创作", "编程 / 日常", "其他"],
                "keywords": ["显卡", "rtx", "gtx", "rx", "gpu", "图形卡"]},
    "游戏机":   {"necessary": False, "hedonic": "hedonic",
                "purpose": ["主机游戏", "派对 / 家庭娱乐", "收藏 / 尝鲜", "其他"],
                "keywords": ["游戏机", "ps5", "xbox", "switch", "掌机"]},
    "手机":     {"necessary": False, "hedonic": "utilitarian",
                "purpose": ["日常通讯", "拍照 / 影像", "游戏", "工作 / 学习", "其他"],
                "keywords": ["手机", "iphone", "mate", "pixel", "小米"]},
    "笔记本":   {"necessary": False, "hedonic": "utilitarian",
                "purpose": ["学习 / 办公", "编程开发", "游戏", "设计 / 剪辑", "其他"],
                "keywords": ["笔记本", "电脑", "thinkpad", "macbook"]},
    "相机":     {"necessary": False, "hedonic": "hedonic",
                "purpose": ["旅行记录", "专业拍摄", "vlog / 直播", "其他"],
                "keywords": ["相机", "微单", "单反", "sony", "canon"]},
    "家电":     {"necessary": False, "hedonic": "utilitarian",
                "purpose": ["换新 / 升级", "刚需替换（坏了）", "新居添置", "其他"],
                "keywords": ["冰箱", "洗衣机", "空调", "电视"]},
    "药品":     {"necessary": True, "hedonic": "utilitarian",
                "purpose": ["急用", "长期用药", "备用 / 常备", "其他"],
                "keywords": ["药", "处方", "维生素", "退烧"]},
    "医疗用品": {"necessary": True, "hedonic": "utilitarian",
                "purpose": ["检测 / 监护", "康复护理", "防护", "其他"],
                "keywords": ["血糖仪", "血压计", "轮椅", "口罩"]},
    "基础食品": {"necessary": True, "hedonic": "utilitarian",
                "purpose": ["日常口粮", "节日 / 送礼", "囤货", "其他"],
                "keywords": ["大米", "粮油", "牛奶", "鸡蛋"]},
}

NECESSARY_EXTRA = ["必需", "急用", "医生", "医院", "处方"]
MODEL_RE = re.compile(r"(?:rtx|gtx|rx|ryzen|core i|酷睿)\s?[0-9]{2,5}[^\u4e00-\u9fff]{0,6}", re.I)


def detect_category(text: str) -> Optional[str]:
    t = text.lower()
    best = None
    for cat, rule in CATEGORY_RULES.items():
        for kw in rule["keywords"]:
            if kw.lower() in t:
                return cat
    return best


def detect_model(text: str) -> Optional[str]:
    m = MODEL_RE.search(text)
    return m.group(0).strip() if m else None


def parse_product_text(text: str) -> Dict:
    """M4.3 规则版：文本 -> 候选 {name, category, source}；失败时 category=None。"""
    cat = detect_category(text)
    model = detect_model(text)
    name = model or (text[:40] if cat else None)
    return {"name": name, "category": cat, "source": "text" if cat else None,
            "raw": text}


# ---------- 画像 ----------

@dataclass
class NeedsProfile:
    product_ref: dict = field(default_factory=dict)
    necessity: str = "optional"
    flow: str = "optional"
    purpose: Optional[str] = None
    deadline: str = "none"
    usage_intensity: str = "low"
    budget_tier: str = "flexible"
    alt_acceptable: str = "no"
    hedonic: str = "utilitarian"
    wait_tier: Optional[str] = None
    price_view: Optional[str] = None
    supply_news: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


ENUMS = {
    "necessity": {"essential", "optional"},
    "flow": {"essential", "optional"},
    "deadline": {"none", "within_30", "within_90", "now"},
    "usage_intensity": {"rarely", "low", "medium", "high"},
    "budget_tier": {"low", "mid", "high", "flexible"},
    "alt_acceptable": {"yes", "no"},
    "hedonic": {"hedonic", "utilitarian"},
    "wait_tier": {"low", "mid", "high"},
    "price_view": {"up", "stable", "down", "uncertain"},
    "supply_news": {"yes", "no"},
}


def validate_profile(p: NeedsProfile) -> List[str]:
    errs = []
    if not p.product_ref.get("category"):
        errs.append("product_ref.category 为空")
    for k, allowed in ENUMS.items():
        v = getattr(p, k)
        if v is not None and v not in allowed:
            errs.append("%s 非法: %r" % (k, v))
    if p.flow == "optional":
        if p.wait_tier is None:
            errs.append("optional 流程缺 wait_tier")
        if p.price_view is None:
            errs.append("optional 流程缺 price_view")
    return errs


# ---------- 问卷生成（确定性） ----------

def _essential_questions(category: str) -> List[dict]:
    rule = CATEGORY_RULES.get(category, {})
    purposes = rule.get("purpose", ["自己用", "家人用", "其他"])
    return [
        {"id": "purpose", "text": "主要用途是？", "type": "choice",
         "options": purposes, "key": "purpose"},
        {"id": "urgency", "text": "多急需要用？", "type": "choice",
         "options": [("现在就要", "now"), ("几天内", "within_30"), ("不着急", "none")],
         "key": "deadline"},
        {"id": "budget", "text": "预算大概在？", "type": "choice",
         "options": [("越低越好（刚需）", "low"), ("合理即可", "mid"),
                     ("愿意为质量多花", "high"), ("没想好", "flexible")],
         "key": "budget_tier"},
    ]


DISCOUNT_QUIZ = [
    {"id": "dq1", "text": "现在就能买；等 2 个月大约省 3%？", "type": "choice",
     "options": [("现在就买", "now"), ("愿意等 2 个月", "wait")], "key": "wait_count"},
    {"id": "dq2", "text": "现在就能买；等 6 个月大约省 10%？", "type": "choice",
     "options": [("现在就买", "now"), ("愿意等 6 个月", "wait")], "key": "wait_count"},
    {"id": "dq3", "text": "现在就能买；等 12 个月大约省 20%？", "type": "choice",
     "options": [("现在就买", "now"), ("愿意等 12 个月", "wait")], "key": "wait_count"},
]


def _optional_questions(category: str) -> List[dict]:
    rule = CATEGORY_RULES.get(category, {})
    purposes = rule.get("purpose", ["工作 / 学习", "娱乐", "其他"])
    return [
        {"id": "purpose", "text": "主要用来做什么？", "type": "choice",
         "options": purposes, "key": "purpose"},
        {"id": "deadline", "text": "最晚什么时候需要？", "type": "choice",
         "options": [("必须马上有", "now"), ("一个月内", "within_30"),
                     ("三个月内", "within_90"), ("不着急，能等到好价", "none")],
         "key": "deadline"},
        {"id": "usage", "text": "预计使用频率？", "type": "choice",
         "options": [("偶尔（每月几次）", "rarely"), ("每周 1-3 次", "low"),
                     ("每周 3-10 小时", "medium"), ("重度（每天用）", "high")],
         "key": "usage_intensity"},
        {"id": "budget", "text": "预算大概在？", "type": "choice",
         "options": [("入门档就够", "low"), ("主流中档", "mid"),
                     ("旗舰 / 顶配", "high"), ("没想好，看性价比", "flexible")],
         "key": "budget_tier"},
        {"id": "alt", "text": "能接受二手或同档次其他品牌吗？", "type": "choice",
         "options": [("都可以", "yes"), ("只接受全新同款", "no"), ("看情况", "yes")],
         "key": "alt_acceptable"},
        {"id": "want_need", "text": "买它更多是「想要」还是「需要」？", "type": "choice",
         "options": [("想要（喜欢 / 升级体验）", "hedonic"), ("需要（影响正事）", "utilitarian")],
         "key": "hedonic_self"},
        {"id": "price_view", "text": "你感觉接下来半年这类东西的价格会？", "type": "choice",
         "options": [("大概率涨", "up"), ("平稳", "stable"), ("会降", "down"), ("说不准", "uncertain")],
         "key": "price_view"},
        {"id": "supply", "text": "最近看到缺货或涨价的消息多吗？", "type": "choice",
         "options": [("有（不少）", "yes"), ("没有", "no")],
         "key": "supply_news"},
    ]


def build_questions(product: dict) -> List[dict]:
    """按品类与必需闸门生成问题屏（贴现 3 小题算一组屏）。确定性。"""
    category = product.get("category") or "未知"
    rule = CATEGORY_RULES.get(category)
    necessary = bool(rule and rule["necessary"]) or any(
        k in (product.get("name") or "") for k in NECESSARY_EXTRA)
    if necessary:
        return _essential_questions(category), "essential"
    qs = _optional_questions(category)
    qs.append({"id": "wait_quiz", "text": "等待意愿测评（3 小题一组）",
               "type": "group", "items": DISCOUNT_QUIZ})
    return qs, "optional"


# ---------- 状态机：回答问题 -> 画像 ----------

def run_questionnaire(product: dict, answer_fn: Callable[[dict], str]) -> NeedsProfile:
    """answer_fn(question) -> 选项值（'now'/'wait'/'yes'/...）；group 题会被拆为 3 次调用。"""
    qs, flow = build_questions(product)
    category = product.get("category") or "未知"
    rule = CATEGORY_RULES.get(category, {})
    base_hedonic = rule.get("hedonic", "utilitarian")
    p = NeedsProfile(product_ref=dict(product), flow=flow,
                     necessity="essential" if flow == "essential" else "optional",
                     hedonic=base_hedonic)
    wait_count = 0
    for q in qs:
        if q.get("type") == "group":
            for item in q["items"]:
                ans = answer_fn(item)
                if ans == "wait":
                    wait_count += 1
            continue
        ans = answer_fn(q)
        key = q["key"]
        if key == "purpose":
            p.purpose = ans
        elif key == "deadline":
            p.deadline = ans
        elif key == "usage_intensity":
            p.usage_intensity = ans
        elif key == "budget_tier":
            p.budget_tier = ans
        elif key == "alt_acceptable":
            p.alt_acceptable = ans
        elif key == "hedonic_self":
            p.hedonic = ans          # 用户自评覆盖品类默认（R05 §2）
        elif key == "price_view":
            p.price_view = ans
        elif key == "supply_news":
            p.supply_news = ans
        elif key == "urgency":
            p.deadline = ans
    if flow == "optional":
        p.wait_tier = "low" if wait_count <= 1 else ("mid" if wait_count == 2 else "high")
        p.price_view = p.price_view or "uncertain"
        p.supply_news = p.supply_news or "no"
    return p
