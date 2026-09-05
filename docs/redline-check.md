# Iris 红线自检清单（Redline Check）

> 状态：定稿（2026-09-05）| 依据：执行原则 P4、product-spec §7、总纲 §2.6、D5、
> R04 §2 校准口径 | 范围：引擎输出、UI/CLI 文案、演示数据、回测报告。
> 规则：全绿 = 通过；黄 = 已知偏差已披露并有缓解/研究信号；豁免 = 场景未涉及并写明理由。

## 检查表

| # | 红线项 | 要求 | 证据（位置） | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| A1 | 概率校准流程 | 对外概率过校准检查（Brier/可靠性） | iris/core/calib.py：collect_pairs + reliability（等频箱、Brier、max_dev>0.10 触发降级） | 🟢 | 机制在引擎内，测试覆盖 |
| A2 | 校准报告产物 | 校准结论落盘可查 | data/demo/calib_report.json（9 SKU，M2.4） | 🟢 | — |
| A3 | 校准样本充足性 | 样本不足不得宣称校准通过 | calib_report.json 各 SKU n=5~6，notes=「校准样本过少，结论仅作流程演示」 | 🟡 | 样本内样本不足：如实标注、不作校准通过宣称（R04 降级路径已走通） |
| A4 | 样本外校准（M7.1 回测） | 概率桶与实现频率偏差 <=0.10 | data/demo/backtest_report.json「calibration」：0-20% 桶 +0.212、80-100% 桶 -0.413 | 🟡 | 已知偏差已披露于回测报告 disclaimer/limits；研究信号：P1 v2 事件相位修正（R01）+ B04 大促节奏；修复前 UI 均附 CI、n 与「合成演示」口径 |
| B1 | n<30 不给单点概率 | 小样本只给方向/区间 | iris/core/p1.py：min_n=30 -> probability=None、confidence=insufficient、只给方向+幅度分位；UI p1Table 显示「样本不足」 | 🟢 | test_p1 覆盖 |
| B2 | n<30 决策降级 | 低置信只黄不红、不构成承诺 | iris/core/decision.py：_confidence + traffic_light（low -> yellow）；build_conditions low_sample 句「低置信参考…不构成承诺」 | 🟢 | test_decision 覆盖 |
| B3 | 事件研究样本标注 | 小样本仅量级参考 | build_events_slim / 条件句事件文案：n=%d「仅量级参考」「不作承诺」（超出 60 天主窗事件） | 🟢 | — |
| C1 | 代理/合成数据标签 | 演示数据全链标注 | source=synthetic-demo（data/ 与代码 docstring）；卡面 badge「合成数据」、K 线「合成演示数据」、evidence「演示价序列为合成剧本」、页面 footer | 🟢 | — |
| C2 | 前代生命周期代理标签 | 新品无历史须用代理并打标签 | data/lifecycle/（gpu/console/home/laptop/phone）已建，但引擎/UI 未接入（demo 无新品场景） | 豁免 | 场景未涉及；未来接入新品时须补「代理数据」标签与测试（挂 B01/B04 之后） |
| D1 | 措辞红线机制 | 生成文案禁用承诺词 | iris/core/decision.py：BANNED_WORDS + _check_copy（运行时 raise）；test_decision 对全部条件句与 plain_language（M7.5）断言无禁词 | 🟢 | — |
| D2 | 文案全库扫描 | 用户可见文案无「保证/稳赚」类词 | 2026-09-05 全库扫描 43 命中全部人工复核：仅为免责否定句（回测 != 未来保证/不承诺）、词表定义、数学语境「绝对价差/绝对值」、内部文档 | 🟢 | 扫描清单与结论见文末 |
| D3 | 不制造焦虑 | 无倒计时/限量/催促式话术 | 全库无「疯抢/手慢无/最后机会/赶紧」类用户话术；事件标题为中性历史记录（「抢购潮与渠道溢价峰值」）；供需条件句附引用（A3）并给事实建议 | 🟢 | 人工复核 |
| E1 | 回测披露 | 回测不承诺未来 | data/demo/backtest_report.json disclaimer：合成剧本、理想化记账口径、参数不搜索、事件相位/替代维度不在范围、可复现 | 🟢 | M7.1 产物 |
| E2 | 页面免责 | 概率口径与假设可见 | iris/web/static/index.html footer：合成数据（截至 2026-09-03）、校准口径、A1-A7 假设可调、不承诺未来；账号数据仅存本机 data/users/ | 🟢 | — |
| E3 | 依据链与样本声明 | 每个数字可展开出处/样本 | 卡片 evidence（data/p1/stats/events/R03/R05/总纲 refs）；P1 表带 CI+n；条件句带 n 与 ref | 🟢 | — |
| E4 | 信息分层与结论优先（M7.5/M9） | 首屏不堆金融术语，细节可展开 | app.js renderCard：首屏 = 结论横幅 + 大白话 + 行为提示 + K 线与 KPI；概率详解/条件与事件/假设与依据三 Tab 分栏 + 依据链面板；decision.plain_language 与 Web/CLI 同源并经 _check_copy | 🟢 | — |
| E5 | 账号与数据边界（M8） | 凭据与用户数据只落本机 | users.py：PBKDF2-SHA256 20 万轮加盐哈希 + 内存令牌（7 天 TTL）；data/users/<用户名>.json 原子写盘；注销即删文件；导出接口 Content-Disposition 用 ASCII 文件名 | 🟢 | — |
| F1 | 不替用户裁决价值 | 主观价值归用户 | 替代矩阵固定措辞「值不值由你判断」；hedonic 用途由画像输入 | 🟢 | — |
| F2 | 主观溢价单列 | 品牌/叙事溢价不进 P2 | D5：替代品维度单列 alternatives，不进 P2（避免双重记账） | 🟢 | — |
| F3 | 行为提示不改裁决（M10） | 提示层只影响「怎么读卡」 | iris/core/behavior.py：4 条确定性规则（大促氛围/高分位反弹/重算焦虑/刚答完冲动），test_behavior 断言 hints 不改 decision/p1；文案复用 _check_copy | 🟢 | 焦虑信号触发的是降温提示（rerun_anxiety/fresh_card），符合 D3 |

## 结论
- 绿 17 项；黄 2 项（A3/A4，均为校准样本与偏差的如实披露，附研究信号）；豁免 1 项（C2，无新品演示场景）。
- demo 文案无「保证/稳赚」类承诺词（D1/D2 机制 + 扫描双保险）。
- 已知限制对答辩口径：P1 为 v1 历史频率法，样本外校准偏差已披露；演示宣称使用「合成剧本内演示引擎」，不作真实市场承诺。

## 附：2026-09-05 全库扫描记录
- 范围：F:/Iris（排除 .venv/.git/__pycache__/.pytest_cache），.py/.md/.json/.html/.js/.css/.txt。
- 词表：BANNED_WORDS + 焦虑话术（疯抢/抢不到/马上涨价/最后机会/赶紧/手慢无/错过就/限时/绝对）。
- 结果：43 命中，0 条用户可见违规；复核分类：免责否定句 12、词表定义 8、数学/学术语境（绝对价差、覆盖率保证）7、内部任务与研究文档 15、扫描脚本自命中 1。
- 复核日期：2026-09-05。
