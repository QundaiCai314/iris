# 需求画像 schema v1（M4.1 定稿）

> 代码实现：iris/agent/needs.py（NeedsProfile / validate_profile）。字段全部映射到 M5 决策参数（出处 R05）。

## 画像字段与枚举
| 字段 | 枚举 / 类型 | 含义与映射（-> M5） |
| --- | --- | --- |
| product_ref | {name, category, source: url/manual/text} | 商品识别结果（M4.3） |
| necessity | essential / optional | 分流闸门：essential 只做渠道比价（R05 §1） |
| purpose | 品类相关枚举 / 自由文本 | 上下文与解释措辞 |
| deadline | none / within_30 / within_90 / now | 可等待时长上限（-> U 等待效用损失） |
| usage_intensity | rarely / low / medium / high | 使用强度（-> U） |
| budget_tier | low / mid / high / flexible | 品牌挡位建议范围（R03） |
| alt_acceptable | yes / no | 是否接受平替 / 二手（决定替代品矩阵权重，R03） |
| hedonic | hedonic / utilitarian | 享乐 / 实用（R05 §2：享乐品等待成本上调） |
| wait_tier | low / mid / high | 等待贴现档（R05 §3 离散选择题反推；low=几乎不愿等） |
| price_view | up / stable / down / uncertain | 通胀 / 涨价水平预期（R02 §3：水平↑提前买倾向↑） |
| supply_news | yes / no | 近期缺货涨价消息（R02 §4 门控信号） |
| flow | essential / optional | 走的问卷分支（调试与审计用） |

## 问卷流程（M4.2，确定性规则版，可复现）
1. 商品确认（M4.3）：链接 / 文本解析 → 候选「商品名 + 品类」；失败则用户手工确认。
2. 必需闸门：类目规则（药 / 医疗 / 基础食品 / 婴儿用品）+ 文本关键词兜底。命中 → 3 题内完成画像（不问时机题）。
3. 可选品主流程 8 题：用途（品类题库）→ 最晚期限 → 使用强度 → 预算档 → 二手 / 平替接受 → 想要还是需要（享乐自评）→ 半年价格预期 → 缺货消息。
4. 等待贴现测评 3 小题（一组）：现在价 vs 等 2/6/12 个月省 X%；选「等」次数 0-1 -> wait_tier=low，2 -> mid，3 -> high（R05 §3）。
5. 输出 NeedsProfile JSON，通过 validate_profile 才能进 M5。

## 校验规则（validate_profile）
- product_ref 非空且 category 非空；necessity / flow / deadline / usage_intensity / budget_tier / alt_acceptable / hedonic / wait_tier / price_view / supply_news 值在枚举内；
- flow=optional 时必须给出 wait_tier 与 price_view（时机引擎输入完整）；
- flow=essential 时 wait_tier 可为 null（不走时机）。
