# FIN 0.1.3 S1-08 Tencent WSA exact-copy AK/SK R3 terminal 与质量结论

日期：2026-08-08

状态：`authentication_and_service_pass / locator_research_quality_fail`

## 1. exact-live 结果

唯一 R3 authority 在 clean/synced commit `b9dfa0250d64ae962ec99b8dce434801da67da37` 上 exact-once 消费。请求体只有冻结的 DELL `Query`；全部 optional fields 省略。运行结果：

- provider/network=`1/1`
- retry/model/document/Evidence=`0/0/0/0`
- elapsed=`1036 ms`
- terminal=`tencent_wsa_exact_copy_r3_response_materialized`
- provider version=`lite`
- raw/unique locator=`10/10`
- provider date field=`10`
- RequestId present
- credential value persisted=`false`

因此本轮明确证明：这组 exact-text standard AK/SK 有效，TC3 签名成功，账号可以访问 WSA `SearchPro`，Query-only schema、capture 和 normalizer 均正常。R2 的 signature failure 不再是当前阻断。

## 2. 为什么仍不通过搜索质量

成功返回不等于研究可用。十条 locator 的实际内容为：

- `8` 条 Dell 官方域／公司域，但全部是驱动、BIOS、固件、SupportAssist 或普通支持导航；
- `2` 条第三方结果分别是装系统／MySQL 权限排障，与研究题无关；
- `0` 条回答 AI server demand、客户、供应链、earnings 或行业证据；
- `10` 个 date 只是 Provider 给出的页面日期，因页面本身无研究用途且日期语义未核验，`0` 个获得金融 publication-date authority。

这说明冻结 DELL query 在当前 `lite` 响应下语义／意图匹配失败。公司域命中率高不能替代研究相关性，更不能把 support 页面晋升为 Evidence。

## 3. 边界与处置

- credential/authentication path：`pass`
- WSA service availability：`pass`
- Query-only transport/schema：`pass`
- locator research quality：`fail`
- Tencent lite production provider：`false`
- three-case comparator：未执行、未自动授权
- SourceHunter integration／Evidence promotion／S1-08／S3／release：均 `false`

R3 不重跑，也不自动改 query、切中文、换 service API Key 或升级套餐。单次结果不能证明腾讯所有 tier 都差，但已经足够否定“把当前 lite 结果直接接入产品”的路径。若未来要测高阶 tier、query rewriting 或 Bearer service API Key，必须先做新的 provider/cost/acceptance 决策，不能把它当 fallback。

本轮 AK/SK 已在聊天明文出现；测试完成后必须在腾讯云控制台删除或轮换。
