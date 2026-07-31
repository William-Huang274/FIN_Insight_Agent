# 396 FIN 0.1 S3-T09 layered Verifier typed-ref fresh Agent proof decision

日期：2026-07-25

## 问题与授权

用户以“继续”授权执行
`S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-FRESH-AGENT-PROOF-DECISION`。
本步骤只允许零调用 proof decision，不包含 admission 签发、消费、exact-live、
Artifact 合成、配对比较或 owner acceptance。

## 决策

在 disposable canonical clone 中重复 prepare，冻结一套全新且不可复用的未来
exact identity：

- WorkUnit：`wu_p02_5_d9dd3698e17079ccd3bbd2a6`
- Attempt：`attempt_fin01_3de738b36b2c011ed984cc58`
- ResearchRun：`research_run_fin01_5322ebc0e99fe4c5f00f3526`
- input digest：`2afb36728277556718eead7a56c3d8ba9ee4485532ac9bb1b6f32204182af872`
- preparation digest：`012d850fcc4e5d54ee8ae3a7e0aaac763ca238196c5ca1589cc9b7fa760a0034`
- prospective admission digest：`fdc5dab0a6045dce123fdee897f337638eb297d961b514cd52e44f1cbf6ac7c2`

23 个已有 ResearchRun 全部不可复用。目标 canonical SQLite 与 object tree
在准备前后分别保持：

- DB SHA256：`f5783e58068f5d07f37167bcb662872b8b92391b1bba81a30d0796c0457f2583`
- object tree SHA256：`90389385fa91b78c27a85a6f4a19b4f5deab0ada0a38f876d86eeedcb6f6a056`

## 冻结合同

proof 精确绑定：

- layered acceptance v1；
- output-v4 与 profile-v4；
- Specialist-v7、Research Lead-v5、Memo Writer-v3；
- ClaimFactLinkPolicy v1、cell-scoped identity v1；
- Verifier state-machine v2、supervision-v2；
- exact path 的七个当前代码摘要。

future exact-live 只有在同一 coherent Run 同时满足以下条件时才可视为产品成功：

- WorkUnit / Attempt / ResearchRun 为 `succeeded/succeeded/succeeded`；
- 六个逻辑节点、十二次 Provider call；
- 九种当前 Artifact；
- typed Claim ref 精确 membership 与 Claim-to-Fact lineage 通过；
- L1 hard integrity 通过；
- unresolved conflict 与 company-total margin gap 等 L3/L4 finding 被持久化，
  但不会因此抹除有效输出。

## 变更

- 新增 proof generator：
  `scripts/releases/prepare_fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision.py`
- 新增 proof decision：
  `configs/releases/fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision_v1_0.json`
- 新增合同测试：
  `tests/contract/test_fin_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision.py`
- 更新 program backlog、identity architecture、Current Context Pack、capability
  ledger 与 root-cause ledger。
- 修复五处历史治理测试/审计的时间耦合：历史 nullable/atomic proof 不再要求
  frozen code digest 等于后续当前代码，也不再占有全局 current next-action；
  profile-v3 历史审计改为校验当时 admission digest/profile，而不是读取当前
  profile-v4 request 文案；历史 snapshot digest 与当前追加 Run 后的 head digest
  分开比较。历史结果与 canonical truth 均未改写。

## 验证

- generator 连续两次生成的正式 JSON 字节级一致：
  `113a5067a03ec70f48ff7c404defe4c3ad9c8ab1e858cd50ee4cc53d434ff116`
- focused proof / typed-ref / layered runtime / nullable-owner / supervision-v2：
  `31 passed`
- 历史 nullable proof / issuance / live audit 与 atomic governance：
  `47 passed`
- strict JSON / JSONL（含 duplicate-key 检查）：通过；
  capability ledger=`376` 行，root-cause ledger=`427` 行
- issuance-scoped Project OS preflight：`pass`，open blocker=`0`
- model / Provider / network / source / tool / admission / supervisor / Run /
  Artifact / promotion / comparison / owner-write：全部 `0`

## 未执行与下一门

本步骤有意未签发 prospective admission，未调用 DeepSeek，未创建 canonical Run
或 Artifact，也未执行 paired comparison 和 owner acceptance。

下一项：

`S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-FRESH-EXACT-ADMISSION-ISSUANCE`

该步骤需独立授权；issuance 只能原样物化 frozen admission，不能消费或启动
exact-live。
