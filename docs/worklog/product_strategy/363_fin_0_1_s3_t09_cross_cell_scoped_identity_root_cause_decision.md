# FIN 0.1 S3-T09 跨 Cell scoped identity 零调用根因决策

时间：2026-07-23 18:16（Asia/Shanghai）

## 结论

本轮只完成 `S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-ZERO-CALL-ROOT-CAUSE-DECISION`。RC-P36-046 确认为项目自有的共享身份合同缺口，不是 DeepSeek Writer JSON 失败，也不是只需要在 Writer 增加一次性条件。

选择 `fin01.s3.cell_scoped_research_identity:v1`：Claim 与 What-Would-Change 的权威身份均为 typed `CellScopedResearchRef(identity_kind, program_cell_id, local_id)`。Provider 生成的本地 ID 原样保留；每个 Specialist Cell 通过现有本地校验并绑定精确 `program_cell_id` 后，由本地运行时派生 scoped ref。Lead、Writer、Verifier 的所有 join 与 lineage 校验必须使用 scoped ref，禁止跨 Cell 使用裸 local ID。

本轮未实现代码、Prompt、schema 或 validator，未签发/消费 admission，未调用模型、Provider、网络、source 或外部工具，也没有 canonical 写入。

## 独立复核证据

- Specialist 的 Claim 与 WWC duplicate set 都在单 Cell validator 内创建，因此 `wwc-001/002/003` 可分别在 Demand 与 Value/Profit 合法出现。
- Lead 把所有 Claim/WWC 裸 ID 分别压入全局 dict/set，已经丢失 Cell namespace。
- Writer 再用裸 `claim_id` / `task_id` 构建全局 map；同名项发生覆盖后，section-level Cell lineage 校验必然把其中一个合法 Cell 判错。
- r2 的真实碰撞发生在 WWC；Claim 当前没有真实碰撞，但生产者与消费者代码路径完全同构，必须在同一共享合同中修复，不能等下一次真实调用再补规则。
- Lead 自己生成的 dependency/gap/adjudication ID 只有一个生产者，当前不纳入跨 Cell scope；以后仍需在 Lead 节点内单独保证唯一。

## 选定合同

- 权威字段：`identity_kind + program_cell_id + local_id`。
- runtime key 使用上述三元组；可对 typed object 计算 canonical digest 做 lineage/exact binding，但 digest 不替代可审计字段。
- 跨 Cell 允许复用相同 local ID；同 Cell 重复、重复 scoped ref、未知/错 kind/错 Cell ref 均 fail-closed。
- Specialist Provider wire shape不因本问题单独升级到 v8；若 Lead/Writer 的 Provider wire schema 必须携带 scoped ref，则只给实际变化的下游 node transport 做版本化。
- Prompt schema 与本地 validator 必须由同一 typed identity contract 生成或消费，不能再各自解释 ID scope。

## 安全 telemetry

统一 family 为 `cross_cell_scoped_identity`，只允许：

- `identity_kind`
- `failure_subtype`
- `failing_item_count`

subtype 固定覆盖 same-Cell duplicate、raw cross-Cell ambiguity、scoped duplicate、scope mismatch 与 unknown ref。禁止写入 raw local ID、Cell ID、digest、item index、回答正文或 private reasoning。

## 兼容性与验收边界

- v1-v7 transport、output-v3、历史 admission digest、r2 failed Run 与 11 份受限原始回答保持不变。
- 禁止通过加前缀、改名、trim、drop、remap 等方式静默“修好”历史数据。
- 未来实现必须以两个 Cell 复用同一 WWC local ID、两个 Cell 复用同一 Claim local ID、非 NVDA/异期间/mixed Evidence-Numeric fixture，以及六节点九 Artifact fake-Provider 全链证明泛化性。
- 本轮没有新的研究 Fact、Evidence、Numeric、Judgment、Report 或 Alpha；S3-T09 仍 blocked。

## 下一项

`S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-AND-SAFE-COLLISION-TELEMETRY-ZERO-CALL-IMPLEMENTATION`

该实现尚未授权；replacement admission、真实调用、rerun、paired comparison、owner review、T10、S4、release 与 production 继续禁止。
