# FIN 0.1.3 S1-08：凭据就绪度与 Firecrawl 语义控制组决策

日期：2026-08-08

## 结论

当前进程没有可安全使用的腾讯 WSA、百度千帆或阿里百炼搜索凭据。检查只读取环境变量名称和“是否存在”，没有读取、回显或保存值；聊天中曾暴露的 AK/SK 不复用。因此，国内供应商优先方向不变，但当前不能诚实执行国内 Provider comparator。

选择一次 Firecrawl keyless `semantic_open_web` 控制组，规模固定为 24 个 execution unit。选择它不是因为 Firecrawl 被提升为生产候选，而是因为新查询编译器专门修复了旧 A4 customer/supply 查询没有 evidence owner 与关系方向的问题；旧 A4 为 `6/6 terminal / 0/6 exact target-in-pool`。若把 22 个 precise official unit 同时执行，就会把语义表达改进与官方域过滤混成一个实验。

## 冻结边界

- 本决策自身授权网络／Provider／模型／正文抓取／Evidence=`0/0/0/0/0`；
- 先实现 exact-once runner、capture-first、typed terminal 和 post-terminal evaluator；
- 通过零调用证明后，另行签发唯一 24-call authority；
- 每 query 最多一次网络尝试，0 retry；
- 原始请求和响应或 typed failure 先物化，再做 normalization；
- 24 个调用全部终态后才能加载 target source ID 和 URL；
- 只报告 locator 质量，不进入正文抓取、reranker、Evidence、Writer 或 DeepSeek；
- 不能自动把 24 semantic 与 22 precise 合并成 46-call run。

## 对产品的含义

这一步回答的是“修正后的查询是否比旧通用查询更会找 customer/supply 候选”，不是“国内搜索接入完成”，也不是“S1-08 通过”。即使 Firecrawl 控制组全绿，也只说明同一矩阵值得拿给国内 Provider 比较；SourceHunter 接入、正式检索能力和研究报告质量仍需各自证明。

机器决策：`configs/releases/fin_ia_0_1_3_s1_08_domestic_provider_credential_readiness_and_firecrawl_control_authority_decision_v1_0.json`。
