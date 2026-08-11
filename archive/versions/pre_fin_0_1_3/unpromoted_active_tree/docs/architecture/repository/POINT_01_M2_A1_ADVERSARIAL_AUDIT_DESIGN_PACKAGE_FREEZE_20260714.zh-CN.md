# Point 01 M2-A1 对抗审计设计与包冻结

日期：2026-07-14
状态：`design_package_frozen_pending_independent_review`

## 目标与范围

本执行点只冻结 M2-A1 后续独立审计所需的输入、独立 expected-cell oracle、owner/authority/typed-stop matrix 和 Git-index package identity。它不运行 compiler、serializer、pack resolution、shadow orchestration、fixture、pytest、模型、网络、工具或任意 store 路径。

冻结 package：`point01-m2-a1-independent-adversarial-audit-package-v1`，digest=`5e464a22aa77723cc15febb8d5a80357d4bc3fac1137da54dbdf25c49ae2a35c`。

## Oracle 与实际输入隔离

- actual-input corpus 仅含四个 sanitized synthetic sector inputs：AI/Semis、SaaS、Healthcare、Banks；没有 business Case、source bytes 或 expected compiler output。
- expected-cell oracle 是单独 artifact，并固定 `runtime_input_forbidden=true`。未来 actual compiler 若 import、读取、hash 或接收该 oracle，必须 typed stop 为 `oracle_leakage_detected`。
- 四行业校准只能在 actual 完成之后由 reviewer-side oracle 比较；不得作为 pack、prompt、compiler input、shadow input 或模型上下文。

## A0-M2 probes 与权责

| Probe | Owner | 验证对象 | 必须 typed stop |
| --- | --- | --- | --- |
| A0-M2-P01 | compiler/serializer owner | compiler、serializer、pack/selection、cell/slot、legacy mapping 与独立 oracle 隔离 | `oracle_leakage_detected` |
| A0-M2-P02 | pack policy owner | versioned pack、selection、evidence-policy、artifact lineage/replay | `pack_version_or_lineage_mismatch_or_policy_upgrade_required` |
| A0-M2-P03 | shadow admission owner | model admission、feature flag、shadow compiler/orchestration 与 store/model/network canary | `shadow_scope_violation_or_test_runtime_isolation_violation` |

package 使用 Git-index bytes，绑定 compiler/packs/selection/serializer/legacy mapping/model admission/shadow boundary 的 source、policy 与 contract tests。mutable docs/worklogs 不进入 package，避免 approval 或治理记录造成 package 自失效。

## 权限边界与下一步

未来 actual P01–P03 必须另有 exact package-external total-reviewer admission `point01-m2-a1-total-reviewer-package-admission:v1`，并在实际前消费 single-use execution receipt。当前 `actual_probes_currently_authorized=false`，legacy TaskRun 仍 authoritative，DecisionSurface 仅 shadow，cutover、模型、Evidence/Writer/full-chain、fixed/production/business/legacy store mutation 全部禁止。

本设计冻结完成后必须停止，等待独立 reviewer 审计 package、oracle separation、typed-stop matrix 和 staged inputs；不得自动进入实际 M2-A1 probes。
