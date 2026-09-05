# Iris（鸢尾）

个人消费购买时机量化 Agent ——「现在买合适吗」的概率化决策引擎。

- 输入：贴一个商品链接（自动解析，失败则手动确认「商品名 + 品类」）
- 澄清：AI 用选择题 + 少量填空题摸清需求（用途 / 最晚期限 / 预算 / 二手接受度 / 必需 or 可选 / 通胀预期）
- 分析：全网价格调研 + K 线 + 历史分位 + 波动率 + 事件日历（新品发布 / 大促 / 政策）
- 输出：P1 降价概率 与 P2 最优决策概率 并列展示；买 / 等 / 换红绿灯；替代品与品牌档位对比；每个数字可展开依据
- 纪律：概率要校准、样本不足只给区间、回测只披露不承诺、给依据不制造焦虑

理论根基：最优停止 / 等待期权、(S,s) 触发带、通胀预期、参考价双锚、行为偏误反制。详见 docs/purchase-timing-research.md。

## 研究（Research Log）

本项目坚持「先研究、后定参」：任何口径与参数决策都来自编号研究文档，不拍脑袋。
- 规范与索引：docs/research/README.md
- R01 事件研究法移植：换代与大促价格窗口 —— docs/research/R01-event-study-pricing-windows.md
- R02 日历促销与生命周期降价的实证规律 —— docs/research/R02-calendar-lifecycle-empirics.md
- R03 特征价格模型：品牌挡位价差归因 —— docs/research/R03-hedonic-brand-decomposition.md
- R04 预测方法选型与概率校准工程 —— docs/research/R04-forecast-baselines-calibration.md
- R05 需求澄清参数化：必需分流与等待贴现 —— docs/research/R05-needs-willingness-to-wait.md

研究 backlog 见 docs/research/README.md 末尾；新增研究按模板登记编号。

## 技术决策
- docs/decisions.md —— D1 技术栈 / D2 LLM 网关 / D3 界面 / D4 数据（2026-09-04 定案）
- config/models.example.json —— 多模型路由模板（reasoning / vision 候选链）



## 运行
- 全量测试：F:\Iris\.venv\Scripts\python.exe -m pytest tests -q（97 passed）
- Web（M6 演示）：python scripts\serve_web.py → http://127.0.0.1:8123（API 冒烟：python scripts\smoke_web_api.py）
- CLI 决策卡：python scripts\render_card_cli.py（--scenario gpu_high|gpu_low|gpu_pdd；--interactive 粘贴文本）
- 回测（M7.1）：python scripts\backtest.py → 报告 data/demo/backtest_report.json（截断历史、无前视、含免责声明）
- 重新生成三画像 demo 卡：python scripts\make_decision_demo.py（data/demo/cards/*.json）
## 执行手册
- TASK_PLAN.md —— 严格任务安排（M0-M7，每步含验收标准；执行时更新进度表）

## 目录
- docs/purchase-timing-research.md —— 方法论总纲（金融学 + 量化，定版）
- docs/product-spec.md —— 产品规格基线 v0.1
- docs/redline-check.md —— 红线自检清单（M7.2）
- docs/pitch-deck.md —— 答辩与展示包（M7.3）
- docs/research/ —— 编号主题研究（本文件的「研究」节）

## 阶段
2026-09-04：方法论/研究/任务手册/D1-D4 定案；M0 完成。M1 完成（数据层 16 tests）。M0-M3 完成；M4 完成：需求画像 schema v1（R05）、规则化问卷状态机（必需闸门 3 题 / 可选品 9 屏含贴现 3 小题）、商品文本解析（品类关键词+型号正则）——66 tests；CLI 剧本（显卡 9 屏画像通过、药品 3 题直达）。M4.3 LLM 语义增强挂起（待 D2 key）。M5 完成（2026-09-04）：决策引擎 —— iris/core/decision.py 期望值分解（G 等待收益/U 效用损失/R 风险/buffer 随波动率加宽）、买/等/换 裁决与红绿灯、P2「现在买最优」参数扰动网格、条件句生成（禁用词红线）；iris/core/alternatives.py R03 替代矩阵（同型号配对/跨型号每元性能对齐/换购门槛 A5）；p1 新增 wait_stats 字段。demo 三画像全字段决策卡（P1+P2+事件+替代矩阵+依据链）：5080 高位→换/等（P2≈1%）、5070 低位→买（P2=100%）、5080 pdd 限期→等（红灯）。——92 tests。假设 A1-A7 待 B05 标定（D5）。M6 完成（2026-09-05）：CLI 决策卡渲染 + Web 端到端（粘贴链接→问卷→决策卡，127.0.0.1:8123，离线静态页）+ 假设编辑器（改期限/贴现档/预算等→重算 P2 与红绿灯，历史可回看）；必需闸门无价格库时给明确空态结论。97 tests + Web 冒烟 11 项。M6.1 交互修复（2026-09-05）：问卷点选即自动进入下一题、末题点选自动出卡；支持「上一题」回改（改选后自动续答，不改可点「继续」前进）；已在无头浏览器完成 8 项交互回归。M7.1 完成（2026-09-05）：scripts/backtest.py 截断历史回测 —— 213 决策点（9 SKU × 3 画像，asof 前定参无前视），报告含命中分布/平均节省/最坏情形/样本外校准桶与免责声明；等建议命中 53.3%、净省 +5.82%，买建议后悔率 45.6%；P1 样本外偏差明显（低桶低估/高桶高估）→ 记为 P1 v2 事件相位研究信号；顺带修复 stats.rolling_vol asof 前视并加回归测试 —— 102 tests。M7.2 完成（2026-09-05）：docs/redline-check.md 红线自检定稿 —— 16 项检查 14 绿 + 2 黄（校准样本不足与样本外偏差均已披露并挂研究信号）+ 1 豁免；全库禁用词扫描 0 违规。M7.3 完成（2026-09-05）：docs/pitch-deck.md 答辩包 v1 —— 3 分钟讲稿、方法论引用表、demo 脚本两条路径（显卡等/换 + 药品必需闸门）已真实演练、差异化口径、大赛方向映射、Q&A 预演。M7.4 完成（2026-09-05）：README/目录与阶段行收官；环境清理（frontend 空壳、临时文件）；最终验证 102 tests + Web 冒烟 11 项 + 服务重启健康。里程碑 M0-M7 全部完成；剩余：git 首次提交（待用户确认）。
