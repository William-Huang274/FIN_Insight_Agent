# FIN 0.1 S2-T01 单 Cell Bounded Real Agent 设计与预检冻结

日期：2026-07-20
状态：`accepted_design_preflight / actual_execution_not_admitted`
机器合同：`configs/releases/fin_ia_0_1_s2_t01_one_cell_bounded_agent_preflight_v1_0.json`

## 1. 本任务的结论

S2-T01 只冻结一个真实 Agent 单 Cell 的可执行前提，不实现或运行 `bounded_agent_internal`。当前 Profile 仅保留产品级 ID，尚未签发可执行的 ProfileVersion；provider、model、endpoint、secret 环境变量、call/token/cost 上限和 exact Case 输入均保持 fail-closed。此次 model/provider/network/external tool/Evidence promotion/真实业务 Case mutation/Human Review/release admission 全部为 0。

这不是延续旧三-Cell standalone DeepSeek runner。旧合同只能提供“单次 transport attempt、失败即停、Writer 白名单输入、逐次记账”的历史参考；其 Case、三 Cell 范围、非 canonical artifact root 和未经重新验证的 provider/model 均与 S2 当前任务不等价。

## 2. 唯一范围与身份

- 公司：`NVDA`；
- Program Cell：`demand_authenticity_and_sustainability`；
- Layer 4 专业语义别名：`demand_signal`；两者是同一 Cell 的产品 ID 与分析角色映射，不得被当成两个 Cell；
- Cell 上限：1；
- 产品 Profile ID：`bounded_agent_internal`；
- 目标 WorkUnit type：`bounded_agent_internal_entry`，当前未加入 API/ExecutionService admitted types；
- 唯一 Runtime：现有 `Fin01ResearchRuntime`；
- 唯一异步路径：`Workbench -> API v1 -> ExecutionService -> existing DurableSchedulerService -> Fin01ResearchRuntime -> existing RuntimeFacade/store -> read projection -> Workbench`。

exact `case_id / case_version / DecisionSurfaceVersion / as_of / input digest` 尚未冻结。S1 fixture Case 只可作为结构回归材料，不能直接冒充 S2 真实评测 Case；历史 deterministic Run 如果输入不等价，也不能直接充当质量基线。

## 3. 单 Cell 执行拓扑

未来每一份 exact execution admission 最多创建 1 个 WorkUnit、1 个 Attempt 和 1 个 ResearchRun，`retry_budget=0`。必须依次形成：

1. Lead bounded plan；
2. real local/repo-available official EvidenceRequest；
3. Candidate collection 与 claim-scoped Evidence Gate；
4. deterministic Numeric program；
5. Specialist financial Judgment；
6. Lead adjudication；
7. Writer no-source；
8. deterministic integrity、semantic fidelity、financial coherence、visual delivery 四层 verifier；
9. 同一 exact Run 下的 immutable artifacts；
10. 与 exact-input-parity deterministic fallback 的独立 Run 比较；
11. 绑定 exact artifact 的 owner product review。

迟到或 stale 输出只能 quarantine，不能 commit。若需要修复，必须改变信息、route、Skill、Context 或可验证实现，并获得新的 exact execution admission、创建新的 Run；S2 最多一次有新信息的 repair cycle，仍无实质增益即停止并请求用户裁决。

## 4. 数据、工具、写入与秘密边界

- 首跑默认只使用本地或仓库已存在的 official assets；source network 默认关闭。若以后确需外部 source route，必须作为单独的 exact execution admission 条目显式批准；
- model-provider egress 与 source-network egress 是两项不同权限，不能互相推导；
- 商业数据禁止；任何未来工具调用都必须经过既有 ToolGateway、exact allowlist、permission/license 与调用账本；
- Candidate 和 Graph edge 都不是 Evidence；Evidence promotion 必须是 exact claim/entity/period/unit/scope、authority/as-of、permission/license、`can_support/cannot_support`、反证对称与 immutable lineage 的 run-scoped evaluation EvidenceVersion；
- 不修改已有 live business Case head，不写 global memory/registry，不做 release admission；canonical execution ledger 只能由现有 RuntimeFacade/store owner 写入，profile adapter direct canonical writes 保持 0；
- 不持久化 secret 或模型私有思维链。

## 5. Writer、Verifier 与产物

Writer 只接收经裁决的 Lead/Specialist/Claim、WWC、cannot-infer、冲突、typed gap、boundary、WriterBrief 以及获准 citation/numeric refs。raw Candidate、raw source rows、retrieval/source tool 和 private reasoning 不得进入 Writer；Writer 的 source/tool calls 固定为 0。

四层 verifier 相互独立：确定性完整性检查 exact identity/引用/数字/no-source/digest；语义层检查是否忠实表达上游 Judgment；金融一致性层检查数字和机制；视觉层检查最终用户表面。Verifier 只产出 finding、severity、earliest owner 和 repair recommendation，不改写研究业务真相，机器 pass 不等于 Human acceptance。

未来最小产物集为 manifest、Evidence、Numeric、Judgment、Workpaper、Report、Trace、Verification、Agent-vs-fallback Comparison 和 Owner Product Review。实际类型、schema 和 canonical binding 由后续实现任务在同一 Runtime 内落地，本轮未创建这些运行产物。

## 6. Agent 相对 fallback 的效果判定

候选与 baseline 必须是两个不同 Run，但绑定同一 exact evaluation CaseVersion、Cell、as-of、问题、source/permission boundary 和 material output surface。对比采用 blind 或 semi-blind，至少检查：直接回答、证据权威、数字桥接、机制深度、反证、边界/cannot-infer、WWC、Workpaper 可重建性和 Report review burden。

`material_value_gain` 只有在零硬完整性退步，并且至少一个研究或产品维度出现可由 owner 指向 exact artifact 的实质改善时成立。虚假引用/误 promotion、material numeric error、identity 错配、静默 fallback、Writer 越权补事实、秘密/权限/数据边界突破均为不可平均的硬失败。

## 7. 后续任务与当前阻断

- `S2-T02`：在零真实调用下，把 `bounded_agent_internal` profile/work-unit/adapters、exact artifact schemas 和 paired baseline parity 接到现有 Runtime；必须另获用户继续指令；
- `S2-T03`：绑定 exact Case/input、provider/model、Agent/Skill/Tool/Graph/Context/eval 版本和 call/token/cost/latency 上限，并执行一次首跑；必须在执行前获得 model/provider egress、预算和 secret-safe preflight 的明确授权；
- `S2-T04`：核验 Evidence promotion、Numeric、Judgment、Writer 与四层 verifier；
- `S2-T05`：完成 exact Agent-vs-fallback 对比与 owner product review；
- `S2-T06`：独立收口，只在有实质增益时允许 S3 解锁，否则 honest block。

当前最早阻断不是运行失败，而是准入尚未成立：ReleaseContract v1.3 仍只允许 S1 fixture，API/ExecutionService 尚未准入 `bounded_agent_internal_entry`，executable ProfileVersion 尚未签发，exact evaluation Case/input、provider/model、费用与权限也尚未绑定。真实执行前必须以新合同显式替换 S1 development admission；只改 backlog 不能授权调用。S2-T01 接受不会解锁真实执行、S3、RG1/RG3/RG4、release 或 production。
