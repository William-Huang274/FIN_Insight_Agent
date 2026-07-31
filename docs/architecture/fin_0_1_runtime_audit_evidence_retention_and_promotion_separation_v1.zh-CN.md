# FIN 0.1 运行时审计证据留存与内容晋升分离合同 v1

状态：capture v2 与 material-numeric classifier v2 已注入运行时，并经 DELL/MU/NVDA 三案例确定性 fixture 与双 disposable-runtime fresh-agent proof；R5 admission 尚未授权或签发，新的 exact-live 尚未执行。

## 决策

运行时必须把“内容是否允许进入正式研究成果”和“是否保留原始证据供审计”分开处理：

- 校验失败可以阻止内容进入 Claim、报告、评审面或其他业务 Artifact；
- 校验失败不得销毁已经发生的模型调用证据；
- telemetry 只负责索引和快速分类，不替代受限原始证据；
- 失败输出只能用于审计，不能自动重放、晋升为金融事实或参与 owner acceptance。

机器合同为 `fin01.runtime.audit_evidence_retention_and_promotion_separation:v1`，冻结于：

`configs/releases/fin_ia_0_1_s4_t06_mu_r4_numeric_classifier_false_positive_and_audit_evidence_separation_disposition_v1_0.json`

## 必须受限保存

每次真实模型调用应保存：

1. 模型实际可见的 system/user 请求；
2. assistant 最终输出；
3. 不含凭据的推理参数；
4. Provider、模型和路由身份；
5. finish reason、status、usage、latency、transport attempts；
6. Run、Attempt、Call、stage、capture sequence；
7. 内容 digest 和不可变对象引用；
8. validator rule code、命中字段路径和安全语义分类。

## 永不保存

- API Key、Bearer token、Authorization header、Cookie、密码；
- Provider 私有推理或隐藏 chain-of-thought；
- 未经过滤的响应头；
- 可能携带敏感内容的未过滤堆栈和异常载荷。

## 原子性

受限 capture 必须在 terminal failure 之前或与其同一原子事务内完成。可选 telemetry 扩展不得否决核心 capture 和三态终态化。终态事件应绑定 capture reference 与 digest；正文不复制到普通事件、运行摘要或业务 Artifact。

## R4 证据

MU R4 第四次调用的 assistant 最终 JSON 已由现有 v1 capture 完整保存，访问等级为 `internal_restricted_run_audit`。回放显示两个被计数的叙事值分别位于：

- `$.fact_layer[0].statement`
- `$.explanation_layer[0]`

两处共同包含报告期标签 `FQ3 2026`。当前正则把报告期数字与财务金额、百分比、计量值统一归类，构成项目内 classifier false positive。`failing_item_count=2` 是命中叙事值数量，不是两个错误财务数字。

R4 的 failed/failed/failed、0 Artifact 和 no-R5 事实保持不可变；本合同只纠正根因解释。

## 当前实现差距

| 能力 | 当前状态 |
|---|---|
| assistant 最终输出受限保存 | 已实现，R4 可回放 |
| 内容寻址及 Run/Attempt/Call 绑定 | 已实现，R4 可回放 |
| 失败输出与业务 Artifact 分离 | 已实现，R4 为 0 Artifact |
| 凭据、私有推理、raw provider envelope 排除 | 已实现 |
| 完整模型可见请求保存 | v2 已实现并经 fixture 证明 |
| 非敏感推理参数完整保存 | v2 已实现 allowlist、digest 与 credential rejection |
| 安全命中字段路径与语义类别索引 | v2 已实现，并绑定 capture ref/digest |
| 报告期与 material numeric 分类 | v2 已实现；本案绑定报告期/请求内标识符 nonterminal，金额、百分比、计量值、未知报告期和未分类数字 L1 terminal |
| v1 历史语义 | 保持不可变；v1 仍按原 blanket numeric 语义执行 |

当前可以宣称 `runtime-injected / deterministic-fixture-proven / fresh-agent-proven`，不能宣称 `R5-admitted`、`exact-live-proven`、`nine-Artifact L1 pass` 或 `owner-accepted`。

## 下一步边界

本轮唯一零调用实现包已经消费，实施记录为：

`configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_classifier_minimum_zero_call_implementation_v1_0.json`

它已经完成：

- versioned capture v2；
- 模型可见请求和非敏感参数留存；
- telemetry 到 capture ref/digest 的安全索引；
- 报告期、标识符、金额、百分比和计量值的分类；
- 失败 capture 不晋升、不自动重放的负向测试；
- R4 capture 的确定性回放回归。

独立零调用 fresh-agent proof 已完成：

`configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_agent_proof_decision_v1_0.json`

它在两个独立 disposable runtime 中证明了当前代码、MU exact input、三案例路径、R4 两个安全字段和 material-numeric mutation 一致，目标 SQLite、object tree 和逻辑快照未变；候选 R5 admission digest 已冻结，但 admission 文件不存在。

下一项仅为零调用权限决策：

`S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-FRESH-EXACT-ADMISSION-R5-AUTHORITY-DECISION`

该决策不得写入或消费 admission，不授权 R5 exact-live、paired assessment、owner acceptance 或 T07。签发与执行必须分别取得后续明确授权。
