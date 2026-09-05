# Iris（鸢尾）

个人消费购买时机量化 Agent ——「现在买合适吗」的概率化决策引擎。

- 输入：贴一个商品链接（自动解析，失败则手动确认「商品名 + 品类」）
- 澄清：AI 用选择题 + 少量填空题摸清需求（用途 / 最晚期限 / 预算 / 二手接受度 / 必需 or 可选 / 通胀预期）
- 分析：全网价格调研 + K 线 + 历史分位 + 波动率 + 事件日历（新品发布 / 大促 / 政策）
- 输出（结论优先）：首屏 = 买 / 等 / 换结论 + 一句大白话 + K 线与价格分位 + 双概率（P1 降价概率 / P2 最优决策概率）；P1 详解、期望值分解、事件日历、替代矩阵、假设重算、依据链全部折叠为可展开项，每个数字可展开依据
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
- 全量测试：F:\Iris\.venv\Scripts\python.exe -m pytest tests -q（110 passed）
- Web（M6 演示）：python scripts\serve_web.py → http://127.0.0.1:8123（API 冒烟：python scripts\smoke_web_api.py）
- CLI 决策卡：python scripts\render_card_cli.py（--scenario gpu_high|gpu_low|gpu_pdd；--interactive 粘贴文本）
- 回测（M7.1）：python scripts\backtest.py → 报告 data/demo/backtest_report.json（截断历史、无前视、含免责声明）
- 重新生成三画像 demo 卡：python scripts\make_decision_demo.py（data/demo/cards/*.json）
## 执行手册
- 里程碑记录：原 TASK_PLAN.md 执行手册已于 M10 后归档删除；各阶段明细见下方「阶段」行与 git log。

## 目录
- docs/purchase-timing-research.md —— 方法论总纲（金融学 + 量化，定版）
- docs/product-spec.md —— 产品规格基线 v0.1
- docs/redline-check.md —— 红线自检清单（M7.2）
- docs/pitch-deck.md —— 答辩与展示包（M7.3）
- docs/data-schema.md —— 数据 schema v1（M1.1）
- docs/needs-profile.md —— 需求画像 schema v1（M4.1）
- docs/card-schema.md —— 决策卡 JSON schema v1（M2.5，含 M8-M10 增补字段）
- docs/decisions.md —— 技术决策记录 D1-D5
- docs/research/ —— 编号主题研究（本文件的「研究」节）

## 阶段
2026-09-04：方法论/研究/任务手册/D1-D4 定案；M0 完成。M1 完成（数据层 16 tests）。M0-M3 完成；M4 完成：需求画像 schema v1（R05）、规则化问卷状态机（必需闸门 3 题 / 可选品 9 屏含贴现 3 小题）、商品文本解析（品类关键词+型号正则）——66 tests；CLI 剧本（显卡 9 屏画像通过、药品 3 题直达）。M4.3 LLM 语义增强挂起（待 D2 key）。M5 完成（2026-09-04）：决策引擎 —— iris/core/decision.py 期望值分解（G 等待收益/U 效用损失/R 风险/buffer 随波动率加宽）、买/等/换 裁决与红绿灯、P2「现在买最优」参数扰动网格、条件句生成（禁用词红线）；iris/core/alternatives.py R03 替代矩阵（同型号配对/跨型号每元性能对齐/换购门槛 A5）；p1 新增 wait_stats 字段。demo 三画像全字段决策卡（P1+P2+事件+替代矩阵+依据链）：5080 高位→换/等（P2≈1%）、5070 低位→买（P2=100%）、5080 pdd 限期→等（红灯）。——92 tests。假设 A1-A7 待 B05 标定（D5）。M6 完成（2026-09-05）：CLI 决策卡渲染 + Web 端到端（粘贴链接→问卷→决策卡，127.0.0.1:8123，离线静态页）+ 假设编辑器（改期限/贴现档/预算等→重算 P2 与红绿灯，历史可回看）；必需闸门无价格库时给明确空态结论。97 tests + Web 冒烟 11 项。M6.1 交互修复（2026-09-05）：问卷点选即自动进入下一题、末题点选自动出卡；支持「上一题」回改（改选后自动续答，不改可点「继续」前进）；已在无头浏览器完成 8 项交互回归。M7.1 完成（2026-09-05）：scripts/backtest.py 截断历史回测 —— 213 决策点（9 SKU × 3 画像，asof 前定参无前视），报告含命中分布/平均节省/最坏情形/样本外校准桶与免责声明；等建议命中 53.3%、净省 +5.82%，买建议后悔率 45.6%；P1 样本外偏差明显（低桶低估/高桶高估）→ 记为 P1 v2 事件相位研究信号；顺带修复 stats.rolling_vol asof 前视并加回归测试 —— 102 tests。M7.2 完成（2026-09-05）：docs/redline-check.md 红线自检定稿 —— 16 项检查 14 绿 + 2 黄（校准样本不足与样本外偏差均已披露并挂研究信号）+ 1 豁免；全库禁用词扫描 0 违规。M7.3 完成（2026-09-05）：docs/pitch-deck.md 答辩包 v1 —— 3 分钟讲稿、方法论引用表、demo 脚本两条路径（显卡等/换 + 药品必需闸门）已真实演练、差异化口径、大赛方向映射、Q&A 预演。M7.4 完成（2026-09-05）：README/目录与阶段行收官；环境清理（frontend 空壳、临时文件）；最终验证 102 tests + Web 冒烟 11 项 + 服务重启健康。里程碑 M0-M7 全部完成并已 git 首次提交（ce2154a）。M7.5 完成（2026-09-05）：决策卡「结论优先」改版 —— decision 层新增 plain_language 大白话字段（买/等/换 + 一句人话，经 _check_copy 红线扫描 + 新测试）；Web 首屏只保留 结论横幅 + 大白话 + K 线与分位，P1 详解/期望值分解/条件句/事件日历/替代矩阵/假设编辑器/依据链全部收进可展开节（重算后自动展开编辑器）；CLI 同步「K线 → 裁决 + P2 + 大白话 → 技术细节」顺序 —— 103 tests。M8 完成（2026-09-05）：账号体系与「我的数据」—— 用户名+密码注册/登录/登出（PBKDF2-SHA256 20 万轮加盐哈希，本地 JSON 存储 data/users/，令牌 7 天）；登录后每次出卡自动存档完整快照（我的数据可一键还原查看/重跑/删除），同品类画像自动预填可一键沿用出卡，卡片可关注/取消关注商品，支持导出 JSON 与注销；前端接入登录态顶栏、登录注册页与「我的数据」三页签 —— 103 tests + 用户 API 冒烟全绿。M9 完成（2026-09-06）：Web 前端「量化终端工作台」彻底重构 —— 从布局形态推翻重来：左 244px 侧栏（品牌/导航/步骤/用户） + 右主画布；问卷改逐题卡片推进，决策卡仪表盘化（结论 banner + KPI 条 + K 线大图 + 概率详解/条件与事件/假设与依据三 Tab + 依据链面板）；样式系统按严格 BEM 重写（.ui-panel/.btn/.card-tab/.kpi/.tag/.me-tabs 等）；K 线 SVG 由前端 CSS 罩染暗化，后端 svgk.py 与 CLI 白底出口不变 —— 103 tests + Web 冒烟 11 项。 M10 完成（2026-09-06）：行为提示层 —— iris/core/behavior.py 四条确定性规则检测用户侧非理性噪音（promo_halo 大促氛围 / high_percentile_rally 高分位+周线反弹 / rerun_anxiety 同会话重算≥3次焦虑 / fresh_card 刚答完问卷冲动），命中时决策卡大白话下方渲染琥珀色降温提示条；规则不改 G/U/R/buffer/P2 数学裁决（test_behavior 断言 decision/p1 不变），文案复用 BANNED_WORDS+_check_copy 红线扫描；/api/recompute 传会话重算次数触发焦虑提示 —— 110 tests + Web 冒烟 11 项。 M12 完成（2026-09-06）：Bloomberg Editorial 视觉识别（方向 A）—— style.css 全重写：暖碳黑 #141414 底 / 琥珀橙 #FF9F1C 强调 / 0px 硬边 / 超大等宽数字（JetBrains Mono） / 涨红跌绿中国语义色；画布 40px 大标题 + 双线分隔，面板琥珀下划线，按钮 mono 大写，KPI 30px 数字网格，决策卡 6px 左边条结论横幅；侧栏 mono 竖排菜单 + 3px 琥珀指示；我的数据 tag 系列 mono 大写语义色标签；登录模态 4px 顶部琥珀条；K 线 CSS 罩染延续；favicon 更新琥珀+暖碳；cache-bust v=12 —— 110 tests + SMOKE PASS (11)。
