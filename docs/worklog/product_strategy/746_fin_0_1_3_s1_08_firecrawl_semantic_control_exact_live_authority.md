# FIN 0.1.3 S1-08：Firecrawl semantic control exact-live authority

日期：2026-08-08

## 签发结论

clean/pushed implementation commit=`12fe18decdbbfc1b745a9023fb0c0837776cf138`。runner、support module、24-query plan、scoring contract、zero-call proof、wire policy 和 projection 实现均以 SHA256 绑定，Project OS authority-issuance preflight=`pass / 0 blocker / 0 contract error`。

唯一 admission=`fin-ia-013-s1-08-firecrawl-semantic-control-r1-20260808`，只允许：

- Firecrawl keyless `semantic_open_web`；
- 24 个 proof-bound execution unit；
- 最多 24 provider/network；
- 每个 identity 最多一次网络尝试；
- 0 retry/model/document fetch/Evidence promotion/reranker；
- 不发送 Authorization/Cookie；
- safe request 和 raw response/failure 先原子保存；
- 24 个身份全部 terminal 后再加载 target source registry。

401/402/403 被视为系统性 Provider 拒绝，剩余身份显式终态化但不继续访问网络。本 authority 不包含 22 个 precise unit，也不允许 combined 46；成功只准入“同矩阵国内 Provider 对照”的后续决策，失败不自动签发 R2。
