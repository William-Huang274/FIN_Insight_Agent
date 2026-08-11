# FIN 0.1.3 S1-08 SearXNG 有界基线结果与付费 API 交接

日期：2026-08-08

阶段：`013-S1-08`

归属问题：`RC-P36-157-fin-0-1-3-s1-08-operational-provider-and-candidate-coverage-insufficient`

## 1. 本轮做了什么

Owner 要求先重塑后续计划，再自建 SearXNG adapter 作为低成本、多搜索引擎的开源诊断路线；它不得立即计入生产能力。执行顺序实际完成为：

1. 冻结 diagnostic-only 产品边界与 no-promotion 合同；
2. 实现 loopback-only、capture-first、fixed-origin JSON adapter、canonical locator dedupe、engine lineage 与 typed failure；
3. 建立本地容器部署，保留并修复 Windows RNG 与 search-healthcheck 非业务 fan-out 两个失败；
4. clean proof v1.1 完成 `15 passed`、三案 full-fake、9 captures、0 network/model/promotion；
5. 签发并只消费一次三案有界 baseline authority；
6. 独立评价 locator 质量、engine participation、日期与生产资格。

SearXNG 官方定位是 metasearch；本实现没有把它当作 FIN 自有 Web index。参考：[SearXNG 文档](https://docs.searxng.org/)、[Search API](https://docs.searxng.org/dev/search_api.html)、[settings](https://docs.searxng.org/admin/settings/settings.html)。

## 2. 正式结果

| 项目 | 结果 |
| --- | --- |
| source commit | `a5014c75e3ce9920cd83239d689aa262e04ee654` |
| case/query | `DELL/MU/NVDA = 1/1/1` |
| FIN→SearXNG / adapter network | `3 / 3` |
| raw / normalized unique locator | `30 / 30` |
| capture | `9` |
| model / retry / document fetch / Evidence promotion | `0 / 0 / 0 / 0` |
| engine contribution | `DuckDuckGo=30`；其余为 0 |
| published date | `0/30` |
| result SHA-256 | `cc42278862241ee65eabbf121bbc387d8837c8464ba32ad45023e26efcf912bf` |
| result digest | `3b1394c991b936a34fbd9c79db4ce94b92d3ae2f2816b3717e6b7bda9410e6aa` |

DELL 前十有 1 条 issuer official、2 条 Reuters；MU 有 2 条 issuer official；NVDA 前十没有 issuer official 或 Reuters。所有条目都只是 locator candidate，title/snippet/score/数字都没有金融事实权威。

## 3. 为什么“跑完”仍然质量失败

这是两个层面的组合，不是单一“开源不好用”。

项目内 query compiler 缺口：

- 请求 `general/news`，但实例只暴露 `general/web`；
- 给所有 engine 强制 `time_range=year`，而 Bing 声明不支持该过滤；
- policy 声明 Google，但镜像默认 Google inactive；
- 调用前没有把实例实际 capability 编译成 provider-specific query。

免费上游的运营边界：

- Brave 三案都因 too-many-requests／429 unresponsive；
- 只有 DuckDuckGo 返回 locator，无法形成真正的多引擎对照；
- 返回结果没有发布日期元数据，无法证明 currentness。

所以正式结论为 `diagnostic_execution_pass_multi_engine_and_currentness_quality_fail`。adapter/capture/terminal 路径通过，不代表多引擎质量、Evidence、Agentic Research 或生产能力通过。

## 4. 终态后的控制台失败

三案业务结果及 runtime result 已先以 UTF-8 原子写入，随后 PowerShell GBK 控制台无法编码 `U+2011`，进程码变为 1。该故障保持为 immutable post-terminal display failure。没有重跑；admission 已消费。修复只令可选控制台输出使用 ASCII escape，不修改已物化结果，并使当前 runner SHA 与旧 authority 不同，防止误复用。

## 5. 计划重塑

当前不继续给免费 engine 逐网址打补丁，也不发 SearXNG 第二次 live。下一步等待一个候选付费 broad-search API 输入，所需资料为：

- standalone HTTPS raw HTTP/curl 示例与 base URL；
- authentication header/query 方式（密钥不写进聊天或 Git）；
- 成功、空结果、限流和错误响应 JSON；
- title、URL、snippet、published date、source/engine、score 等字段语义；
- domain/date/language/category/pagination/result-count 支持；
- rate limit、并发、地区、价格与使用条款。

收到后先做零调用 `ProviderCapabilityProfile + fixture + secret-safe transport` 资格审查，再用相同 DELL/MU/NVDA semantic intent 和 evaluator 跑一次有界 comparator。不同 Provider 不要求 HTTP 参数逐字相同；FIN 冻结语义、预算、normalization 和评价标准，由 provider-specific compiler 只发送对方明确支持的过滤条件。

只有 comparator 证明稳定性、日期、来源多样性、required-slot coverage、错误率、延迟与成本后，Owner 才决定 production Provider／source claim／no-R4。此前 additional SearXNG live、DELL R4、ranking、MU/NVDA transfer、S3、Workbench 和 release 均不准入。

## 6. 证据

- `configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_result_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_quality_assessment_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_post_terminal_display_failure_v1_0.json`
- `.codex_runtime/fin013-s1-08-searxng-bounded-diagnostic-baseline-r1/execution-result.json`

本记录没有创建新产品版本，没有改变 FIN 0.2 定义，也没有将 diagnostic locator 晋升为 Evidence 或研究结论。
