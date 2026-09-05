# 决策卡 JSON schema v1（docs 侧，M2.5）

> 代码实现：iris/core/card.py（build_card / validate_card）。所有对外数字都应有来源链（evidence 字段，M3/M5 追加）。

## 结构
{
  "schema_version": "1.0",
  "meta": { product_id, sku_id, asof_date, generated_at, engine_version },
  "stats": { 由 iris.core.stats.describe 输出：
             asof, last_price,
             lookbacks: { "90"|"365"|"730": { n, min, max, mean, median, iqr, pct_position } },
             ma: { "20": ...|null, "60": ...|null },
             volatility: { window_days, annualized, pct_position },
             trend },
  "p1": { "30"|"60"|"180": { 主/辅窗口，见下 } },
  "events": null | {...},        // M3 填充（事件窗口统计）
  "alternatives": null | [...],  // M5 填充（替代品矩阵）
  "decision": null | {...},      // M5 填充（买/等/换 + P2）
  "evidence": [ {ref, note}, ... ]  // 依据链
}

## p1 窗口对象
必填：window_days, drop, n, confidence(sufficient|insufficient), method, method_note, direction, bucket, buckets, percentile_position, n_sufficient, min_n, sample{first_date,last_date,span_days,note}
confidence=sufficient 追加：probability(点估计), ci95[lo,hi]（Wilson 95%）, hits
confidence=insufficient 追加（不给 probability）：median_future_low, low_q25（幅度分位，仅方向输出）

## 校验规则（validate_card）
- meta 六字段齐全；stats 含 last_price 与 lookbacks；p1 必须含 "60" 主窗；
- p1 每窗必填字段齐全；sufficient 必须有 probability/ci95；insufficient 不得携带 probability。
- 违反任一条 = 卡片不可对外（研究规范：无出处参数 = bug）。


## v1 全字段填充（M3/M5/M6 之后，engine_version >= 0.3.0）
- kline（M6 管线追加）: 周 OHLC 数组 [{date, open, high, low, close, n}]（prices.resample_ohlc freq=7），CLI/Web 渲染用；Web 另有 /api/kline 输出自绘 SVG。
- events（M3 填充）: { promo|supply|launch?: { horizons: {"30"|"60"|"90": {n, mean_pct, ci95_pct, min_pct, max_pct}}, control_used, control_note }, upcoming: [ {type,title,date,days_ahead,beyond_days,confidence,summary_text?} ] }（upcoming 为 asof 后 180 天内的匹配事件）
- alternatives（M5.3，R03 降级版配对）: { target:{sku_id,label,price,benchmark,per_yuan}, rows:[ 同型号行 row_type=same_product / 跨型号行 row_type=substitute，字段见 iris/core/alternatives.py build_rows ] }（行字段：row_type, sku_id, product_id, label, brand, tier, channel, benchmark, bench_ratio, price, saving_abs, saving_pct, diff_pct, per_yuan, per_yuan_target, satisfies_need, need_bench_ratio, note）；satisfies_need 由用途最低性能比（A4：AI/3D 0.85、游戏 0.75、日常 0.6）判定。
- decision（M5，决策引擎 v1）: { recommendation: buy|wait|switch, traffic_light: green|yellow|red, mode: essential|deadline_now|gate_switch|timing_engine, window_days, n_windows, confidence: sufficient|low, note, decomposition?: {wait_days, n_windows, price, saving_pct/saving_yuan(G), u_pct/u_yuan(U), loss_history_pct, supply_premium_pct, r_pct/r_yuan(R), buffer_pct/buffer_yuan, net_pct/net_yuan, params}, p2: {probability, n_scenarios, buy_count, wait_count, confidence, method, note, dimensions}, conditions: [ {scenario, text, ref} ], switch_to?: 替代行摘要|null, params_note }
- 口径速查：净期望 net = G - U - R - buffer（总纲 §2.5）；net>0 等、否则买；A5 换购门槛 8%；样本 n<30 -> low（只黄不红）；文案禁用词 BANNED_WORDS 由测试强制（test_decision.py）。