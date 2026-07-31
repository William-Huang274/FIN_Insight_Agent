# FIN 0.1 S3-T08：三 Cell bounded-agent adapter 修复与 readiness 复跑

日期：2026-07-22

## 授权与结论

用户以“继续”只授权 `S3-T08-THREE-CELL-BOUNDED-AGENT-PROFILE-INPUT-OUTPUT-ADAPTER-REPAIR`。本轮没有签发或消费 T09 admission，没有调用模型、Provider、网络、来源或外部工具，也没有写真实业务 Case、Human Review、release 或 production 状态。

修复通过。T08 readiness 从 `exact_live_blocked_owned_three_cell_executor_gap` 变为 `ready_for_S3_T09_exact_admission_decision_pending_separate_user_authority`。这只代表 owned profile/input/output/canonical path 已接通，不代表 T09 已获权或真实 Agent 质量已经证明。

## 最早根因与修复

最早缺口在 `bounded_agent_executor.py`：S2 admission 强制一个 demand Cell，input compiler 只消费 `demand_signal`，executor 只有单 Specialist/Lead 路径。canonical facade 也只承认旧 profile 的 trace 和 Artifact mapping。

本轮保留 S2 `fin01.execution_profile.bounded_agent_internal:v1`、历史 admission 类、已消费身份与 digest 逻辑原样，新增独立 `fin01.execution_profile.bounded_agent_internal_three_cell:v1`：

- blind input compiler 绑定同一 Case/WorkUnit/Attempt/Run/DecisionSurface 和 T02-T07 exact version/digest；
- 三个 Specialist 只收到本 Cell 的 Runtime/Context、Evidence route、Numeric 和 bounded Graph 输入；
- T06/T07 只提供输出 contract 与 lineage digest，deterministic Judgment、Report 和 paired baseline 正文不暴露给 Agent；
- provider-neutral executor 固定编排三 Specialist、一个 cross-cell Lead、一个 no-source/no-tool Writer 和一个四层 Verifier；
- Specialist fact 层只接受 exact Evidence/Numeric authority refs，Candidate 和 Graph context 不能晋升为 fact；
- 每个节点必须绑定 Agent definition 与 Skill pack version；
- 同一 bounded work-unit owner 不能同时装配 S2 和 S3 profile；
- canonical facade 接纳新 profile 的两类 trace event 和原有九类 bounded Artifact，没有新增 Runtime、Registry、Writer、Store 或 gate family。

## 独立复核

首轮 node-level fixture 在 executor 完成六个节点后，被 canonical facade 先后以 trace event 未准入、profile artifact mapping 缺失 fail-closed。两处都在 canonical owner 中补齐，没有绕过校验。修复后零调用 fixture 形成一个 terminal Run、六个 node receipts 和九个 cross-linked canonical Artifact。

Visual 层保持 `review_required`，明确说明 browser 与 Human acceptance 不在本 fixture 内。15 个 entry root cause 均继续是 full-chain blocker；其中 12 个不再阻断“能否进入 T09 admission decision”，但仍等待 T09 paid artifact、T10 owner review，或后续 source/data/calibration 证明。

## 验证与边界

- 新 adapter 最终合同数：5（包含机器结果/ledger readiness 断言）。
- T08 + S2 历史兼容：`92 passed in 90.24s`。
- `git diff --check`：pass。
- 模型、Provider、execution network、source network、external tool、live business write、Human Review write、新 exact admission、paid run：全部 0。
- FIN 0.1 S1-S3 + Workbench 广泛回归：`178 passed in 183.37s`。

## 下一步与回滚

下一项是 `S3-T09-EXACT-THREE-CELL-LIVE-ADMISSION-DECISION`，必须等待新的用户授权，先冻结 exact provider/model、六节点预算、credential env、fresh execution identity 和 immutable input digest；当前权限不能签发或执行。

回滚可移除新 S3 profile/input/output 类型和 factory 参数，撤销 facade 的新 profile/event mapping，并恢复 backlog/context/ledger；S2 历史代码与 T02-T07 deterministic artifacts 不需要改写。
