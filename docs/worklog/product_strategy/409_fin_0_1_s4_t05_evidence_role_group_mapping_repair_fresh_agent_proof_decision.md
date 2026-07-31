# FIN 0.1 S4-T05 Evidence Role Group Mapping Repair Fresh-Agent Proof

日期：2026-07-26

## 权限与边界

用户以“继续”授权：

`S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-FRESH-AGENT-PROOF-DECISION`

本轮只允许独立零调用 proof。未授权 replacement admission 签发或消费、第二次 DELL exact-live、paired assessment、Human review、S4-T06、S5、release 或 production。

## 独立复证

新增只读 proof generator：

`scripts/releases/prepare_fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_fresh_proof.py`

它执行以下 fail-closed 检查：

- 重新核对 implementation contract 与七个 current code hashes；
- 在两次独立 disposable clone invocation 中执行 DELL exact prepare；
- 重新派生 `[4,5,5]` 共 14 个 exact roles；
- 冻结 mapping、Canonical slot alignment 与 shared dispatch 三个 digest；
- 验证 actual/preflight 共用 `compile_profile_evidence_dispatch`，S4 没有 fixture candidate fallback 或 ticker mapping branch；
- 冻结全新 WorkUnit、Attempt、Run 与 prospective replacement admission digest；
- 验证旧失败 Run 继续存在且没有复用；
- 验证目标 DB、object tree 与 logical snapshot 前后不变；
- 构造 executor factory 但不触发 Provider callback。

两次独立输出完全一致，canonical output digest 为：

`2f804ea9bdec35e95287af5007d128aa4b46e0b7d369594a112ff37f2dea2b3c`

## 冻结结果

- WorkUnit：`wu_p02_5_65677179348a532b5090c1c5`
- Attempt：`attempt_fin01_19aa79399a8c3008c4e4b62c`
- Run：`research_run_fin01_9756044e7d7f23b3ff9fb395`
- input digest：`3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- preparation digest：`0bddfa9ec05c33ec4b4b7ac745bd1cbad42a48588cf81472906dd889d74f2182`
- mapping digest：`73284fd4fc8ada1e45a44aa1a627d011ea591227842f5172eb6d9ae15f99c812`
- alignment digest：`9c35e5345a13ef3a9e8f919c8a6b29016c0ba0961066fdfb06b62317054a9cfb`
- dispatch digest：`6b96006f8d19d6ed7ddf59b3dec4b32d33a65ca5ff6516e1c248a6d53f09f9e8`
- prospective admission digest：`058c579211eb1f4573959d86f0b904b64e2535e749631ab7ee208571ef601af3`

prospective admission 只在决策内冻结；文件不存在，issued、consumed、execution started 均为 false。

## 验证

- proof decision + implementation focused：`20 passed`
- proof、implementation、root disposition、首次 failure 与 T04 issuance 相邻回归：`34 passed`
- 两次独立 proof invocation：`equal`
- Python compileall：`pass`
- JSON / JSONL validation：`pass`
- 下一关 Project OS scoped preflight：`pass`，open full-chain blockers=`0`
- model/provider/network/source/tool：`0/0/0/0/0`
- admission issued/consumed：`0/0`
- target canonical/object write：`0/0`

## 结论

`RC-P36-058` 的工程 blocker 已通过独立 fresh proof 关闭。这个结论只说明已知的 Provider 前 evidence taxonomy 缺口不再阻断新的精确输入；它不等于 DELL exact-live 成功。

DELL 仍没有一条新的 coherent terminal-succeeded 九 Artifact Run，也没有 paired assessment，因此 DELL R2 仍为 `not_proven`。

下一项：

`S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

该项仍需独立授权，且只能签发未消费 admission，不能直接启动执行。
