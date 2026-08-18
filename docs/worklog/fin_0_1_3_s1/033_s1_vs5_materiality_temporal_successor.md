# S1 VS5 命题实质性与跨期候选 successor

日期：2026-08-18
状态：`engineering_pass / COST_valid_temporal_R2_candidate_complete_evaluation_pending / hidden_splits_unopened / S1_qualified=false`

## 为什么要做 successor

COST valid-temporal R1 的失败不是资料、解析、CUDA 或 DeepSeek 问题。20 条人工候选均已存在于官方 10-K 对象库，但同店销售 4 条全部落在前 20 之外，跨期比较只保留 2/5，毛利率反方漏 1 条。最早问题位于：

1. 类型化 EvidenceRequest 已点名具体业务问题，但 v1 QueryFacetPlan 仍把 facet、行业和 case pack 的通用词全部塞进每个查询；
2. bounded RetrievalNeed 先生成 metric×product 组合，后面的独立业务概念会被上限截掉；
3. `FY2024 FY2025 comparison` 只是文本 product，而不是要求同公司、同指标、同口径、两期同时出现的结构约束；
4. 最终 review 前 20 会被同一 facet 的重复候选占满；
5. 旧 Evidence Role 规则偏向开发期 AI／半导体表达，新行业的精确业务词即使出现在来源中也可能被 ontology 的闭集边界误判为不确定；收入确认政策中的 `recognized` 又可能被误当作当期经营结果。

因此不能继续调 BGE／Qwen 权重、扩大 top-k 或针对 COST 写对象 ID。R2 只允许验证 provider-neutral 的命题编译、期间配对与候选席位结构。

## 一次治理纠正

R1 失败记录最初建议“必须新增一个未观察 temporal case”。该说法过严。预注册机器合同明确允许 `valid_temporal_max_executions=2`，并把 valid temporal 定义为配置选择阶段；Owner 也已授权在同一 S1／VS5 内继续。

修正后的边界是：

- R1 永久保留为失败证据；
- 不改 R1 结果、不覆盖旧 runner、不调门槛；
- COST 已成为被观察的 valid 案例，R2 即使通过也不能单独证明泛化；
- R2 只能是预注册的第二次、也是最后一次 COST valid-temporal 运行；
- JPM／CAT frozen test 和 NVO／SHEL／0700.HK heterogeneous holdout 继续不可读取、不可执行；
- 若 R2 再失败，不进入 COST R3，转为架构处置或另行预注册独立 temporal case。

## 实现内容

### 1. 冻结 v1，建立明确 v2 边界

第一次实现曾直接修改预注册时已哈希冻结的 `query_plan.py`、`financial_intent.py`、`evidence_role.py` 和 `financial_evidence_shortlist.py`。定向新测试虽通过，但全仓回放立刻暴露两项失败：预注册 digest 漂移、VS1 结果 digest 漂移。

该做法已撤销。四个 v1 文件逐字恢复，原 digest 和旧纵切重放重新通过。新行为进入：

- `src/retrieval/query_plan_v2.py`
- `src/retrieval/financial_intent_v2.py`
- `src/retrieval/evidence_role_v2.py`
- `src/retrieval/financial_evidence_shortlist_v2.py`
- `src/retrieval/qualification_runtime_v2.py`
- `scripts/data_retrieval/run_s1_vs5_qualification_candidates_successor.py`

这不是第二套产品主线，而是使旧证据可重放、successor 行为可辨认的有界合同版本。R2 通过后，是否将 v2 晋升为当前 S1 Runtime 仍需后续独立资格决定。

### 2. 命题优先的查询编译

类型化 EvidenceRequest 存在时，v2 lexical／exact query 只使用请求实际点名的 metric 和 product；身份、期间、来源、关系、facet 与 semantic question 仍继承冻结 v1 合同。广义 case plan 保持 v1，不受影响。

### 3. RetrievalNeed 先保留原子、再做组合

v1.2 need policy 在固定上限内先为每个 metric／product 生成独立 need，再生成 cross-product。通用 role cue 不再重复附着到每个 typed need；纯期间表达被编译为 fiscal-year constraint，不再冒充业务产品。

### 4. 新业务词与 Evidence Role

ontology 仍是 synonym／proxy 扩展权威，但不再被当作闭集：未登记的新业务词只有在来源中逐字出现时才能兼容，不自动获得 `same-store` 等未经复核的同义词。

Evidence Role v2 使用请求词＋事实状态判断当前候选究竟是实际结果、机制／定义还是风险；仅写“收入确认”的会计政策不再因 `recognized` 被当成经营结果。规则不包含 COST、ticker、对象 ID 或 gold 路径。

### 5. 跨期配对与 facet 均衡

金融 shortlist 只在候选层为请求的同指标、各 fiscal year 保留位置，不比较数值、不授予 NumericFact。最终 review prefix 在请求的 facet 间确定性轮转，然后再按完整融合顺序补足；Candidate 仍不是 Evidence。

## 零调用证明

- DELL／MU／NVDA：同一 v2 核心保留请求点名词，反转输入顺序后独立 intent 覆盖不变；没有把通用 `bookings` 重新塞进聚焦查询；
- COST：5 个 valid-temporal 命题、全部 facet 使用 v1.2 need compiler；每个独立 metric／product 在预算内保留；temporal need 显式携带 FY2024／FY2025 与 same-basis requirement；
- 新业务词：逐字 `comparable sales` 可识别，未授权 `same-store sales` 不会自动晋升；
- 角色：同店销售实际变化可成为直接需求候选，收入确认政策不能冒充当期结果；
- 时间：同一 metric 的 FY2025／FY2026 候选进入 review 头部前先保留两期；
- 旧合同：R1 candidate policy／旧 Runtime input／预注册 digest 和 VS1 replay 均保持通过；
- learned vector 合同：仍为 `cuda:0 + FP16`，CPU fallback=false；本轮零 learned vector、零网络、零模型。

复证结果：全仓 `629 passed`；successor、旧合同与旧 replay 定向 `10 passed`。只物化 `valid_temporal/vs5_qualification_inputs_v1_1.jsonl`，没有物化 hidden successor input。

## COST R2 label-blind 候选执行

设计在干净提交 `1fa65512` 冻结，独立 authority 提交为 `32a2a673`。唯一一次 `FIN-0.1.3-S1-VS5-VALID-TEMPORAL-CANDIDATE-R2` 已完成：

- 5 个 COST 命题全部执行，编译 113 个命题级 RetrievalNeed；
- BGE／Qwen 各重排 1,440 对；
- learned execution 全部位于 `cuda:0`、FP16，设备为 NVIDIA GeForce RTX 4060 Laptop GPU；
- 对象 embedding cache 命中，但 successor 查询和 pair manifest 已重新计算；
- 0 网络、0 生成模型、0 CPU vector fallback、0 retry；
- evaluator reference 未加载，候选没有 Evidence／NumericFact 权限；
- private raw 为 1,405,046 bytes，SHA-256 `ff760f5a9ee77b07c7253d7e85727bdb9a995d66d22812119928e1a225af935c`。

该结果只能说明候选生成成功，不能提前查看标签后宣布检索通过。public projection 必须先冻结提交，随后才允许独立 evaluator 加载 valid-temporal reference。

## 分离 evaluator 工程门

R2 evaluator 沿用 R1 的同一参考、20 条目标、五项业务影响模板和不可补偿门槛；没有复制一套 attempt-only evaluator，而是让现有 canonical evaluator 同时识别 v1 与 v1.1 schema。旧候选状态仍按 v1 校验，successor 只增加新的 label-blind status；评价 policy 另行绑定 frozen public／private candidate、evaluation runtime 和 runner digest。

工程复证为全仓 `631 passed`，active baseline 通过，secret scan 7,127 files／0 finding。此时尚未加载真实 COST reference；只有 evaluator design clean push、再签发独立 exact-once authority 后才能评分。

## 当前真实状态

本轮达到 `engineering_pass` 并完成 label-blind R2 candidate execution：

- COST R2 execution authority 已单独签发并消耗；
- 新查询和双 reranker 分数已在 CUDA／FP16 完成；
- 尚未读取 evaluator reference 进行 R2 评分；
- 没有 Evidence／NumericFact 晋升；
- current Runtime Registry、Evidence Pack、Workbench 和历史 S3 attempt 均未改变；
- natural scanned official source gate 仍失败；
- S1、S3、完整真实链、S4／S5 均未通过。

## 下一步

1. 将本记录、评测标准、架构说明、Project OS 与 RC-S1-024 同步；
2. 运行 active baseline、Project OS、compileall、secret／JSON 治理；
3. 当前 successor 设计已在 `1fa65512` clean push；
4. R2 authority 已在 `32a2a673` clean push；
5. 唯一一次 CUDA FP16 R2 candidate 已完成并保留 raw；
6. public candidate result 已冻结；下一步 clean push evaluator policy，再单独签发 evaluator authority；
7. 评价若通过，只进入 qualified-human reference review 与隐藏执行资格决策；若失败，停止 COST 重跑并做架构／新 temporal case 处置。
