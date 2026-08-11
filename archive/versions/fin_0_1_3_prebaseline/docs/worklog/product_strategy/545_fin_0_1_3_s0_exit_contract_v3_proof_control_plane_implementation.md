# 545 — FIN 0.1.3 S0 Exit Contract v3 proof control plane 实现

日期：2026-08-01

结论：`engineering pass / v3 implementation consumed / eligibility authority pending`

## 1. 本项范围

本项只实现 `fin_0_1_3.S0.exit_contract:v3` 的 proof policy 单一来源和 host 消费前 exact execution boundary。它不重做六角色 reference registry、29 项 Runtime resource、八类 typed environment root 或 DELL/MU/NVDA 业务 Runtime，不执行 clean-head eligibility、host/formal proof、模型、Provider、网络或业务链。

v1/v2 实现、失败证据与已消费预算保持不可变。

## 2. 实现内容

- 新增版本化 repository-reference proof policy source，将 `unknown_reference_behavior=fail_closed` 与 `unknown_reference_reporting=collect_all_typed_envelope` 分开；
- active manifest v1.3 只保存 `policy_ref + policy_sha256`，proof control plane 先校验同一 source，再确定性投影为 immutable v2 compiler surface；被 v2 artifact 哈希绑定的 `hermetic_test_runner.py` 保持 byte-identical；
- reference-role registry v1.0 不改写；新 v1.1 只把完整 current compile 中唯一 unknown `execution_started.json` 分类为 `package_relative_audit`，六角色与金融 Runtime 语义不变；
- `proof_control_plane.py` 定义 policy/binding、eligibility payload/attestation 和 host authority 的 typed schema、canonical digest 与 fail-closed validator；
- v3 runner 把 contract-only、eligibility 和 host 模式显式分开。eligibility 可绑定 clean/synced HEAD、execution/active manifest、ordered source bindings、Project OS preflight、tracked snapshot、compiled inventory 与 selected tests；
- host 路径必须在 base execution 、消费标记和 import sweep 之前重算并精确匹配 eligibility attestation，再验证 repository 外的单次 host authority；
- schema、binding digest、canonical digest、policy value、consumer order、registry digest、attestation recompute 和 authority 漂移全部 fail closed；
- current active manifest 不再让被 immutable v2 artifact 哈希绑定的历史测试持续拥有 mutable current 投影。

## 3. 验证边界

本项只运行零调用测试：临时 Git repository compiler fixture、policy mutation、attestation/authority digest binding、host pre-consumption recompute order、current manifest/projection/Project OS 校验和 DELL/MU/NVDA 确定性链可见性。

实际 clean-head eligibility 需要提交后的 clean/synced HEAD 与单独 authority，因此本项没有执行；host/formal proof 也没有创建 authority 或消费预算。

## 4. 产品与版本真值

v3 maximum/observed `[implementation, eligibility, host, formal]=[1,1,1,1]/[1,0,0,0]`。RC-P36-090–095 全部继续 open；FIN 0.1.3 S0、S1/S2 entry 和 FIN 0.1 release 继续 blocked/false。本项没有用户可见金融研究能力增量，不创建 FIN 0.1.4，不改变 FIN 0.2 Earnings Review Alpha 定义。

当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_9.json`

当前 active manifest：`configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_3.json`

当前下一项：`FIN-0.1.3-S0-EXIT-CONTRACT-V3-CLEAN-HEAD-EXACT-BOUNDARY-ELIGIBILITY-ATTESTATION-AUTHORITY-DECISION`

## 5. 最终零调用结果

- v3 focused schema/digest/order/registry/attestation/authority/current-compile matrix：`13 passed`；
- active manifest 六个 unique test path：`79 passed`；
- 完整 current repository compile：`1,256 paths / 1,256 tracked / 5,104 reference observations / 0 unknown / 0 explicit allowlist`；
- 六角色计数：`repository_resource=1,741 / package_relative_audit=12 / external_content=54 / restricted_runtime_audit=220 / model_run_report=16 / semantic_followup=3,061`；
- closure digest=`76668d8a11e4762e085b34a24f32a7eb7d664a4fcff800cf83a417d82c6bfa56`，reference observation digest=`59396528cea0c6f4ab6bcf9e7dca5cea91547b4806d1db6a348c737865f3cad5`；
- `src/sec_agent/hermetic_test_runner.py` 仍为 v2 绑定 SHA256=`98ea3b835ae8be1631745b41b2b20e27c90eb3086e1b9572a61ae3e80bfa3c41`；
- credential/model/Provider/network/source/admission/business Run/Artifact 全为 `0`。
