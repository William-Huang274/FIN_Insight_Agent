# Dell Agentic 完整纵切：Wave 0A 零模型合同与 A02 精确身份边界

更新时间：2026-09-03 07:59 +08:00

产品版本：FIN 0.1.3

分支：`codex/fin013-dell-s1-s2-product-bridge`

实现起点 commit：`f7d9bc5c36bfe2e65d2d1137fea65eed231440ba`

实现提交：`6f383c29b10da0e2f972960d2c9c7eaf579c364c`（已推送）

状态：`WAVE_0A_ZERO_MODEL_IMPLEMENTED_AND_PUSHED / TARGET_REGRESSION_170_PASS / FINAL_INDEPENDENT_P0_P1_0_0 / MAINLINE_COMPOSITION_NOT_IMPLEMENTED / RC-S3-105_OPEN / A03_ABSENT`

## 1. 本工作包的授权和边界

本工作包只落实 S3/179 已冻结详设中的 Wave 0A 零模型领域合同。它的目标不是先写一套新的后端，而是先把成熟 Agent Server 资格化和后续 Dell 单 case 所需的 FIN 领域边界变成可执行、可反例验证的合同。

本工作包明确没有执行：

- DeepSeek、OpenAI 或其他 provider/model 调用；
- 网络、外源搜索、S1、S2、MCP、Redis、Agent Server、queue、SSE 或 frontend；
- A02 retry/resume 或任何 paid successor；
- A03 创建、映射或 placeholder；
- Evidence admission、S2 write、报告生成、人工验收或产品发布；
- 旧 R14 continuation、R15/R16 或 formal gate。

因此，本记录只证明 zero-model domain-contract readiness，不证明 runtime composition、backend、provider、检索、财务研究内容或完整产品纵切已经跑通。

## 2. canonical runtime v1.2

新增 `src/sec_agent/canonical_runtime/contracts_v1_2.py` 和 machine contract：

- `AgentSessionV1_2`：稳定 case conversation / 顶层 thread；
- `ResearchRun`：一次完整研究生命周期；pause/resume 不换 Run，follow-up 才创建 child Run；
- `RunInvocation`：一次 start/resume/recovery worker dispatch 与 lease；
- `ActionAttempt`：一次 model/tool/capture/publish 副作用尝试；
- `RecoveryDisposition`：对 ambiguous dispatch 的不可变恢复决定；
- `CanonicalSessionEventV1_2`：session-scoped contiguous digest chain；
- `RunEventProjection`：按 run 过滤后可重建的授权投影，不冒充业务真值；
- `ContextCheckpointV1_2`：显式保存 plan、graph、coverage、Evidence/Fact/Claim/Calculation、disclosure、Skill consumption、finding/intervention、budget 和 stop refs；
- host-resolved ACL snapshot 与 authorization view，调用者不能直接提交当前 ACL 真值。

`required_material_refs` 不是调用者自由填写字段。作者分离审查曾发现 creator/validator 同时接受调用者传入 notebook/open-finding expected 集合，因而可“传空再自证”；该 P1 已转为修复项：新增薄 `CurrentContextMaterialResolver` trust port。current snapshot 绑定 accepted plan/graph、canonical event-ledger snapshot、notebook revision，以及 coverage/minimum-route、Evidence、Fact、Claim、Calculation、disclosure/Skill receipt、gap、feedback、counterevidence、question/finding、intervention、authority、stop、budget、context projection 与 LangGraph checkpoint 的完整 typed current closure；`notebook_refs` 由这些字段确定性派生。creator/validator 不再接受 caller-authored current/expected/extra typed 字段，resume 时重新读取 host snapshot，并核对 current session/run/invocation/event tip、snapshot digest 与全部材料闭包。`finding_opened/finding_resolved` 还会从 canonical events 重建未关闭集合，和 snapshot repository view 不一致即拒绝。

## 3. legacy v1.0/v1.1 与 A02 精确身份

v1.0/v1.1 保持不可变输入，只通过显式 adapter 进入 v1.2。普通 adapter 对真实 A01/A02 paid/run/session identity fail closed；它们不能把 legacy execution label、Run、Invocation 或 Action 混成一个 ID。

A02 只通过 content-addressed exact source bundle 映射：

- paid execution：`20260902-dell-reference-vertical-structured-a02`；
- ResearchRun：`dell-reference-vertical-structured-run-a02`；
- AgentSession：`SESSION::LEGACY::A02`；
- initial RunInvocation：`RUN_INVOCATION::LEGACY::A02::1`；
- Planner ActionAttempt：`planner-f8adf0fc5bf7-5d28981f08f4acc97e3a`；
- ResearchRun terminal status：`START_FAILED`；
- Planner receipt：`FAILURE / host_payload_validation_failed`；
- resume/successor authority：false。

历史发生时间来自原 A02 artifact；迁移时间只记录 import，不替换历史时间。A02 source bundle、四层 identity、request/failure receipt、objective、snapshot 和 base-plan digest 均精确绑定。A01 因当前没有同等级 exact source bundle，继续 fail closed。

新增 A02 saved `parsed_payload` 零模型回放：它只验证已冻结语义 payload 并返回 typed feedback；不读取或持久化 provider raw envelope、hidden reasoning 或 credential，不进行 model/network/provider call，也不授权 successor。其 host-resolved immutable source record 在消费时重新结构化验证，不能只依赖调用者可自行重签的摘要。

## 4. Dell Agentic 领域合同

新增 `src/sec_agent/agent_runtime/dell_agentic_contracts.py`：

- CoverageState 与 Q1–Q9 material coverage；
- answer-free `MinimumRouteObligation/BaselineSourcePlan`；
- `ResearchPlan` 与 `AgenticPlanDeltaV1_2`；
- `RuntimePolicySnapshot`、`ModelNodeAuthorityMatrix`、`RuntimeScope`；
- 从已接受 plan 中签发的 `RuntimeScopeAuthorizationRecord`；
- current verified-artifact registry resolver；
- GapEligibility request/decision；
- DecisionArtifact、sanitizer receipt 和 model-visible manifest binding；
- zero-model transport boundary 与 durable typed audit event。

Runtime scope authorization 绑定 case、agent、role、task、task kind、objective、plan、research graph、runtime/disclosure policy、authority matrix 和 permission set。签发者必须重新验证 accepted plan、找到唯一 active task、要求 task owner role 与 sealed agent role 一致，并证明所需 authority 是 scope permission 的子集。

PlanDelta 不能静默删除 required minimum route，Gap 不能把 empty result、未搜索 route、tool failure 或 caller-supplied stale registry 改名为 public-information gap。两者均通过 host resolver 重新读取 current registry revision/tip。

## 5. 渐进式披露合同

新增 `src/sec_agent/agent_runtime/progressive_disclosure.py`：

- L0 answer-free compact catalog；
- L1 semantic contract / inventory / complete Skill；
- L2 candidate metadata / detailed tool output contract / selected Skill resource；
- L3 bounded Evidence/Fact/Artifact content；
- L4 operator-only diagnostic，禁止进入普通 model context。

每次 request/grant/read 都绑定 session/run/invocation/action/agent/task、runtime scope authorization、runtime/disclosure policy、catalog snapshot、resource identity/content digest、canonical event 和 receipt。Runtime policy 与 disclosure policy 使用不同 digest 并交叉绑定；即使一次调用没有 grant，model-visible manifest 也必须显式绑定 disclosure-policy digest。

最终合同审查又发现 manifest 的 current PlanDelta、observation、feedback、action menu、budget/stop/intervention 和 checkpoint ref 仍可由调用方直接传入并让 runtime 重签。该 P1 已按同一薄 trust-port 模式修复：`CurrentModelContextResolver` 返回 host-current、self-digest snapshot；snapshot 绑定 exact scope/authorization、Session/Run/Invocation/Action、accepted plan/graph、canonical ledger snapshot/tip/revision 与两份 policy。manifest assembler 不再接收上述当前状态参数，`governance_summary` 改由重新验证的 RuntimePolicySnapshot 确定性派生，并将 current-model-context snapshot digest 写入 manifest。

重放该修复时又发现第三个 P1：runtime policy digest 虽与 scope/authorization 相等，但 policy 内部仍可自签另一 case、版本、as-of、data/catalog/disclosure policy，导致 Dell scope 收到错误治理摘要。最小修复在同一消费边界逐字段核对 case/version/as-of/data snapshot，交叉核对 current catalog 与 disclosure policy，并要求 scope branch/permission 是 policy allowlist 子集；每个内部字段均有独立负例。没有因此增加新架构或 resolver。

随后审查者按原 current-state 攻击改为“重签整个 snapshot”后确认，`issued_by=host` 和 self-digest 本身仍可伪造，形成第四个 P1。最终修复没有再叠一层 resolver：Runtime 在签发 exact ActionAttempt 的 sealed `RuntimeScope` 前，对 snapshot ID、resolver/store revision、当前 refs、action menu、budget/stop/intervention/checkpoint 与五层 identity 生成 `model_context_state_digest`；scope authorization 和 canonical action-intent event 已绑定该 scope digest。manifest 消费时重算 current snapshot state digest 并与这个先行 anchor 比较。调用者修改整组 payload 或来源 revision 并同时重签 snapshot 的反例现会 fail closed。

## 6. 消费边界根因修正

实现过程中发现：Pydantic `frozen=True` 不能阻止 `model_copy/model_construct` 跳过 validator。只在初次构造时校验、随后相信 typed object，会允许字段被修改后继续流入授权逻辑；只校验 self-digest 也不够，因为伪造者可以同时重签摘要。

因此 Wave 0A 统一采用：所有 current-state、identity、plan/evidence、ACL、checkpoint、recovery、policy、receipt 和 authorization 对象，在实际消费点从 `model_dump(mode="python")` 重建并重新运行字段、Literal、嵌套模型、model validator 与 self-digest 校验。

本轮代表性 fail-closed 反例包括：

- L1 resource 被改成 answer-bearing；
- disclosure receipt token 被替换；
- current canonical ledger repository/events 被替换；
- runtime/disclosure policy budget 或 digest 被替换；
- authority matrix 中 not-authorized node 被伪加 provider binding；
- ACL snapshot issuer 或 nested grant 被替换；
- event type 被改为缺少 owner identity 的 event 后重签摘要；
- checkpoint graph digest 被改成非法值后重签摘要；
- checkpoint 调用者同时提交空 notebook/open-finding expected 集合，或自签 graph/coverage/minimum-route；
- recovery decision 与 continuation/retry 语义冲突后重签摘要；
- PlanDelta 删除 required route proof；
- current registry nested artifact 被替换；
- manifest objective 被 caller swap；
- manifest current PlanDelta/observation/feedback/action menu/budget/stop/intervention/checkpoint 被 caller 直接提交；
- current-model-context snapshot 虽被重新签名但 plan/ledger/policy binding 已陈旧；
- current-model-context payload 被整体替换并重新签名，但其 state digest 不匹配先行 sealed RuntimeScope anchor；
- runtime policy digest 已绑定但内部 case/version/as-of/data/catalog/disclosure-policy/allowlist 与 current scope 不一致；
- task owner role 与 scope role 不一致；
- A02 immutable source record 被改成 successor-authorized 后重签摘要。

## 7. 机器合同和实现文件

机器合同：

- `configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_2.json`；
- `configs/research/evals/fin_ia_0_1_3_dell_a02_identity_import_bundle_v1_0.json`；
- `configs/research/evals/fin_ia_0_1_3_dell_a02_saved_planner_payload_offline_replay_v1_0.json`；
- `tests/fixtures/dell_a02_planner_parsed_payload.json`。

代码：

- `src/sec_agent/canonical_runtime/contracts_v1_2.py`；
- `src/sec_agent/agent_runtime/dell_agentic_contracts.py`；
- `src/sec_agent/agent_runtime/progressive_disclosure.py`；
- `src/sec_agent/agent_runtime/dell_a02_offline_replay.py`。

测试：

- `tests/test_agent_runtime_v1_2_contracts.py`；
- `tests/test_dell_agentic_contracts.py`；
- `tests/test_dell_progressive_disclosure.py`；
- `tests/test_dell_a02_offline_replay.py`；
- 更新 `tests/test_dell_reference_vertical_a02_gate.py`，使其识别冻结设计后允许的 zero-model v1.2 文件，同时继续拒绝 A03/provider/paid successor。

详设同步更新了实施中证明的更严格边界；没有改变 S3/179 的产品范围和停止条件。

## 8. 验证结果

目标回归命令：

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  tests/test_agent_runtime_v1_2_contracts.py `
  tests/test_dell_agentic_contracts.py `
  tests/test_dell_progressive_disclosure.py `
  tests/test_dell_deepseek_structured_agents.py `
  tests/test_dell_a02_offline_replay.py `
  tests/test_dell_reference_vertical_a02_gate.py `
  tests/test_dell_reference_vertical_cli.py
```

结果：`170 passed in 11.47s`。

附加静态检查：

- 新增四个 Python 模块 `compileall` 通过；
- 四个新增/更新 JSON contract/fixture 由 PowerShell `ConvertFrom-Json` 解析通过；
- `git diff --check` 通过；
- 当前环境未安装 ruff/black/mypy，因此没有伪称这些工具已运行。

## 9. 独立审查

最终作者分离审查没有把第一次绿测当成完成。只读合同审查依次发现并由作者在同一 Wave 0A 责任层修复四个 P1：

1. checkpoint 允许调用者同时提交 current/expected material，可能传空自证；改为完整 `CurrentContextMaterialResolver` snapshot closure；
2. manifest 允许调用者直接提交 current PlanDelta/observation/feedback/action/status；改为 `CurrentModelContextResolver`；
3. runtime-policy digest 已绑定，但内部 case/version/as-of/data/catalog/disclosure-policy/allowlist 未逐字段交叉核对；补 current scope/catalog/policy exact binding；
4. `issued_by=host` 与 snapshot self-digest 仍可由调用者整体重签；把 snapshot identity、resolver/store revision、五层 runtime identity 和完整 current payload 的 state digest 先行封入 sealed RuntimeScope，并由 current authorization/canonical event 锚定。

最终合同审查重放整体重签 current payload、runtime-policy 内部漂移和 checkpoint 旧反例，结论 `P0=0 / P1=0`。独立范围与声明审查确认机器合同、冻结详设、实现和本记录一致，且没有把 Agent Server、Redis、backend/frontend、S1/S2、RC-S3-105、A03、provider 或完整产品误写成已完成，结论同为 `P0=0 / P1=0`。

审查和回归均未联网、未调用模型、未读取或修改 live Codex SQLite/JSONL。该结论只覆盖本工作包列出的 zero-model contracts、A02 exact identity/offline replay 和消费边界；不构成 mainline composition、数据检索、Agent runtime、报告或产品验收。

## 10. 仍然开放的边界

1. `RC-S3-105` 没有关闭：SourceFamilyCompiler、current inventory、Reviewed Evidence selector、Q1–Q9 coverage/minimum-route 在真实 composition root 中尚未接线。
2. Wave 0A 代码尚未进入 Agent Server、PostgreSQL、Redis、LangGraph、SSE、HITL 或 frontend。
3. 没有证明模型自主规划、多轮上下文、Specialist/Counter/Lead/Verifier repair loop 或最终报告质量。
4. 没有创建 A03，也没有任何新 paid authority。
5. `mainline_consumption_evidence=[]`；本工作包是下一阶段的领域合同前置，不是完整 runtime adoption。

## 11. 下一合法入口

本工作包完成 clean commit、push 和 Project OS 对账后，进入 Wave 0B：对成熟 Agent Server 做 zero-model serving qualification，实测 license/key/egress、资源/数据驻留、thread/run/cancel/resume/SSE 行为和 FIN Session/Run/Invocation cardinality map。

Wave 0B 仍禁止 provider/model/paid execution。只有其形成采用或拒绝 receipt 后，才决定成熟 serving adapter 或最小 single-worker fallback；随后才进入 RC-S3-105 inventory/compiler/data-disclosure composition。
