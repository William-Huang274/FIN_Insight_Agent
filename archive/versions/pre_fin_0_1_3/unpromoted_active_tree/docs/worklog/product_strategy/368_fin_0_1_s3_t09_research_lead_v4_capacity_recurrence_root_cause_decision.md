# FIN 0.1 S3-T09 Research Lead-v4 capacity recurrence 零调用根因决策

时间：2026-07-23 22:27（Asia/Shanghai）

## 问题

output-v4 exact live 已完成九个 Specialist segments，但 Research Lead-v4 在 1800/1800 output tokens 发生 length stop。当前任务只允许读取受限回答、代码和合同并决定根因与修复方向，不允许实现、签发或再次调用模型。

## 独立审计

受限回答共 7,177 bytes，其中 24 个完整 typed scoped refs 占 4,030 bytes，即 56.15%；第 25 个 ref 在 `program_cell_id` 内被截断。相同 24 个引用若用三字符请求内 alias 承载仅需 120 bytes；使用本轮选择的四字符 alias，已生成前缀的反事实投影约为 3,291 bytes。该投影只证明结构放大，不冒充完整回答。

对照 Lead-v3 完整回答为 3,540 bytes、876 tokens、38 个 scalar refs，并正常 stop；Lead-v4 输入由 5,340 增至 6,738 tokens。当前回答在未完成时已经超过 6,000-byte Provider segment ceiling，因此单纯增加 token 只会把失败移动到 byte gate。

## 决策

最早项目内 owner 是 Provider wire 与 canonical authoritative identity 的表示混用，而不是 DeepSeek JSON、分析正文或证据体量。选择新的 Lead-v5：

- Provider 只从一次性闭合 alias table 中选择 `C001` / `W001`；本地在 parse 后扩展回 `CellScopedResearchRef`，再走现有 output-v4 validator 和 canonical persistence。
- alias 不是权威身份，也不作为 canonical identity 持久化；raw local ID、未知/错 kind/错字段/duplicate/normalize/fuzzy remap 全部 fail-closed。
- dependency/adjudication/gap 的机械 row ID 改为本地按已验证顺序生成；语义 statement、引用选择和冲突判断仍由模型负责。
- 每个引用列表唯一，最大值来自 exact scoped surface，而不是写死 NVDA 或 Cell 数量。
- 分离 raw wire、canonical alias segment 与本地 typed expansion 三种容量：raw 8,192 bytes、canonical alias 6,000 bytes、单字段 320 字、总 narrative 3,200 字；Lead 1,800 tokens、aggregate 16,800 tokens、USD 0.10 与 retry=0 均不增加。
- 本地 typed expansion 上限不得继续沿用未经 output-v4 证明的 8,192 常量；implementation 必须按 exact admitted surface 和最大合法 shape 计算并写入 versioned profile。

## 边界与下一项

本轮 model/provider/network/source/tool/admission/Run/Artifact/comparison/Human Review 均为 0。没有研究质量增益，RC-P36-040 仅完成 root-cause decision，RC-P36-046/037 与 S3-T09 继续 blocked。

确定性验证：新决策与历史 trace 合计 `31 passed`；release JSON、两本 Project OS JSONL、`git diff --check`、新增内容 secret scan 与 raw-capture boundary scan 全部通过。没有执行模型、网络、实验或 canonical 业务写入。

下一项为：

`S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-COMPACT-SCOPED-REFERENCE-WIRE-LOCAL-TYPED-EXPANSION-AND-DUAL-CAPACITY-ZERO-CALL-IMPLEMENTATION`

需单独授权；只能实现合同、profile/capability、fake Provider 和 deterministic capacity fixtures，不得签发 admission、真实调用、rerun、比较、review 或进入 T10/S4/release/production。
