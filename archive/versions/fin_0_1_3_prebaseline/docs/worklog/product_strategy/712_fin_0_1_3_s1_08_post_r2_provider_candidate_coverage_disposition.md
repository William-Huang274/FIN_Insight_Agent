# 712 — FIN 0.1.3 S1-08 DELL R2 后 provider / candidate coverage 零调用处置

日期：2026-08-08
阶段：`013-S1-08`
状态：`disposition selected / implementation pending / no live authority`

## 1. 这次处置解决什么

DELL R2 已证明 SourceHunter 能在失败或缺证据时完整收尾，但没有证明它能形成研究可用的候选池。唯一 R2 已消耗，不能再用“多跑一次看看”代替根因判断。本次只读 R2 的 immutable result、589 条 receipt、受限 capture 和当前 v2 Runtime，选择下一份结构实现包；没有联网、没有模型/Provider 调用、没有签发 R3。

机器决定见：

- `configs/releases/fin_ia_0_1_3_s1_08_post_r2_provider_candidate_coverage_disposition_v1_0.json`

## 2. 比原结论更具体的新发现

R2 的 16 次网络调用不是均匀花在五类 Evidence Slot 上：

- 3 次用于 landing discovery；
- 13 次用于 document fetch；
- 其中 1 次是 DELL SEC 8-K，另外 12 次全部花在 MSFT customer slot；
- supply slot 在全局上限耗尽前没有执行过一次真实网络调用；
- market source 缺失虽然不耗网络，却仍被重复 revision 三次。

MSFT 的 12 个 document fetch 中有 3 个 earnings/event 页面、9 个下游客户案例页。当前 source-family 规则把 `/customers/story/` 归为 `customer_official_disclosure`，却没有表达“这是谁的客户、证据方向是什么”，所以微软客户案例可能被误当成微软自身 AI 基础设施需求证据。这里不是简单关键词不足，而是关系方向合同缺失。

另外，配置中的 `document_ceiling_per_query=1` 实际限制的是“最多接受 1 个 candidate”，不是“最多抓 1 份文档”。只要前一份文档没有通过，adapter 就会继续抓，直到全局 16 次耗尽。这是 customer slot 吞掉预算、supply slot 饿死的直接项目根因。

日期解析也确实太浅：当前只看 anchor 的 `data-date`、anchor 文本里的 ISO 日期和 HTTP `Last-Modified`。capture replay 显示，Microsoft FY26 Q4 press release 和 earnings-call 页面正文明确含有 `July 29, 2026`，但两页仍被记为 `discovered_source_published_date_unproven`。这说明部分候选不是来源不存在，而是本地元数据 parser 没有读出官方页面已经给出的日期。

最后，同一份 DELL 8-K 被绑定到两个 role，Runtime 报告 `2/16=0.125` yield，但 unique source 实际只有 1，唯一文档效率应为 `1/16=0.0625`。role coverage 和 unique-source efficiency 必须分账。

## 3. 选定方案

下一包统一解决五件事，而不是逐网址修补：

1. **结构化官方发现**：实现官方 IR 的 RSS/Atom、robots/sitemap、结构化 endpoint/JSON-LD locator；SEC 扩展 20-F/6-K，并允许 customer/supply slot 使用对应公司 SEC 路线。
2. **官方域内受限搜索**：从 capture-first 的 landing、feed 和 sitemap 构建同域 URL index，再按 Evidence Slot、实体角色、关系方向、日期和 source family 排序。它不是 broad Web search；当前 `external_site_search` 仍保持 unavailable。
3. **typed 日期权威**：区分 filing date、published date、event date、modified date；支持 feed、JSON-LD、OpenGraph、`time`、官方 release masthead 和 event heading。不得把任意财务期间、URL 中的 FY 字样或 HTTP modified date偷换成 published date。
4. **Evidence-Slot-aware 调度**：全局 16 次暂不增加；issuer/regulatory、customer、supply 分别预留 `4/4/5`，其余 3 次仅在每个必需 slot 至少获得一次机会后作为共享余量。每 attempt 最多抓 2 份文档、最多接受 1 个 unique document；一个 slot 不得先跑完三轮再轮到下一个。
5. **source 与 role binding 分账**：一个 canonical document 只 fetch/materialize 一次，可绑定多个 role；主效率指标按 unique accepted document / actual network calls 计算，role coverage 单列。

## 4. 为什么没有直接接 broad search API

当前项目只有 provider-neutral `external_site_search` 接口，没有已配置、可审计的实际 Provider、credential、成本和 failure taxonomy。把 Codex 自己可用的 Web 搜索或某个临时接口冒充产品能力，会再次形成“接口写了就当可用”的假象。

本轮先实现无需第三方搜索凭据、又能显著提高官方材料发现率的 official-domain bounded search。将来拿到真实 search API 后，只需新增 Provider profile 并通过 domain restriction、capture/provenance、成本和 provider-swap non-regression；不用改 Evidence Gate 骨架。

## 5. 下一包的零调用门

在请求任何新 live authority 前，必须用 R2 capture replay 与 DELL/MU/NVDA fake/mutation 证明：

- 16 个 R2 request 全部可重建并按 slot 归因；
- 两个 Microsoft 官方 release/event 页面能提取 typed 日期，但任意正文日期不能冒充 publication date；
- 9 个微软下游客户故事不会被当成微软自身基础设施需求；
- supply slot 不会再被 customer slot 饿死；
- market source unavailable 只产生一次 typed gap、零 revision；
- 同一 canonical source 不重复网络抓取，只产生一个 source document 和多个 role binding；
- 20-F/6-K、stale/future/conflicting date、malformed sitemap、cross-domain redirect、relationship reversal、slot quota mutation 都 fail closed。

通过这些工程门后，也只允许单独做 fresh-live authority decision；本处置不继承已消费的 R2，不授权 R3、MU/NVDA、ranking、BGE/Milvus、DeepSeek 或 S3。

## 6. 主动反思

原先把失败主要概括为“provider coverage 不足”仍然太宽。如果直接补一个搜索 Provider，现有串行调度、错误的 fetch ceiling、关系方向缺失和日期解析薄弱仍会把新候选浪费掉。正确顺序是把 provider、候选语义和预算编译成一个结构包，再用 capture replay 证明它们协同工作。

本次没有降低任何搜索质量门，也没有把公开材料没找到解释成材料不存在。S1-08 继续保持产品质量失败，直到新的 live candidate pool 真正通过。

收尾验证还发现一项共享治理缺口：Project OS 只识别五个固定的开放状态值。RC-P36-157 使用 `open_disposition_selected_*` 这种描述性开放状态时，即使账本明确列出 forbidden scope，预检仍在进入 scope 匹配前把整条 blocker 跳过。因此最初的 `pass / open blockers=0` 不能单独作为权限依据。当前没有在 S1-08 重构 Project OS，而是把 RC-P36-156 的最新投影改回 canonical `status=open`，用 wildcard block 加本零调用包的显式 allowlist 恢复 fail-closed；后续 live 仍须 runner/admission 直接绑定。状态枚举校验和正式 run-scope registry 继续归共享 S0/S5 治理修复。

## 7. 验证与未执行

- Project OS 初始 selected-scope preflight：`pass / open blockers=0`；
- governance negative probe：三个明确禁止的 live/ranking/S3 scope 最初均 `pass_unexpected`，确认不是可信强制门；
- RC-P36-156 canonical-open wildcard 投影后复测：本零调用 implementation scope=`pass`，三个禁止 scope=`blocked/blocked/blocked`；共享代码与 scope registry 仍未修复；
- 只读 R2 capture 审计：`16 request = 3 landing + 13 document`；
- model/provider/network/retry/admission：`0/0/0/0/0`；
- 未运行新 Runtime 测试，因为本项是 disposition，不是 implementation；
- 未修改 immutable R1/R2 result、capture 或 consumed admission。

下一项：`S1_08_POST_R2_OFFICIAL_DOMAIN_RELATIONSHIP_AWARE_LOCATOR_AND_SLOT_BUDGET_ZERO_CALL_IMPLEMENTATION`。
