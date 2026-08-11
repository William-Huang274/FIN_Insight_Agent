# FIN 0.1 S4-T04 DELL Source-Grounded Input And Fresh Proof

日期：2026-07-26

## 结果

`RC-P36-056` 的项目内 upstream gap 已修复并关闭。DELL bounded official-source routes、issuer-bound Evidence/Numeric、context-only Graph、typed gaps、Canonical Case/DecisionSurface、exact input head 与 fresh nonreuse proof 已形成一条可审计链。

本轮严格止于 fresh proof：未签发 admission，未调用模型或 Provider，未创建 WorkUnit、Attempt、Run、业务 Artifact，也未执行 Human acceptance。下一项是需独立授权的 `S4-T04-DELL-FRESH-EXACT-ADMISSION-ISSUANCE`。

## Source-Grounded 输入

P34 的 11 条 DELL official routes 已全部执行，形成：

- 9 个 source snapshots；
- 11 个 route receipts；
- 6 条 issuer-bound Evidence；
- 22 条 exact-value Numeric；
- 2 个本地确定性派生指标；
- 4 条 context-only Graph edges；
- 9 个 typed gaps。

事实层覆盖 FY2026 与 Q1 FY2027 的 AI server orders、shipments/revenue、backlog、ISG revenue/operating income、company cash flow，以及应收、存货、应付等 working-capital 数据。产品与客户部署材料只用于界定 XE9712、GB200 NVL72、liquid cooling 和 named deployment context。

以下边界没有被数字或关系图越权替代：

- 不从 ISG 或 company-total 数字推断 AI server/product-specific gross profit 或 operating profit；
- 不从 orders/backlog 直接推断 revenue conversion timing；
- 不把公司官方陈述当成独立 counterevidence；
- Graph edge 不作为 direct Evidence；
- working-capital 变化不自动归因于单一产品或客户。

Source pack：

- ref=`configs/releases/fin_ia_0_1_s4_t04_dell_source_grounded_input_pack_v1_0.json`
- SHA256=`1a173ac6097195bdc6d2dd0f3d43544a947069d6848786f4fe9ca9eb805c8ec9`
- logical digest=`27842233fdc469d5824bdc30ba21b752e35948781254c20adb1fed38df3fe639`

## Canonical Materialization

通过既有 canonical CaseService、PlanningService 与 Runtime API 物化，不进行手写 SQLite 业务写入：

- Case=`case_7b5c2042bef3825b8df71a96`
- Case version=`1`
- DecisionSurface=`p02_decision_surface_d31fd75b31ad8385e9d8376a:v1`
- planning status=`accepted`
- Cell count=`3`
- input head digest=`97c9d6c09effa7293fe886d9d36e8a74a969e9a1dc3f8af2b435efbf1a08cebc`
- input object digest=`61293b24558b856f67c7826c7218852e064c47f5e69c607f5a0d291ae9221954`
- input object bytes=`200368`

连续两次 materialize 的 canonical logical digest 都为 `ed53001e3a11a243e88daeba73c1127181ce96ac7095c119a1ba6a75dde1bffe`。该 DELL Case 当前为 1 Case、1 CaseControl、1 DecisionSurface、3 Cells、14 evidence slots、2 planning checkpoints，以及 0 WorkUnit、0 Attempt、0 Run、0 Artifact。

## Fresh Proof

零调用 prepare 冻结：

- WorkUnit=`wu_p02_5_2ebc452430c3eac0db8de47c`
- Attempt=`attempt_fin01_87e5480ea908aff63ffe9e1f`
- Run=`research_run_fin01_2eced17671df87082b95db9a`
- input digest=`3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- preparation digest=`a293b64b958ea31f900173609e771ca3d5cfea21e693f9bb057a8e3d07e6f9e3`
- prospective admission digest=`da035e71d9eee81e9c76c5243a396bafaacfc29cd1f01e66eb1a66b8b757a60f`

三类 execution identity 均确认不存在于 canonical execution tables。prospective admission file 明确不存在，状态为 `unissued/unconsumed/execution_not_started`。

## 验证

- preparation 连续执行两次，decision SHA256 均为 `b4fd981df6c19f8b5f02bf1c8a3053fdc77d53bf4ed739e72eb31b8d8d45bf79`；
- target 二次 materialization logical digest 相等；
- S4 当前主线：`31 passed`；
- S1–S4 受影响相邻合同分组：`168 passed`；
- 下一项 admission issuance scope Project OS preflight=`pass`，0 open blocker；
- source network calls=`13`；
- model/provider/paid/admission/Run/business Artifact/Human=`0`。

## 下一步与边界

下一项为：

`S4-T04-DELL-FRESH-EXACT-ADMISSION-ISSUANCE`

签发步骤必须重新生成并精确比较 source pack、Case/DecisionSurface/input head、fresh identities、代码与 prospective admission digest，然后只原子写入一个 `issued=true / consumed=false / execution_started=false` admission 并停止。

DELL exact-live、九 Artifact、paired assessment 和 R2 均属于后续独立授权；MU、NVDA、Human R3、S4 pass、S5、release 与 production 均未认定。
