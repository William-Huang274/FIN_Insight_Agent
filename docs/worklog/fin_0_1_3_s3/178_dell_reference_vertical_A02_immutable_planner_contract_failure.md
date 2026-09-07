# DELL 完整纵切 A02：不可变 Planner 合同失败与 successor 停止门

更新时间：2026-09-03 00:20 +08:00
产品版本：FIN 0.1.3（未创建新产品版本）
分支：`codex/fin013-dell-s1-s2-product-bridge`
运行绑定 commit：`e50713b3d6d29ff4c9bc464dae004d9479bef269`

## 1. 结论先行

A02 已按 Owner 授权从 clean、pushed、双 zero-call preflight 通过的 commit 唯一启动一次。它没有到达 HITL，也没有进入 S1、S2、MCP、Specialist、Counter 或 Lead。唯一真实执行的模型节点是 Planner：DeepSeek HTTP 200 并返回一个九分支 tool-call 草案，但该草案在宿主 `EvidenceRequest` 合同校验中失败，attempt 以 `start_failed` 不可变收口。

这次运行同时证明 A01 的 provider parser 修正确实有效：provider JSON 已作为 plain mapping 到达宿主 `_validate_payload`，不再被 `PydanticToolsParser` 的 list/tuple 差异提前错杀。A02 暴露的是新的、项目自有的更早责任层：Planner 没有获得真实数据目录，而 provider-visible JSON Schema 也没有表达宿主的条件字段约束。

因此禁止对 A02 重试、恢复或覆盖，也不应仅放松三处 validator 后创建付费 successor。逐条 selector 对账进一步证明：A02 草案中的 16 个本地请求全部使用 foundation 的抽象 family ID／role，而当前 1,025-node structured corpus 使用具体 route/source-role；按真实 MCP metadata-prefilter 语义复算为 `16/16` 本地请求匹配 `0` 个节点。只修表面 schema 会把失败推迟到材料为空，极可能再次产出边界说明而不是高质量报告。

## 2. 启动前冻结状态

- A02 attempt：`20260902-dell-reference-vertical-structured-a02`
- run：`dell-reference-vertical-structured-run-a02`
- snapshot：`20260902-dell-structured-s1-s2-external-a02`
- case：`DELL_AI_INFRA_REFERENCE_VERTICAL`
- research as-of：`2026-09-02T23:59:59+08:00`
- branch：Q1–Q9，共 9 个研究分支
- launcher SHA-256：`72637741b556ca767431fe67d14692340f4ae5aa13e9cb98dcb2bdb7e2be59f8`
- Owner decision SHA-256：`b3a9d3976ee994c44438089457be0096e813f5cf7ab31e4421921921fe6acfdb`
- A02 config SHA-256：`5a012f9edc22d32ca5c6b5d16d76fc927d561ecd9c4f190a5ffc80956ca78ddb`
- clean implementation commit 与 upstream：均为 `e50713b3...bef269`

启动前两道 zero-call gate 均通过：

1. Project OS gate：repository clean/synced、credential 仅验证存在而不读取/保存值、model/network/provider calls=`0/0/0`。
2. A02 launcher `-PreflightOnly`：9 branches、597 knowledge records、61 Reviewed Evidence、structured RAG、fresh S2、12-route frozen external candidate pack、MCP、LangGraph 和 SQLite checkpointer 构造通过；`graph_invoked=false`，model/external discovery/external capture=`0/0/0`。

启动前稳定产品相关回归为 `115 passed in 72.10s`；A02 gate 5 passed；gate+CLI 31 passed；compileall、JSON/JSONL、PowerShell parse、diff check 与 secret scan（8,423 files／0 findings）均通过。历史 Project OS 测试中仍有由旧 live-authority JSON 固定旧 source SHA 引起的预期 drift，未改写不可变历史 decision，也没有把这部分伪称全仓绿色。

## 3. 唯一真实运行的精确结果

### 3.1 Attempt 终态

- status：`start_failed`
- started：`2026-09-02T23:54:51.099264+08:00`
- failed：`2026-09-02T23:55:36.644206+08:00`
- wall elapsed：`45,544.951 ms`
- error：`DeepSeekStructuredAgentError('model_structured_payload_invalid')`，由 TaskGroup 汇总为 start failure
- API key persisted：false
- retry/fallback：无执行痕迹
- approve/reject resume、render、publication、formal、product acceptance、release：全部 0

### 3.2 模型调用与费用证据

唯一 call ID：`planner-f8adf0fc5bf7-5d28981f08f4acc97e3a`

| 字段 | 实际值 |
|---|---:|
| Provider / model | DeepSeek / `deepseek-v4-pro` |
| HTTP 结果 | 200，`finish_reason=tool_calls` |
| 输入 tokens | 21,489 |
| 输出 tokens | 2,874 |
| 总 tokens | 24,363 |
| provider elapsed | 32,359.116 ms |
| outcome | `host_payload_validation_failed` |
| transport retries | 0 |
| fallback model calls | 0 |

这些 tokens 已消费，必须归入失败调用成本，不能因为宿主验证失败而记为 0。

### 3.3 Graph 实际到达位置

SQLite checkpoint 主库保持 3 checkpoints／28 writes。最新持久化 phase 为 `foundation_bound`，下一节点为 `plan`；Planner 异常以 `__error__` write 保存，但没有成功的 `planner_output`、`plan_digest` 或 `branch_tasks` checkpoint。

实际执行矩阵：

| 层 | 实际执行 |
|---|---|
| Foundation bind | 成功 |
| Planner | 1 次真实调用，响应后校验失败 |
| S1 / Reviewed Evidence / local BM25 | 0 |
| S2 mart query | 0 |
| MCP tool calls | 0 |
| frozen candidate replay / Exa / DDG | 0 / 0 / 0 |
| 9 Specialists | 0 |
| Counter 与定向回派 | 0 |
| Lead / verification | 0 / 0 |
| HITL | 未到达 |
| report | 不存在 |

模型返回的九个 task 只是无效草案，没有成为 graph 已绑定的 `branch_tasks`，不得写成“九分支 multi-agent 已运行”。

## 4. 宿主合同的四条直接错误

用当前冻结 Pydantic 合同对保存的 `parsed_payload` 离线重放，得到：

1. Q6 第一条 `reviewed_first`：有 source role／route／lane，但没有 `issuer_ids`，报 `local_evidence_request_scope_underbounded`。
2. Q7 第一条 `reviewed_first`：同样没有 `issuer_ids`，报相同错误。
3. Q9 唯一 `external_required`：携带只允许本地检索使用的 `source_roles`、`route_ids`、`retrieval_lanes`，报 `external_request_local_retrieval_scope_forbidden`。
4. Q9 唯一请求被拒后，task 随后报 `evidence_requests` too short。

这里不能简单解释成“DeepSeek 不听话”。Provider-visible schema 只暴露字段、默认值、类型和 enum，没有表达上述条件规则；Planner system prompt 又要求本地请求复制 constraints、当方法未建立 constraint 时留空，这与宿主“本地必须同时有 issuer_ids 与 source_roles”的 validator 直接矛盾。对 `external_required`，prompt 也没有明确声明必须清空所有本地 selector。

Planner 同时生成了 2 个 FinancialFactRequest，均为 DELL、`quarter_discrete`、`exact_period_end`，请求 2026-05-01 与 2026-01-30 的 11 项允许 metric；它们可通过当前 schema，不是本次失败责任层。当前 FY27 Q2 仍没有可冒充的 S2 `NumericFact`，后续即使执行也必须保留显式 numeric gap。

## 5. 更深的材料目录错位

### 5.1 Planner 实际可见的能力

Attempt composition 的 `planner_tool_capabilities` 只有：

- cutoff／as-of；
- 抽象 `evidence_routes`；
- finance capability 与 mart identity。

它没有：

- 1,025 个 structured nodes 的可用 issuer／source-role／route／period inventory；
- 61 条 Reviewed Evidence 的可选 locator inventory；
- r12 12 条 frozen external routes 的 branch、publisher、title、domain 和 route ID inventory。

换句话说，系统让 Planner 负责选资料，却没有把“资料架上实际有什么、标签叫什么”告诉它。

### 5.2 16/16 本地请求离线 selector 对账

真实 structured nodes 的 metadata inventory 为：

- 1,025 nodes；
- issuers：`AMAZON, ANTHROPIC, DELL, HPE, META, MICRON, MICROSOFT, MLCOMMONS, NVIDIA, US_BIS`；
- lanes：`parent, prose_leaf, table_leaf`；
- 20 个 concrete route IDs；
- 11 个 concrete source roles，例如 `issuer_management_disclosure`、`hyperscaler_demand_primary`、`regulator_primary`、`supplier_management_disclosure`。

A02 Planner 却使用 `F1_SEC_ISSUER_FACTS`、`F2_DELL_IR_EARNINGS`、`F3_DELL_PRODUCT_SUPPORT`、`F4_CUSTOMER_CAPEX_DEPLOYMENT`、`F6_COMPUTE_PLATFORM_SUPPLIERS` 等 foundation family IDs，以及 `issuer_narrative_and_company_defined_metrics`、`platform_and_supplier_state` 等抽象 role。它还使用了本地不存在的 ticker-like issuer IDs，如 `MSFT`、`AMZN`、`GOOGL`、`NVDA`、`MU`、`TSM`。

真实 MCP 的行为不是把这些抽象标签再翻译一次：只要请求携带 `route_ids`，`reviewed_first` 会直接转到 exact structured local lookup；metadata-prefilter 对 issuer／role／route／lane 做精确 membership 过滤。因此离线按同一语义对账的结果是：

```text
local requests = 16
requests matching at least one structured node = 0
zero-match requests = 16
```

这说明三条表面 validator 即使被放松，所有本地 Evidence request 仍会变成 exact-route gap；而 A02 17 条请求中只有 Q9 一条 external。r12 冻结外源包也几乎不会被消费。这个失败属于 Planner capability projection 与数据合同错位，不是 BM25、dense、reranker 或文档 chunk 质量失败。

## 6. A01 与 A02 不应被混为同一个问题

- A01：provider 返回合法 JSON arrays，但中间 `PydanticToolsParser` 用 strict Python tuple 语义提前拒绝；A01 草案为 9 tasks／19 Evidence requests／10 external。
- A02：plain JSON mapping 已成功到达宿主验证，证明 A01 parser successor 有效；A02 草案为 9 tasks／17 Evidence requests／1 external，但宿主条件合同与实际数据 inventory 没有被 provider-visible 地投影。

A01 草案也不能直接拿来复用：当前合同相较 A01 已增加本地 selector 与 `selection_mode` 等字段，离线重放并不合法。A01 更偏 external、A02 更偏 local 还说明 free-form Planner 的路线选择存在显著方差；不能把“这次模型运气好不好”当成完整纵切的材料覆盖机制。

## 7. Artifact 与完整性

Attempt 根目录：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\runtime\attempts\20260902-dell-reference-vertical-structured-a02`

| Artifact | SHA-256 |
|---|---|
| `composition.json` | `f840b70995d180121a867507f4e8045cc65652f9021d4e8f4b1abbb8861f792c` |
| `start-input.json` | `0ff29f4c447f0641bcbcdec1d8a2351b17622a59f51c871509e237feea261e46` |
| Planner started journal | `db36a895266738eb2402f14d6b794d0399409de1c134017c50910b6b47e579e2` |
| Planner outcome journal | `234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7` |
| `failure.at-start.json` | `62abc666ca3d6a24496b0f220ea661ea83971591bf9886d62542dc0e19b8123a` |
| checkpoint `.sqlite3` | `2ac3f769c401d4e75ae3081d5b0bca9ead594d7162aafa00a5cda4b0d6d03853` |

审计时存在两个必须披露、但不得冒充运行痕迹的边界：

1. 人工 precondition 检查曾误看 `.sqlite`，而 runner 的真实路径是 `.sqlite3`；runner 自身对正确路径做了不存在检查并安全创建，因此没有覆盖旧 identity，但人工检查路径应在 successor checklist 修正。
2. 独立 reviewer 使用 SQLite `mode=ro` 读取 WAL-mode checkpoint 时，SQLite 仍创建 32,768-byte `.sqlite3-shm` 与 0-byte `.sqlite3-wal` sidecar。主库 SHA、mtime、3 checkpoints／28 writes 未变；sidecar 是审计读取副作用，不是 A02 runtime activity。它们未被删除或再次打开。

## 8. 最小 successor 设计，不建设新框架

下一步不应再加一套治理协议、第二套 MCP、第二套 crawler 或自研 Planner 框架。最小设计是把现有成熟组件和现有数据合同接对：

1. **投影真实 inventory**：把 structured corpus、Reviewed Evidence 和 frozen external pack 的 answer-free 目录投影给 Planner；只含 branch、route ID、issuer、source role、period、publisher/title/domain 与 authority state，不含题目答案或未审事实。
2. **用显式 tagged union 表达 EvidenceRequest**：`reviewed/local` 与 `external` 使用 provider-visible 的判别类型，让条件字段在 JSON Schema 中可见；不再把关键约束藏在响应后的 model validator 中。
3. **冻结每个分支的最低资料路由**：从已经批准的 foundation 与真实 inventory 编译一份 answer-free baseline source plan。Planner 可以增加、收窄或提出 delta，但不得静默删除九分支的最低覆盖。
4. **缩小 Planner 职责**：优先让 Planner 只返回 `PlanDelta`，而不是每次自由重写完整 9-task／EvidenceRequest 图。Multi-agent 的真实性仍由隔离 Specialist、真实 S1/S2 tools、Counter 定向回派、Lead synthesis 和 HITL 证明，不需要用一个巨大自由文本 Planner 充当单点失败源。
5. **允许一次有预算的语义修复**：只有在 provider 已返回、错误属于可反馈的 request-level schema 时，才可把精确 validation errors 回传给 Planner 做最多一次 repair；必须有新的 task-specific `TokenBudgetBasis` 和明确停止条件，不能隐藏为 transport retry。
6. **付费前先离线证明**：用 A02 保存 payload 与 synthetic variants 验证 schema、inventory、baseline coverage、selector match、external/local separation；要求 9/9 branch minimum coverage、所有 local exact selectors 至少命中一个合法 candidate、external selector 零本地字段、0 model/network calls。

只有这些离线条件通过、独立 reviewer P0/P1=0、形成新 clean pushed commit 和新的 Owner decision 后，才可创建新的 immutable attempt 身份。A02 本身永久失败，不 resume、不 retry；截至本记录，没有创建或授权 A03。

## 9. 当前真实产品状态

- 数据地基：structured corpus、61 Reviewed Evidence、fresh exact-period S2、r12 12-route external candidate pack 均已绑定并分别有局部真实 smoke／qualification，但 A02 未实际消费。
- RAG/S1：本次没有产生新的检索质量结论；既有 BM25 provisional baseline 与 candidate-only authority 不变。
- S2：本次查询 0；fresh S2 contract 局部通过的状态不变，不能写成 A02 已验证。
- Runtime：clean composition、checkpoint、budget/round authority 和一轮真实 Planner 调用成立；完整 multi-agent fan-out、Counter、Lead、HITL、报告质量、时延与总成本均未验证。
- 公开展示：仍没有可展示的最终 Dell 报告，不能把 A02 写入简历为“端到端跑通”；可以诚实写成一次可观测、fail-closed 的 structured Planner failure，但这不是用户要的最终案例成果。

活动停止门是 `RC-S3-105-dell-A02-planner-capability-inventory-and-conditional-contract-mismatch`。在该门关闭前，不得创建新付费 attempt、不得把 A02 改写为 HITL 成功、不得推进 report/formal/product/publication/release。
