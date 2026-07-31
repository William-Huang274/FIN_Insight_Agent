# FIN 0.1 S4-T05 Research Lead gap-atom projection fresh-agent proof decision

日期：2026-07-27

## 问题与边界

上一项已将 `fin01.s3.bounded_agent.research_lead_owner_grade:v6` 和 `fin01.s3.research_lead_gap_atom_deterministic_projection:v1` 实现到 runtime，并以 fake Provider 完整链证明。用户本轮“继续”只授权独立零调用 fresh-agent proof，不授权签发或消费 admission、第五次 DELL exact-live、paired assessment、S4-T06、Human review、release 或 production。

历史 R4 保持 immutable：三态 failed、Artifact=0、Research Lead observed 8 个旧 `remaining_gaps`、calls=10、tokens=54,986、cost USD 0.02004878，且没有 Writer/Verifier/paired assessment。fresh proof 不追溯验证、截取或重分类该回答。

## 决策与实现

- 新增 deterministic proof generator：`scripts/releases/prepare_fin_ia_0_1_s4_t05_research_lead_gap_atom_projection_fresh_proof.py`。
- generator 每次在 disposable runtime clone 上执行 double prepare，并由 `build_decision` 再独立调用两次；两次完整输出必须相等。
- 目标 canonical DB、object tree 与 logical snapshot 只读审计前后不变。
- 重新绑定当前 implementation 的三项 exact code/test SHA，确认 v6 启用 projection、v5 不启用、policy field/ranking/finding 合同一致且没有 DELL/DeepSeek 特判。
- prospective R5 只从已消费 R4 前向修改新 admission ID、execution mode、fresh input identity 与 `research_lead_transport_ref=v6`；DELL exact input、12-call/USD 0.10/retry-zero 预算、Specialist-v7、output-v4、Writer-v3、ClaimFactLinkPolicy、TaskClaimLinkPolicy 和 restricted capture 保持。
- prospective admission 仅作为 decision 内 frozen payload；目标文件未物化。

## 证明结果

- fresh WorkUnit：`wu_p02_5_b63a5202479c6be6fcedbe94`
- fresh Attempt：`attempt_fin01_ba8728e601ea22f6592189e2`
- fresh ResearchRun：`research_run_fin01_3ce365aa075bacbc2cc31346`
- input digest：`3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- prospective admission digest：`378731667e55e56740b5fd2fcc81fc152e3b2da91e15230cc7db33a6034ca5db`
- clone execution counts：`4/4/4/0 -> 4/4/4/0`
- 三个历史 failed ResearchRun 全部存在且未复用。
- model/provider/network/source/tool/admission issuance/consumption/target write/paired/Human：全部 0。

验证：

- 新 fresh proof 合同：`6 passed`
- S4-T05：`147 passed`
- 完整 S4：`184 passed`
- prospective admission schema/profile/factory zero-call：通过
- 历史 current-state 测试：只新增最新 proof 解析优先级，旧 decision/admission/failure/digest 断言未放宽

## 当前结论与下一项

RC-P36-061 状态推进到 `fresh_proof_contract_frozen_admission_issuance_pending`。这证明当前代码、DELL 输入、fresh identity 与 prospective admission 可确定性重建，但不是 live model 证据、DELL R2、paired assessment 或产品验收。

下一项仅为：

`S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-PROJECTION-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

后续若获独立授权，只能原样签发 frozen R5 payload，不得在同一步消费或执行。rollback 仅需移除本轮 proof/测试/账本增量；历史 R4 与 runtime 实现无需改写。
