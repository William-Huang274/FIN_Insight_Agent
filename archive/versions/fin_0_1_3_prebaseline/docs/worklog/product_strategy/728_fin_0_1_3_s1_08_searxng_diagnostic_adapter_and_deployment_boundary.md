# 728 — FIN 0.1.3 S1-08 SearXNG 诊断 adapter、部署失败证据与 fan-out 边界修复

日期：2026-08-08

阶段：`013-S1-08`

结论：adapter 的首个 clean-source 零调用证明通过；本地部署先后暴露 Windows launcher 兼容缺陷和“搜索式健康检查”越界，均留痕并在正式案例查询前停止。修复后的容器可健康启动，但尚未执行 DELL/MU/NVDA 正式诊断 baseline。

## 本轮完成

- 新增独立 `SearXNGDiagnosticAdapter`，只输出 locator、标题、摘要候选、日期候选、引擎和排名候选。
- 请求先保存，响应再保存，之后才解析；403、429、超长响应、坏 JSON、schema 漂移、跨 origin 和 transport 失败均保留 typed terminal。
- canonical URL 去重会去掉 tracking 与敏感 query 参数，同时合并而不抹掉 engine lineage。
- `evidence_promotion_allowed=false`、`writer_citable=false`、`financial_fact_authority=false`、`numeric_authority=none` 在 policy、locator 和 result 三层固定；mutation 无法把 locator 晋升成 Evidence。
- clean commit `8a2c8fa6` 的首个独立零调用 proof：`14 passed`，DELL/MU/NVDA 三案 full-fake 均完成，`9 captures / 0 network / 0 model / 0 evidence promotion`。
- 官方 SearXNG 镜像固定到 `2026.7.28-c01178d03` 的 Linux/amd64 digest；服务只绑定 `127.0.0.1:8888`，JSON output 显式开启。

## 失败尝试与根因

1. 本地部署 A1 在生成临时 secret 时失败。原因不是 SearXNG，而是 Windows PowerShell 所用 .NET 没有静态 `RandomNumberGenerator.Fill` 和新式 `Convert.ToHexString`。launcher 已换成兼容的实例 RNG 和 `BitConverter`。
2. 部署 A2 虽启动成功，但 healthcheck 使用 `/search?q=health`。这会周期性扇出到上游搜索引擎，至少观察到 6 次无业务 health 搜索；默认 engine loading 还触发一次 Wikidata 初始化访问。服务已在正式案例查询前停止，A2 不算 baseline。
3. A2 同时观察到 DuckDuckGo CAPTCHA、Brave 429、Startpage CAPTCHA 与 Wikidata 403。这是“自托管聚合器不等于自有搜索索引”的直接证据，不能把 SearXNG 宣称为稳定生产 Provider。

## 结构修复

- healthcheck 改为只访问本地首页，禁止调用 `/search`。
- `use_default_settings.engines.keep_only` 固定为 Bing、Brave、DuckDuckGo、Google，避免默认引擎集合和启动期 Wikidata访问漂移。
- 预算术语拆开：FIN 可以精确控制“adapter→SearXNG query calls”，但 SearXNG 内部对多个引擎的 HTTP fan-out 不是 FIN adapter 能逐请求 exact-once 的表面。本轮固定最多 4 个配置引擎，并要求输出 unresponsive engine lineage。
- 新增部署安全测试，防止搜索式 healthcheck、开放端口、引擎集合漂移和 Windows-only launcher API 回归。

## 产品边界与反思

这轮最重要的反思不是“再加一个兜底”，而是 healthcheck 也可能成为隐藏的业务调用。今后任何 metasearch、crawler 或 tool server 都必须分别核算控制面探活、FIN 到 Provider 的调用、Provider 内部 fan-out，不能把三者都叫作“一次网络调用”。

当前只建立了诊断 plumbing 和本机可部署性；搜索召回、来源质量、Evidence 质量、稳定性和生产 SLA 都没有通过。下一步先在修复后的 clean commit 重做 v1.1 零调用 proof；通过后才可签发最多 3 个 FIN query、0 retry 的自托管 diagnostic baseline。未来用户提供付费 API 后，必须沿同一 locator contract 单独建 provider profile 和对照实验，不能直接替换成生产能力。
