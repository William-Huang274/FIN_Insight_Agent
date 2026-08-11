# 394 — S3-T09 layered runtime alignment 与 final exact-live

日期：2026-07-25
状态：`runtime_alignment_live_path_passed / verifier_repair / zero_artifacts / T09_blocked`

## 目标与授权

用户授权先按分层 Agent 验收标准实施 runtime alignment，再签发全新 admission 并执行一次 exact-live；只有同一 coherent Run 产生九个 Artifact 后才进入配对验收。未授权自动 retry、fallback、replay、relaunch、rerun、captured-output rewrite、owner acceptance、T10、S4、release 或 production。

## Runtime alignment

新增 `fin01.s3.research_profile.nvda_three_cell:v4`：

- 320 字符为质量 target；
- 512 单字段与 3200 aggregate 为非终止 L3/L4 quality ceiling；
- 8192-byte Provider wire、6000-byte canonical alias 与 local-expanded envelope 继续是硬容量；
- blank/non-string、scope、Numeric、authority、identity、lineage 与 permission gate 不变；
- 历史 profile-v3 与既有 terminal truth 不回写。

Provider request、local assembly、quality observation 与 fake Verifier fixture 同步。聚焦 runtime/profile/Lead-v5/output-v4 回归为 `34 passed`；完整 fake path 可在质量 finding 存在时生成九 Artifact。

## Fresh proof 与 admission

- admission digest：`424add2dd9105a9a775af36bb31af4c62e6f1654597fccee7b1ebbee86f66550`
- WorkUnit：`wu_p02_5_373d25143a8098705ee4586f`
- Attempt：`attempt_fin01_36f3d705973f68a4d8df4244`
- ResearchRun：`research_run_fin01_db6800815317852334584e51`
- profile：`fin01.s3.research_profile.nvda_three_cell:v4`

两次 proof prepare 相等；Project OS scoped preflight 与 runner exact zero-call preflight 均通过。fresh identity 在消费前不存在，credential 只确认存在，未读取或持久化值。

## Exact-live 结果

supervision-v2 直接启动 actual runner，runner self-finalized exit receipt，exit code=0；只读 monitor 无 mutation 或 signal。

完整调用路径：

- 9 个 Specialist segments：全部 `ok/stop`
- Research Lead：`ok/stop`
- Memo Writer：`ok/stop`
- Verifier：`ok/stop`

计量：

- model/provider/network：`12/12/12`
- input/output/total tokens：`54,070 / 6,035 / 60,105`
- estimated cost：USD `0.02573402`
- capture/readback：`12/12`
- retry/fallback/replay/relaunch/rerun：`0/0/0/0/0`

Lead 的 wire 为 3282 bytes，aggregate narrative 为 2106 字符，最大字段 394 字符；仅一项超过 320 target，没有超过 512 或 3200。旧 narrative terminal failure 未复发，runtime alignment 的 live path 成立。

## 首个终止点

Verifier 返回合法 native JSON、四层顺序与完整五字段 finding。`artifact_or_claim_refs` 使用明确的 typed scoped-ref object：

`identity_kind + program_cell_id + local_id`

本地 shape gate 仍要求 nonblank string，因此以 `s3_bounded_verifier_finding_schema_invalid` 停止。这是项目内 L2 representation drift：request 的 “exact ref” 与 typed identity contract/local validator 没有单源生成。

但不能只把 dict 转成 string 后宣布成功。Verifier 本身的状态是：

- deterministic integrity：pass
- semantic fidelity：review_required
- financial coherence：review_required
- visual delivery：pass
- decision：repair

typed issue codes：

- `scope_digest_mismatch`
- `unresolved_cross_cell_conflict`
- `unattributed_company_total_margins`

这些 finding 触及 scope、conflict 与 attribution，必须进入 L1 integrity review；不能 silent normalize、忽略、改写 capture 或从历史 Run 拼接 Artifact。

## Canonical truth 与阶段结论

- WorkUnit / Attempt / ResearchRun：`failed / failed / failed`
- terminal consistency：true
- orphan：false
- Artifact：0
- paired comparison：未开始
- owner acceptance：未写入
- S3-T09：blocked
- T10/S4/release/production：未授权

下一步仅为零调用：

`S3-T09-VERIFIER-TYPED-SCOPED-REF-L2-RECOVERY-AND-L1-SEMANTIC-FINDINGS-DISPOSITION-ZERO-CALL`

先统一 typed exact-ref 的 request/validator/fake Provider 合同，并用 canonical evidence 分别处置三个语义 finding；在此之前不得自动签发第二次 live。

## 证据

- `configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_runtime_alignment_zero_call_implementation_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_final_fresh_agent_proof_decision_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_final_fresh_exact_admission_issuance_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_final_exact_live_execution_result_v1_0.json`
- `tests/contract/test_fin_0_1_s3_t09_layered_acceptance_runtime_alignment.py`
- `tests/contract/test_fin_0_1_s3_t09_layered_acceptance_final_exact_live_result.py`
