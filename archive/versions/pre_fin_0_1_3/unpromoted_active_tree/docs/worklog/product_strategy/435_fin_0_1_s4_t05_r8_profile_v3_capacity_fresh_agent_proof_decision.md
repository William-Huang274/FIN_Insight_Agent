# FIN 0.1 S4-T05 RC-P36-065 profile-v3 capacity fresh-agent proof 决策

日期：2026-07-28

范围：`S4-T05-DELL-R8-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-FRESH-AGENT-PROOF-DECISION`

## 目标与边界

对已经 fixture-proven 的 DELL profile-v3、共享 Specialist capacity resolver、安全 byte telemetry 和 case-runtime overlay 做独立零调用证明，并冻结 prospective R9 identity/admission。该项不签发或消费 admission，不执行 exact-live，不读取 R8 restricted capture，不做 paired assessment、owner acceptance 或 S4-T06。

## 证明方法

新增独立 proof generator：

`scripts/releases/prepare_fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_capacity_fresh_proof.py`

生成器执行以下检查：

- 校验 implementation SHA 与四个 exact code bindings；
- 从 immutable R8 admission、issuance 和 terminal failure 重新确认 consumed/failed/0 Artifact 历史事实；
- 把 prospective admission 升级到 DELL profile-v3，但保持 Specialist-v8、Provider schema、token、cost、retry-zero 和所有语义 gate 不变；
- 通过共享 resolver 重算 `provider/local segment/whole union=6000/8192/24576`；
- 在 disposable runtime clone 上执行 double prepare、executor factory 与 create-app；
- Provider callback 被强制禁止；
- 对完整证明再独立执行两次，并要求输出逐字段相同；
- 校验 target canonical SQLite、object tree、logical snapshot 与 counts 前后不变。

## 结果

- independent proof invocations：2；
- outputs equal：true；
- target counts before/after：WorkUnit=7、Attempt=7、ResearchRun=7、Artifact=0；
- Provider/network/source/tool/canonical write/restricted capture read：全为 0；
- effective runtime binding digest：`789ffa18ab6d4c994117fd2a196a455d3979ccab18e2eec7cd60723644a1711d`；
- overlay digest：`15915cd181d6ccf05521792770ccea8faf0fadba82ac0d061f4898d9e4465a25`；
- profile contract digest：`e2b48105b5df69089b0adb7562e0f83d58cdc5ad5ec0a3794a0d84822481978c`；
- fresh input digest：`f9868c5d7daa051adfccba1c1d2de9c1209d6781bfa76c4569aee76d640e230d`；
- prospective R9 admission digest：`e7b98ed203087c926e33e7e71f3e5d4d0fe5cc16df57307105fdb85679491b43`；
- prospective WorkUnit：`wu_p02_5_0f6c8d74d2a47a5a98ffe58b`；
- prospective Attempt：`attempt_fin01_ad16ed80b2ed788d3924c614`；
- prospective ResearchRun：`research_run_fin01_6566beb727cded66f3d54ead`；
- focused proof tests：`5 passed`。

决策记录：

`configs/releases/fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_capacity_fresh_agent_proof_decision_v1_0.json`

## 状态与下一步

RC-P36-065 达到 `independent fresh proof pass`，但尚无新的 live Artifact。R8 历史失败不重写；DELL R2、paired assessment、owner acceptance 与 S4-T06 均未通过。

下一项：

`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

下一项只能在独立授权下原样物化 proof 冻结的 R9 admission；签发决策自身不得消费或执行它。
