# 637 FIN 0.1.3 S1-02 material Numeric program、公式重算与 typed gap

日期：2026-08-06
状态：`S1_02_engineering_pass / S1_in_progress / S1_03_next`

## 结论

S1-02 已把 FIN 0.1.3 的 Numeric 基础从“每案三条 consolidated number 加两条 margin”扩展为有边界、可复算、可拒绝的三案例 material Numeric program。当前结果是 `23 base facts / 14 derived metrics / 8 typed gaps / 45 governed slots / 0 ungoverned`，模型、Provider、网络和业务 Run 均为 0。

这不是 F07 的最终产品验收。它证明的是所有当前计划进入核心 Claim/表格的数字必须有完整 authority，或以 typed gap 停止；S1-03 仍需证明官方来源、parser/fallback 和 source exhaustion，S3/S4 仍需证明研究链真实消费与 UI/产品可用性。

## 根因与范围判断

旧 0.1.2 Numeric Pack 只有 revenue、gross profit、operating income 三个 exact fact 和两个 margin。DELL revenue 又是错误的 FY2025 Q4 `23.931B`，导致 gross margin `88.797%`、operating margin `26.0624%` 虽然“公式可算”，但金融语义错误。S1-01 修复 period truth 后，S1-02 必须同时补齐公式输入面、比较期 instant、case-specific material gap 和准入规则，否则一个数字只要格式正确仍可能进入产品。

本项没有抓取新来源，也没有为缺少的分部/产品数据造数。Gold Mart 仍保留每指标 current authority；average inventory 所需的 beginning inventory 从同一 current 10-K、同一 filing 的 normalized SEC staging 中精确恢复，保持 source-bound 且不越过 S1-03。

## 实现

- versioned policy 定义 DELL/MU/NVDA 的 base slot、formula slot、case-specific requirement 和 Claim/table allowlist；
- compiler 只读 current Gold SQLite，并从 normalized SEC staging 选择同 filing 的比较期 inventory；
- 每个 base fact 绑定 entity/issuer、metric、fiscal year/period、period role/start/end/duration、unit/currency/scale、source filing/date/URL/row locator 与 snapshot/as-of；
- 确定性 Decimal 重算 gross margin、operating margin、FCF、average-inventory days 和 capex intensity；
- 缺少 input 会同时形成 input gap 与 dependent formula gap；case-specific 未覆盖项形成显式 typed gap，均不宣称 source exhaustion；
- conflicting authority、跨案 identity、错误 unit/scale/time、formula/result tamper、unknown Claim/table ref 全部 fail closed；
- program 与三案例 program set 均内容寻址，release record 与 current active suite 绑定。

## 真实结果

| Case | Base | Formula | Gap | 关键公式结果 |
| --- | ---: | ---: | ---: | --- |
| DELL | 9 | 4 | 3 | GM `22.2357%`；OM `6.5263%`；FCF `1.869B USD`；inventory days `25.32` |
| MU | 7 | 5 | 3 | GM `39.7908%`；OM `26.1384%`；FCF `1.668B USD`；inventory days `139.34`；capex intensity `42.4234%` |
| NVDA | 7 | 5 | 2 | GM `74.9887%`；OM `62.4175%`；FCF `60.853B USD`；inventory days `85.66`；capex intensity `2.4798%` |

DELL 另保留 ending AR `10.298B`、AP `20.832B`，但没有足够可比期 authority 时不生成变化公式。8 个 typed gap 覆盖 DELL server/ISG revenue、profit、可比 AR/AP change；MU HBM revenue、profit、PVM；NVDA Data Center product revenue、profit。它们由 S1-03 继续做 attempt-backed 来源证明。

## 验证与历史边界

- 新 contract tests：policy、真实 DELL 重算、比较期缺失、authority conflict、unit、identity、formula tamper、三案 release 和 active-suite digest；
- current S0–S1 suite：`53 passed / 1 historical event-time assertion deselected`；
- adjacent T03–T05：`19 passed / 2 historical digest assertions deselected`；两项是 S1-01 合法改变数据/source 后旧 T04 exact-input 与 T05 living-source SHA 的 event-time 断言，不是 S1-02 回归；
- 额外旧 Fundamental Agent 相邻回归：`10 passed / 1 failed`。失败是 HEAD 自 2026-07-19 即存在的 prompt metadata compactor 将 `line_item_count` 从 int 转为 string；本轮未触碰相关文件。该 typed-contract 漂移登记 RC-P36-134，归 `013-S2-01`，不在 S1-02 顺手修 Agent prompt；
- materializer 对真实本地数据重复生成应保持 byte-identical；生成态大文件不进入 Git；
- 旧 FIN 0.1.2 Evidence Pack、R2/R3 与 Owner acceptance 全部保持 immutable，未被新数据偷偷改写或继承。

## 下一步

进入 `013-S1-03`：对 required EvidenceSlot 做 official SEC/IR、PDF/redirect/parser fallback 与 capture-first 尝试；每项要么得到 accepted evidence，要么得到 attempt-backed typed gap。S1-02 的声明缺口不能直接当作“已穷尽来源”。S1-04 Graph、S1-05 retrieval usefulness 以及 S2/S3 模型与内容质量继续留在各自阶段。
