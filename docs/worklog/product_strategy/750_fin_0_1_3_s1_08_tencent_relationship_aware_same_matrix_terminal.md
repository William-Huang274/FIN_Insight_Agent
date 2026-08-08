# 750 — FIN 0.1.3 S1-08 Tencent relationship-aware same-matrix terminal

日期：2026-08-08

## Exact-live 终态

唯一 admission `fin-ia-013-s1-08-tencent-semantic-same-matrix-r1-20260808` 已在 clean `4545f453d5f4c0f46b51e3befe77ac723f198992` exact-once 消费：24/24 查询成功、24/24 `Version=standard`、0 retry/model/document/Evidence、whole-run=`31,945 ms`、p50/p95/max=`873/1,330/9,184 ms`，文档计价=`1.104 CNY`。

74 份 runtime capture 已保留；72 个结果引用 SHA 全部匹配，result/assessment digest 与相互绑定通过。环境中的实际 AK/SK 未出现在 capture、result 或 assessment，通用 Key pattern 扫描也通过。

## 研究质量结果

- 返回 172 个 locator occurrence、126 个全局唯一 URL，172/172 带 Provider date；
- topical useful=`103/240`，低于同矩阵 Firecrawl 的 `133/240`；
- 六个 case-slot 的冻结一手来源命中=`0/6`，Firecrawl 为 `5/6`；
- exact target 为 0，因此 Provider date 虽有值，发布日期准确性没有任何可验证观察；
- 只有 4 个 occurrence 位于 Dell/Microsoft/TSMC 等官方域，内容是 Azure Search 产品页、Dell support 页和 TSMC CoWoS 技术页等，不是被冻结的一手财报/业绩会目标；
- 腾讯结果的主要 hostname 为 `so.html5.qq.com`、GitHub、Sina、`new.qq.com`、Toutiao，说明快速且多样，但当前标准搜索对严格金融一手来源 precision 不足。

hard gate 终态=`fail_diagnostic_only`。腾讯仍是 diagnostic provider，不接 SourceHunter，不允许 reranker/document fetch 把 0/6 “救成通过”，也不追加 query patch 或 replacement attempt。

## 下一项

只允许零调用执行 `S1_08_POST_TENCENT_SAME_MATRIX_PROVIDER_PORTFOLIO_AND_PRODUCTION_SEARCH_BOUNDARY_DECISION`：决定 production SourceHunter 应采用“官方 precise adapter + broad semantic locator”的组合，还是继续审查另一家国内 raw-search Provider。该决定前 S1-08、ranking、S3 和 release 继续 blocked。
