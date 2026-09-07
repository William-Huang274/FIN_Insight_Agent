# S1 请求级 Candidate Ceiling Provenance 工程门

日期：2026-08-18

状态：`provider_neutral_contract_integrated / direct_product_request_proven / current_CUDA_replay_pending / public_gap_authority_false`

## 业务问题

此前产品会返回“找到若干候选”或“没有候选”，但不能回答资料究竟在哪里丢了。对研究用户而言，以下情况完全不同：

1. 只过滤了旧静态快照，真正 BM25／向量路线根本没运行；
2. BM25／Qwen 已运行，但在最多 96 个候选的并集里没有形成完整材料组；
3. 材料组在并集里已经形成，却因同源配额或 16 条审阅窗被截掉；
4. 候选完整进入审阅面，只是尚未由 CandidateDecision 晋升为 Evidence。

若这些情况不拆开，系统很容易把自己的查询、容量或排序问题写成“公开资料没有披露”。

## 实现

新增 provider-neutral `CandidateCeilingProvenance`，绑定当前 request digest、runtime binding digest 和 candidate contract。它记录：

- 当前来源／对象谱系是否绑定，但明确不裁决来源是否披露了目标事实；
- 静态快照 lane、候选数和缺失 source role；
- requested／available／executed route 状态；
- eligible object、BM25 first-stage、Qwen first-stage、union 和 final review 数量；
- first-stage、union、final review 是否触顶；
- 每个 material requirement 在 bounded union 内是否完整、是否保留到 final review、最早观察到的损失层；
- 固定 `candidate_is_not_evidence=true`、`source_gap_authority=false`、`public_information_gap_eligible=false`。

直接 EvidenceRequest 只做静态快照时，收据明确返回 `hybrid_candidate_runtime_not_executed`。受控计划实际执行 Hybrid 后，同一字段被当前运行结果替换，不沿用计划态。API response model、Workbench service 和 DELL 产品 replay 的公开投影已接入该字段。

## 验证

- 直接快照不得冒充 Hybrid 已执行；
- 96／96 bounded union 内不完整 requirement 标记为 `at_or_before_bounded_candidate_union_ceiling`；
- 并集内完整但未进入 final review 标记为 `post_union_source_quota_or_review_cut`；
- 修改收据令 public gap 为 true 时校验 fail closed；
- 当前真实 Workbench direct DELL request 返回 binding-bound、non-gap provenance；
- replay public projection 不泄露候选 ID；
- targeted 70、全仓 730、compileall 全部通过。

## 尚未证明

本轮仍未实际重跑 DELL CUDA／FP16 Hybrid，因此不能声称八个真实请求的损失层已经重新分类。source disclosure、OCR／parse 内容充分性和外源路线耗尽也不由该收据证明。下一步必须从干净提交复用不可变 R3 scope 执行一次零模型 CUDA replay；结果通过后再把同一合同迁移至 MU／NVDA，并才允许 RC-S1-034 消费。
