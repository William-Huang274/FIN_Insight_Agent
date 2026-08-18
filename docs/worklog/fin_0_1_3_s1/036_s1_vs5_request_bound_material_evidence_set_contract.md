# S1 VS5 request-bound 材料组与同口径跨期合同

日期：2026-08-18

状态：`contract_translated_and_development_fixture_proven / runtime_integration_pending / S1_not_qualified`

## 为什么要做

COST valid-temporal R2 并不是又一次“换 Embedding 还不够强”。R2 已把 any-hit、材料 facet 和 required role 拉到门槛，但 20 条已审对象只进入 15 条：汽油替代解释、毛利表和同口径现金流表排在第 21；另两条 membership 对象又超出被冻结 EvidenceRequest 的 revenue／gross-margin／operating-cash-flow 范围。

这暴露出两个合同问题：

1. 单对象 top-K 只能说明哪些片段排名高，不能保证一项研究判断所需的 direct、counter、bridge、context 和跨期同口径材料成组齐全；
2. reference 若没有绑定运行前请求，可能在看到结果后把未请求主题混进评分，导致检索器为一份不一致的“答案清单”负责。

历史 COST R1／R2 均保持失败，valid 次数已用完，禁止 R3。本轮只做零调用结构处置，没有调用网络、DeepSeek、Embedding、reranker，也没有读取 hidden reference。

## 实现内容

新增统一合同 `src/retrieval/evidence_set_coverage.py`：

1. `MaterialEvidenceRequirementPlan` 只能从公开 EvidenceRequest 的 case、entity、metric、product、facet、role 和 period 编译；禁止 candidate、object、qrel、source URL 或答案 URL。
2. 每个 requirement group 明确 direct／counter／bridge／context、实体、指标、产品和期间模式。
3. 同口径 temporal group 必须是单实体、单指标、单产品，覆盖至少两个请求年份；运行前按“每年各需一个对象”的最坏情况预留 review capacity。
4. 正式审阅面先保留完整材料组，再按原始稳定排名补满；错误公司的候选直接排除并留下 hard-boundary receipt。
5. plan、selection 和 evaluation 均内容寻址；任何字段或摘要篡改 fail closed。
6. evaluator reference 必须绑定 plan digest，requirement IDs 必须与运行前计划完全相等；允许预注册多个等价对象集合，也允许以单一对象形成不可替代硬门。
7. required-group coverage 是资料组完整性门；exact-object recall 仍保留为 parser／recall／ranking 诊断，二者不互相冒充。
8. 被选中仍只是 Candidate，不能获得 Evidence 或 NumericFact 权威。

## 回归设计与结果

新增 synthetic development matrix，故意覆盖不同业务形态而不是复制 COST：

- DELL：需求 direct、发行人 counter、TSM 上游 bridge；
- MU：当期业绩 direct、周期 counter、经营现金流 bridge；
- NVDA：需求 direct、客户集中 counter、TSM 产能 context；
- COST：FY2024／FY2025 同口径经营现金流 temporal bundle。

四案共 10 个材料组，全部满足；核心代码 0 ticker 分支，跨案候选入选 0。mutation 覆盖请求外 metric、gold identity 泄漏、跨期容量不足、错 basis、漏年份、错公司、候选排列变化、等价对象、唯一对象、reference／plan 不一致及摘要篡改。

验证结果：

- 合同测试：13 passed；
- 相邻 VS5 测试：34 passed；
- 全仓：646 passed；
- Python compileall：通过；
- active baseline：155 Python／8 frontend／16 Runtime resources／0 forbidden reference；
- repository secret scan：7,140 files／0 finding；
- JSON／JSONL parse 与 `git diff --check`：通过；
- network／generation model／learned vector／hidden reference read／Evidence promotion：均为 0。

`run_project_os_full_chain_preflight.py` 是绑定一次付费／自然模型执行 decision 的专用入口，本切片没有生成也不需要生成 live decision；因此没有拿历史 S3 decision 冒充本轮权限。若后续进入任何 paid node，仍必须另行建立当前 task-specific `TokenBudgetBasis` 和 decision-bound preflight。

机器结果：`configs/retrieval/fin_ia_0_1_3_s1_material_evidence_set_coverage_zero_call_result_v1_0.json`。

## 没有被证明的内容

这轮不能写成“COST 已修好”或“S1 已通过”。当前真实候选结果还没有统一提供材料组需要的 label-free case／facet／role／metric／product／period／basis metadata；自然 ResearchBlueprint 也还不会生成 `MaterialEvidenceRequirementPlan`。因此 synthetic matrix 只证明合同可行，不能冒充 current Runtime 纵切。

COST 两条 membership reference 的去留必须由 qualified human 裁决：若未来问题明确要求会员经营面，则先扩展未来请求再冻结新 reference；若问题仍只要求收入、毛利和经营现金流，则未来 reference 不应混入 membership。无论选择哪一项，都不能改写 R1／R2。

既有 hidden reference 因披露事故失去盲性；当前 Codex 不能自我生成 replacement blind gold。新的 unseen temporal program 必须先冻结无标签 case／source／request，再由独立评审在 candidate freeze 后生成 Git 外 reference。

## 下一门

1. 生成 COST request／reference consistency 的 qualified-human review packet，不代替人工作决定；
2. 实现 current candidate metadata → material group adapter；
3. 实现自然 ResearchBlueprint → request-bound material requirements 编译入口；
4. 用当前开发纵切做真实 zero-call replay，证明同一 canonical spine 的消费者确实使用新审阅面；
5. 通过后才预注册新 unseen temporal case；blind label 继续留在隔离的人类评审面。

当前结论：`S1_qualified_stable=false`，test／holdout、完整 S1→S3、发布均不得放行。
