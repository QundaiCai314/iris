# Iris 数据 schema（v1，M1.1 定稿）

> 代码实现：iris/core/models.py 与 iris/core/prices.py。字段增删必须同步此文档（研究规范 §4）。
> 存储：JSON 文件（demo 阶段可读优先）；data/demo/catalog.json + data/demo/events.json + data/demo/prices/<sku_id>.json。后续可平滑迁移 SQLite。

## 1. catalog.json（实体与 SKU 目录）
{
  "products": [ {商品实体} ],
  "skus": [ {SKU} ]
}

### 商品实体 Product
| 字段 | 类型 | 约束 / 说明 |
| --- | --- | --- |
| product_id | str | 唯一 slug，例 rtx5080 |
| name | str | 展示名（可中文） |
| category | str | 品类（显卡 / 手机 / ...），必需闸门与代理曲线族用 |
| launch_date | str | ISO 日期；生命周期代理起点（R02 §3） |
| lifecycle_family | str | 代理曲线族 id（gpu / phone / laptop / console / home） |
| status | str | active / discontinued |

### SKU
| 字段 | 类型 | 约束 / 说明 |
| --- | --- | --- |
| sku_id | str | 唯一，格式 <product_id>-<brand>-<tier>[-<channel>] |
| product_id | str | 指向 Product |
| brand | str | 品牌（R03 品牌溢价哑变量） |
| tier | str | entry / mid / high（初值；M5 起改由属性向量聚类复核，R03 §3） |
| channel | str | 渠道（jd / tmall / pdd / ...）；品牌价差比较须同渠道（R03 §2） |
| attributes | obj | 属性向量：vram_gb / tdp_w / cooling / warranty_years / benchmark（统一基准分，R03 性能分） |
| launch_price | int | 上市价（元），生命周期曲线基准 |

## 2. prices/<sku_id>.json（日价序列）
{ "sku_id": "...", "source": "synthetic-demo|user-reported|manual|scraped",
  "points": [ {"date": "YYYY-MM-DD", "price": 8599, "quality": "confirmed|estimated"} ] }
- 约束：price 为正整数（元）；date 严格递增；同文件内日期不得重复；跳过日期 = 当日缺失（校验时统计缺失率）；points 数下限 30；quality=estimated 用于「无官方数据时估算」并需 source 说明。
- 每点都带来源与新鲜度语义：文件级 source + 点级 quality；抓取场景的抓取时间进文件 meta（后续扩展）。

## 3. events.json（事件字典，R01 §3）
[ {"event_id": "...", "type": "launch|promo|policy|supply", "title": "...",
   "date": "YYYY-MM-DD", "scope": "all|<product_id>", "confidence": "official|reported|synthetic"} ]
- launch：发布 / 发售日（分开则 event_id 区分）；promo：促销谷日（如 618=06-18、双11=11-11，同一波促销只记谷日，窗口分析按 R01 默认 -30~+90）；policy / supply：政策与供需事件。
- 大促为年循环事件：每年一条（供 R01 多事件 pooling）。

## 4. 校验规则（iris/core/prices.py，validate_*）
1. 价格 > 0 且为整数；2. 日期 ISO 且严格递增；3. 无重复日期；4. 文件内 sku_id 与文件名一致；5. catalog 内 product_id / sku_id 唯一；6. SKU.product_id 必须存在；7. points 数 >= 30（demo 下限）；8. 大缺口（连续缺失 > 90 天）给警告级输出。
- 违反 1-7 = error（拒绝加载）；违反 8 = warning（加载但报告缺失率）。

## 5. 派生口径（resample，M1.3 提供，M2 深化）
- resample_ohlc(points, freq)：freq=7D 按 ISO 周聚合 open/high/low/close（周的 open=周内首日价，close=末日价，high/low=周内极值）；无点周跳过（不插值伪造，总纲 2.1）。
