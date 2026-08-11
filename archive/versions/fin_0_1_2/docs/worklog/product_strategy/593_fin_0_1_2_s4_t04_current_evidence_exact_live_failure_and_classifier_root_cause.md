# FIN 0.1.2 S4-T04 current Evidence exact-live 失败与 classifier 根因

时间：2026-08-04

## exact-live 结果

fresh admission 已消费且不可重用。三位 Specialist 全部完成，3 份 local Fact receipts 与 7 份 Provider interaction captures 已保存；Research Lead 输出在本地校验阶段以 `s4_case_numeric_authority_provider_narrative_invalid` 终止。总计 7 calls、38,724 input tokens、2,315 output tokens、USD 0.01885899、0 retry/fallback/replay，0 Artifacts。Terminal digest=`e6859a91…fd9`，execution-result SHA256=`32cb7e6e…8b43`。

## 根因

受限 capture 审计证明 Lead 没有输出财务数值，命中的只是 schema 允许的本地 Claim ID：`C001/C002/C005/C006`。当前 v2 classifier 用 Unicode `\b` 识别 request-local identifier；ID 后接中文括号时能完整识别，后接中文“有”时因两侧都被 Python 视为 word character 而没有边界，随后内部数字 `001/002/005/006` 被第二个正则误判为 material numeric。

因此这是项目内 CJK identifier classifier 假阳性，不是 DeepSeek 不遵循指令，不是 T03 检索失败，也没有形成真实财务数值越权。RC-P36-116 归 T04/shared Runtime classifier。

## 处置边界

本轮按 exact-once stop rule 没有修改 classifier、重用 admission、签发第二 admission 或重跑 live。T04 输入桥接 engineering pass 保留，但 T04 exact-live 与 current source-grounded NVDA R2 未通过，T05 不进入。

下一步应先做一次零调用结构修复：将 local identifier 改成 ASCII-aware 边界，覆盖 CJK 标点、直接 CJK 邻接、Latin/underscore 邻接和真实财务数值 mutation；通过后再单独决定是否签发一个 fresh replacement admission。
