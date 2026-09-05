# R02 日历促销与生命周期降价的实证规律

- 编号 / 日期：R02 / 2026-09-04
- 状态：草案（待评审）
- 研究问题：大促与新品周期有没有可靠的跨商品经验规律，能编程进「事件日历」与「前代代理曲线」？
- 一句话结论：有规律但要反直觉地用——「大促即全年最低」不成立（有双11 后反弹的实证）；周期性促销的经济学解释是卖家的价格歧视；电子耐用品存在量级稳定的生命周期折价曲线，可作新品代理先验；供需冲击期规律失效需门控。

## 1. 反直觉事实：大促不一定最低
PLOS ONE（2024，p.pone.0296654，双11 平台折扣与消费者策略性等待研究）：案例显示部分品牌手机在购物节前夜跌到低位，双11 后价格反而回升数百元。
→ Iris 不假设「等到正日 = 最低」：事件日历应输出整条期望路径（不少最低点出现在预售期与前夜），用 R01 方法逐段统计。

## 2. 为什么有周期性促销：价格歧视
Jin Huang（NYU 上海，CBER 讲座「Is It Time for a Sale?」，2023）的经济学解释：周期性折扣不是成本波动，而是卖家对耐心 / 不耐心买家做跨期价格歧视。
→ 对用户的含义：折扣是可预测的筛选机制，耐心通常有回报；但促销日历是卖家设计的，Iris 必须把「等到下一窗口的期望收益」与「等待成本」比较后再建议，而不是默认「等大促」。

## 3. 生命周期折价曲线（新品代理先验库来源）
- idealo（欧洲比价平台；媒体转述 2017，非同行评审，取量级）：科技新品发布约 16 天后平均已比首发低约 5%；电子产品开始明显降价的中位时点约在发布后 80 天。
- idealo 统计经德语行业媒体转述（CE-Markt，2021，非审阅）：发布约半年后平均低约 24%（多期报道数字在 24~29% 间波动，只取量级）。
- 手机价格路径实证（IGI Global，2015，Price and Sales Volume Patterns of Mobile Handsets）：中位机型价格在销量峰值月（约第 5 销售月）为上市价约 89%，两年后约 47%；功能进入主流的时点均价约上市价 58% → 「上市一年后跌去约三分之一」是电子耐用品常见量级（手机最规则，显卡受供需扰动大）。
- 算力成本长期趋势：笔记本价格研究（Computers & Industrial Engineering，2000）引用算力价格年降 20~30% 的规律，支撑「旧硬件时间价值递减」先验。
→ Iris 应用：新品 / 无历史商品 → 按品类生命周期曲线族（手机 / 笔记本 / 显卡 / 游戏机 / 家电分族，参数 = 发布后月数 -> 期望价 / 上市价百分比），输出打「代理数据」标签（总纲 2.6）。

## 4. 失效条件（何时别信日历）
供需冲击（矿潮、短缺、关税）会压倒日历与生命周期规律 → 需「异常状态门控」：当波动率分位超阈值或出现供需类事件新闻时，日历 / 代理曲线权重下调，让位给 R01 事件窗口与实时分位。

## 5. 来源
[1] PLOS ONE（2024）How do e-commerce platforms and retailers implement discount pricing policies under consumers are strategic?（PMC11086857）
[2] Jin Huang, Is It Time for a Sale? The Economics Behind Discounts, NYU Shanghai CBER 讲座（2023；视频与文字报道）。
[3] idealo 平台统计，经 Redes&Telecom（2017）与 CE-Markt（2021）转述（媒体数据，非同行评审）。
[4] IGI Global（2015）Price and Sales Volume Patterns of Mobile Handsets and Technologies。
[5] Forecasting notebook computer price as a function of constituent features（2000）Computers & Industrial Engineering（S0360835200000140）。
