# FIN 0.1 S3-T09：owner-grade v3 segmented fresh exact admission 签发

日期：2026-07-22

## 问题与授权

用户以“授权”允许当前唯一下一项 `S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-ADMISSION-ISSUANCE`。本轮只能把已冻结的 admission payload 和 digest 原样签发；不得消费、调用模型/Provider/网络/source/tool、创建 canonical WorkUnit/Attempt/Run/Artifact、比较 baseline、执行 Human Review，或进入 T10/S4/release/production。

## 决策与实施

签发前 Project OS scoped preflight 通过。新 admission 文件严格等于 decision 中的 prospective payload：

- admission ID：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-exact-admission-r1`；
- digest：`8ac50f35b786f954db11d36b851145f8e476653a2be887124c7ad33fdafc17a9`；
- frozen Run：`research_run_fin01_613dad1d30f9ce5357213b21`；
- input digest：`41179ecdca0853e0e4d1a49af6ada129cb5bfae5913891b0a184eb900a60dd05`；
- transport：`fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v1`；
- output contract：`fin01.s3.bounded_agent_three_cell_output:v3`；
- budget：12 次 semantic/provider/network call，三个 Specialist 分段预算各为 1600/1200/1400，aggregate output ceiling=16200，USD cap=0.10；
- attempt=1，retry/fallback/repair/rerun=0，首个 parse/shape/schema/semantic/length failure 必须 terminal fail-closed。

签发回执明确记录 `issued=true`、`consumed=false`、`execution_started=false`。credential 只检查环境变量存在，未读取、输出或持久化值；Provider callback 构造计数为 0。当前 `LLM_GATEWAY_TRANSPORT_RETRIES` 仍未设为 0，因此未来执行前必须重新满足该预条件。

## 结果与证据

目标 runtime 保持四个历史 ResearchRun 和十三个 Artifact；新 WorkUnit/Attempt/Run 均仍不存在。canonical DB SHA256 保持 `91ea473f...f39c`，Object tree SHA256 保持 `00ac740b...a75`。

新增或更新：

- `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_exact_admission_v1_0.json`；
- `configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_issuance_v1_0.json`；
- `tests/contract/test_fin_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_issuance.py`；
- current backlog、Project OS 三类账本、context/handoff 和两份源计划。

精确 affected suite 为 `89 passed in 3.41s`。此前完整 S3-T09 通配回归超过 180 秒命令外壳时限，未产生失败断言；随后改为本轮新增合同及全部被推进 current-backlog 断言的精确回归集。首次专项测试中的只读快照字段名误写为 `artifact_ids`，已按真实字段 `artifact_refs` 修正；这不涉及运行时或验收放宽。

本轮没有模型训练、推理、Provider 请求或付费任务，因此没有新增 model-run ledger。

## 后续与安全边界

当前下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-LIVE-EXECUTION`，仍需单独授权。即使获授权，也必须先设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0`、重跑 exact zero-call preflight，再 exact-once 消费 admission；无论成功或失败都停止，不得自动 retry/fallback/repair/rerun、paired comparison 或 Human Review。

RC-P36-039 与 RC-P36-037 都保持 full-chain blocker；签发本身没有提升 research-quality maturity，也不能证明 junior analyst 质量。
