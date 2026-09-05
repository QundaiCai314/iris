# -*- coding: utf-8 -*-
"""M4 需求问卷测试。"""
from iris.agent.needs import (CATEGORY_RULES, NeedsProfile, build_questions,
                              detect_category, detect_model, parse_product_text,
                              run_questionnaire, validate_profile)


def _answers(vals):
    it = iter(vals)
    def fn(q):
        return next(it, "none")
    return fn


GPU_ANS = ["游戏", "within_30", "high", "mid", "yes", "hedonic", "up", "yes", "wait", "now", "wait"]
DRUG_ANS = ["急用", "now", "mid"]


def test_essential_drug_branch():
    product = {"name": "布洛芬缓释胶囊", "category": "药品", "source": "manual"}
    qs, flow = build_questions(product)
    assert flow == "essential"
    assert len(qs) <= 3
    ids = [q["id"] for q in qs]
    assert "wait_quiz" not in ids          # 必需不分发贴现测评
    p = run_questionnaire(product, _answers(DRUG_ANS))
    assert p.necessity == "essential" and p.flow == "essential"
    assert validate_profile(p) == []
    assert p.wait_tier is None


def test_optional_gpu_full_flow():
    product = {"name": "RTX 5080", "category": "显卡", "source": "manual"}
    qs, flow = build_questions(product)
    assert flow == "optional"
    qids = [q["id"] for q in qs]
    assert "wait_quiz" in qids
    assert len(qids) == 9                   # 8 主屏 + 贴现组屏
    p = run_questionnaire(product, _answers(GPU_ANS))
    assert validate_profile(p) == []
    assert p.wait_tier == "mid"            # 3 道贴现题中 2 次选等
    assert p.price_view == "up" and p.supply_news == "yes"
    assert p.hedonic == "hedonic"


def test_wait_tier_mapping():
    product = {"name": "iPhone", "category": "手机", "source": "manual"}
    base = ["日常通讯", "none", "medium", "high", "no", "utilitarian", "stable", "no"]
    # 直接验证映射逻辑：wait_count<=1 -> low
    p = run_questionnaire(product, _answers(base + ["wait", "now", "now"]))
    assert p.wait_tier == "low"
    p = run_questionnaire(product, _answers(base + ["wait", "wait", "now"]))
    assert p.wait_tier == "mid"
    p = run_questionnaire(product, _answers(base + ["wait", "wait", "wait"]))
    assert p.wait_tier == "high"


def test_reproducible_questions():
    p1 = {"name": "RTX 5080", "category": "显卡", "source": "manual"}
    p2 = {"name": "RTX 5080 另一家", "category": "显卡", "source": "manual"}
    qs1, _ = build_questions(p1)
    qs2, _ = build_questions(p2)
    assert [q["id"] for q in qs1] == [q["id"] for q in qs2]
    assert qs1 == qs2                       # 同品类确定性


def test_category_specific_questions():
    gpu, _ = build_questions({"name": "5080", "category": "显卡", "source": "manual"})
    phone, _ = build_questions({"name": "iPhone", "category": "手机", "source": "manual"})
    g_purpose = next(q for q in gpu if q["id"] == "purpose")["options"]
    p_purpose = next(q for q in phone if q["id"] == "purpose")["options"]
    assert g_purpose != p_purpose
    assert "AI / 跑模型" in g_purpose


def test_parse_product_text_gpu_url():
    r = parse_product_text("https://item.jd.com/1000.html 华硕 RTX 5080 TUF 显卡")
    assert r["category"] == "显卡"
    assert r["name"] and "5080" in r["name"]
    assert r["source"] == "text"


def test_parse_unknown_text():
    r = parse_product_text("今天天气不错想买个东西")
    assert r["category"] is None


def test_detect_model():
    assert detect_model("RTX 5080 16G") and "5080" in detect_model("RTX 5080 16G")
    assert detect_model("随便一段话") is None


def test_profile_validation():
    p = NeedsProfile(product_ref={"name": "x", "category": "显卡"}, flow="optional")
    errs = validate_profile(p)
    assert any("wait_tier" in e for e in errs)
    assert any("price_view" in e for e in errs)
    p.wait_tier = "high"
    p.price_view = "up"
    assert validate_profile(p) == []
