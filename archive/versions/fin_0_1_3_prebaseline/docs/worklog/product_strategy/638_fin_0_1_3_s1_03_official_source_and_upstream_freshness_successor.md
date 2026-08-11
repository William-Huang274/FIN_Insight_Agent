# 638 — FIN 0.1.3 S1-03 official source 与上游 freshness successor

日期：2026-08-06
阶段：`013-S1-03`；有界重开 `013-S1-01/S1-02`
结论：`S1-03 engineering_pass`，`S1` 尚未关闭，下一项 `013-S1-04`

## 1. 为什么没有直接把 S1-03 记成通过

S1-03 的目标是把 official IR、SEC、PDF/redirect/parser fallback 和 source attempt 做成 current 证据，而不是继续使用旧 fixture。第一次 current 证明很快暴露出两个不同层次的问题：

1. official-source parser 确实存在 binary junk、phrase-first false match 和 first-occurrence selection 缺陷，归 S1-03 修；
2. 更严重的是，S1-01/S1-02 的 current annual 输入仍然 stale。此前只修复了“Q4 不能冒充全年”，却没有确保截至 research as-of 选择最新已公开年报；策略文件仍手写 fiscal year。

第二项不能伪装成 S1-03 parser 问题，也不能留到 S3 renderer 再改数，因此登记 `RC-P36-135` 并有界返回最早 owner。历史 S1-01/S1-02 记录保持原样，只产生 current successor。

## 2. 上游 freshness successor

执行了只覆盖 DELL、MU、NVDA 和 2025–2026 年的 targeted SEC CompanyFacts/submissions refresh，没有覆盖或删除旧 4.296GB staging。private successor 形成：

- 3 个 issuer；
- 3,196 条 current structured fact rows；
- 5 条 relevant submissions；
- 60 条三案 Runtime rows；
- 60 条 targeted Gold rows。

Material Numeric v1.1 不再把 fiscal year 当手工 owner，而是确定性选择 `source_filed_at <= as_of_date` 的 latest annual period。mutation 明确证明晚于 as-of 的 future filing 不可被选中。当前 annual revenue 是：

- DELL FY2026：USD 113.538B；
- MU FY2025：USD 37.378B；
- NVDA FY2026：USD 215.938B。

Material program 从历史 S1-02 的 `23 base / 14 formula / 8 gap / 45 governed` 形成 current successor `25 base / 16 formula / 7 gap / 48 governed`。DELL 增加应收、应付起止事实与变化公式；没有把旧结果重写成新结果。

## 3. Official-source 运行历史

所有 request/response 都先进入 private content-addressed capture，再解析或失败；凭据与 raw capture 正文不写 Git。

| Attempt | 处置 | 原因 |
| --- | --- | --- |
| diagnostic | 仅诊断，不是 authority | 当时没有 shared admission |
| R1 | immutable failed post-run semantic audit | MU HBM glossary 出现被误认成实质需求证据 |
| R2 | immutable failed post-run semantic audit | matcher 只看第一处出现，遗漏后文真实联合语义；另有一次 DELL transport failure |
| R3 | terminal success，但被 current successor supersede | semantic 3/3 已成立，但仍绑定 stale NVDA FY2025 且未提取 DELL 精确 segment 数值 |
| R4 | current formal proof | shared exact-once admission；当前来源、parser 和 numeric extractor 全部绑定 |

R4 的结果为：

- 10 次 source network calls；
- 0 次 model/provider/business run；
- 17 个 required source slots；
- 11 个 accepted evidence；
- 6 个 attempt-backed typed gaps；
- 三案各 3 条 official semantic evidence；
- DELL 官方 FY2026 PDF 确定性提取 AI-optimized server revenue USD 24.683B、ISG operating income USD 7.111B。

SEC archive 路径返回 403。该响应被 capture-first 保存，但只代表该路线在本次环境不可用，不代表事实不存在，所以所有剩余 gap 仍为 `source_exhaustion_proven=false`。

## 4. 合并后的 current S1 数值与来源面

两条 DELL official exact fact 使用原 material typed-gap digest 做受控消解，不允许自由数字叙事替换：

- 48 个 material slots；
- 27 个 effective exact facts；
- 16 个 deterministic formulas；
- 5 个 remaining attempt-backed numeric gaps；
- 9 个 official semantic evidence slots；
- Numeric＋semantic 共 57 个 governed slots，0 ungoverned。

剩余 5 个 gap 是：

1. MU HBM revenue；
2. MU HBM profit；
3. MU price/volume/mix decomposition；
4. NVDA product/accelerator revenue；
5. NVDA product/accelerator profit。

它们不能由 consolidated company number、Data Center segment revenue 或定性叙事推导，因此保留 gap 是正确结果，不是 S1-03 失败。

## 5. 工程改进与反思

本轮再次证明，“parser 通过”和“当前金融真值通过”不是一回事。后续 S1 数据阶段必须同时回答：

- 数据是否刷新到 research as-of；
- period semantics 是否正确；
- latest-available selection 是否由代码而非手工策略拥有；
- 原始响应是否先保存；
- parser 是否只晋升完整语义窗口；
- 无法证明的事实是否保留 typed gap。

正式 source proof 也不应把每次局部代码修正都计成一个新产品版本。R1–R3 是同一 S1-03 current source contract 的 immutable evidence；R4 是修复后的 current successor。模型没有参与本轮，因此所有失败都不是 DeepSeek 能力问题。

## 6. 验证与边界

聚焦合同覆盖 annual freshness、future filing、JSON/HTML/PDF/redirect/parser failure、binary junk、false promotion、numeric extraction、typed-gap composition、shared exact-once replay 和 release digest binding。

最终 current active suite 为 `64 passed / 1 historical event-time assertion deselected`。原始未筛选运行诚实显示同一节点为 `64 passed / 1 failed`；失败节点要求 S0-02 历史 decision 的 living-document SHA 永远等于当前 Project OS 字节，属于已登记的 event-time 断言，不是 current S1 回归。旧 decision/test 均未修改，active suite 只显式记录 deselection。release materializer 连续两次输出 byte-identical。

S1-03 的通过只证明 current official-source acquisition/parser/capture/gap contract。以下仍为 false：

- authoritative Graph edge；
- retrieval usefulness；
- Agent 消费；
- 八维研究内容质量；
- product/full-chain acceptance；
- FIN 0.1.3 release。

下一项严格是 `013-S1-04-AUTHORITATIVE-RELATIONSHIP-GRAPH-EDGE-AND-TYPED-EMPTY-COVERAGE`。
