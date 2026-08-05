# FIN 0.1.3 扩展产品表现案例与对抗测试计划

日期：2026-08-05
状态：`planned / no_new_case_execution / no_model_calls`

## 1. 目标

本计划用于证明 FIN 0.1.3 修复后的产品表现，不以增加 full-chain 次数为目标。测试分层执行：大量 deterministic truth/adversarial fixture、少量 changed-node natural canary、一次最终三案例 product qualification。

## 2. 案例分层

### A. 正式 release cases

| Case | 主要覆盖 | 必须通过的异常边界 |
| --- | --- | --- |
| DELL | server OEM、年度/季度营收、利润和现金流、订单/需求质量 | FY/Q4 duration collision、53-week/period label、IR/SEC 对账、USD scale |
| MU | memory cycle、产品组合、毛利/现金流、客户与供需 | fiscal year、cyclical price/mix、库存与 capex、typed external gap |
| NVDA | AI demand、value capture、supply/customer/export counter-thesis | 年度/季度、客户集中、供应链、出口限制、可观测 WWC |

三案必须走同一 current Runtime、dynamic DecisionSurface、Workbench 和 authenticated review；不得为每案维护独立逻辑分支。

### B. 结构回归 cases（deterministic/node-level，不要求付费 full-chain）

| Case family | 建议代表 | 目的 | 0.1.3 边界 |
| --- | --- | --- | --- |
| Enterprise SaaS | CRM 或同类公开披露 fixture | 验证 universal archetype、RPO/deferred revenue、非制造业 metric policy 和 typed gap | 不建立完整 SaaS Sector Pack |
| US Bank | JPM 或同类公开披露 fixture | 验证 bank metric family、NIM/CET1 与普通企业 income-statement metric 不可混用 | 不建立完整 Bank Sector Pack |
| Foreign issuer shadow | TSM 或 ASML 的 reviewed snippets | 验证 20-F/6-K、EUR/TWD、多币种和 foreign filing boundary | diagnostic-only；发现 shared L1 才阻断 |

### C. 对抗 fixture families

1. annual、quarter、YTD、TTM 和 53-week duration 冲突；
2. amended/restated filing 与旧值并存；
3. duplicate XBRL facts、不同 taxonomy concept、同 end date 不同 duration；
4. USD/EUR/TWD、多 scale、百分比与 basis-point；
5. PDF、HTML、redirect、IR landing page、不可达 source 和 parser failure；
6. stale source、published_at 缺失、as-of 之后来源；
7. Graph 正向 edge、无权威证据 typed empty、跨案 edge、未知 entity；
8. candidate 可达但 rank 丢失、parser 可读但 authority 不足、accepted 但未被使用；
9. 证据互相冲突、issuer 自述与外部证据不一致；
10. 通用 Claim、重复 gap、无指标 WWC、unresolved conflict 冒充综合；
11. cross-case identity、stale digest、Artifact mutation、capture/result 缺失；
12. reviewer session expiry/revocation/restart、重复 decision、repair 后 stale review。

## 3. 测试金字塔

| 层级 | 规模原则 | 外部调用 | 通过目标 |
| --- | --- | --- | --- |
| L0 schema/unit | 所有合同与纯函数 | 0 | 类型、enum、duration、unit、identity、digest |
| L1 financial truth fixture | 三正式案例＋对抗矩阵 | 0 | 100% reviewed material facts entity/period/duration/unit/scale 正确 |
| L2 retrieval/parser/Graph | required slot gold/negative set | 默认 0；受控 source canary 单独签权 | known reachable source 可达，零 false promotion，失败 typed |
| L3 node quality | changed Specialist/Lead/Writer/Verifier family | 每 changed node family 最多一次自然 canary | 公司专属机制、证据边界、冲突、gap、WWC rubric 通过 |
| L4 product integration | DELL/MU/NVDA fake/replay＋一次正式 candidate | deterministic 先行；最终候选一次 | create→run→repair→review、9 Artifacts、三案 current R2、NVDA R3 |
| L5 release | RG1–RG5 | 不允许临时 debug rerun | rollback、成本、安全、burden、honest release decision |

## 4. 预注册质量断言

### Financial truth

- 所有 material number 必须有 entity、fiscal year、fiscal period、duration/instant、unit、scale、source locator 和 formula/aggregation role。
- quarterly value 不能以 annual label 进入 Numeric、Claim、Workpaper 或 Report。
- `source_filed_at`、`published_at`、`as_of_date` 和 local snapshot time 分字段保存，不得互相代填。
- derived metric 必须可由 exact inputs 重算；不能重算则 typed gap。

### Retrieval and evidence

- 每个 required EvidenceSlot 必须得到 accepted evidence，或保留 route attempts、拒绝原因和 typed exhaustion。
- candidate count、accepted count 和 evidence-use count 分开；accepted 未使用必须可解释。
- issuer-only evidence不能冒充独立外部 corroboration。
- Graph edge 只有在 approved relationship evidence 具备 entity、relation、time 和 source 时才能晋升。

### Research quality

- 任何核心 Claim 不得只靠“证据方向支持当前单元判断”之类通用句式通过。
- Claim 必须说明本案对象、机制、证据/数字和边界；缺证据时明确 cannot infer。
- conflict 必须 resolve/defer/block；gap 必须有影响、优先级、owner 和下一步。
- WWC 必须具有 observable indicator、direction、time/threshold 和 evidence route。
- Report 必须形成 thesis/counter-thesis/valuation-or-price-in boundary，而不是 Claim 数量汇总。

### Product usability

- analyst 不编辑 JSON 即可创建、恢复、检查、退回和完成 Case。
- 至少一条实际 targeted repair 从 request 到新 evidence/artifact diff 和 closeout。
- reviewer action 绑定 exact version，repair 后旧 decision 自动 stale 或显式 superseded。
- 记录任务耗时、review 耗时、编辑数、repair 次数和失败理解；不得用测试通过数代替用户价值。

## 5. 执行与成本纪律

1. 先建立 gold/negative fixtures 和 ceiling；ceiling 不足时修 S1，不训练/调用下游模型。
2. 不为每个字段单独 live。合同 family 完成后最多一个 node canary。
3. 正式三案例 full-chain 只在 S0–S4 deterministic gate 全绿后执行。
4. 任一新 L1 停在责任阶段，不自动 replacement；L2–L4 finding 按预注册 release blocking 级别处置。
5. 外部来源、模型调用、token、成本、attempt、capture 和 terminal result 必须进入 run ledger。

## 6. 当前未执行

本计划没有新增数据下载、source canary、DeepSeek 调用、full-chain、Case、Artifact、review action 或 release qualification。案例和阈值在实现前还需要生成 reviewed gold manifests。
