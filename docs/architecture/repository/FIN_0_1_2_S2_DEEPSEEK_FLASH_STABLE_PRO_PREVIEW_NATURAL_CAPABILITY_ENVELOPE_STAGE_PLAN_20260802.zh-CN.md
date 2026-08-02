# FIN 0.1.2 S2：DeepSeek Flash stable / Pro preview 自然能力边界 StagePlan

日期：2026-08-02

状态：`S2 StagePlan pass / T02 zero-call implementation next / model call not authorized`

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
| S2-T02 | 双模型 route、当前合同 source/binding、paired-canary compiler 的一次零调用实现 | 0 | DELL/MU/NVDA fake、mutation、capture、请求等价性和精确六调用计划全绿 |
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

## 10. 当前下一项

`FIN-0.1.2-S2-T02-DUAL-MODEL-ROUTE-CURRENT-CONTRACT-SOURCE-AND-PAIRED-CANARY-COMPILER-ZERO-CALL-IMPLEMENTATION`

本 StagePlan 没有读取 credential、调用模型或 Provider，也没有执行网络、业务 Run 或 Artifact 写入。
