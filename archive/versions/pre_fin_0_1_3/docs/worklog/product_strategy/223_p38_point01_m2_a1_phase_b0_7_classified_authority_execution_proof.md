# P38 Point 01 M2-A1 Phase B0.7：authority 分类与 v2.10 execution proof

## 结论

当前状态仅为 `B0.7_repaired_refrozen_pending_independent_review`。未创建 active human approval、admission、receipt、正式 namespace、baseline 或 Step 2；没有网络、模型、tool/provider、full-chain、fixed/business/secret store 写入。

## 修复内容

- 新建 production `ProductionHumanJITWindowApprovalV2_10` 与 synthetic `SyntheticNonhumanAuthorityV2_10` 两个不可互换 schema；production authority 必须携带 total reviewer receipt、actor 与 decision-source provenance，生产 CLI 在任何路径/authority 创建前拒绝 test/synthetic/nonhuman authority。
- 新建 package-bound `execute_approved_window_core`：只接收 `ValidatedAuthorityContext`。temporary SQLite/local child 的四支实际同图 proof 覆盖 happy、corrupt actual、reviewer failure、child exit；失败分支 durable `outcome_unknown` 并拒绝 replay。
- oracle/reviewer artifact 先写入、readback、核验 digest，才可 append succeeded terminal；missing oracle、OSError、其他 post-consume 普通异常均安全收口为 outcome_unknown。closeout 只在 terminal 后幂等生成。
- v2.10 package 把 orchestrator、registrar、parent、clean child、core、tests 和 trigger normalized-DDL digest 一起纳入 Git-index hashes；`transport_isolation.runtime_hash_bindings` 与 authority entry 只引用 v2.10，旧代际仅保留 historical/superseded evidence。

## 冻结证据与验证

- package / gate：`667bda3783bffcb55a770c5988574fb9117b8bae0106ad1db1ff5a4b7267a177` / `6cb11b86eaa06ef9c1c6279d46a34618a63a13b2476d06340b20d537f8750f1b`
- plan / gate：`fcde99f18615e1498cdf0056ccb84260c5a6a26def8b52317e39f56c245d981f` / `c1e475a0bb7c8502d4e825a4bd197a5f520fa6c66d40349758a9f5086083b640`
- blueprint / gate：`972a232b1a08ba86766f2824ed9f342d37e4ba169aa7d68c16fde66f077abda2` / `c8a38f4b89362575640741d3ef7eebf32769e2f87df80c310b2974e9f6b1ebd1`
- `python -m pytest -q tests/contract/test_point01_m2_a1_v2_8_operational_proof.py tests/contract/test_point01_m2_a1_v2_10_execution_proof.py`：`22 passed`。
- v2.10 refreeze production validator 在 no-admission 状态 fail-closed 为 `package_admission_required`；formal namespace absent。fixed approval DB before/after SHA-256：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 保留边界

等待 total reviewer 独立审核。不得签发 active baseline approval、执行 baseline/剩余 15 场、进入 Step 2–5 或 M3–M7；不得执行 paid/full-chain、production cutover、商业数据采购、真实业务 Case mutation 或 legacy authority change。

## P0-A/P0-B repair/refreeze（2026-07-17，待独立复核）

第一轮独立复核拒绝旧 `667bda…` 包：review receipt 只是一对 approval 内字符串，且 production callback 可替换 lifecycle。此次不重跑 baseline，只完成以下定向整改：

- `ProductionReviewerDecisionReceiptV2_10` 成为 package-external immutable artifact；production preflight 显式加载并验证 receipt digest、actor/reviewer、decision/source、six个 package/plan/blueprint digest、scenario/scope/boundary/namespace 与有效期。
- 删除 callback production path；唯一 kernel 负责 register、consume、v2.10 parent/clean-child leaf、actual validation、真实 oracle/reviewer、terminal/recovery。production 与 synthetic 只能差异化 authority/root/leaf。
- 新增 P0 回归：missing/digest/actor/package drift receipt；resolved read-only production preflight；四个真实 v2.10 child branches；first `open_existing` failure 后通过 known authority root recovery 成为 `outcome_unknown`；replay denial。

本次 superseding artifacts：package/gate=`789684d17a1e928f829869db60b2ef2ce4eac49d0dbee7cff377edc879b72e02` / `52d388be0666e25f23587129059c8edb1b9a323ad86d88768b030b69c5fd82b3`；plan/gate=`5ad5fcd297fde6c9dc9dfc43b19c8caade50ceb523dda77014d8b439a1a6f2fa` / `98a5d7eceabc84808023a44e34af6b3f8a3c085a1f888205dfc7bec2c58209b4`；blueprint/gate=`20244a5b289507b492299e449bbfede881d420926921132395e2ad752cbe7cac` / `89109d721a457874df243b0775db458c5552fb11d27c20799ed5268651f47d96`。`26 passed`；fixed approval DB SHA-256 仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；所有正式 authority/namespace/baseline/external count 均为 0。
