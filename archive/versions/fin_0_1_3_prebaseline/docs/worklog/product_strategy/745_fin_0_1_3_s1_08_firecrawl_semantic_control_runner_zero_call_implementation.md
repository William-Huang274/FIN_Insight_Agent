# FIN 0.1.3 S1-08：Firecrawl 关系感知语义控制组 runner 零调用实现

日期：2026-08-08

## 已完成

1. 从 canonical SearchIntent 和 ProviderWireProjection 机械生成 24 个 Firecrawl semantic execution unit，覆盖 DELL/MU/NVDA、customer/supply、关联 evidence owner 和中英查询；没有手填 Gold URL。
2. 固定 request body 为 `query + limit=10 + sources=[web]`，不发送 Authorization/Cookie，不触发 scrape。
3. runner 要求 clean worktree、唯一 runtime root、唯一 result、Project OS scope pass 和 authority 文件／实现 commit／source SHA 绑定。
4. 每次调用先保存 safe request；收到响应后先原子保存 raw bytes，再解析；HTTP/transport/parse 失败同样形成 typed terminal。401/402/403 作为系统性拒绝，剩余计划身份显式终态化而不继续浪费调用。
5. evaluator 先验证 24 个身份全部 terminal，再加载 target source registry；统计 topical useful@10、六个 case-slot target-in-pool、matched-target 日期、来源域多样性、credits、现金支出和 p50/p95。
6. 控制组即使全门通过，`sourcehunter_integration_eligible=false`、`domestic_provider_capability_established=false`，避免把控制实验冒充产品能力。

## 零调用和回放证明

- plan=`24 intent / 24 execution unit / 3 cases / 2 slots / 2 languages`；
- plan digest=`3d636459894758b12986bab383e287d50888ca4f61b4f57ee2566e76126d9e19`；
- 旧 A4 terminal/assessment SHA 重新核对为 `0f3339...a9bcc` / `cc6475...7c24f`，旧结果保持不可变；
- full-fake 证明可在每个 case-slot 找到冻结目标、日期与多样性门全过，但仍不准入 SourceHunter；
- Gold/URL 注入、重复 locator、缺失单一 case-slot target、Gold 加载顺序均有 mutation；
- focused tests=`8 passed`，network/provider/model/document/Evidence=`0/0/0/0/0`。

## 下一步

只能从干净 implementation commit 单独签发 `S1_08_FIRECRAWL_RELATIONSHIP_AWARE_SEMANTIC_CONTROL_EXACT_LIVE_AUTHORITY_ISSUANCE`。签发后执行唯一一次 24-query control；失败保留 terminal，不补跑，不扩展到 precise lane 或其他 Provider。
