# FIN 0.1.2 S2：DeepSeek Flash stable / Pro preview 自然能力边界 StagePlan

日期：2026-08-02

状态：`S2-T03 bound runner and atomic capture preflight pass / exact six-call execution authorized not started`

## 1. S2 到底要回答什么

S0 已证明当前工程包可复现，S1 已证明 DELL、MU、NVDA 的确定性三案链。S2 只回答一个问题：在同一份当前合同下，DeepSeek V4 Flash stable 与 Pro preview 哪一个更适合作为 S3 主线，以及模型到底只负责哪些判断，哪些内容必须由本地程序生成。

本阶段不生成九件套，不做三案 full-chain，不做 DELL/MU/NVDA 产品验收，也不把速度或 JSON 可解析误报成金融研究质量。

## 2. 为什么不能直接复刻旧 canary

旧 Pro canary 和 exact-live 暴露了四类不同问题：

1. Fact 小候选池能够自然返回合法 JSON 和判断原子；
2. Claim 首次失败是条件语义只存在于本地 selector，没有进入模型可见合同，属于项目合同缺口；
3. WWC 返回 6 个可见合法候选后，被本地代码用最终 top-3 上限提前拒绝，属于候选容量与最终选择容量混淆；
4. Fact 曾看见 22 个合法 alias 后全部返回，说明不能把“模型会自行控制数量”设为硬可靠性前提；数值叙事和日期字段也证明模型不应直接拥有 material number 或 calendar deadline。

因此本轮不再测试模型能否背诵长而刚性的完整结构。模型只选择 request-local aliases、closed enums 和 bounded judgment atoms；本地代码拥有 material number、period/date、identity、ID、ordering、lineage、最终 rendering 和 L1。

## 3. 新发现的当前漂移

当前 `common_runtime_contract_family_source_v1_0` 的状态文字仍写着“尚未迁移到 live Runtime”，但 binding 与 S1 十 consumer 证明已经表明迁移完成。同时 `bounded_agent_executor` 的多个 admission 校验把模型硬编码为 `deepseek-v4-pro`。

这不推翻 S1 的行为证明，但会让 Flash/Pro 无法在同一版本化合同下公平比较。登记 `RC-P36-098`，由 S2-T02 在任何模型调用前修复。v1.0 历史文件不改写；T02 创建新的当前 source/binding 与 S2 model-candidate registry，并保持历史 Pro admissions 不变。

## 4. 四个固定任务

| 任务 | 内容 | 调用预算 | Exit |
| --- | --- | --- | --- |
| S2-T01 | 本 StagePlan、历史证据审计、阶段归属和预算冻结 | 0 | 当前计划、机器合同、投影和 Project OS 一致 |
| S2-T02 | 双模型 route、当前合同 source/binding、paired-canary compiler 的一次零调用实现 | 0 | `engineering_pass`：97 项组合回归全绿，三案各 6/6 fake/capture/assembly 通过 |
| S2-T03 | MU 单 Cell、Fact/Claim/WWC、Flash/Pro 配对自然输出 canary | 主要 6 calls | 六个独立结果与 capture 完整，或形成诚实 transport block |
| S2-T04 | 盲配对 assessment、模型/本地 surface disposition、S2 closeout | 0 | 选择 S3 主线或明确 no-model surface，并冻结成本与证据边界 |

不存在自动 S2-T05，也不在 S2 内跑 full-chain。

## 5. T02 必须实现什么

- 新增一个版本化模型候选 registry：`deepseek-v4-flash` 是用户确认的 stable API-only 首选候选，`deepseek-v4-pro` 是用户确认的 preview、历史主线 control；两者都不因写入 registry 自动成为 Runtime 主线。
- 同一 provider、base URL、Chat Completions JSON-object、temperature=0、thinking disabled、reasoning none；不做 Provider hopping 或自动 fallback。
- 参数化 S2 canary route，而不是修改历史 admission 的含义。
- 同一 family 的 Flash/Pro 请求除 model/model_ref、fresh call identity 和不可避免的 receipt 字段外逐字节相同。
- Fact 在调用前由本地 planner 把可见候选池限制到最多 6；Claim 的 kind/support 条件规则同时进入 prompt、wire、validator、selector、fake 和 typed failure；WWC 先验证最多 6 个候选，再稳定选择最多 3 个。
- Provider 不得直接写 material number、calendar date、case identity、runtime ID、lineage 或 raw ref；模型只选择 alias/enum/atom，本地渲染最终内容。
- 完整保留模型可见请求和最终 assistant 输出，先 capture 再校验；credential、headers、Cookie 和 private reasoning 永不保存；失败输出不得晋升业务内容。

## 6. T03 为什么是六次调用

测试对象是三个已经改变过合同边界的 family：Fact、Claim、WWC。每个 family 用同一 MU 输入分别调用 Flash 和 Pro，一共 6 calls。family 之间不互相喂输出，因此任何一个语义失败不会阻止收集其余 family 的结果；只有鉴权、transport、安全或 capture 失败才全局停止。

这样做是为了在一轮内暴露完整边界，避免再次出现“看到一个字段、改一个字段、再 live 一次”。主要预算为最多 6 calls、50k input tokens、8.4k output tokens、USD 0.06、900 秒；retry、fallback、Provider hopping、prompt-only retry 都是 0，业务 Run/Artifact 写入也是 0。

## 7. 如何选择 Flash 或 Pro

先看 hard integrity：transport/finish、native JSON、schema、alias/enum、容量、跨字段语义、禁止表面、本地 assembly、capture/terminal result，任一失败都不能靠主观质量分覆盖。

再做隐藏模型名的盲评，每个 family 对四项各评 0–2 分：证据选择相关性、认识论克制、决策有用性、信息密度。最后记录 token、延迟和成本，但性能不替代质量。

- 两者全部 hard pass：默认选 stable Flash；只有 Flash 三 family 的盲评总分比 Pro 低超过 2 分，才考虑 Pro preview，并明确 preview 生命周期风险。
- Flash hard fail、Pro hard pass：可选 Pro，但只拥有通过的 family surface。
- 两者在同一 family 均失败：不继续扩大 prompt；该 surface 转为本地确定性 ownership，或 S2 honest block。
- 不允许自动 Runtime fallback 或调用时模型切换。

## 8. 失败后的唯一维修边界

如果 T03 证明比较器、模型可见合同、capture 或本地 assembly 本身有项目缺陷，问题必须留在 S2 修最早 owner。最多允许一个合并后的零调用 repair bundle，以及只针对受影响 family 的 Flash/Pro 两调用 replacement pair；都需要新 digest 和单独用户授权。

模型真实不遵循合同、自然输出质量弱或两模型能力差异，不属于 replacement 理由。replacement 后再出现新的项目失败类别，S2 直接 honest block，不进入新的逐字段 live 循环，也不自动创建 FIN 0.1.3/0.1.4。

## 9. 阶段归属

- RC-P36-080 的 Provider surface 边界与模型选择属于 S2，阻断 canary closeout；
- RC-P36-067/068 的本地数字与 identity owner 在 S2 保持不放宽，最终九件套证明属于 S3/S4；
- RC-P36-083 的广义跨 family compiler 仍属于 FIN 0.2，不因本次三个 scoped family 而宣称关闭；
- RC-P36-084 的 Verifier 与交付质量属于 S3/S4；
- strict-schema transport 继续停放，不阻断 DeepSeek JSON-object + local validation 主线。

## 10. T02 实现结果

T02 已完成唯一一个零调用实现包。当前 v1.1 source/binding 与 Flash stable / Pro preview 候选 registry 均由独立 S2 RuntimeResourceRegistry 做哈希约束，历史 v1.0 source/binding 和旧 Pro admission 未改写。三个 family 各生成一对模型可见内容逐字节一致的请求，只有模型身份和调用身份不同。

实现时额外发现并在本任务最早 owner 处收口了三项设计漂移：Provider 不再回写本地 `program_cell_id`，而是在校验后由本地注入；Fact 合同补入有界 statement/boundary 供模型做相关性判断，但输出仍只能选择 alias/enum；S2 资源 loader 与旧默认 registry 完全隔离，避免新阶段路径污染 S0 历史资源权威。对应 RC-P36-098/099/100 均以零调用证据关闭。

组合回归为 `97 passed / 0 failed`（95 项 Runtime/历史兼容矩阵，加 2 项结果与 current projection 闭环）。覆盖 DELL/MU/NVDA、Flash/Pro 六调用计划、请求等价、身份/跨案/日期/Claim 条件/WWC 容量 mutation、capture-before-validation、语义失败继续收集和 transport 失败停止。credential、模型、Provider、网络、业务 Run/Artifact 调用均为 0。

机器结果：`configs/releases/fin_ia_0_1_2_s2_t02_dual_model_route_current_contract_source_and_paired_canary_compiler_zero_call_implementation_v1_0.json`。

## 11. 当前下一项

`FIN-0.1.2-S2-T03-PAIRED-CANARY-BOUND-RUNNER-ATOMIC-CAPTURE-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

零调用权限审查已通过并有条件签发六调用 authority。审计发现 T02 只有 compiler、本地 materializer 与内存 fake capture，缺少该实验专用真实 runner 和校验前原子受限 capture persistence，登记 RC-P36-101。下一项只补 runner/capture/preflight；preflight 通过前不得读取凭据或执行六调用。sub2api `gpt-5.5 /responses` strict-schema 路线继续 parked，不与当前官方 DeepSeek 路线混用。

## 12. T03 preflight 实现结果

专用 runner、T03 资源注册表、原子内容寻址对象仓与显式单次 transport attempt 已完成。runner 不再依赖测试 helper，而是从已登记的 MU exact fixture 重建当前 compiler；零调用 preflight 重新派生的六个 request/equivalence digest 与 authority 全部一致。capture 在本地 validation 前持久化，raw Provider envelope、credential、header、Cookie 和 private reasoning 不进入对象仓；失败 terminal 与 sanitized execution result 均保留。

实现证据为 focused=`28 passed / 0 failed`、包含 T02 与资源/网关/对象仓的组合回归=`61 passed / 0 failed`；加入结果文件与 current projection/backlog 闭环断言后，最终分别为 `30 / 63 passed`。语义失败继续五个调用、transport 失败留存 capture 后停止五个调用、capture/预算/重复 execution identity 均 fail closed。preflight 没有读取凭据或调用模型/Provider/网络，最坏主预算估算为 `USD 0.029058`，低于授权上限 `USD 0.06`。RC-P36-101 因此关闭。

当前唯一下一项已经变为：

`FIN-0.1.2-S2-T03-MU-FLASH-STABLE-VS-PRO-PREVIEW-PAIRED-NATURAL-OUTPUT-CANARY-EXACT-SIX-CALL-EXECUTION`

该项只消费既有六调用 authority；没有 retry、fallback、Provider hopping、自动 replacement pair 或业务 Run/Artifact。只有完成六个 terminal/capture 或形成诚实 transport block 后，才能进入 T04。

## 13. T03 exact 六调用结果与当前边界

授权的 MU 六调用已严格执行一次：六个调用均 `finish_reason=stop`、transport attempt=1，形成 6 个受限 capture 和 6 个 terminal result；总 usage=`9106 input / 1021 output`，按冻结费率估算 `USD 0.00484938`。没有 retry、fallback、provider hopping、replacement pair 或业务 Run/Artifact。

Fact、Claim 的 Flash/Pro 四项均通过，Pro WWC 通过；Flash WWC 在本地 semantic validation 被 `s4_compiled_wwc_unbound_date_alias_forbidden` 拒绝。受限证据审计显示 Flash 只使用已绑定日期 alias，但在 `next_authority_event` / `next_reporting_event` cadence 下同时给出了日期 alias。模型可见 schema 允许 `review_date_alias` 为任一 allowed alias 或 `NONE`，却没有公开本地校验器的条件：只有 `bound_date` 可带日期 alias，其余 cadence 必须为 `NONE`。

因此该结果不是 Flash 指令不遵循，也不是 Pro 已胜出；WWC pair 是受项目合同不对称污染的无效测量。RC-P36-102 在 S2-T03 打开，T04 不得进入。按本 StagePlan 第 8 节，当前只做零调用处置，判断是否消费唯一合并 repair bundle，并是否另行签权一次仅 WWC family 的 Flash/Pro replacement pair；本轮不自动修补或重跑。

当前下一项：

`FIN-0.1.2-S2-T03-WWC-REVIEW-CADENCE-DATE-ALIAS-MODEL-VISIBLE-CONTRACT-PARITY-AND-AFFECTED-FAMILY-REPLACEMENT-PAIR-DISPOSITION-DECISION`
