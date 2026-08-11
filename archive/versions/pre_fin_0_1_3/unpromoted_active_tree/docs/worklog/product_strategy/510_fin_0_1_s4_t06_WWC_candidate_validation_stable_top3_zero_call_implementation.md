# FIN 0.1 S4-T06 WWC candidate validation / stable Top-3 zero-call implementation

日期：2026-07-30

## 结果

已完成唯一 WWC 零调用结构包。运行时现在明确区分：

`Provider candidate 1..6 -> 全量逐项校验 -> 本地稳定选择 1..3 -> 本地 canonical 渲染`

R7 的直接缺陷已修复：`_assemble_wwc` 不再在 selection 前使用
`fact_selected_maximum=3` 拒绝第 4–6 个合法候选。WWC 的
model-visible contract 与 compiled surface 同时暴露 candidate 上限 6 和
final-selected 上限 3。

## 全量校验与选择

所有候选在 selection 前依次校验 exact shape、Claim/Authority/Date alias、
closed enum、primary authority membership、重复和 temporal authority。任一候选
无效都会使整段 fail-closed，不静默丢弃。通过后按 Claim epistemic priority、
Authority specificity、trigger actionability、cadence、transition、canonical
digest 和不可达的 ordinal 尾项稳定排序；exact semantic duplicate 在排序前拒绝，
所以候选排列不会改变最终结果。

fake Provider 现在自然生成 6 个不同 WWC atom，而不是仅生成 1 个；因此
DELL/MU/NVDA full-fake 都真实穿过六候选边界，并各自达到：

`6 nodes / 12 calls / 12 captures / 9 Artifacts`

最终每个 Cell 只收到 3 个本地 canonical WWC task。

## 全链与制品审计

边界与负例覆盖 `0/1/3/6/7`、六项中非法第六项、unknown/cross-case alias、
非法 enum、unbound date、exact duplicate 和候选排列变化。Research Lead、
Writer、Verifier 分别在第 10/11/12 次调用失败时，之前及当前失败 capture 都完整
保留。既有 runner 的 terminal-result materialization 同样通过。

最终 9 Artifact 安全包新增 lineage 重算：manifest 的 lineage contract/family/
digest 与 trace 的原始 lineage 都必须和 input pack 一致。数值投影、报告数值、
case title/entity label、manifest lineage digest、trace lineage payload 的 mutation
均被 L1 hard-integrity 拒绝。

## 验证

- WWC / full-chain / downstream capture：`23 passed`
- 最终 Artifact mutation + terminal result focused：`2 passed`
- safety + temporal adjacent suite：`15 passed`
- touched Python compile：pass
- model / Provider / network / source calls：`0 / 0 / 0 / 0`
- admission / WorkUnit / Attempt / Run / business Artifact：`0`

implementation：
`configs/releases/fin_ia_0_1_s4_t06_mu_wwc_provider_candidate_validation_and_deterministic_final_selection_minimum_zero_call_implementation_v1_0.json`

## 阶段边界

本轮只证明当前工作树的确定性全链。R7 仍 immutable failed，formal MU exact-live
ceiling 仍为 0；没有创建 R8 或 replacement admission，没有 paired、owner 或
T07。RC-P36-083 推进为“runtime 已注入 / current zero-call full-chain 已证明 /
independent fresh proof pending”；RC-P36-080 仍等待未来 formal nine-Artifact
L1 重证。

下一项：

`S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-FINAL-SELECTION-INDEPENDENT-FRESH-AGENT-PROOF-DECISION`

下一项仍是零调用独立 disposable-runtime proof；是否允许 replacement exact-live
必须在 proof 之后另做项目级决定。
