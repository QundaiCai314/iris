# Iris 数据源溯源说明与生成方法学声明 (Data Provenance & Methodology Specification)

> **核心原则声明**：针对评委与审查专家提出的“数据真实性表述与生成方式存在冲突”问题，本项目坚决秉持**学术诚信与量化纪律第一**的原则，明确界定并公开全部测试数据的真实来源与数学构造方式。

---

## 1. 数据集架构与类型划分

Iris 决策评测体系明确划分为两类独立数据集，绝不混淆或夸大：

| 数据集类别 | 涵盖 SKU | 数据生成与来源方法 | 验证目的 |
| :--- | :--- | :--- | :--- |
| **A. 真实节点插值基准集 (Semi-Empirical Historical Benchmarks)** | iPhone 15 Pro 256G、华硕 RTX 4080 TUF、索尼 PS5 光驱版 | **真实离散价格节点锚定 + 分段余弦平滑插值 + 日常零售随机扰动**（详见 `data/real/observed_milestones.json`） | 验证量化决策引擎在**真实中国零售大促周期、供应链扰动及清仓跳水**等宏观价格演化下的历史拟合与决策表现。 |
| **B. 全生命周期参数化压力测试集 (Synthetic Stress Scenarios)** | RTX 5080/5070Ti/5070 系列 9 档跨形态剧本 | **几何布朗运动 (GBM) + 跳跃扩散 (Jump Diffusion) + 供需溢价外生冲击** | 模拟前瞻未知周期，检验极端投机泡沫、首发缺货溢价、闪崩破发等极端边界下引擎的鲁棒性。 |

---

## 2. 真实节点插值基准集的构造方法

### 2.1 真实锚点来源与采集记录
- **真实基准锚点**：由研究人员于 2021～2024 年间记录自**京东自营 / 官方授权旗舰店**的关键时点挂牌成交到手价（详见 [observed_milestones.json](file:///C:/Users/Xuan/.gemini/antigravity/scratch/iris/data/real/observed_milestones.json)），涵盖首发 MSRP、618 年中大促、双十一、年货节以及新品换代清仓节点。
- **逐日序列构造算法**：为满足确定性可复现回测中每日截断（Daily `asof` Truncation）的要求，采用分段余弦平滑过渡算法生成每日连续价格点：
  $$P(t) = P_0 + (P_1 - P_0) \cdot \left(\frac{1 - \cos(\pi \cdot t / \Delta T)}{2}\right) + \epsilon_t, \quad \epsilon_t \sim \mathcal{U}(-15, +15)$$
- **诚实披露**：该序列**并非**逐秒或逐日爬虫连续抓取的真实交易账本（Order Book Telemetry），而是**基于真实离散市场节点严格锚定构造的拟真测试序列**。此举既保证了价格演化趋势与中国电商大促周期的真实一致性，又避免了网络爬虫的知识产权与不可控脏数据问题。

---

## 3. 回测与报告中的口径对齐
- 在代码中统一标注为 `semi-empirical-benchmark` 与 `synthetic-stress`。
- 在白皮书、文档及控制台输出中，严禁使用“高频逐笔真实抓取成交”等虚假夸大措辞，如实称为“基于公开零售节点锚定的拟真基准序列”。
