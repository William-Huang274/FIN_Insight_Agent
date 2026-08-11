# R59 Reference Ledger And Sandbox Policy

Date: 2026-06-29

## Prompt

用户要求把 R59 前后端参考平台吸收项更新进 R59 文档，并且每个参考来源都要标注出处，方便后续追溯、新增、删除和记录进入项目后的表现。随后要求讨论 sandbox / 沙盒是否有必要以及应该怎么做。

## Decision

R59 不能只维护一张“外部平台参考表”。它需要三个长期维护对象：

- `ReferenceSourceLedger`：记录来源、版本、review date、适用范围、采用/不采用理由、映射到 FinSight 的对象和关联 demand。
- `ReferenceChangeLedger`：记录参考来源新增、更新、降级、删除和替代原因。
- `ReferenceAdoptionPerformanceProfile`：记录某个外部设计进入项目后是否真的改善了质量、效率、可审计性或用户体验。

Sandbox 也应进入 R59，而不是只放在 R56 的 runtime 权限讨论里。原因是 FinSight 会做上传文件解析、联网抓取、浏览器渲染、Python/JS 计算、Deliverable render、quant backtest、MCP-style 工具调用和 B 端多租户数据访问。这些都需要文件、网络、凭证、artifact 写入和人工批准边界。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`：
  - 新增 `ReferenceSourceLedger` 合同。
  - 新增 `ReferenceChangeLedger` 合同。
  - 新增 `ReferenceAdoptionPerformanceProfile`。
  - 增加参考来源留痕规则和 sandbox / isolation 参考补充。
  - 新增 `SandboxPolicy` 合同，覆盖 actor、tool、filesystem、network、credential、code execution、artifact write 和 approval。
  - 新增工具分层 sandbox 策略：DB/RAG read、crawler/browser、parser/document render、Python analysis、Deliverable Composer、Quant backtest、Admin ops。
  - R59 demand 从 D01-D16 扩展到 D17-D20。
  - Acceptance gates 新增参考台账和 sandbox regression 要求。
- 更新 `docs/worklog/00_internal_master_checklist.md`：
  - 记录 R59 reference/sandbox update 和未完成 runtime enforcement。

## 2026-06-29 Follow-up Update

用户要求把“先做策略合同、本地轻量隔离、B 端生产或高风险工具再升级为 container / gVisor / microVM / Kubernetes namespace + network policy”三步展开写入 R59。

本次补充：

- 在 R59 `10.4 Sandbox / 沙盒隔离策略` 之后新增 `10.5 Sandbox 三阶段落地路线`。
- Step 1 `Contract first`：明确要落 `SandboxPolicy`、`ApprovalPolicy`、`ToolInvocationLedger`、`PermissionRequest`、`SandboxRunProfile`、`CredentialLease`、`ToolPolicyBinding`，并写清与 R56/R57/R58/R59/R60 的接入关系和 gate。
- Step 2 `Local lightweight isolation`：把本地实现拆成 DB/RAG read、crawler/browser fetch、parser/document render、Python analysis、Deliverable Composer、Quant backtest 六类工具，并写 path/network/domain/writer/malicious upload/credential/artifact path smoke gate。
- Step 3 `Production / high-risk isolation`：定义 container、gVisor/Kata/microVM、Kubernetes namespace、isolated quant worker 的适用边界，以及 `SandboxOrchestrator`、`NetworkProxy`、`CredentialBroker`、`ArtifactProxy`、`PolicyAuditStore`、`TenantBoundaryGate` 组件和 release gate。

## References Used

- OpenAI Codex sandbox / approvals / hooks：用于区分 sandbox technical boundary 与 approval policy，并吸收 workspace/network boundary、agent phase credential boundary 和 hook lifecycle。
- Anthropic Claude Code sandboxing：用于吸收 filesystem isolation + network isolation、domain allowlist、MCP/subprocess 继承边界和 scoped credential proxy。
- Google Gemini Enterprise Agent Platform / Agent Gateway release notes：用于吸收 agent/tool/agent 间连接治理、identity、gateway、observability 和 DAG trace。
- LangGraph / LangSmith Agent Server、Temporal HITL、Copilot Studio、Onyx、Glean、Palantir AIP、Hebbia、Dify、RAGFlow 等参考仍按 R59 主文档台账维护。

## Verification

- 本轮为 docs-only 更新。
- 2026-06-29 初次更新后已运行 `git diff --check` 和 candidate-file secret scan。
- 本次 follow-up 更新后待重新运行 `git diff --check` 和 candidate-file secret scan。
- 未运行 runtime / frontend / backend tests，因为没有改代码、schema 或测试文件。

## Follow-up

- R59-D17：把 reference ledger 变成 repo 内 machine-readable registry 或 SQL table。
- R59-D18：建立参考变更流程和项目内表现评估。
- R59-D19：实现 `SandboxPolicy` / `ApprovalPolicy` / `ToolInvocationLedger` runtime contract。
- R59-D20：Workbench 显示工具允许/阻断原因，并加入 sandbox regression：network escape、path escape、credential injection、malicious upload、forbidden tool-call、artifact publish 越权。
