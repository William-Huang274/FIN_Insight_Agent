# 875 — FIN 0.1.3 S3 small-judgment successor natural canary 失败审计

日期：2026-08-11

阶段：S3 targeted repair

结论：唯一 natural canary 已失败并停止；混合根因为项目合同欠编译与模型数字表面越权

## 真实运行

run=`fin013_s3_small_atom_b351adc5bb4bc396d39a` 已 exact-once 消费。DeepSeek Pro transport 正常、finish=`stop`，`2,400 input／565 output／2,965 total tokens／7,027 ms`，profile 估算约 `$0.0024005`，source／tool／retry／fallback=`0`。terminal 在本地 contract validation 以 `s3_small_atom_disposition_invalid` 失败；raw request／capture、parsed output、terminal 与 consumption receipt 全部保留，validated／projection／successor 文件均不存在，promotion=false。

## 业务上答对与答错了什么

模型正确保留“ISG 分部利润不能替代 AI server 产品利润”，正确保留 gross margin、cash conversion、audited product-profit bridge 三个缺口，盈利方向和 Evidence 语义也正确；缩小模型动作面后没有再出现 price-in 越权。这说明结构调整确实保住了核心研究判断。

但它把 `repair_partial` 和一段自由文本写进本地要求枚举的 disposition 字段；把四条 Evidence 同时列为 accepted 和 boundary；把四个 Numeric ref 全列入 used，而本地只允许 operating-margin-target ref；atom 还写回了被明确禁止的定性数字带。逐层零调用反事实必须修正 disposition、refs／numeric selection、numeric surface 三组问题才通过，因此不能视为一个拼写偏差。

## 为什么不全算 DS 的错

请求里虽然列了字段名，却没有把 observation／resolution 的合法枚举写给模型，也没有给四条 Evidence 一份互斥 role schema；`used_numeric_refs` 还会自然被理解为“所有实际用过的数字引用”。这些是项目合同欠编译。DS 对明确的 no-numeric-band 指令仍然违反，这部分是模型表面遵循失败。结论必须记为 mixed root cause，而不是“DS 完全不会分析”或“Harness 已经没问题”。

本轮按 authority 停止，不重试、不人工修绿、不生成报告。若继续，下一项只能先做 provider-neutral 的显式 enum／per-Evidence disposition／numeric-selection 合同处置和 immutable replay；之后再独立判断是否值得新的 replacement natural canary。
