# 648 — FIN 0.1.3 S3-02 公司专属 Claim 与可观测 WWC

日期：2026-08-06

## 结果

`013-S3-02` 达到 `engineering_pass`。旧 0.1.2 产品页中的“证据方向支持当前单元判断”“详见本地绑定事实”和 9/9 重复 WWC 已定位为旧通用 renderer surface；本轮不修改历史产物，也不继续向这种 renderer 打字段补丁。

当前 S2 九个代表性 Claim 已统一编译为公司专属 Claim Card：每张包含本案公司、研究问题、公司专属机制、证据边界、精确 Numeric 或 typed gap、选择权威和 lineage。共绑定 12 个 exact Numeric、2 个 typed gap；13 条已选择 What-Would-Change 均具备指标/事件、方向、时间窗、阈值和下一证据路线。

## 真实性边界

九张 Claim Card 中只有四张拥有既有 DeepSeek exact-once natural choice：DELL demand、MU value/profit、NVDA counterevidence、NVDA demand。其余五张保留 `fixture_choice_engineering_only`，不得作为业务真值或产品结论。S3-01 新增的 29 个动态 Cell 没有 Provider choice，全部保留 `planned_no_claim_choice`，没有为了填满报告伪造 Claim。

S3-02 未改变模型可见 alias/enum 合同，只改变本地 Claim/WWC 组装和验证，因此不重复做 paid canary。剩余自然选择应在 S3-03–S3-05 确定性门禁通过后，由唯一一次正式 full-chain 获取。

## 验证与边界

Focused=`7 passed`；current successor=`214 passed / 1 historical assertion deselected`。cross-case Numeric、通用 Claim、缺失 WWC 阈值、fixture 冒充 natural 等 mutation 均 fail closed；model/provider/network/source/business run=0。

本轮不宣称九张 Claim 都是真实模型判断，不宣称 29 个新增 Cell 已完成研究，也不宣称 Lead/Writer/Verifier、八维内容质量、产品验收或 release。下一项为 `013-S3-03` 跨 Cell dependency/conflict/gap synthesis。
