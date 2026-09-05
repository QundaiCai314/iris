# R04 预测方法选型与概率校准工程

- 编号 / 日期：R04 / 2026-09-04
- 状态：草案（待评审）
- 研究问题：P1（降价概率）用什么模型族计算，才能同时满足准确、可解释、不自欺？
- 一句话结论：零售 / 需求时序预测的实证反复显示复杂模型难以稳定超过简单基线；Iris 默认「历史模拟 + 事件修正 + 生命周期代理」，区间用 conformal 类方法做小样本校准并报告覆盖率；深度学习只作研究性对照。

## 1. 实证：复杂不等于更准
- ARIMA vs LSTM（Lviv 大学期刊 Electronics and Information Technologies，2025）：零售销量递归多步 LSTM 未超过自回归基线（误差累积 + 架构选择问题）。
- 需求管理时序预测评估（IEEE，2024）：简单基线在一个数据集上稳健胜过复杂模型；seasonal naive 的季节捕捉表现好。
- 概率预测挑战的普遍经验（例：arXiv 2211.16171 气象概率预测挑战）：简单 / 集成均值常击败单一复杂模型。
→ Iris 语境：单商品价格序列样本小（一款显卡约 2~3 年日度 = 700~1000 点）、事件稀、信噪比低，深度学习既无胜算又伤可解释性。引擎用透明基线，ML 只做对照，「看起来很 AI」在答辩里反而是减分项（无法交代参数出处，违研究规范 §4）。

## 2. 概率输出的校准与样本纪律（P1 工程化）
- 评估指标：区间预测看覆盖率（coverage）与 CRPS / 对数分数；校准后的分布普遍优于未校准（EMOS 类校准研究，SIS 2020 会议）。
- 小样本校准工具链：split / inductive conformal prediction 给出有限样本覆盖率保证；RSA-CP（ICML 2026）针对小样本校准集提升效率；广义 Venn / Venn-Abers（ICML 2025）输出带保证的校准概率。
- Iris 纪律落地：历史切 fit / calibration 两段；P1 输出一律「点估计 + 区间 + n」；n < 30 只给区间；每月滚动校准检查（实际覆盖率 vs 名义值），偏差超 ±0.1 即回退为「仅方向」输出——把总纲 2.2 的校准义务变成可执行流程。

## 3. 何时才升级模型（全部满足才考虑 ML 对照）
单商品（或代理族）≥ 3 年干净日度数据、同类事件 ≥ 15 起、校准集 ≥ 300 样本，且滚动回测显著优于基线。预计真实场景极少触发，届时以对照实验形式进入研究库（新开 R 编号），不直接上生产。

## 4. 来源
[1] Lviv 大学（2025）ARIMA vs LSTM 零售销售建模，Electronics and Information Technologies（publications.lnu.edu.ua）。
[2] IEEE（2024）Evaluation of Time Series Forecasting Strategies for Demand Management。
[3] arXiv:2211.16171 概率时序预测挑战（气象）。
[4] SIS 2020（EMOS 校准研究：覆盖率 / CRPS / 对数分数评估）。
[5] ICML 2025 Generalized Venn / Venn-Abers Calibration；ICML 2026 RSA-CP（小样本 conformal prediction）。
