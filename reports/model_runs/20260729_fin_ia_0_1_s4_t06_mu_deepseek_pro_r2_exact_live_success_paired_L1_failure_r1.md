# MU DeepSeek Pro R2 exact-live success / paired L1 failure

## Summary

2026-07-29 执行唯一授权的 S4-T06 MU R2 exact-live。六节点、12 次 Provider 调用和 9 个 Agent Artifacts 全部技术成功，Lead-v7 的本地 fact-presence materialization 得到真实证明。随后 success-only deterministic baseline 和独立 paired assessment 发现 critical numeric-authority 与 case-identity failures；因此 MU R2 未通过，未执行 owner acceptance、R3 或 T07。

## Repository and command

- repository：`D:\FIN_Insight_Agent`
- branch：`codex/layered-data-source-expansion`
- worktree：执行前后均为已存在的大型 mixed dirty state；本轮未清理、覆盖或自动提交用户改动
- entry：`scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py launch`
- runner：`scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_live_validation.py`
- supervision root：`.codex_runtime/fin01-s4-t06-mu-fact-presence-local-materialization-r2-supervision-r1`
- retry/fallback/replay/relaunch/rerun：全部禁止且实际为 0

## Frozen inputs and settings

- Case：`case_ec7da8015386e7bfeda92c61`，ticker=`MU`，version=`1`
- DecisionSurface：`p02_decision_surface_dd094559ce4c0f79d242e852:v1`
- exact input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- admission digest：`55fb08cac25b3a03109b13ae645d858b90b2074873f5355e6ed47ac93c6cd65c`
- provider/model：`deepseek / deepseek-v4-pro`
- endpoint：`https://api.deepseek.com/beta`
- Specialist transport：`fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7`
- Research Lead transport：`fin01.s3.bounded_agent.research_lead_owner_grade:v7`
- fact-presence policy：`fin01.s3.research_lead.conflict_fact_presence_local_materialization:v1`
- ceilings：12 model / 12 provider / 12 network calls，16,800 output tokens，USD 0.10
- credential：仅运行时使用；值未持久化或输出

## Exact-live outputs

- WorkUnit：`wu_p02_5_43322e55457b647277d2297a`
- Attempt：`attempt_fin01_217f2f2aaaa051080a540f2a`
- ResearchRun：`research_run_fin01_1920b03b8205e9861dfb5676`
- states：`succeeded / succeeded / succeeded`
- logical nodes：6
- calls model/provider/network：`12 / 12 / 12`
- transport attempts/failures：`12 / 0`
- Provider status / finish reason：全部 `ok / stop`
- usage receipts / restricted captures / readbacks：`12 / 12 / 12`
- Agent Artifacts：9
- machine Verifier：`accept_for_internal_review`
- input/output/total tokens：`69,484 / 7,734 / 77,218`
- estimated cost：`USD 0.0303834`
- receipt latency sum：`120,474 ms`
- source network / external tools / business-head writes：`0 / 0 / 0`

runtime result 不持久化 raw Provider response、assistant output text、private chain-of-thought 或 credential。

## Success-only baseline and paired assessment

技术成功触发了获授权的 zero-call deterministic baseline：

- distinct WorkUnit/Attempt/Run；
- `4` baseline Artifacts；
- model/provider/network=`0/0/0`；
- source Agent Run/Artifacts unchanged；
- baseline body 未暴露给 Agent；
- read-only verify-only pass。

独立四层验收结果：

- L1=`fail`：5 组 material numeric statements 与绑定 MU authority 不符；MU report title 错写为 NVDA；
- L2=`pass`：仅一个非终态 narrative-target finding；
- L3=`material gain present but inadmissible`：Agent 相对 baseline 增加 6 claims、8 WWC tasks、3 dependencies、3 conflicts 和 4 selected gaps；
- L4=`fail`：错误实体、数字对账负担和过密摘要。

该结果证明机器 Verifier 的 `accept_for_internal_review` 是 false negative，而不是 owner acceptance。

## Interpretation

这不是 transport、credential 或调用稳定性失败。DeepSeek Pro 确实完成了全部模型节点；其中模型生成的 numeric statements 与已绑定 authority 不对应，属于模型行为的一部分，但项目承担更早的控制责任：delivery surfaces 仍允许 model-authored material numbers 持久化，Verifier 只检查 ref membership，未检查 exact value/unit/period/segment/sign correspondence。

错误 NVDA 标题完全是项目代码问题，因为 title 不由模型拥有。RC-P36-078 可关闭；RC-P36-067/068 以 live MU recurrence 重新打开。

## Evidence and governance

- exact-live result：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_r2_exact_live_execution_success_result_v1_0.json`
- exact-live result SHA256：`d4ac5502ed6d87a43de853877511a0c61f9bfc42b6a5ec17f56dfe38a5d95e1b`
- runtime result SHA256：`aa38a0f62c559dbebdd0c3381510f5a316322409004a58ee12cea8243b346e01`
- baseline result SHA256：`3e2ecff47959236aaf1cea09dd33cc598e39cf4e8527565a63c577790c512932`
- paired assessment SHA256：`fe31c95f92ac9a2e41be6ace784498084839edf16c300f4006e6f6ac11414fa1`
- launch / exit receipt SHA256：`b75cbd3ceddb60169aa6cc5c52e9dd50e9f842abb5543d809a14632ca7bb6594 / 41c7104f075c440940a3f85ba8bfb32f44337f995607a24f227c39e5e78957b8`

结论：exact-live technical pass，paired L1 fail，MU R2 not accepted。下一步仅允许零调用 `S4-T06-MU-R2-L1-NUMERIC-AUTHORITY-AND-CASE-IDENTITY-LIVE-RECURRENCE-ROOT-CAUSE-OR-SCOPE-DISPOSITION-DECISION`；不得 automatic R3、Artifact rewrite、owner acceptance 或 T07。
