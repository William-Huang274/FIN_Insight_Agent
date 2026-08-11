# 665 — FIN 0.1.3 S2-05 Experiment A 动态节点 Runner 零调用实现

日期：2026-08-07
类型：`runtime implementation / experiment governance / research-quality boundary`
状态：`zero_call engineering pass / fresh admission authority pending`

## 1. 本轮完成了什么

S2-05 不再复用旧三调用 canary 或九次 compact Anchor。仓库已新增 Experiment A 专用：

1. runtime policy，冻结 DeepSeek Pro、单案 10–12 calls、campaign 最大 36、retry/fallback=0、per-node token、成本与 timeout envelope；
2. case-scoped dynamic runner：Lead 先规划 6–8 个研究单元，随后动态展开 Specialist，再执行 synthesis、Writer、Verifier；
3. production entrypoint，默认只做零调用 preflight；没有独立 admission 文件时不能执行模型；
4. 一案一个 shared exact-once admission、capture-first、typed terminal 与首错停止；
5. raw model-only、supervisor correction、corrected candidate、evaluator-only 四轨隔离。

## 2. 研究质量上额外修正的地方

首轮测试虽然通过，但复审发现“引用合法”仍可能只引用少量冻结证据，形成形式正确、内容空洞的报告。该问题没有后传，而是在 S2-05 本阶段修正为：

- Lead 六个 mandatory family 必须全部覆盖；
- 33 条 case-local evidence 与显式 gaps 必须被研究单元完整分配；
- 每个 Specialist 必须处置其全部 assigned evidence/gaps；
- synthesis 必须保留全部显式 gaps；
- Writer 六个正式 section 的引用并集必须覆盖完整 case pack；
- 数值叙事只允许出现冻结 case input 已有的数字表面；跨案 ID、错误日期、未知数字、漏证据和未绑定章节均 fail closed。

这仍不是“研报质量已经通过”。结构门禁只能防明显的身份、证据、数字和遗漏错误，不能判断经济机制是否深刻、反方是否有力、文字是否真正有投资价值。那些能力必须由真实 DeepSeek raw run、hidden rubric 和后续 supervisor/corrected 对照证明。

## 3. 留存与失败语义

每次 Provider 返回后，runner 在解析或校验前先原样保存：

- 完整模型可见 messages 与调用参数；
- 完整 gateway result、assistant content、finish reason、usage 和 raw response；
- capture digest/ref、节点身份和调用序号。

`api_key_env` 与凭据正文不进入 capture。任何 transport、invalid JSON、schema、cross-case、numeric、coverage 或 Verifier material failure 均停止当前案例；campaign 不会自动启动下一案。原始结果只进入 `raw_model_only`，不会自动晋升业务 Artifact，也不会写 correction、corrected 或 evaluator track。

## 4. 零调用证据

- focused runtime + authority：`34 passed`；
- 当前全部 FIN 0.1.3 S2 命名合同：`95 passed`；
- DELL/MU/NVDA 完整 full-fake：`30 calls`；
- 8-unit 上界：单案 `12 calls`；
- 5/9 units、跨案 evidence、错误 as-of、漏 Evidence/Gap、Provider timeout、invalid JSON、token/cost 超限、未授权数字、Writer 漏引用和 Verifier material failure 均已 mutation fail closed；
- compileall、`git diff --check` 通过；
- admission/model/Provider/network/MCP/business promotion=`0/0/0/0/0/0`。

机器结果：`configs/releases/fin_ia_0_1_3_s2_05_experiment_a_dynamic_node_runner_zero_call_implementation_v1_0.json`。

## 5. 当前边界与下一步

S2-05 的 deterministic engineering blocker 已清除，但 Experiment A 的 DeepSeek 分析能力仍未测试，不能把 full-fake 当成产品能力。

下一项限定为：

`FIN-0.1.3-013-S2-05-EXPERIMENT-A-FRESH-ADMISSION-AUTHORITY-DECISION`

下一轮先只读核对干净提交、runner/policy/input digest、凭据 presence、真实成本与一次性执行边界。通过后才可按 DELL→MU→NVDA 分案签发；每案成功才允许进入下一案，任何 material failure 停止并返回，不自动补丁或重跑。S2-06 的 supervisor correction、hidden evaluator 与 corrected comparison 仍不属于当前 raw runner。
