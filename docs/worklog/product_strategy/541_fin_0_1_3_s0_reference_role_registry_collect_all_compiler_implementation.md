# FIN 0.1.3 S0 reference-role registry 与 collect-all compiler 实现

日期：2026-08-01

状态：`engineering pass / v2 implementation 1 of 1 consumed / host and formal proofs not executed / zero external call`

## 实现结果

- 新增单一版本化 `ReferenceRoleRegistry`，精确拥有 `repository_resource`、`package_relative_audit`、`external_content`、`restricted_runtime_audit`、`model_run_report`、`semantic_followup` 六类角色。
- 字段 owner 先于值命名空间；因此 `followup_ref="official quarterly cohort/definition bridge"` 即使含 `/` 仍是业务语义 follow-up，不再进入路径启发式。
- v2 closure compiler 只把 `repository_resource` 递归加入 tracked-or-typed inventory；包内审计、外部内容、受限 Runtime 审计、model-run report 与语义 follow-up 均观测但不自动打包或晋升业务内容。
- v2 policy 明确拒绝 `non_repository_reference_fields`，未把 T03 暴露的 47 个字段改造成新例外清单。
- collect-all 在遍历完整已知闭包后统一生成 observations、role counts 与稳定 digest；未知项用一个受限 typed failure envelope 一次返回并标记 `business_promotable=false`，保持 fail closed。
- 历史 v1 classifier 路径继续存在，旧 T03 closeout、失败 SHA、`1/1` 预算和未执行 T04 均未改写。

## 验证

- 正式 current v1.2 manifest 编译：`1,233 paths / 1,233 tracked / 0 allowlist / 4,996 reference observations / 0 unknown`。
- 角色计数：repository=`1,640`、package audit=`6`、external=`54`、restricted runtime=`219`、model-run=`16`、semantic=`3,061`。
- observation digest：`aaae9c9fd43042b23748e2ce7baccec7e9d98bdfc4f58781fa68e94c7760408b`。
- positive、two-unknown collect-all、duplicate key、cross-version、rule-order、untracked/traversal/symlink、历史 v1 兼容、Runtime registry、typed environment 与三案例 deterministic 相关矩阵：`83 passed`。
- 历史 T03 测试改为校验 closeout 中的 frozen runner snapshot，而不要求未来当前 runner 永远等于旧 SHA；旧证据文件没有改动，旧 T03 仍为 terminal failed。
- credential/model/Provider/network/source/admission/business Run/Artifact=`0/0/0/0/0/0/0/0`。

## 边界与下一项

本次只有工程基础增量，没有用户可见金融研究能力增量。RC-P36-090–094 继续 open/full-chain blocker；S0 必须等新的 host proof 与 conditional formal two-disposable proof 全绿后才可关闭，S1/S2 与 release 仍 blocked。

实现记录：`configs/releases/fin_ia_0_1_3_s0_reference_role_taxonomy_registry_and_collect_all_compiler_minimum_zero_call_implementation_v1_0.json`，SHA-256=`9bf91966018e6e0a3b5378f073f44039f9690fce23d80412397bc7764292ee63`。

唯一下一项：

`FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-ZERO-CALL-ENGINEERING-PROOF-AUTHORITY-DECISION`
