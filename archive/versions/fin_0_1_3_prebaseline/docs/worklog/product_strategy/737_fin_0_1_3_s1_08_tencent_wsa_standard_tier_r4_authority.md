# FIN 0.1.3 S1-08 Tencent WSA standard-tier R4 authority

日期：2026-08-08

状态：`zero_call_contract_pass / authority_issued_unconsumed`

## 决策与实验控制

Owner 声明已将元宝搜索从 lite 切换到 standard，并批准再试一次。R4 不改查询来制造表面改善，而是固定：

- 与 R3 相同的 AK/SK authentication path；
- 与 R3 字节一致的 DELL Query-only request；
- 相同 endpoint、SDK、normalizer、result ceiling 和 0 retry；
- 唯一预期变化为 Provider subscription `lite -> standard`。

R4 attempt=`fin013-s1-08-tencent-wsa-standard-tier-r4`，绑定 immutable R3 result 与 quality assessment。预算为 `1 provider/network / 0 retry/model/document/Evidence`，文档标准版单次成本为 `0.046 CNY`。凭据仅 hidden input，值不进入 Git、authority、capture 或 terminal。

## 零调用证明

- focused/related tests：`37 passed`
- compile：`pass`
- Project OS scoped preflight：`pass`
- same-query mutation：通过
- optional wire field mutation：fail closed
- provider/network/model/document/Evidence：`0/0/0/0/0`
- credential persisted：`false`

## 后续边界

提交推送 clean authority 后只消费一次 R4。评估必须同时报告 observed Provider Version、`useful@10`、target-in-pool、日期语义、来源多样性、成本和延迟；禁止用 reranker 或正文抓取补救候选召回。

若 standard 仍失败，只允许进入 Owner 指定的 DELL/MU/NVDA 中英 query × Evidence Slot comparator 零调用设计和证明；该 contingency 不自动授权 comparator live 或 SourceHunter integration。即使单条 R4 成功，也只证明同一 DELL query 的 tier delta，不等于三案例生产接入通过。
