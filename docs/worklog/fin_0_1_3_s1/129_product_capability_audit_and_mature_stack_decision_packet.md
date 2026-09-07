# S1 工作记录 129：产品能力全面审计与成熟技术栈决策包

日期：2026-08-30
状态：READ-ONLY PRODUCT AUDIT COMPLETE / MATURE-STACK RESEARCH COMPLETE / OWNER DECISION PENDING / ALL IMPLEMENTATION FROZEN

## 1. 任务来源

Owner 在看到 R14 已从 RAG 检索问题演化成大规模确定性英文 NLP/治理系统后，要求：

1. 先做一次产品全面审计；
2. 分清哪些能力应由 FIN 自己拥有，哪些应引入成熟技术栈；
3. 对所有 adopt 区域做完整技术栈调研；
4. 先展示结果，再决定下一步；
5. 在决定前不继续 R14 或扩大范围。

本轮依据安全续接 checkpoint、AGENTS.md、current context pack、senior collaboration policy、capability/root-cause ledgers、external pattern registry、financial research method registry、R14 source plan 和最新工作记录恢复连续性。没有读取、fork 或修改旧任务的 live SQLite/JSONL。

## 2. Git 与 R14 基线

审计开始时：

- canonical checkout：D:\FIN_Insight_Agent；
- branch：codex/fin013-dell-s1-s2-product-bridge；
- HEAD/origin：9f2b62834fa1bedcf48f353466f40f3ae75d4c43；
- worktree：clean；
- R14 implementation freeze：7e25cad95ee84b39fb2a51063100405bc27da6e5；
- R14 preview：27,026 total / 26,787 pass / 239 fail；
- failure：228 event-semantics / 11 assertion-semantics；
- event mismatch：277；
- I2 governance：PASS；
- owner same-R14 decision：pending；
- R15/R16：不存在。

本轮没有改 R14 production/test/config/frozen evidence，没有执行 formal、模型、Provider、网络、外源、embedding、reranker、Evidence、S2/S3 或新报告。

## 3. 作者分离的三路只读审计

为避免原作者视角把既有架构当作默认答案，本轮并行使用三个只读、作者分离的审计面：

1. repository capability audit：
   - 量化 src/retrieval/R-number/runtime/runner/preflight/config/worklog/eval；
   - 映射 Keep Build / Adopt / Hold / Retire；
   - 判断产品主路径与历史 attempt 是否发生结构性混淆。
2. data-plane mature-stack research：
   - 官方 source/XBRL/crawl/WARC；
   - PDF/OCR/layout/table/chunk；
   - provenance/storage；
   - lexical/vector/hybrid retrieval；
   - embedding/reranker；
   - grounding/citation；
   - graph 与 whole-RAG platform。
3. control-plane mature-stack research：
   - Agent state/checkpoint/HITL/durable jobs；
   - provider SDK/structured output/gateway/MCP；
   - schema/preflight/policy/IAM；
   - OTel/OpenInference/MLflow/Phoenix/Langfuse/Ragas；
   - human review 与 Quarto/Pandoc/CSL。

外部技术事实优先使用官方文档、官方仓库、标准和原始论文；产品采用判断与官方事实明确分开。

## 4. 核心审计事实

只读量化（PowerShell 非空文本行口径，不是包含空行的 physical LOC）：

- src：205 个 Python 文件 / 170,511 行；
- src/retrieval：118 文件 / 92,803 行；
- DELL R-number 版本化模块：43 文件 / 55,032 行；
- 版本化链占 retrieval 约 59.3%，占 src 约 32.3%；
- R14 frozen commit：37 文件 / 26,568 新增行；
- src/sec_agent/research：37 文件 / 45,244 行；
- scripts/research：43 文件 / 55,747 行，其中 31 个 run_* 占约 94.3%；
- project_os_preflight.py：14,870 行；
- tracked configs：1,190；
- ignored eval：18,419 files / 约 2.055 GiB；
- src/financial_facts：约 1,804 行。

确认的结构性问题：

- execution-attempt 的历史差异已逐渐固化为长期产品架构；
- 通用 Agent/runtime/provider/eval/artifact plumbing 体量远超金融事实内核；
- R3–R14 已形成自建通用英文事件语义系统；
- 工程成功和治理完整性多次没有转化为产品能力；
- 当前最早产品缺口仍是 blind S1、真实外源、16 项人审、S2 bridge、reader citation、WWC 和产品验收。

## 5. Build / Adopt / Hold / Retire 结果

### Keep Build

- identity/as-of/period/version/lineage；
- source role/use rights/citation eligibility；
- Candidate/Evidence/NumericFact 分权；
- Evidence admission 与 GapEligibility；
- PIT facts、unit/scale/dimension/vintage/conflict；
- product→revenue/profit/cash bridge；
- materiality/causal boundary/counter/WWC；
- claim↔locator 与 report/release gate；
- FIN gold/hard negatives/human rubric；
- Evidence-focused Workbench。

### Adopt Mature

- source connector/crawl/WARC；
- XBRL processor；
- PDF/OCR/layout/table/chunk；
- PostgreSQL/object store/Parquet；
- hybrid search/vector index；
- reranker serving；
- source-grounded LLM semantic extraction；
- Agent checkpoint/HITL；
- provider SDK；
- OTel/trace/eval/experiment backend；
- generic schema/policy/IAM；
- untrusted-content intake security；
- citation/report rendering。

### Hold

- GraphRAG/knowledge graph；
- 4B/7B models/fine-tuning；
- autonomous multi-agent；
- automatic Evidence promotion；
- Temporal/LiteLLM/OPA/Langfuse before trigger。

### Retire or Shrink

- R14 deterministic parser as open-language production truth engine；
- R3–R14 parallel active implementations；
- attempt-specific runner/schema/policy/successor branches；
- raw provider HTTP/SSE gateway；
- custom trace/eval file pile；
- regex/keyword/open-English semantic judge；
- generic runtime dashboard inside FIN Workbench。

Retire means “leave future production mainline after a proved migration”, never deleting frozen failures or historical evidence.

## 6. 推荐成熟栈

Data plane：

- SEC APIs + Arelle；
- Scrapy + Playwright + warcio/WARC；
- Docling default、MinerU challenger、最多一个 managed ceiling；
- PostgreSQL + Parquet + DuckDB；
- pgvector vs OpenSearch frozen A/B；
- BGE reranker v2-m3 vs Cohere ceiling；
- XBRL and PDF dual-channel；
- productization 后按云选 WORM object storage。

Semantic：

- LangExtract exact-span pattern；
- DeepSeek Flash/Chat structured SemanticCandidate；
- Pydantic strict schema；
- deterministic issuer/period/amount/unit/source/locator validators；
- abstain/disagreement/human；
- Evidence admission 保持独立。

Control plane：

- LangGraph 作为唯一 Agent state/checkpoint/HITL；
- official OpenAI Python SDK 指向 DeepSeek + thin capability adapter；
- OTel + OpenInference；
- MLflow primary experiment/trace/artifact backend；
- Quarto + Pandoc + CSL；
- Temporal/LiteLLM/OPA/Langfuse 按触发条件后置。

Whole-platform：

- RAGFlow 只做隔离 benchmark；
- Dify 当前排除；
- GraphRAG hold；
- 不用 whole platform 接管 FIN canonical authority。

## 7. 对 S1/128 建议的更新

S1/128 从已冻结的两个局部根因出发，建议过一次同 R14 revised implementation。该建议在“能否有界修掉 239/277”这个局部问题上仍成立。

本轮产品级审计增加了此前局部门没有覆盖的证据：

- R3–R14 版本化链 55,032 行；
- R14 单轮新增 26,568 行；
- product capability delta 仍为 none；
- 市场存在成熟 source-grounded LLM structured extraction/span alignment/human escalation 模式；
- 当前产品最早缺口不在 parser。

因此项目推荐更新为：

- 不再把继续扩写 deterministic parser 作为默认动作；
- R14 保持冻结，等待 Owner 在两个待授权候选路线中决定：
  - A：一次最小同 R14 修复；必须同时满足 27,026/27,026、277/277 mismatch eliminated、zero new failure code、原 population/event/price/property/mutation/resource/transaction/privacy gates 不弱化、禁止 case/text/event 特例与 validator bypass，并获得新的 author-separated read-only pre-formal PASS，之后才 legacy；
  - B（本轮推荐）：在同一 S1 责任层建立 LLM-assisted replacement shadow。RC-S1-109/110 在完整 replacement 通过并由 Owner 裁决前继续 open；当前 parser/failure/output 只作 immutable regression/baseline evidence，不作 truth oracle；case-correct human-adjudicated gold 才是判定基线。exact span、strict schema、hard validators、abstain、关键金融 slice、human gold 与独立审计全部通过后，Owner 才能决定 replacement adapter 是否接管并关闭同阶段责任；
- 两个选项都不能创建 R15/R16、进入 formal 或自动 Evidence promotion；
- infrastructure migration 与 R14 semantic decision 必须分开，不混入同一 attempt。

## 8. Durable outputs

- [产品审计](../../product/FIN_0_1_3_PRODUCT_CAPABILITY_BUILD_ADOPT_HOLD_RETIRE_AUDIT_20260830.zh-CN.md)
- [技术栈决策包](../../architecture/research/FIN_0_1_3_MATURE_TECH_STACK_LANDSCAPE_AND_ADOPTION_DECISION_PACKET_20260830.zh-CN.md)
- [技术来源快照清单](../../architecture/research/FIN_0_1_3_MATURE_STACK_RESEARCH_SNAPSHOT_MANIFEST_20260830.zh-CN.md)
- [本工作记录](129_product_capability_audit_and_mature_stack_decision_packet.md)

## 9. 当前 authority

本轮完成的是：

- product/capability audit=true；
- mature-stack official research=true；
- recommendation packet=true。

仍为 false：

- stack adoption/migration；
- R14 implementation change；
- R14 pre-formal/formal；
- R15/R16；
- external/model/reranker；
- Evidence/S2/S3/report/product/publication/release。

下一合法动作只有 Owner 审阅和决策。未经新授权，不执行 P0 pilot。

## 10. Fresh independent review and correction

在三路作者分离审计完成后，另请一名未参与编写的 reviewer 对产品审计、技术栈决策包、来源快照、Project OS 状态和 Git 边界做只读审查。初审结果为 `P0/P1/P2/P3=0/4/4/2`；reviewer 没有改文件、暂存、提交、运行模型或取得任何执行 authority。

初审暴露的四个 P1 是：

- A／B 两条 R14 路线的 same-stage closure 条件还不够完整，容易把 shadow pilot 误读为根因已关闭；
- provider SDK 默认 retry 与 FIN 的 exact receipt／unknown-completion fail-closed 合同冲突；
- 把第三方输出一律称为 Candidate，压扁了 capture、parsed element、fact observation、retrieval candidate 和 semantic candidate 的层级；
- 文档解析、爬取和模型摄入没有显式纳入 malware、active content、SSRF、prompt injection、sandbox、egress 与 DLP 威胁面。

四个 P2 是统计口径、Windows／WSL2／Docker／remote／managed 部署资格、未经校准的 confidence 表述和版本／许可快照；两个 P3 是内部链接与技术包导航。

本轮只修正文档与治理合同：

- A 恢复 S1/128 的完整 `27,026/27,026`、`277/277`、zero-new-code、原门不弱化和 fresh pre-formal PASS 条件；B 明确保持 `RC-S1-109/110` open，以 case-correct human-adjudicated gold 而不是旧 parser 作为真值；
- P0 provider adapter 显式 `max_retries=0`，每个 wire attempt 独立记录 request hash、idempotency key、start／terminal receipt、provider request ID 和 retry ordinal；unknown completion 终止为 `unknown_external_completion` 或 `duplicate_risk`；
- canonical envelope 分为 `SourceCapture`、`ParsedElement/TableCell/Locator`、unadmitted `FactObservation`、`RetrievalCandidate`、`SemanticCandidate`，只有 FIN admission 可以产生 Evidence／NumericFact；
- 增加 untrusted-content security gate、deployment-profile qualification、uncalibrated diagnostic score 边界和版本／许可 snapshot manifest；
- 修复内部链接，并增加事实／推断／Owner 建议／待资格验证／时效不确定性图例。

同一 author-separated reviewer 随后只读复审，最终结果为 `PASS，P0/P1/P2/P3=0/0/0/0`，原十项 finding 全部关闭且未出现新 P0/P1。这个 PASS 只覆盖“决策材料内部一致、边界没有越权”；它不是组件安装、版本许可、Windows 运行、模型质量、R14、S1、Evidence、产品或发布 PASS，也没有授权执行任何 P0 pilot。
