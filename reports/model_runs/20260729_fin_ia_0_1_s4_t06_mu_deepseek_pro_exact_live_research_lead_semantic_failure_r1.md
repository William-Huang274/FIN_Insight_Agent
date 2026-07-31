# MU DeepSeek Pro exact-live R1：Research Lead semantic failure

## Summary

2026-07-29 执行了唯一授权的 S4-T06 MU R1 exact-live。9 个 Specialist segment 完成，Research Lead Provider 调用成功返回，但本地 semantic validator 因 `fact_presence_summary` 与 Claim Card support facts 的确定性摘要不一致而 fail-closed。运行无孤儿进程、无 transport failure、无 retry，未生成业务 Artifact，也未进入 success-only paired assessment。

## Command and code path

入口：

`python scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py launch ...`

主路径：

- `scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`
- `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_live_validation.py`
- `src/sec_agent/s3_bounded_agent_profile.py`
- `closed_research_lead_output:v3`

supervision root：

`.codex_runtime/fin01-s4-t06-mu-fresh-exact-r1-supervision-r1`

## Frozen inputs

- Case：`case_ec7da8015386e7bfeda92c61`
- DecisionSurface：`p02_decision_surface_dd094559ce4c0f79d242e852:v1`
- exact input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- execution identity：`fin01-s4-t06-mu-fresh-exact-live-r1`
- admission digest：`56005ffb1227e9ec1ead1b73b780342dfeaeef06bbdb0eff01592d7cdc19c891`
- provider/model：`deepseek / deepseek-v4-pro`
- base URL：`https://api.deepseek.com/beta`
- retry budget：`0`

## Settings and governance

- ceiling：12 model calls、12 provider calls、12 network calls
- output-token ceiling：16,800
- cost ceiling：USD 0.10
- automatic retry/fallback/replay/relaunch/patch/rerun：禁止
- paired assessment：仅在六节点 coherent success、typed Verifier success、12 receipts/captures 和 9 Artifacts 全部成立后允许
- raw Provider HTTP、private reasoning、credential：不得持久化

## Outputs

- Specialist：3 nodes / 9 segments，全部 `ok/stop`
- Research Lead：call #10，`ok/stop`
- Writer：未调用
- Verifier：未调用
- WorkUnit/Attempt/Run：`failed/failed/failed`
- Artifact：0
- orphan：false

终态错误：

`s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch`

stage=`research_lead`，phase=`node_envelope_accounting`，validator=`closed_research_lead_output:v3`，subtype=`fact_presence_summary_mismatch`，field=`conflict_adjudications.fact_presence_summary`，failing count=`1`。

## Usage and efficiency

- calls model/provider/network：`10/10/10`
- transport attempts/failures：`10/0`
- input/output/total tokens：`51,164 / 6,882 / 58,046`
- cache hit/miss：`2,816 / 48,348`
- total cost：`USD 0.02702893`
- receipt latency sum：`93,426 ms`
- receipts/captures/readbacks：`10/10/10`

运行在预算内停止；由于失败发生在 Writer/Verifier 前，剩余 2 次调用和对应成本没有发生。

## Interpretation

模型输出通过传输与枚举形状校验，但在一个可由已绑定 Claim Cards 确定性重算的摘要字段上语义不一致。该现象同时具有两层责任：

1. 模型没有在该字段遵循输入事实关系；
2. 项目仍把确定性派生值交给模型生成，尽管历史 RC-P36-041 已指出应本地派生。

因此不能把结果描述为网络或 Provider 故障，也不能仅靠 prompt 加码后重跑。下一步是零调用结构性 disposition。

## Caveats and acceptance

- 本轮没有 9 Artifacts，不能评价最终 Memo、Verifier 或 Agent 相对 baseline 的成品增益；
- paired baseline/assessment 未执行是成功门禁的预期行为；
- owner acceptance、MU R2、T07、S4/S5 均未获得；
- strict-schema transport 仍独立停放。

## Evidence

- release result：`configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_failure_result_v1_0.json`
- release result SHA256：`ac048a27964330f776e0452f0fe7fff3d064805b5e6fadccb695d2460ee5a930`
- runtime result SHA256：`66514372b85cd3b8f2abbb1e1df33254d700ae9c86a62558288ec057675b4fa7`
- terminal inspection SHA256：`45c53b09de9964b97a540657842ec76d71653994476f05f2ae4f416481982dbe`
- tests：focused/current `16 passed`；S4-T06 `131 passed`
