# 651 — FIN 0.1.3 S3-05 八维质量门与 formal Anchor readiness

日期：2026-08-06

## 结论

S3-05 的 deterministic 质量门已工程通过；同时完成了一次正式链路入口审计和零调用全链修复。当前可以在 clean/synced commit 后签发一次九节点 DeepSeek Pro fresh admission，但尚未签发、未调用模型，也没有三案正式分数或人工内容接受。

## 本轮修复

- 将八维 Rubric 编译为逐案 `ScorePacket`：总分至少 24/32，Q1–Q7 不低于 2，Q1/Q2/Q3/Q8 不低于 3，至少四维不低于 3。
- L1/L2 在 L3 评分前独立阻断；DELL 季度/年度 duration 错误不能被内容分数补偿。
- 每一维评分理由必须引用对应 Claim、section、Evidence、Numeric 或 WWC；Q3 必须引用 Numeric，Q7 必须引用 WWC。
- paired assessment 要求同 evidence/input head、不同 Run/Artifact、Agent 达绝对门槛且至少三维 reviewer-confirmed material gain。
- qualified-human content acceptance 与 workflow/identity acceptance 分离；Codex、自动化和 LLM judge 均不能代签。
- 当前三份 S3-04 fixture-mixed 预览全部在评分前拒绝，正式评分与 pass 均为 0。

## 入口审计发现与处置

入口审计发现，S3-02/03/04 validator 仍把 `4/9 natural + 5 fixture` 和 `0 all-natural` 写成固定预期；仓库也没有 FIN 0.1.3 的九节点正式 runner。因此直接签 admission 即使得到 9/9 自然输出，后半链也会拒绝 successor。这是项目代码问题，不是 DeepSeek 问题。

现已：

- 让 Claim、Lead、Workpaper 和 quality entry 根据实际 authority/count 校验，同时保持历史 fixture 记录有效；
- 新增九 request、capture-first、shared-ledger exact-once runner；
- 预算冻结为 9 Provider calls、每 request 1 次、0 retry、0 fallback；
- full-fake 成功路径形成 `9 Claim / 3 all-natural Lead / 3 all-natural Workpaper / 3 quality entry`；
- fault injection 在第 4 call 失败时只保存 4 份 capture，并跳过后 5 项；同一 admission 二次消费 fail closed；
- 新文件统一进入 `repair_closeout` 命名空间，没有修改 S0 历史资产基线来迁就新增文件。

## 验证

- S3-05 focused：8 passed。
- formal Anchor runtime/successor focused：6 passed。
- current canonical successor：240 passed / 1 historical assertion deselected。
- compact input：9 request，共 24,289 字符，单项最大 4,169 字符。
- model/provider/network/source/business run：0/0/0/0/0。

## 下一步与边界

下一步必须先提交并推送当前 clean implementation，再签发一次 fresh admission 并 exact-once 执行。真实成功后仍需本地完成 L1/L2、final verifier-bound delivery、逐案八维评分、paired assessment 和 qualified-human content acceptance；任何一步不能由本轮 full-fake 或测试数量替代。
