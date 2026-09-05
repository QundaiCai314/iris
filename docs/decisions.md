# Iris 技术决策记录（Decisions）

> 规则：技术决策在此登记（结论 / 日期 / 理由 / 否决项）。代码实现与文档冲突时以此为准，改它需用户同意。

## D1 技术栈（2026-09-04 定案，用户授权 agent 选「最合适最稳健」）
- 后端：Python 3.12.12，独立虚拟环境 F:/Iris/.venv（由 F:/AstrBot/backend/python/python.exe 创建，隔离宿主，pip 26.2.1 可用）；Web 框架 FastAPI + uvicorn（已装 0.141.1 / 0.52.4）；数据库 SQLite（标准库）；服务端口 8123（沿用用户旧项目习惯）。
- 统计核心：纯标准库实现（滚动分位 / 波动率 / 历史模拟），不依赖 numpy / pandas。数据量在千点级，纯 Python 足够快，且每个口径可读可审计（研究规范 P1：无出处参数 = bug；黑盒向量化反而难审）。
- 前端：iris/web/static/ 纯静态（HTML + 原生 JS + 自绘 SVG K 线），无构建步骤、无 CDN，离线可用；FastAPI 托管静态文件；前后端通过 /api/* JSON 分离。
- LLM 客户端：标准库 urllib 自研 OpenAI 兼容客户端（iris/llm），不绑供应商 SDK；失败自动沿候选链降级。
- 测试：pytest（已装 9.1.1，tests/）；git 已 init，.gitignore 排除 .venv / 本地配置。
- 否决：Node 全栈（本机量化与脚本生态弱于 Python）；numpy/pandas（重依赖、审计性差、收益低）；React + Vite 构建链（演示期维护成本高，违反离线稳健目标）。

## D2 LLM 接入（2026-09-04 定案，用户指定候选族；模型命名已联网查证）
- 多 provider 网关：OpenAI 兼容协议；config/models.example.json 定义 providers / models / routes；密钥走环境变量（IRIS_OPENAI_API_KEY、IRIS_ZHIPU_API_KEY、IRIS_DEEPSEEK_API_KEY），config/local*.json 不入库。
- 路由：reasoning（问卷生成 / 商品解析 / 解释）链：gpt-5.6-sol → glm-5.3 → deepseek-v4-pro；vision（图片 / 截图价格识别）链：gpt-6-astra → gpt-5.6-sol → glm-5.3-flash。
- 模型事实（2026-09-04 查证，改版以供应商文档为准，只改配置不改代码）：
  - OpenAI：GPT-6 Astra 2026-09-03 发布、分阶段开放中（API 定价 10 / 50 美元每百万 token）；gpt-5.6 系列 2026-07 全面开放：sol 5 / 30，terra 2.5 / 15（后调 2 / 12），luna 1 / 6（后调 0.2 / 1.2）；别名 gpt-5.6 = sol。
  - 智谱：glm-5.3（2026-08-19，OpenAI Chat Completion 兼容，base open.bigmodel.cn/api/paas/v4）；多模态低成本：glm-5.3-flash（GLM-5 系列首个原生多模态）。
  - DeepSeek：deepseek-v4-pro / deepseek-v4-flash（旧名 deepseek-chat / deepseek-reasoner 已于 2026-07-24 退役）。
- 默认主力：gpt-5.6-sol（Astra 未全面开放前）；Astra 可用即把 reasoning 链首切换 gpt-6-astra（配置一处）。
- 无 key 兜底：问卷生成走规则决策树（M4.2），语义解析走人工确认（M4.3），整体开发不被阻塞。

## D3 界面形态（2026-09-04 定案）
CLI 先行（scripts/render_card_cli.py，M5/M6 验收用）→ Web 版（M6：FastAPI 托管静态前端，127.0.0.1:8123，粘贴链接 → 问答 → 决策卡页）。

## D4 演示数据（2026-09-04 定案）
合成价格序列（显卡场景：5080 / 5070 / 5070Ti 多品牌 SKU，含换代事件与大促日历）+ 用户提供少量真实价格点打「用户回填」标签；真实历史价抓取（慢慢买等）列为 B01 渐进目标，demo 不赌实时抓取（spec 6）。


## D5 M5 决策引擎口径与假设参数（2026-09-04 定案 v1）
- 决策公式（总纲 §2.5）：net = G - U - R - buffer；net > 0 建议等，否则买；替代品显著更优（A5 门槛 8%）且满足用途最低性能比时建议换。实现：iris/core/decision.py（decompose / decide / p2_probability / build_conditions / build_decision）。
- G / R 的历史部分不引入新假设：直接用 P1 同分位段候选窗口的 wait_stats（p1.py 新增字段：等满窗以窗内最低价成交，saving = 低于现价的期望节省、loss = 高于现价的期望损失）。
- 假设参数 A1-A7（数值待 B05 问卷实验标定，展示可调、可展开依据）：
  A1 使用强度月效用损失（%价/月：rarely 0.5 / low 1.0 / medium 2.0 / high 3.5）；
  A1b 享乐系数 1.6 vs 实用 1.0（方向 R05 §2.3）；A2 等待档位系数（low 1.6 / mid 1.2 / high 0.8，R05 §3）；
  A3 供需升温附加 1.0%（问卷 supply_news=yes 或 60 天内 supply 事件时计入 R）；A4 用途最低性能比（AI/3D 0.85 / 游戏 0.75 / 日常 0.6）；
  A5 换购门槛 8%；A6 缓冲基数 2.0% 现价 x（0.5 + 波动率分位）——(S,s) 触发带随不确定性变宽（总纲 §1.2）；A6b 红灯阈值 = 净期望 >= 3%；A7 通胀预期缩放（中心恒 1.0，只加宽 P2 扰动带，方向总纲 §1.3）。
- P2（现在买是 60 天视野内最优的概率）= 确定性扰动网格（档位系数/期限/波动率/通胀缩放/供需附加）中「裁决=买」的份额；替代品维度单列于 alternatives，不进 P2（避免双重记账）。
- 必需闸门（essential）与 deadline=now 不跑时机模型：直通「买」，只做渠道/同款换牌比价（R05 §1）。
- 红线落实：样本 n<30 -> decision 低置信、只黄不红；文案禁用词清单 BANNED_WORDS 由测试强制；替代品「值不值由你判断」措辞固定。
- 否决：蒙特卡洛价格路径模拟（P1 频率口径已够且更可回测）；多维随机抽样（确定性网格可复现，答辩友好）。

## 变更记录
- 2026-09-04：D1-D4 首次定案（本文件建立）。
- 2026-09-04：D5 决策引擎口径与假设 A1-A7 定案 v1（实现 M5，92 tests）。
