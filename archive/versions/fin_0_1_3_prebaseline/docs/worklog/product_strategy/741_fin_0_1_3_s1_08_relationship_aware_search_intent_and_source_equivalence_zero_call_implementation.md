# FIN 0.1.3 S1-08：Relationship-aware SearchIntent 与 source-equivalence 零调用实现

日期：2026-08-08

## 问题与用户决定

Firecrawl A4 与 Tencent 24-query comparator 都使用 subject company＋通用 customer/supply 关键词。代码审计证明 v3 planner 已经计算 Microsoft、Dell、Micron、NVIDIA、TSMC 等 evidence owner，却没有把 owner、别名和经济方向投影到 Provider 可见查询。用户明确要求先修查询编译，不能把失败全部归因国内 API；同时说明采购上优先国内、人民币结算以及微信／支付宝等便利，Exa 不作为默认主线。

本轮按该决定留在 `013-S1-08`，只实现零网络、零模型的 query/evaluator contract。没有创建 FIN 0.1.4，没有改写历史 Tencent、Firecrawl、SearXNG 或 DELL Attempt。

## 关键设计反思

旧计划曾写“修完后继续跑 24-query comparator”，但新 requirement 又要求 customer/supply 按 counterpart entity 分开。两者不能同时成立。当前 v3 catalog 展开后，每案有 6 个 owner-slot 组合；中英双语即 12 条官方精确 intent，三案共 36。customer/supply 另有 8 条／案语义开放网 intent，共 24。若强行仍用总数 24，只能重新把多个 owner 拼回一条 query 或丢掉部分 owner。

因此本轮冻结为两个独立 lane：

- `precise_official_domain=36`；
- `semantic_open_web=24`；
- 只在 zero-call universe 中合计 60，当前 Provider authority=0；
- future comparator 必须分别给 ceiling、成本和 stop rule，不能默认一次性调用 60 次。

## 完成内容

### 1. SearchIntent compiler

新增 `src/sec_agent/s1_08_search_intent_compiler.py` 与版本化 policy。每个 intent 绑定：

- case、Evidence Slot、subject；
- 唯一 evidence owner、aliases、owner role；
- claim direction；
- owner reporting period 与 as-of；
- source families、language、route class、preferred official domains；
- research-objective digest 与 provider-visible compact query。

query 不复制整段中文研究目标，也不包含 URL、Gold source/evidence/target ID。跨实体 query 明确搜索 owner 自身需求或供给披露，subject 只作 research context，避免虚构直接客户／供应商关系。60 条 query 全部唯一，字符数 `76–268`、平均 `163.4`、上限 300。

代表样例：

- Microsoft／DELL customer-demand：`Microsoft Azure Q3 FY2026 ... own AI infrastructure demand ... Dell Technologies DELL research context ...`；
- TSMC／NVDA supply：`台积电 TSMC 2026年第二季度 自身供给产能与约束 ... 英伟达 NVDA 研究关联背景 ...`。

### 2. Typed source equivalence

`exact_locator_match` 与 `typed_source_equivalent_match` 分账。equivalent 只允许：

1. SEC accession；
2. verified canonical locator；
3. verified redirect final locator；
4. 双方 verified content SHA-256 identity。

同时强制 case、owner、source family、document kind、published date 和 authority 一致。相同公司／期间／事件但不同 press release、prepared remarks、transcript 或 filing 不等价；Provider date 不取得金融日期权威。

### 3. Proof 与 mutation

- 新专项：`13 passed`；
- 全部 S1-08：`19 files / 169 passed`；
- Project OS exact scope preflight：pass、open blocker=0；
- 三案 36 个 official synthetic reference：`12 exact + 24 typed-equivalent + 0 no-match`；
- mutation：cross-case、wrong-direction、future as-of/date、alias collision、fan-out budget、catalog/objective permutation、unverified canonical、same-event different-document、wrong owner、SEC accession、redirect、content identity；
- 首轮 mutation 真实发现 future-as-of 被父类 `ValueError` 误归为 date-invalid；已修正为独立 `future_as_of` code 后重跑通过；
- network/provider/model/document fetch/Evidence promotion=`0/0/0/0/0`。

机器证明：`configs/releases/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof_v1_0.json`。

## 产品与工程结论

项目内“owner/方向没有进入查询”的根因已达到 zero-call engineering pass。它不反向证明 Firecrawl、Tencent 或任何国内外 Provider 的 live 质量，也不表示 SourceHunter 已接入新 compiler。旧 Tencent 失败仍是旧 Provider＋旧 query contract 的真实结果，但不能再代表新 query plan 的上限。

国内支付与运营便利是有效产品约束，但应落在 `ProviderCapabilityProfile` 的 procurement/operation 字段，而不是核心 SearchIntent 分支。当前候选顺序改为：

1. 零调用审查 Tencent relationship-aware successor 与百度千帆 standalone Web Search；
2. 阿里百炼 model-attached search 作为独立 lane；
3. 火山引擎只有拿到 standalone raw schema 后才计入；
4. Firecrawl 保留免费控制；
5. Exa 只作为可选国际 semantic benchmark。

官方参考：

- Tencent SearchPro：<https://cloud.tencent.com/document/product/1806/121811>
- 百度千帆 Web Search：<https://cloud.baidu.com/doc/qianfan/s/2mh4su4uy>
- 阿里百炼 Web Search：<https://help.aliyun.com/zh/model-studio/web-search/>

## 下一步与边界

下一项只允许：

`S1_08_DOMESTIC_FIRST_PROVIDER_INPUT_QUALIFICATION_AND_RELATIONSHIP_AWARE_COMPARATOR_SCOPE_DECISION`

它先核对 standalone/raw 或 model-attached 能力形态、认证、schema、domain/date/filter、分页、限流、人民币成本、充值／发票和凭据治理，再决定 precise 36 或 semantic 24 中哪条 lane 值得签发。不得复用聊天暴露的旧 Key，不自动联网，不签 SourceHunter integration，不解锁 ranking、DeepSeek、S3/S4/S5。

## 变更文件

- `src/sec_agent/s1_08_search_intent_compiler.py`
- `configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof_v1_0.json`
- `scripts/releases/materialize_fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof.py`
- `tests/contract/test_fin_0_1_3_s1_08_relationship_aware_search_intent_compiler.py`
- PRD、TECH_02、FIN 0.1.3 计划、Project OS 与本工作记录。
