# 871 — FIN 0.1.3 S3 small-judgment clean proof 与 successor canary 决策

日期：2026-08-11

阶段：S3 targeted repair

结论：结构 clean proof 通过；值得再做一次独立 successor natural canary，但 execution 仍须分离

## clean proof

commit `9eadecd6...f73d` 被分别导出为两个全新 Git archive，并在凭据清空、socket 封锁的 fresh Python 进程中运行。两边注入相同 digest 的 corrected／historical DELL Pack 与本次失败 capture；worker 输出逐字节一致。proof=`b891e4d4...e9bf1`，model／provider／network／source／retry=`0/0/0/0/0`。

两边都证明：旧自然输出仍因原合同失败且不可晋升；它的 Evidence 与 NUM 选择正确，但 target changed flag 与 price-in 边界错误。新结构把四个 cell 稳定投影为 `supported_with_limits/true`、`cannot_infer/false`、`supported_with_limits/true`、`supported_with_limits/true`。alias 变成中性引用短语，金融数字 mutation 继续 fail closed。失败 replay 会写 parsed 文件并令 validated ref=null，raw capture 不丢。

## 是否值得再调用一次 DS

值得，理由不是“再赌一次”，而是输入合同已经发生结构性变化：前次失败的内部 cell 状态面已删除，零调用不能证明自然模型是否会遵循新动作面。一次 `8,854` 字符、最多 `1,200 output tokens／USD 0.02` 的 Pro canary 能提供这一条新信息。

但必须明确它的含义：输出合同内含 bounded expected Evidence semantics，所以这主要是 action-surface adherence 与 atom quality canary，不是开放式金融推理泛化测试。通过也只允许进入修复后的 DELL fixed-pack 报告；失败则停止，不重试、不再逐字段扩 Prompt、不进入报告。

下一步只实现新 live scope、fresh exact-once admission 与 capture-first runner；签发 admission 不等于 execution。提交推送后须再次 clean preflight，再独立签 execution authority。
