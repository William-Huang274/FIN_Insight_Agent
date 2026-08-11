# FIN 0.1.3 S1 Dell／Micron timeout autopsy 与 official-reader recovery engineering

- 日期：2026-08-10
- Owner 指令：按 timeout capture 审计 → 等价官方路线／传输 → replay／mutation／clean proof → fresh authority → 一次 source live；只有 core ready 才运行 enriched DeepSeek 比较
- 所属阶段：S1 source acquisition／Evidence Pack semantic completeness
- 本轮真实模型调用：0
- 当前状态：working-tree zero-call engineering pass，clean proof 与 source live 尚未发生

## 大白话结论

前一轮不是 Dell 和 Micron 没有资料，也不是 DeepSeek 不听话。两个官方静态文件在本机网络路径上都已连上 TCP／TLS，但一直收不到 HTTP 正文，35 秒后 timeout；旧 capture 因此没有 status、body，parser 根本没机会工作。

本轮没有再请求成功的 Alpha Vantage 或 TSMC。Dell 保留官方 Q1 FY27 transcript；Micron 选择官方 Q3 FY26 Prepared Remarks，因为它明确覆盖“DRAM/NAND 需求超过供给、紧张延续到 2027 年以后”和“HBM 封装产能自 2027 年上半年贡献”两组研究问题。Jina Reader 的匿名诊断能从这两个 exact official URL 返回完整正文并命中全部目标锚点，但这些诊断只用于决定 transport profile，未直接晋升为 Evidence。

## 零网络 autopsy

两组 predecessor request／failure capture 都按 raw SHA 绑定：

- Dell：`official_source_transport_timeout / connect_or_read / timeout`；
- Micron：`official_source_transport_timeout / connect_or_read / timeout`；
- 两者均无 HTTP status、response body 或 parser receipt；
- request 为普通 allowlisted HTTPS GET，无 Authorization、Cookie 或来源凭据。

独立 `curl` 对 Dell 原文件、Micron 原文件和 Micron Prepared Remarks 均在约 0.4–0.6 秒完成 TCP／TLS，但 25 秒内没有 HTTP bytes；域名落到桌面网络的 `198.18.0.0/15` synthetic range。由此不能把失败归因 urllib parser，也不能宣称官方内容不存在。

## 新的分权方式

Jina Reader 只承担 retrieval intermediary：

1. 输入必须是 allowlisted exact official URL；
2. Reader 原始 JSON 先完整 capture，再解析；
3. Reader 回显 URL 必须与 official URL 一致；
4. Evidence 的 source URL／official locator 继续指向 Dell／Micron；
5. lineage 明示 origin bytes 未直接保存、intermediary raw response 已保存；
6. Reader 永不拥有 financial／numeric authority，也不能自行关闭 Gap。

匿名资格诊断观察到 Dell Reader body 约 55.8k 字符，四组关键锚点均存在；Micron body 约 26.8k 字符，供需与 2027 HBM packaging 两组锚点均存在。它只证明一次候选 transport 可用，不证明未来 live、Evidence Pack 或生产 SLA。

## 实现与验证

新增 successor 从 immutable predecessor Pack（22 Evidence／15 gaps／1 NumericFact）开始，只执行两条 source route：

- Dell 3 fragments：AI orders＋backlog＋供需、客户保供／pricing discipline、AI server profitability target；
- Micron 2 bounded fragments：memory tight beyond 2027、HBM packaging H1 2027。

成功 fixture 形成 27 Evidence／14 gaps；只关闭 `dell-gap-ai-system-margin`，不会用供应商 read-through 关闭 Dell-specific allocation、价格、情景或相对估值缺口。TSMC 与 Alpha 输入按 predecessor digest 零网络复用。

定向与相邻回归=`33 passed`。已覆盖 Dell timeout 后 core false 但其他门保留、Micron anchor 缺失只关闭 supplier gate、cross-origin、Reader URL mismatch、provider authority escalation、timeout capture mutation、raw response metadata 和 exact Pack counts。

## 下一步

先提交并推送当前实现，再在两个 clean Git archive worker 中复证。proof 通过后单独签发 24 小时 fresh authority，只消费两次 source network、0 retry／model。live 若 `core_research_ready=false`，立即停止并向 Owner 返回业务缺口；若为 true，才从 changed Pack 重新编译完整 DeepSeek 报告链，不能复用旧 Specialist／Writer 节点。
