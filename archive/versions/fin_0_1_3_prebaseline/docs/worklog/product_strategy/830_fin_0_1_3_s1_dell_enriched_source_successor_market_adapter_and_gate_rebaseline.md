# FIN 0.1.3 S1 DELL enriched source successor：行情适配器与双门重定基

日期：2026-08-10
状态：working-tree engineering pass；fresh clean proof／authority／exact-live 均未开始

## 本轮为什么改变原门禁

旧计划把 Dell issuer、TSMC／Micron 补源和 point-in-time 行情同时设成一条报告硬门。真实工程结果表明这会把不同层级的问题混在一起：没有 Dell 自身管理层证据确实会伤害需求／利润研究；但一个行情 Provider 暂时失败，不应抹掉已经有效的基本面研究。反过来，一条收盘价也不足以声称估值完成。

Owner 提供 Alpha Vantage credential 并批准继续 1–5 后，本轮将门重新定义为：

- `core_research_ready`：predecessor Pack＋Dell issuer fragments＋TSMC immutable capture；
- `supplier_context_ready`：Micron bounded supplier disclosure；
- `valuation_input_ready`：Alpha Vantage exact-date raw close NumericFact；
- `valuation_ready` 只作为前一字段的兼容展示别名，禁止解释成 fair value／target price ready；
- `successor_pack_ready_for_model_input` 只由 core 门控制。

## 已实现

1. 新增 provider-neutral `MarketPointRequest`、`MarketDataAdapter`、capture-first client 和 `MarketPointInTimeNumericFact`。
2. Alpha Vantage primary 固定为 `TIME_SERIES_DAILY／compact／JSON`，只读取 research as-of 的 `4. close`；不接 adjusted close，不比较预置答案。
3. AKShare／东方财富实现为 shadow profile。它能比较同日 raw close，但事实状态固定为 `diagnostic_shadow_only_never_authoritative`，不会进入 Evidence Pack 的 numeric facts。
4. request capture 不保存 API key；transport 只在内存中注入。safe endpoint 删除 `apikey`。Provider 若在 body 回显 credential，只保存 body digest／长度和 typed rejection，不保存 body。
5. 新 DELL successor 从 immutable 20-item predecessor 出发，复用已保存 TSMC capture，不再次联网；新 live 只计划 Dell transcript、Micron deck、Alpha primary、AKShare shadow。
6. Pack 合并允许同一来源的多个 Evidence item 复用完全相同的 content-addressed SourceMaterial；digest 或 URL 不一致仍 hard fail。
7. 单点行情成功只关闭 `dell-gap-valuation-basis`；`dell-gap-price-in-boundary` 和 `dell-gap-scenario-sensitivity` 永不因单点 close 自动消失。

## 当前验证

- 行情 adapter／secret／shadow tests：7 passed。
- enriched successor／双门／gap tests：4 passed。
- 联合 targeted source recovery／supplement 回归：23 passed。
- 新 Project OS exact scope 已登记，scoped preflight=`pass／0 blocker`。
- live network／Provider model／DeepSeek／retry=`0／0／0／0`。
- 本机 shadow 依赖已安装并冻结为 AKShare `1.18.84`；它不进入核心依赖，也不拥有 Evidence 权威。

验证覆盖：primary success、wrong symbol、missing exact date、negative close、rate limit、secret echo、shadow non-promotion，以及 `core=true/valuation=false`、`core=false/valuation=true`、三门同时通过和单点价格不得关闭相对估值／情景缺口。

## 尚未证明

- Alpha Vantage 当前 key 是否真实返回 DELL 2026-08-06 exact row；
- AKShare `106.DELL` shadow 当天是否可取及是否与 primary 一致；
- Dell／Micron 新官方路线在当前网络环境能否返回并通过 anchor；
- enriched live Pack 的真实 Evidence／Gap 数量；
- changed Evidence Pack 是否让 DeepSeek 的需求、利润、供给、竞争、反方、WWC 和估值边界判断实质改善。

## 第一次 fresh proof 的诚实失败

implementation commit `4ba5fa19...` 推送后，第一次 clean proof 在 worker 1 载入 policy 时终止，尚未进入 fake source、Pack 合并或任何网络／模型调用。直接原因不是业务逻辑，而是跨 checkout 文件绑定：Windows 工作树中的两个历史 result JSON 使用 CRLF，`git archive` 中为 LF；新 policy 当时绑定 raw bytes SHA，导致同一 Git 内容在 fresh worker 被误判为 drift。

该失败没有删除、覆盖或包装成通过。修复把受 Git 管理的 JSON 改为 `lf_normalized_utf8` 哈希模式；私有 predecessor Pack 与 TSMC capture 继续使用 raw-byte SHA。新 successor 同时停止复用历史 recovery loader 的 raw-CRLF 内部绑定，改为在新合同中直接验证已绑定 recovery policy、capture file SHA 和 response body SHA。新增 CRLF／LF 等价与真实内容 mutation 回归后，定向＋相邻测试=`24 passed`，JSON／JSONL／py_compile／secret scan 通过；修复仍需新 commit／push 后重新运行两个 fresh worker，当前不能提前记为 clean proof pass。

这不是第一次遇到该类问题。RC-P36-146 已明确要求新合同使用 canonical JSON 或 normalized digest，但当时经验只留在根因账本，没有变成新 binding 的默认审查项。本次复发登记为 RC-P36-175；含义不是再造一套例外，而是承认“历史教训未制度化”也是根因。

## 下一步

1. 完成 docs／Project OS／secret scan 和提交推送。
2. 两个 fresh Git archive worker 做零网络、零模型复证；历史失败保留，不回写。
3. fresh proof 通过后签发一次 2 official＋1 Alpha＋1 AKShare authority。
4. exact-live 后以 `core_research_ready` 决定是否编译 changed Evidence Pack；Alpha 失败只留下 valuation typed gap。
5. changed Pack 从头重编译模型输入，再最多运行一次 DeepSeek 同结构报告；这是信息增量比较，不是 strict same-input 模型增益比较。

本轮没有把市场行情、完整估值、Owner acceptance 或 release 记为通过。
