# FIN 0.1 S4-T05 RC-P36-065 R9 exact-live execution authority decision

日期：2026-07-28

范围：`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

## 结果

已签署 R9 exact-once execution 与 coherent success 后只读 paired assessment 的零调用授权。当前 admission 仍为：

- issued=true；
- consumed=false；
- execution_started=false；
- WorkUnit/Attempt/ResearchRun/Artifact 新增数均为 0；
- model/provider/network/source/tool/paired/Human 均为 0。

authority decision：

`configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_exact_live_execution_and_paired_assessment_authority_decision_v1_0.json`

SHA256：

`c37828b968d30d9ebdeb03a91253a636300f79b536c09a1fb18579dfe8c127de`

## 预执行证据

Project OS scoped preflight：

- status=pass；
- open blockers=0；
- output=`.codex_runtime/s4_t05_dell_r9_capacity_execution_authority_project_os_preflight.json`；
- SHA256=`bcdbb25491a867660c795f95674081bd2470d1ff2ff37d62e0e3f67a9880197b`。

exact runner disposable-clone preflight：

- status=`pass_exact_zero_call_execution_preflight`；
- credential presence=true，但值未读取、未输出、未持久化；
- Provider health probe=false；
- transport retries=0；
- target counts 前后均为 `7/7/7/0`；
- model/provider/network/source/tool calls=0；
- output=`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t05_dell_r9_specialist_validated_segment_union_capacity_r9_r1_live_execution_preflight.json`；
- SHA256=`57540d33b8e28067bf6e8a4d4abf844b7944a28247cab0c92e1b7e3ee68c3c36`。

第一次 runner preflight 在调用 Provider 前因进程环境未显式设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0` fail-closed；随后仅在单次进程内显式设为 0 并重跑通过，没有修改持久环境或消费 admission。

## 冻结执行合同

- profile=`fin01.s4.research_profile.dell_oem_three_cell:v3`；
- capacity contract=`fin01.s3.specialist_local_assembly_capacity.validated_segment_union_upper_bound:v1`；
- provider/local/whole caps=`6000/8192/24576`；
- model=`deepseek-v4-pro`；
- maximum model/provider/network calls=`12/12/12`；
- maximum output tokens=18000；
- maximum total cost=USD 0.10；
- retry/fallback/replay/relaunch/patch/rerun=0；
- source network、external tool、business case head write 均禁止。

成功必须同时满足：

- coherent terminal states=`succeeded/succeeded/succeeded`；
- 6 logical nodes；
- 12 Provider calls、12 receipts、12 restricted captures；
- exactly 9 Artifacts；
- typed Verifier success；
- manifest/receipt/capture/Artifact parity；
- L1-L4 layered acceptance。

任何首个可信失败都立即 fail-closed；失败后不得 paired、自动第二次执行或临时 patch。paired assessment 只在上述成功合同成立后允许。

## 历史指针稳定化

两个早期 R8 合同测试原先通过枚举 `implementation -> proof -> issuance` 文件推断全局 current next，导致每新增合法阶段都需修改历史测试并触发哈希连锁。现已收敛为只验证 program backlog 与 detailed backlog 的 current pointer 一致，不再让历史阶段拥有未来流程枚举。

因此只发生文件 binding 更新：

- implementation SHA=`212cb8b2a4416ff797d74676fe3dce091849b35503caf3b0e893c7061a1b97af`；
- fresh proof SHA=`9eebbacff223481f72be37651761e56ff758c7f98a0e23ddbbbb9e06ee50bb56`；
- issuance SHA=`08ac58341f15683471c1ad35ba159c5ece3cd3ece7adbbe927fa5d2c65499b25`。

R9 admission payload、file SHA=`05592e970cd1646a31c43a5e37ed0896eb2733dc818266859dc91c283241bb2c`、canonical digest=`e7b98ed203087c926e33e7e71f3e5d4d0fe5cc16df57307105fdb85679491b43`、identity 与 runtime state 均未改变。

## 边界与下一步

本轮未运行 exact-live、未消费 admission、未生成 Artifact、未执行 paired assessment，也未进入 S4-T06。

下一项唯一为：

`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-EXACT-LIVE-EXECUTION`

dependency/conflict、Writer/Verifier、all-node atomization 与 cross-provider strict schema matrix 继续后传 S4-T10→S5，不回流 T05。

## 验证

- R9 authority + issuance + fresh proof + capacity implementation + R8 disposition/typed-failure 相邻链：`27 passed`；
- 更新账本后的 final Project OS preflight：`pass / open blockers=0`；
- 完整历史 S4-T05 contract suite：`229 passed / 34 failed`。

完整历史 suite 的 34 项失败集中在 R3–R7 时代的测试把当时 `current_next` 或当时代码 SHA 当成永久真值；它们不否定当前 R9 admission、authority、zero-call preflight 或 27 项相邻链。按单任务序列边界，本轮不回改全部历史阶段或扩大 RC-P36-065；该历史测试治理债后传 S4-T10→S5。另有一次 PowerShell 未展开 pytest 通配符导致 `no tests ran`，已用 46 个显式文件路径重跑，未把该次空跑计为通过证据。
