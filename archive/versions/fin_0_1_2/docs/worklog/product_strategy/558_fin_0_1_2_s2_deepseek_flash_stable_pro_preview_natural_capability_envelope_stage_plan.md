# FIN 0.1.2 S2 DeepSeek Flash stable / Pro preview 自然能力边界 StagePlan

日期：2026-08-02
状态：`S2-T01 pass / S2-T02 zero-call implementation next / model call not authorized`

## 本轮结论

FIN 0.1.2 的 S0、S1 结论保持不变。S2 不直接跑 full-chain，而是先用一个有界配对实验决定两件事：DeepSeek V4 Flash stable 与 Pro preview 哪一个可以进入 S3；Fact、Claim、WWC 三个改变过合同的 family 中，模型到底还能拥有哪些判断表面。

模型只允许选择 request-local alias、closed enum 和 bounded judgment atom。本地程序继续拥有 material number、日期、案例 identity、ID、ordering、lineage、最终 rendering 和 L1。旧 exact-live 已证明，把这些表面交给模型会产生数值叙事、未绑定日期、候选容量和跨字段语义等混合失败，不能再靠逐字段 live 修复。

## 历史证据如何进入新计划

- 旧 Pro canary 的 Fact 通过，可作为小候选池判断原子的正证据；
- Claim 首错是项目没有把条件语义放进模型可见合同，不能记成模型能力失败；
- WWC 六候选在本地 top-3 选择前被错误拒绝，是 candidate 与 selected capacity 漂移；
- Fact 曾面对 22 个合法 alias 并全部返回，说明候选池必须在 Provider 前本地限界；
- 数值和自然日期继续属于本地 truth owner；
- strict-schema transport 仍停放为非阻断交接项，当前 DeepSeek 主线仍是 JSON-object 加本地语义校验。

## 固定任务与预算

S2 只设四项任务：T01 StagePlan；T02 双模型 route、current source/binding 和 paired-canary compiler 的一次零调用实现；T03 MU 单 Cell 的 Fact/Claim/WWC × Flash/Pro 六次独立调用；T04 盲评、surface disposition 和 closeout。不存在自动 T05。

主要 live 预算为 6 calls、50k input tokens、8.4k output tokens、USD 0.06、900 秒；retry、fallback、provider hopping、prompt-only retry 和业务 Run/Artifact 都为 0。只有项目自己的比较器、模型可见合同、capture 或 local assembly 缺陷使比较失效时，才可在一次合并零调用修复后另行授权受影响 family 的 Flash/Pro replacement pair，最多 2 calls。模型不遵循或质量弱不是重跑理由。

family 彼此隔离，所以单个语义失败不会阻止剩余独立调用；鉴权、transport、安全或 capture 失败才停止剩余调用。这样一轮即可收集三个 family 的能力边界，避免再次进入 one-by-one live repair。

## 新发现与归属

审计发现 `common_runtime_contract_family_source_v1_0` 的状态文字仍称尚未迁移，但 S1 binding 与十 consumer 证明已经确认迁移；同时 `bounded_agent_executor` 的 admission 校验硬编码 `deepseek-v4-pro`，无法在同一 current contract 下公平表达 Flash/Pro 配对 canary。

已登记 `RC-P36-098`。它不推翻 S1，但在 T02 新建 versioned current source/binding、model-candidate registry、参数化 canary route 并完成 fake/mutation/capture 验证前，阻断一切 S2 模型调用。旧 source 和历史 Pro admissions 不改写。

## 产品边界

本轮没有新增终端用户功能，也没有读取 credential、调用模型/Provider/网络，或创建业务 Run/Artifact。S2 目前只完成了比较设计与工程边界冻结，不代表 Flash 或 Pro 已通过，不代表三案例产品链、九件套、R2/R3、owner acceptance 或 release readiness。

## 下一项

`FIN-0.1.2-S2-T02-DUAL-MODEL-ROUTE-CURRENT-CONTRACT-SOURCE-AND-PAIRED-CANARY-COMPILER-ZERO-CALL-IMPLEMENTATION`
