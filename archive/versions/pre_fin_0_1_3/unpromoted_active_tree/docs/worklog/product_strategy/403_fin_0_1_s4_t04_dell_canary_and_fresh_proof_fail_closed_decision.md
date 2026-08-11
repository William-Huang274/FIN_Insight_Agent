# FIN 0.1 S4-T04 DELL Canary And Fresh-Proof Fail-Closed Decision

日期：2026-07-26

## 结果

S4-T04 的 Provider-only canary 判定完成并选择 `omit`；fresh-agent proof 未冻结，T04 未完成。项目在 admission 前因 `RC-P36-056` fail-closed。

用户以“继续”批准严格限于 T04 的零调用 canary-need 与 fresh-proof 决策。本轮没有执行 source route、模型、Provider、付费调用、canonical DELL Case/Run 写入、admission、业务 Artifact 或 Human review。

## Canary 决策

DELL 相对已验证 S3 主线只改变 issuer identity、research profile、case-local method context 和 input head。以下 Provider-owned 或 transport surfaces 没有改变：

- DeepSeek provider/model 与 beta endpoint；
- Specialist v7、Research Lead v5、Memo Writer v3 transport；
- output-v4、Verifier state-machine-v2；
- restricted capture policy 与 supervision-v2；
- retry/fallback/replay/relaunch/rerun=0。

因此没有具名的 Provider-only 风险。单节点 canary 既不能证明六节点跨 Cell coherent product，又会增加一次不能替代 exact-live 的付费链，故省略。

## Fresh Proof 为什么停止

T02 DELL Case Pack 只包含问题、权限、method 与 typed boundary：

- Evidence/Numeric/Graph/Claim/Judgment/conclusion 均为 0；
- canonical CaseVersion ID 为空；
- P34 有 11 条 DELL issuer/product/customer official-source routes，但全部为 `planned_not_executed`；
- 11 条路线均禁止未经执行与 parser lineage 直接 promotion；
- parser-backed promotable DELL row 为 0；
- target canonical runtime 的 DELL Case/DecisionSurface/WorkUnit/Attempt/Run 均为 0。

因此无法冻结一个可运行、source-grounded 的 input digest、WorkUnit、Attempt、Run 或 prospective admission。继续签发只会让付费模型重新发现确定性已知的 cannot-infer 空输入，这违反 Project OS 的 upstream-first 与 full-chain guard。

## 验证

- T04＋T03 focused：`13 passed`；
- S3→S4/Workbench 相邻合同回归：`77 passed`；
- preparation script Python 编译通过；
- read-only preparation 连续两次完全相等，canonical digest=`ee131c187e1dd83d1963fca3a96b0aaacc4640e7b60c55bc119acc542590495f`；
- next repair scope Project OS preflight=`pass`，0 open blocker for that allowed repair scope；
- canonical database read-only audit前后 SHA256 相等。

正式决策件为 `configs/releases/fin_ia_0_1_s4_t04_dell_provider_canary_need_and_fresh_agent_proof_decision_v1_0.json`，SHA256=`0c2cf1a84fb78c3e3dc86f2dd10bd93c37ff4c6321a2825d2b686773c2ce289c`。

## 下一步与边界

下一项为需独立授权的：

`S4-T04-DELL-SOURCE-GROUNDED-EXACT-INPUT-HEAD-MATERIALIZATION-AND-FRESH-PROOF-REPAIR`

该步骤应执行 bounded official DELL source routes，记录 locator/parser attempt，仅 promotion issuer-bound Evidence/Numeric 与 context-only Graph，保留未支持产品利润/客户分配的 typed cannot-infer；之后物化 canonical DELL CaseVersion/input head，再重跑 fresh nonreuse proof。

在 `RC-P36-056` 关闭前，不允许签发 admission 或进入 S4-T05 exact-live。DELL R2、MU R2、NVDA R3、S4 pass、S5、release、production 均未认定。
