# 763 — FIN 0.1.3 S1-08 external combined recovery authority

日期：2026-08-09
状态：`one recovery exact-live authorized / admission not issued`

## 决策

基于 clean/synced implementation commit `3aa510d386c8a2e9bebe576cfa0f6986025cc9de`、clean-proof record commit `e610a24ab0b17fab63c4eb085f356986b6798410`、双 archive／双 fresh process 复证和当前 Project OS preflight，批准唯一一次 recovery combined exact-live。

继续执行有明确价值：official lane 的受控 DNS 握手修复必须真实越过 HTTP 边界才能关闭；Firecrawl 若仍处于 credit exhaustion，新 Runtime 在首个 `429 reason=credits` 后停止，不再浪费另外 23 次调用。若额度已恢复，则 case-slot 公平顺序优先覆盖三案与 customer／supply。

## 硬边界

- admission／execution=`1/1`；
- official／Firecrawl／total network ceiling=`48/24/72`；
- retry／fallback／automatic replacement=`0/0/false`；
- model／embedding／rerank／Evidence promotion=`0/0/0/0`；
- Firecrawl 仍只提供 locator candidate；
- official local date、relationship authority、capture-first 和 typed gap 不放宽；
- 不授权 internal exact／BM25／dense／graph，不授权 qrels、BGE／fusion／rerank 或下游研究链。

authority 在提交后才可由 runner 校验并签发 admission。运行成功也只进入外源 closeout assessment，不能直接声称 S1-08 或产品研究质量通过。

authority digest：`89953376a9c3466bea3ced16b791318b3fc620d19b08de0418fbfc49213674ab`。
