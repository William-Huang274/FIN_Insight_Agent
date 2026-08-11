# FIN 0.1 S3-T09 Specialist-v7 live validation R1

执行日期：2026-07-23（Asia/Shanghai）

结论：未通过研究产品验收。Specialist-v7 第一 Cell 的三个 Provider segments 都正常 `stop`，并通过 profile/capability 驱动的内层 8192-byte 校验；随后 outer executor 仍按历史 v5/v6 版本集合选择限制，把 v7 回落到旧 6000-byte 上限并抛出裸 `ValueError`。这是项目代码残留，不是本次 DeepSeek JSON 或 Fact authority 失败。

## 精确执行事实

- Admission digest：`9657d30751eea5f24ea26b73fa9d93909b2df0c9966f96539a405a9dde1e72a6`
- WorkUnit：`wu_p02_5_10ff261f10fe7a6c7cecfc7a`
- Attempt：`attempt_fin01_1119ac82535a73593f0e0c03`
- ResearchRun：`research_run_fin01_ebf0f6376cec28087151562e`
- Provider / model：DeepSeek / `deepseek-v4-pro`
- Gateway 事实：3 model / 3 provider / 3 network calls
- token：10,375 input + 1,826 output = 12,201 total
- latency：29,566 ms aggregate
- 成本：精确值不可重建；USD `0.00162623..0.00610174`
- retry / fallback / rerun：`0 / 0 / 0`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：0；orphan=false
- restricted capture / readback：`0 / 0`

## v7 的真实效果

第一 Cell 的 facts、claim cards 和 WWC 三段均完成，inner v7 validator 使用显式 research profile 的 8192-byte bounded assembly 上限并通过。上一轮 Graph context 被当作 Fact authority 的失败没有在第一 Cell 复现。

这只构成 RC-P36-044 的局部 live 证据。Value/Profit、Lead-v3、Writer-v2、Verifier 和九 Artifact 产品路径均未到达。

## 首个可信失败

outer executor 在 node 已返回 validated envelope 后再次校验 Specialist output。该分支只把 v5/v6 识别为 8192-byte bounded assembly，v7 未被纳入，于是使用 legacy 6000-byte 上限。由“内层 8192 通过、外层 6000 失败”可确定第一 Cell 序列化大小位于 6001..8192 bytes；由于原文未持久化，不能重建精确字节数。

这说明 v7 的 capability/profile 收敛还没有覆盖所有 consumer，仍留有一个累计版本集合。下一步应先做零调用根因决策，把 outer revalidation 改为消费同一 capability/profile，而不是再增加 `v7` 特判。

## 遥测与复盘缺口

runner result 报告 0 calls / 0 tokens，但 gateway events 记录三次 started/finished 和 12,201 tokens。outer 裸 `ValueError` 绕过 `BoundedAgentExecutionError` 的 usage/capture 传播，因此三份 final assistant text、usage receipts 与精确 cache split 均未进入持久化链路。

三份原文不可恢复，本记录不猜测其内容。下一步的零调用决策还必须覆盖 post-node failure 的 capture-before-terminal 与 typed error propagation，防止再次出现“终态可信、过程证据丢失”。

## 审计边界

本轮 post-run 只使用 direct SQLite `mode=ro`、文件摘要与 gateway event 读取，没有实例化 target service。执行后 canonical counts 为 `14/14/14/13`，database SHA-256 为 `d0a78d6a...11b9`，object tree 保持 `b11b26b3...6bdc7`；审计本身没有新增业务对象或 Artifact。

下一项：
`S3-T09-OWNER-GRADE-SPECIALIST-V7-OUTER-ASSEMBLY-CAPABILITY-AND-CAPTURE-ZERO-CALL-ROOT-CAUSE-DECISION`。
本轮不授权修复、replacement admission、模型重跑、comparison、owner review、T10、S4、release 或 production。
