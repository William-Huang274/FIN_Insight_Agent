# Model Run：MU DeepSeek Pro R7 WWC candidate/selected cardinality failure

## Summary

- Run ID：`20260730_fin_ia_0_1_s4_t06_mu_deepseek_pro_r7_WWC_candidate_selected_cardinality_failure_r1`
- Purpose：执行唯一一次 Claim compiled-contract v2 formal MU exact-live，验证六节点、12 receipts/capture-v2、9 Artifacts 与最终 L1
- Status：`terminal failed / project-owned WWC cross-layer contract drift`
- Run type：inference
- Timestamp：2026-07-30 21:39:27–21:39:47 +08:00
- Environment：local Windows，Python 3.10.11
- Provider/model：DeepSeek / `deepseek-v4-pro`

## Code And Command

- Git：`54d2e072`，branch=`codex/layered-data-source-expansion`，历史累计 dirty worktree
- Entry point：`scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`
- Admission：`fin01-s4-t06-mu-claim-support-role-v2-fresh-exact-admission-r7`
- Execution identity：`fin01-s4-t06-mu-claim-support-role-v2-final-exact-live-r7`
- Retry：0；transport attempts per call：1
- Supervision：`fin01.s3.exact_run_supervision:v2`

## Inputs

- Case：MU，case version=1，as-of=`2026-07-26T00:00:00Z`
- Input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- Preparation digest：`610e86e10bc3a4a4bf8d67952f1a9cd21683661d4d5b86b2e02cf64ef160a033`
- Claim contract：`fin01.s4.deterministic_judgment_atom_planner_and_compiled_contract_invariants:v2`
- Candidate boundary：Provider WWC maximum=6；intended local selected maximum=3
- Source network / external tools / live business head writes：disabled

## Outputs

- WorkUnit：`wu_p02_5_b1ba05e5d4200026121136da`
- Attempt：`attempt_fin01_200b7d2e9df3174d116ac3df`
- Run：`research_run_fin01_0a14c336e71a863ca383784b`
- Terminal states：`failed / failed / failed`
- Completed nodes / Artifacts：`0 / 0`
- Runtime result：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_claim_support_role_v2_r7_live_execution_result.json`
- Durable result：`configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_exact_live_execution_failure_result_v1_0.json`

## Results

- Calls：semantic/provider/network=`3/3/3`
- Tokens：input/output/total=`13,108/1,120/14,228`
- Cost：USD `0.00667638`
- Latency sum：`11,564 ms`
- Receipts/capture-v2=`3/3`
- Retry/fallback/replay/relaunch/rerun=`0/0/0/0/0`

三个调用均返回 `status=ok / finish_reason=stop`。第三段 WWC 输出是合法 JSON，并返回 model-visible 合同允许的 6 个 candidate；本地 assembler 却在 selection 前以最终 selected 上限 3 拒绝，触发 `s4_compiled_wwc_atom_shape_invalid`。

## Experiment Governance

- Hypothesis：Claim v2 与 compiled-contract invariants 可让 formal MU full-chain 达到 9 Artifacts 并通过 L1
- Decision target：coherent 6 nodes / 12 calls / 12 captures / 9 Artifacts / independent L1 / retained Agent gain
- Ceiling：12 calls，16800 output tokens，USD 0.10，retry=0
- Baseline：当前 deterministic three-case full-fake=`6/12/12/9`
- Stop condition：首个可信 L1 立即停止，无 R8
- Decision label：`stop / project-level disposition required`
- Mainline decision：R7 已消费，不可重跑；paired/owner/T07 不具资格

## Runtime Efficiency

- Wall time：约 20 秒
- Provider latency sum：11.564 秒
- Failure occurred after：3 calls / 14,228 tokens / USD 0.00667638
- Efficiency diagnosis：不是性能瓶颈；fail-fast 在第一个 specialist node 内终止，避免剩余 9 次调用
- Serving implication：在修复 candidate/selected cardinality 分层前，不可放开该 WWC Provider surface

## Caveats And Next Step

- 没有生成可做金融质量 paired assessment 的 Artifact；
- 本结果不证明 DeepSeek 整体不可用；
- 它证明项目的 WWC model-visible candidate contract 与 local final-cardinality enforcement 不一致；
- next=`S4-T06-MU-R7-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION`。
