# FIN 0.1.3 S1-08：国内 Provider wire projection 与公平 comparator 零调用实现

日期：2026-08-08

## 结果

`S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION` 已通过：

- canonical SearchIntent 仍为 `36 precise + 24 semantic=60`，没有缩短或改写；
- Tencent、Baidu、Alibaba MCP、Firecrawl 共物化 `240` 个 intent-bound wire object；
- compact query 使用公司／Evidence Slot 相关研究词，不再使用机械的 `own/context/IR-SEC` 标签；
- 百度 query units=`37–66`，兼容从 canonical 原文 `0/60` 提升到 wire `60/60`；
- 24 条 semantic query 在四家之间逐 intent 完全相同；
- exact request payload 合并后，每家只需 `22 precise + 24 semantic=46` 个执行单元，而不是 60 个调用；
- 专项 `12 passed`，S1-08 全组 `181 passed`；
- Project OS 组合测试 `15 passed`；其中历史 S0-04G 用例改为服从最新 typed blocker projection，不再错误要求旧 S0 scope 永久可执行，未放宽当前门禁；
- network/provider/model/document/Evidence=`0/0/0/0/0`。

这仍只是 engineering proof，没有运行任何 Provider，也没有进入 SourceHunter。

## 查询质量调整

首版短查询虽满足 72-unit 上限，但人工审阅发现它仍偏合同标签，例如 `own AI capex demand IR/SEC ... context`。这类字符串“可验证”不等于“更容易找到高质量资料”。最终版改用每家公司与槽位相关的检索词：

- Microsoft demand：`Azure AI capex datacenter capacity earnings`；
- Dell demand：`AI server backlog demand earnings`；
- Micron supply：`HBM capacity supply outlook earnings`；
- NVIDIA supply：`Blackwell supply constraint outlook earnings`；
- TSMC supply：`CoWoS advanced packaging capacity earnings`；
- issuer／regulatory 分别使用公司相关经营词＋`earnings` 或 `SEC filing`。

中文使用对应中文主题词，同时保留 ticker／产品专名。完整 `claim_direction`、`source_families`、owner、period 和 intent digest 保存在 wire metadata；搜索字符串只承载对召回有用的原子，不靠冗长边界说明维持审计。

## 公平性与 Provider 差异

1. semantic lane：同一 intent 在四家 Provider 的 query bytes 完全一致，不使用 site/date hidden filter。
2. precise lane：canonical intent 相同，但允许使用 Provider 官方字段：
   - Tencent：单 `Site`＋`FromTime/ToTime`；不发送历史出错的 `Mode/Cnt`；
   - Baidu：全部 preferred domains＋ISO `page_time` 范围；
   - Firecrawl：`includeDomains`，不启动 scrape；
   - Alibaba MCP：只保留 provisional `query/count`，完整 tool schema capture 前 `admission_eligible=false`。
3. hidden target、Evidence Gate 与 source-equivalence 口径不因 Provider 改变。

## 为什么 60 intents 只需要 46 calls

同一个 Microsoft、TSMC、Micron 等官方披露可能同时服务 DELL、MU、NVDA 多个研究案例。删掉官方查询里无益的 subject context 后，36 个 precise intent 自然归并为 22 个完全相同 payload；24 个 semantic intent 因包含研究主体仍保持 24 个独立 payload。

Runtime 不丢弃 60 个身份，而是创建 explicit execution unit：一个 payload capture 绑定一至三个 `consumer_intent_id/digest`，之后按各案例 hidden target 独立评分、独立 lineage。这样减少 14 次重复调用，又不会把一案结果静默污染另一案。

## 当前边界

- Tencent 需要新建且未在聊天暴露的凭据；
- Baidu API Key 未配置；
- Alibaba MCP 只确认官方示例中的 tool name、query/count 与 pages，完整 tool schema 尚未 capture；
- Firecrawl 是可立即使用的无密钥 control，但不是国内采购能力；
- 46 是每家两个 lane 合计的 execution-unit ceiling，不是已授权的一次 live；
- ranking、正文抓取、Evidence promotion、DeepSeek、S3 与 release 均未解锁。

## 下一项

`S1_08_DOMESTIC_PROVIDER_CREDENTIAL_READINESS_AND_FIRECRAWL_CONTROL_COMPARATOR_AUTHORITY_DECISION`

该决策只做两件事：

1. 只检查凭据“是否存在／可用范围”，绝不回显值；若 Tencent/Baidu 没有 fresh secret，就不能签发国内 live；
2. 决定是否在等待国内 Key 时先执行一次 Firecrawl control，以及只签 `22 precise`、`24 semantic` 中哪一 lane，不自动执行 46 次。

## 证据

- policy：`configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json`
- runtime：`src/sec_agent/s1_08_provider_wire_projection.py`
- proof：`configs/releases/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_and_fair_comparator_zero_call_proof_v1_0.json`
- tests：`tests/contract/test_fin_0_1_3_s1_08_domestic_provider_wire_projection.py`
