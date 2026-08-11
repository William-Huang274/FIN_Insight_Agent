# P38 / Point 01 P01-G2.1 Operational Baseline Incident

日期：2026-07-17
状态：`P01_G2_1_BASELINE_FAILED_STOPPED_PENDING_INDEPENDENT_REVIEW`

## 执行范围

按 total reviewer 已委托的一次性 P01-G2.1 tranche 执行。唯一有 authority 的 case 是 `g2-baseline` / `p01-baseline-separated-input`；目标经过既有 M2-A1 v2.10 production lifecycle kernel。三个负例在 baseline 成功前不得运行。

## 预检查与冻结

- P01-G2.1 package / gate：`7ded46ddadb54a697877e3426bab8b9ab868bab0ceb7c2cd735a7349b15339e1` / `6bf29f9397d82d1e2b540c2520cb1f85f9f51c2886e28ba77169e5c23668340d`。
- 上游 tranche / gate：`aeeccb1525d693f1dc19eb42a6f9666fed3ebf4a3b3f578f73fd8dc22678f861` / `32cc169081b9e4158894925d4fb207824c28bc17e408190e6cce900de950b7a5`。
- v2.10 staged inputs=`79/79`；P01 execution package inputs=`13/13` Git-index binding。
- fixed approval DB SHA-256 before/after：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。
- formal v2.10 namespace 与 P01 case root 在执行前均不存在。

## 实际结果

baseline 已完成 package-external outer authority、v2 reviewer receipt、human approval、admission、receipt registration 和 atomic consume。随后 production parent/clean-child leaf 返回非零：

```text
failure_reason = v2_10_actual_leaf_nonzero_after_consume
kernel_state   = outcome_unknown
event sequence = REGISTERED -> CONSUMED_BEFORE_RUN -> TERMINAL(outcome_unknown)
```

- baseline case result digest：`58de7732bfeffee09d80f93fb997aa898727c7ea84e29d8c844f7607b92a858b`
- terminal digest：`13785b7d5d0bdee2459842d1eaa7137eccdbd747aa969f36aa309970194daf8c`
- actual / oracle / reviewer artifact：均未生成。

v2.10 adapter 只向 kernel 回传 child return code，并未持久化 captured stdout/stderr。因此当前证据不足以将具体 child failure 归因为某一生产模块；不得将推测写成 root cause。

## 停止与保留

- `g2-wrong-package-or-approval`、`g2-stale-input-version-drift`、`g2-unauthorized-transport` 均为 `not_executed`；其 authority/admission/receipt/namespace/runtime/terminal counts 均为 0。
- network/tool/model/provider success、fixed-store write、business Case mutation、legacy authority change 均为 0。
- 隔离 temporary authority/runtime root、consumed receipt 与 append-only ledger 必须保留，不得清理、重试、重放、续签、补发或自动修复。

## 下一步

仅等待独立审计界定可读 forensic 与最小 repair 范围。该事件不代表 P01-G2、M2 operational qualification、Point 01 或 production readiness 通过。

## R1 Forensic Repair（2026-07-17）

独立 disposition 接受 incident containment、拒绝 operational qualification，并只授权 `P01_G2_1_R1_FORENSIC_REPAIR_ONLY`。R1 不重新执行任何 case，不创建 admission/receipt，不触碰已消费 SQLite ledger 或 historical terminal。

- 修复点是 production adapter 的最早 observability gap：future nonzero child 在 parent 返回前持久化 `ChildExecutionIncidentEnvelope`，包含 stage、returncode、argv shape digest、stdout/stderr digest、bounded redacted excerpt、可得异常分类、authority/receipt/admission 引用和 canonical digest；raw stdout/stderr、credential、token、User-Agent、环境变量、秘密与用户数据禁止进入 Git 或下游。
- future `TERMINAL(outcome_unknown)` 以 envelope digest/ref 作 exact binding。既有 terminal 不能原地修改，改由 independent immutable reconciliation artifact 表明 historical capture status=`not_persisted_pre_r1`，因此任何 production root-cause 只能保持 hypothesis，等待 deterministic fixture 才可证明。
- historical count reconciliation 固定为：attempt=1、success=0、actual artifact=0、registration=1、consume=1、runtime materialization=1、outcome_unknown terminal=1、negative execution=0。
- deterministic tests 只会启动 sanitized local failed-child，并在 pytest temporary root 写入 envelope/fixture ledger；不读现有 formal namespace、authority root 或 fixed approval DB，也不调用 network/tool/model/provider/业务 store。

完成状态只能是 `P01_G2_1_R1_FORENSIC_REPAIR_PENDING_INDEPENDENT_REVIEW`。在审计验收前，不得申请 fresh operational receipt、baseline retry、negative probes、Step 3-5 或 FIN 0.1 entry。

## R1.1 Sanitization Contract Repair（2026-07-17）

R1 复核结果为 `REJECT_AND_REPAIR_P01_G2_1_R1_SANITIZATION_CONTRACT_ONLY`。被拒的不是 historical containment，而是 future envelope 的三条数据最小化绕过：`--flag=value` 会污染 argv shape digest；quoted JSON 与 `User-Agent` 等 header 未完整脱敏；`source_refs` 可由调用方带入任意字符串。

R1.1 只实现 sanitization contract repair：

- argv shape 改为 flag name + argument category，metamorphic tests 证明只换 token/path/receipt/scenario/output value 不改变 digest；
- 新增严格 `ChildExecutionSourceRefs`，在启动 child 前拒绝 extra key、路径、URL、换行、secret-like identifier、超长 identifier 和非 lowercase SHA-256 digest；
- excerpt sanitizer 覆盖 quoted JSON、assignment、Authorization/Bearer/Cookie/Proxy-Authorization/User-Agent 与 URL query。它是 bounded supported-shape sanitizer，不宣称通用秘密消除；未知敏感行宁可整行替换；
- R1.1 reconciliation/package/gate 只 supersede R1 rejected evidence，不改历史 terminal/ledger/counts，也不生成任何 authority、receipt、namespace 或 operational artifact。

本轮测试仅为 temporary local fixtures；未执行 baseline/negative、网络、模型、tool/provider、fixed store 或业务写入。状态只能是 `P01_G2_1_R1_1_SANITIZATION_REPAIR_PENDING_INDEPENDENT_REVIEW`。

## R1.1 接受后的单次 pre-baseline root-cause diagnostic（2026-07-17）

独立审计接受 R1.1 bounded forensic patch 后，仅允许一次同 lane、隔离的根因诊断；没有创建 package/gate、human authority、admission、receipt 或 formal namespace，也没有读取/写入历史 authority root、consumed ledger 或 fixed DB。

- clean-process MRE 直接执行当前 `M2A1ActualRunner` baseline code path，首个确定性停止为 `full_compiler_input_invalid:forbidden_substitutions_required:*`。根因是 legacy objective adapter 未把 evidence-role 的禁止替代规则写入 `EvidenceSlotSeed`，与 M2.1 policy 的 `require_forbidden_substitutions=true` 冲突。
- 本轮允许的一次最小修复在 adapter 中加入确定性、安全的 role mapping：`issuer_metric -> relationship_graph_only`、`relationship_signal -> issuer_metric_substitute`、`commercial_tracker_metric -> public_proxy_as_exact`。explicit legacy value 保持权威；unknown role 与显式空/非法值 fail-closed。聚焦 regression 通过。
- 修复后的同一 clean-process MRE 到达下一独立 blocker `case_delta_pack_lineage_missing`，无网络/tool/model/provider 成功、无 fixed-store 访问或写入。按本轮一次 repair 上限不再继续。
- public runner serialization probe 显示前一 compiler validation 错误会成为 immutable `typed_stop=compiler_input_full_validation_failed` 并正确 readback；因此它不能单独解释 historical child 的 `nonzero`。pre-R1 没有保存 stdout/stderr，historical root cause 仍是 `historical_root_cause_inconclusive_user_decision_required`。

本 execution point 的唯一状态为 `P01_G2_PRE_BASELINE_ROOT_CAUSE_DIAGNOSTIC_PENDING_INDEPENDENT_REVIEW`。未运行 baseline/negative、网络、模型、tool/provider、fixed-store/business write；不得申请 fresh receipt 或自动继续 repair。

## AI-semis case-instance pack lineage product repair（2026-07-17）

用户随后单独授权仅修复当前 AI-semis baseline 的 `case_delta_pack_lineage_missing`。修复没有重跑 baseline、没有消耗/创建 authority、admission 或 receipt，也没有重写 historical incident evidence。

- 复用 `PlanningPackVersion(scope_kind="case_delta")`，建立 `pack-case-m2-a1-ai-semis-no-override:v1`；它不是占位 ref，而是可复算 `no_override` payload，digest=`71d9a25e7973db55ec0a99295e90d51d9acb2ed87c988b548d4e8089d00d28b9`。
- payload 绑定 baseline case、版本、freshness、`provisional_case_delta`、`official_first`、universal/sector/report-type exact base refs、decision/source ref 和空 additions/removals/overrides；seed、metadata、registry selection/resolution 与后续 composition/serializer lineage 统一使用该 exact version。
- M2-A1 metadata validation 对 missing payload、case drift、base-pack drift、decision-source 缺失和 digest mismatch 均 fail-closed；移除 lineage ref 也会 typed stop。未修改 already accepted 的 forbidden-substitution mapping，也未尝试解释 historical child nonzero。
- deterministic/component suite：`30 passed`；authority/receipt/baseline/network/tool/model/provider/fixed-business write 均为 `0`；fixed approval DB fingerprint 未变。

当前状态只能为 `P01_G2_CASE_INSTANCE_PACK_LINEAGE_REPAIR_PENDING_INDEPENDENT_REVIEW`。必须停止等待独立复核，不能消耗最后一次 operational baseline。
