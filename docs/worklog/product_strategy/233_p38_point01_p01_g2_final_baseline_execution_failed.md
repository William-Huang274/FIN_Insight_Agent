# P38 Point 01：P01-G2 final candidate-bound operational baseline 失败停机

日期：2026-07-17

状态：`P01_G2_FINAL_BASELINE_FAILED_USER_DECISION_REQUIRED`

## 已执行的唯一授权范围

仅运行 `m2-a1-ai-semis-input` / `p01-baseline-separated-input`，使用显式冻结入口
[run_point01_p01_g2_1_candidate_bound_baseline.py](D:/FIN_Insight_Agent/scripts/engineering/run_point01_p01_g2_1_candidate_bound_baseline.py)。

执行前，candidate 四件套、bridge 四件套、inner v2.10 family、105 项 Git-index/working 输入、CaseInstancePack、四份 stable contracts、fixed approval DB 指纹与空 namespace 均通过核验。candidate 与 bridge 的批准 digest 分别保持为：

- candidate package：`bba3ce4bc30467b4997e2be71803e8bf01608411dae6dc0a27a60f6a02ac75f9`
- bridge package：`06a3ef6b5f1d8677e79e81676131ae3b8e83fcd87f9ccaeb9ed911100360f879`
- inner v2.10 package：`4ca222da5dd5ab7991d258d49eb30a377e6c8f82e1a0885d8912567324d3d5e8`

## 终态证据

- reviewer decision digest：`fcc59334cbe11dd65808dce34a0b792d03989f297031e430ce7ec07c603de640`
- HumanApproval digest：`d71a11583c1be136cb611d59a9f387bf8dc7c765945f1297a5d5d79fa2b9cadc`
- receipt lifecycle：`REGISTERED → CONSUMED_BEFORE_RUN → TERMINAL(outcome_unknown)`
- terminal digest：`728d9ebd2e5c215f0c782f258c22e154658f316286e3c058ce43c379b99f0342`
- child incident envelope SHA-256：`9bbb7cc3d0077865cff6cf5b97eb884de87e2071e8904a9a105dd23228a5aa62`

child 在 `production_actual_clean_child` 阶段以 return code `1` 结束。仅生成受限、脱敏的 incident envelope；没有 actual、oracle 或 reviewer artifact，故未产生 success terminal。

## 计数与边界

- baseline attempt：1；baseline success：0；actual/oracle/reviewer artifact：0
- authority/admission/receipt registration/receipt consume/runtime materialization：各 1
- terminal outcome unknown：1；negative case：0
- network/tool/model/provider success、fixed/business write、legacy authority change、真实业务 Case mutation：均为 0
- fixed approval DB SHA-256（前后）：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`

正式运行根目录保留在 `D:/temp/FIN_Insight_Agent/point01_m2_a1_candidate_bound_final_baseline_v2_10`，不得清理、覆盖或作为后续输入。receipt 已消费，禁止 replay、retry、renewal、replacement receipt 或自动 repair。

## 已知边界

脱敏 stderr 仅足以证明 child 进程非零退出，不足以确认具体根因。既有 frozen child package-path 假设只能作为候选，不能在缺乏可复现证明时标记为根因。本轮不执行三个 negative，也不进入 P01-G3、Step 3-5、P01-G5 或 FIN 0.1 entry；后续必须由用户重新裁决。
