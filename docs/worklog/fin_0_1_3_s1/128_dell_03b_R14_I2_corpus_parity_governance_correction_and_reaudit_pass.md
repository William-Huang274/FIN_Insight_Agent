# S1 工作记录 128：DELL 03B R14 I2 corpus parity 治理纠正与 fresh re-audit PASS

日期：2026-08-29
状态：`R14 implementation frozen at 7e25cad9 / unique preview FAIL 239 cases / I2 governance PASS 0/0/0/0 / separate owner decision required before same-R14 revised implementation`

## 1. 安全续接与精确 Git 身份

本轮依据 `D:\temp\codex_history_recovery_checkpoint_2026-08-29.md` 恢复工程连续性；不读取、fork 或修改旧主任务的 live SQLite／JSONL，也不把旧任务 UI 当作最新事实源。

- 目标分支：`codex/fin013-dell-s1-s2-product-bridge`；
- R14 implementation freeze commit：`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- 实际分支 checkout：`D:\FIN_Insight_Agent`，续接开始时 clean 且 HEAD 精确为上述冻结提交；
- Codex 安全续接 worktree：以 detached HEAD 从同一冻结提交开始，避免同一分支被两个 worktree 同时占用；
- 本轮未创建 R15／R16，未改写任何既有失败、formal attempt 或私有证据。

## 2. 冻结 preview 事实

唯一既有 corpus parity preview 暴露 `27,026` 个 case 中 `239` 个失败、`26,787` 个通过：

- `228` 个 `R14_graph_event_semantics_recomputation_failed`；
- `11` 个 `R14_graph_event_assertion_semantics_recomputation_failed`；
- source lane=`135`，compiled lane=`104`；
- `239/239` primary case key 唯一，失败文本 digest=`235` 个；
- frozen source：`1,888` rows，SHA-256=`d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45`；
- frozen compiled：`34,199` rows，其中首个 unique model-text case=`25,138`，SHA-256=`1c3e48486f933d23306dbabacb1641e26cb9bbc5b474da932d602752dff3fa92`。

安全续接时在冻结 snapshot 上只读复算，精确重现上述 `27,026 / 26,787 / 239 / 228 / 11`。这不是新的正式 attempt，不写结果、不调用模型／Provider／网络／外源，也不产生任何 downstream authority。

## 3. I2 v1.0 候选与 fresh FAIL

首个 owner-visible failure freeze 候选为：

- commit：`8544c7ee5f1cdcbe8863591714775bae9f656157`，parent=`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- artifact：`configs/audits/fin_ia_0_1_3_commit_7e25cad9_dell_03b_r14_i2_corpus_parity_failure_freeze_v1_0.json`；
- result digest=`7ebe811d7a9cc2a3e7c113f43aa8418ef2e69150fb7d9147b3fcfb0880f1cd02`；
- failure inventory digest=`49acf114c03ab97e059ee3bd928736d06d70b1d5a6d8d3af2dcdfabc68e2a5d1`。

全新、作者分离、`fork_turns=none`、只读 reviewer `/root/r14_i2_readonly_audit` 对 exact commit 给出 `I2_GOVERNANCE_FAIL_REVISION_REQUIRED`，`P0/P1/P2/P3=0/0/2/0`：

1. case-only inventory 未冻结 `277` 个 event mismatch 的完整分母与子形态；
2. downstream deny set 未完整覆盖计划中的禁止面。

失败已 append-only 保留于 `configs/audits/fin_ia_0_1_3_commit_8544c7ee_dell_03b_r14_i2_governance_audit_fail_v1_0.json`，result digest=`116ed25b1f4f30d3026edd3a73fa166eede4fbff63e3a54ed3d17260633e6800`。不得把 v1.0 的失败改写成 PASS。

## 4. v1.1 纠正冻结与两类最早责任层

治理 successor commit=`8e7e76932a38dc920d99583aad7883a2d7ef7de5`，parent=`8544c7ee5f1cdcbe8863591714775bae9f656157`。v1.1 artifact 为 `configs/audits/fin_ia_0_1_3_commit_7e25cad9_dell_03b_r14_i2_corpus_parity_failure_freeze_v1_1.json`，其：

- result digest=`93bd682707bb5f5ee3cfd337edae76c7f74d2e5bb23f4388bd9b035c6e73373a`；
- case inventory digest=`49acf114c03ab97e059ee3bd928736d06d70b1d5a6d8d3af2dcdfabc68e2a5d1`；
- event inventory digest=`68d267f77400a350cd698bf3c4baf7152067b437290084596a4fa370965276e5`；
- 完整冻结 `239` 个 case 与 `277` 个 event mismatch，`277/277` stable event key 唯一且 `239/239` case link 完整。

`277` 个 event 的完整子形态为：

| 最早责任层 | 根因／形态 | event 数 |
|---|---|---:|
| `R14-02_EventArgumentGraph_producer` | `RC01_SYNTHETIC_EMPTY_UNKNOWN` | 246 |
| `R14-02_EventArgumentGraph_producer` | `RC01_SYNTHETIC_EMPTY_UNKNOWN_WITH_SCOPE_AMBIGUITY` | 9 |
| `R14-02_EventArgumentGraph_producer` | `RC01_SYNTHETIC_NOMINAL_PRICE_PARTIAL_AUGMENTATION` | 5 |
| `R14-02_EventArgumentGraph_producer` | `RC02_ASSERTION_REPORTED_TO_ISSUER_FINAL_MENTION_DRIFT` | 17 |

这里仅有两个根因簇，没有第三簇：

1. synthetic ambiguous predicate 在 producer 初始分支中写入空 semantic labels 与 `unknown`，即使 predicate word 位于冻结 semantic vocabulary；后续 nominal-price 分支还可能只局部补 ASP/pricing，形成语义不完备；
2. producer 以中间态 `attribution_mentions` 计算 `speech_mode`，validator 则以最终 `graph.mentions` 复算，导致 17 个 event 从 `reported_speech` 漂移为 `issuer_reported`。

两者都是项目内、同一 R14、同一 producer 层的实现责任；不能甩给 validator、R14-04 或外部信息边界。

## 5. fresh re-audit 结果

第二名全新、作者分离、`fork_turns=none`、只读 reviewer `/root/r14_i2_rereview` 对 exact commit `8e7e7693...` 完成 re-audit：

- verdict=`I2_GOVERNANCE_PASS`；
- `P0/P1/P2/P3=0/0/0/0`；
- 从 frozen input 独立重建 `239` 个失败 case，检查 `11,621` 个 final events；
- 与 v1.1 完整 event inventory 做 `277/277` object equality；
- 重算 `246 + 9 + 5 + 17 = 277`，确认无第三根因簇且两簇最早责任层均为 `R14-02`；
- 检查 exact acceptance、case/event identity、停止条件和 downstream deny matrix，确认 deny matrix 是 source plan 的严格超集。

PASS receipt：`configs/audits/fin_ia_0_1_3_commit_8e7e7693_dell_03b_r14_i2_governance_reaudit_pass_v1_0.json`，result digest=`b46a9b5d0027f704a0413022691220c199d1a133b5d38c6cbae6eed0ff90a16a`，Git blob=`b2b48b37ccea0debc3fa823f58c87c3d0478c0f0`，file SHA-256=`2adc01ac07793b24df2574ee09ba0a7515ef64b4706e16b54c09a8c1fc3dddc6`。

两个 reviewer 均为 read-only；writes／git mutation／formal／network／model-provider／external-source／downstream action 全部为 `0`。第二名 reviewer 没有重跑完整 `27,026` preview；它只对已冻结 `239` 个失败 case 做全 event 复算，未来完整 zero-failure replay 仍是实现验收义务。

## 6. 冻结输入合同、验收与停止条件

若 Owner 另行授权同一 R14 revised implementation，必须同时满足：

1. frozen source/compiled SHA、rows、case identity 与 denominator 不变；
2. `27,026/27,026` case 零失败；
3. 本次冻结的 `277/277` event mismatch 全部消除；
4. zero new failure code；
5. 原 R14 population/event/price/property/mutation/resource/transaction/privacy gates 全部保留；
6. 禁止按 case key、text SHA、event ID 做特例，禁止只修首个 exception，禁止弱化／绕过 validator；
7. 修复后仍须新的 author-separated read-only pre-formal review；未 PASS 不得进入 B／policy／formal。

建议的同 R14 修复边界只有两项：

- ordinary 与 synthetic predicate 共用一套 canonical semantic derivation；
- assertion attribution 以 finalized graph 为唯一输入，或采用等价的 deterministic two-pass 计算。

若一次同 R14 修订仍无法把 frozen `239/277` 与完整 `27,026` 验收全部清零，立即停止在同一 R14，保留新 attempt identity 并回到 Owner 决策；不得用 R15/R16、validator weakening、case special-case 或扩大到外源／模型来规避。

## 7. 当前权力边界与建议

I2 PASS 的唯一效力是：证据已经足够让 Owner 作出一次独立的“是否授权同一 R14 revised implementation”决定。它本身不授权改代码。

当前继续冻结：R14 implementation change、B／pre-formal、policy／formal、03C、外源补源、0.6B/4B、reranker、Evidence admission、Pack/Readiness、S2/S3、新研报、qualified-human、产品、publication 与 release；`all_downstream_authority=false`，未列动作也不获权。

项目建议为“授权同一 R14 的有界 revised implementation”，理由是两个根因都已由完整 `239 case / 277 event` 证据定位到 `R14-02`，没有第三根因簇，且可以在不改变产品范围、输入、validator 或下游门的情况下修复。但在 Owner 明确批准前，代码必须保持在 implementation freeze `7e25cad9...`。

## 8. 治理收口验证与既有测试阻断

- PASS receipt canonical result digest 复算 exact：`b46a9b5d0027f704a0413022691220c199d1a133b5d38c6cbae6eed0ff90a16a`；v1.0、FAIL receipt、v1.1 的 result digest 也分别复算 exact；
- configs JSON：`1,187` 份全部可解析；Project OS JSONL：`8` 份／`1,412` 行全部可解析；
- 与本次 ledger 追加直接相关的 `test_current_fixed_pack_decision_passes_without_network_or_secret_read` 和 `test_new_scope_specific_blocker_fails_closed`：`2 passed in 2.66s`；
- `git diff --check` 与 governance-only changed-path guard：通过，未触及实现/runtime 路径。

完整 `tests/test_project_os_preflight.py` 未通过，首个失败为既有历史 S3 binding：`configs/research/evals/fin_ia_0_1_3_s3_multi_agent_preview_zero_call_result_v1_2.json` 当前 checkout SHA-256=`98ccb9166aabe13723e7fbf96f0f1bc1197d789a7de4d4cffaca4326928c60ca`，历史 decision 期望=`aae7214b118e12f4c438b4fa0234140042c3736d301c32faace0d35fe69bf7ac`，触发 `project_os_artifact_sha_drift`。该文件相对当前 HEAD 无 diff，本轮也未改 S3 artifact 或 decision；因此这不是 I2 的新 finding，不能在 R14 I2 治理收口中顺手修复。失败保持可见，相关完整套件不得宣称 PASS。
