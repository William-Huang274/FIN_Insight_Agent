# 869 — FIN 0.1.3 S3 DELL value/profit repair canary live failure audit

日期：2026-08-11

阶段：S3 动态研究与 targeted repair

结论：自然 canary failed；不重试、不进入完整报告

## 真实执行

唯一 admission 已 exact-once 消费。DeepSeek Pro `1 call／4,678 input／1,075 output／5,753 total tokens／13,249 ms／0 retry`，transport 与 JSON 均成功，完整 request／response 已先保存。formal terminal 在本地合同校验失败：`s3_repair_canary_model_numeric_surface_forbidden`；business promotion=false。

## 模型做对了什么

DS 正确返回了 `accepted_partial_resolution`，选择 `E021` 为 accepted Evidence、`E002／E008／E023` 为边界，完整保留 audited product-profit bridge／cash conversion／gross margin 三个 gap，并选择正确 NUM ref。说明模型可以做小范围的 Evidence 角色、盈利方向和残余边界判断。

## 真实失败，不只是首个字段

把首个错误展开后，至少有三类关键问题：

1. 模型在 atom 里重复了获批的定性数字带；同时三条 atom 写了 `E021` 等内部 alias。本地“任意数字”规则把 alias 数字也当金融数值，属于部分 severity false positive。
2. `value_and_profit_capture` 虽然返回 `supported_with_limits`，却把 `judgment_changed` 写成 false，与 accepted partial repair 自相矛盾。
3. `cross_chain_price_in_and_expectations` 被写成 `mixed`，从经营盈利证据越推到市场 price-in；没有估值／预期证据时应保持 `cannot_infer`。

另有质量 finding：模型把 `writer_admission_boundary` 当作要找一条业务证据的研究 cell，而不是本地写作控制面。项目侧还发现失败 terminal 错填了一个未写出的 `validated_output_ref`；但原始 output 完整保存在 capture，没有丢失。

零调用 counterfactual 依次去掉 atom 数字／alias、修正 target changed flag、恢复 price-in cannot-infer 后才通过。因此不能把本轮解释为“只差一个正则”或“DS 只少遵守一个字段”。

## 结构性处置

下一实现不逐字段补 DS prompt。模型动作面缩减为：Evidence disposition、盈利方向、产品／分部归因边界、residual-gap enums 和少量机制／边界 prose；本地确定性 Runtime 负责 affected cells、state、changed flag、Evidence／NUM／WWC refs、数字展示和 Writer admission projection。失败 capture 只用于设计与审计，不得 post-hoc 晋升。

完整 DELL 报告仍 blocked。任何 successor natural canary 都必须在结构修复、mutation、clean proof 和新的独立价值／权限决策后另行签发，不能复用本 admission。
