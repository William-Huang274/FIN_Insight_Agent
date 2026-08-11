# FIN 0.1 S4-T05 RC-P36-065 R9 profile-v3 capacity fresh exact admission 签发

日期：2026-07-28

范围：`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

## 目标与边界

原样物化 fresh-agent proof 冻结的 prospective R9 admission，并完成零调用 issuance preflight。该项不消费 admission、不创建 WorkUnit/Attempt/ResearchRun、不执行 exact-live、不做 paired assessment、owner acceptance 或 S4-T06。

## 签发检查

新增：

- `scripts/releases/issue_fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission.py`
- `tests/contract/test_fin_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission_issuance.py`

签发前：

- 重新生成 fresh proof，并在签发后补齐 issuance-aware 历史断言；后续 authority 阶段将历史 current-pointer 测试改为只验证双账本一致，最终 proof SHA=`9eebbacff223481f72be37651761e56ff758c7f98a0e23ddbbbb9e06ee50bb56`；
- 校验 proof generator 与 contract-test SHA；
- admission payload 逐字段等于 proof frozen payload；
- canonical admission digest 等于 `e7b98ed203087c926e33e7e71f3e5d4d0fe5cc16df57307105fdb85679491b43`；
- profile=`fin01.s4.research_profile.dell_oem_three_cell:v3`；
- capacity resolver=`fin01.s3.specialist_local_assembly_capacity.validated_segment_union_upper_bound:v1`；
- provider/local segment/whole union=`6000/8192/24576`；
- executor factory 使用 forbidden Provider callback 构建，调用数为 0；
- fresh WorkUnit/Attempt/ResearchRun 在 target runtime 中仍不存在；
- target database 与 object tree 未改变。

## 签发结果

- admission ref：`configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission_r9.json`；
- admission file SHA：`05592e970cd1646a31c43a5e37ed0896eb2733dc818266859dc91c283241bb2c`；
- issuance ref：`configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission_issuance_v1_0.json`；
- issuance SHA：`08ac58341f15683471c1ad35ba159c5ece3cd3ece7adbbe927fa5d2c65499b25`；
- issued=true；
- consumed=false；
- execution_started=false；
- model/provider/network/source/tool calls=0；
- WorkUnit/Attempt/ResearchRun/Artifact=0；
- paired/Human=0。

## 状态与下一步

RC-P36-065 当前为 `R9 admission issued unconsumed / exact-live authority decision pending`。这仍不是 live repair、九 Artifact 产品、DELL R2 或 owner acceptance。

下一项：

`S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

只有独立授权后才能 exact-once 消费 R9；retry、fallback、replay、relaunch、rerun 必须为 0，paired assessment 只在完整成功后进入。
