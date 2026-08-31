# FIN 0.1.3 成熟技术栈全景与采用决策包

日期：2026-08-30
状态：OFFICIAL-SOURCE LANDSCAPE COMPLETE / POSTGRES+DAGSTER S2 SHADOW IMPLEMENTATION CANDIDATE / FINAL CLEAN QUALIFICATION PENDING / NO PRODUCTION CUTOVER AUTHORITY
产品审计：[FIN 0.1.3 产品能力全面审计](../../product/FIN_0_1_3_PRODUCT_CAPABILITY_BUILD_ADOPT_HOLD_RETIRE_AUDIT_20260830.zh-CN.md)
来源快照：[成熟栈来源与版本资格快照清单](FIN_0_1_3_MATURE_STACK_RESEARCH_SNAPSHOT_MANIFEST_20260830.zh-CN.md)
审计基线：codex/fin013-dell-s1-s2-product-bridge @ 9f2b62834fa1bedcf48f353466f40f3ae75d4c43
R14 implementation freeze：7e25cad95ee84b39fb2a51063100405bc27da6e5

## 1. 执行摘要

市面上有成熟的 RAG、搜索、文档智能、Agent runtime、实验评测和企业基础设施。FIN 当前不需要继续把这些通用能力都做成自己的长期平台。

推荐的目标组合不是一个“万能 RAG 产品”，而是一组可替换、权限受限的成熟组件：

~~~text
数据面
  SEC/监管机构 API + XBRL + Arelle
  Scrapy + Playwright + warcio/WARC
  Docling default parser
  MinerU local challenger；一个 managed parser ceiling
  PostgreSQL + Parquet + DuckDB
  PostgreSQL+pgvector vs OpenSearch 冻结集 A/B
  BGE reranker v2-m3 vs Cohere managed ceiling

语义层
  LangExtract 的 exact-span/structured-extraction 模式
  DeepSeek Flash/Chat 作为 source-grounded candidate judge
  Pydantic strict schema + deterministic hard validators
  abstain / disagreement / human escalation

控制面
  Dagster：外层数据/研究 workflow primary candidate
  Prefect：同一外层责任的 challenger
  LangGraph：仅内层 Agent state/checkpoint/HITL candidate
  官方 OpenAI Python SDK 指向 DeepSeek + 薄 capability adapter
  OpenTelemetry + OpenInference
  MLflow：一个主要 run/trace/eval/artifact backend
  Quarto + Pandoc + CSL：确定性报告渲染

达到触发条件以后才加
  Temporal · LiteLLM · OPA · Langfuse · enterprise IAM/SCIM
~~~

FIN 继续拥有：

- source/as-of/entity/period/unit；
- Candidate/Evidence/NumericFact 权限；
- Evidence admission、Gap、PIT、财务桥；
- claim↔locator、causal/materiality/WWC；
- human acceptance、release gate 和 immutable receipts。

Owner 后续已授权 Steps 1–3 的本机隔离 qualification，并继续授权单一依赖源、PostgreSQL支持画像和一条 Dagster shadow vertical；本决策包仍不授权生产切换、删除旧代码、模型/外源调用或修改 R14。

### 1.1 阅读图例

| 标签 | 含义 |
|---|---|
| OFFICIAL FACT | 来自官方文档、官方仓库、标准或原始论文的能力/许可/限制描述 |
| FIN INFERENCE | 根据 FIN 当前规模、Windows 环境和产品边界作出的推断 |
| OWNER RECOMMENDATION | 建议采用、暂缓或排除；不是执行权限 |
| QUALIFICATION REQUIRED | 必须在 frozen fixture/corpus/gold 上实测，未经测试不得晋升 |
| UNVERIFIED / TIME-SENSITIVE | 版本、许可、价格、region、retention 或 Windows 路径尚未固定 |

本文件给出的软件名称大部分仍是 landscape shortlist，不是已选择的 production build。下节列出的控制面子集已经 exact pin 并写入 qualification manifest；其余 data/model/product 候选仍为 UNPINNED，不能从滚动网页链接推导生产资格。

### 1.2 2026-08-31 控制面 qualification delta

Owner 已批准并完成一个不切生产的 Z 盘 control-plane slice：它调用真实 FIN fact-mart 代码路径，但输入是手工、确定性的 DELL-shaped PIT fixture，并非现场 SEC 来源回放。隔离环境使用 Python 3.13.7、uv 0.10.7 和 277-package hash lock；summary 位于 `Z:\FIN_Insight_Agent_qualification\20260831_control_plane_slice_v1\manifests\qualification-summary.json`，SHA-256=`c6750a23b729b80b769cb6c850a7320cded818ca9d50443f680d5c6afbea8150`。

- Dagster `1.13.20`：原生 retry、持久化 run、跨进程 readback、Z 盘状态和 telemetry-off 均通过，成为外层 workflow primary candidate；
- Prefect `3.8.4`：原生 retry 与最终状态通过；默认用户目录写入曾失败，显式关闭 result persistence 并固定 home/memo/state 后通过，保留 challenger；
- MLflow `3.15.2`：run/params/metrics/artifact/client readback 通过，但 Windows job execution backend 不支持，且 transitive security gate 未过；
- OpenTelemetry `1.44.0`：1 root + 3 child spans 通过；OpenLineage `1.52.0` FileTransport START/COMPLETE 同 run ID 通过；
- DVC `3.67.1`：一次 Windows `file://` 本地远端失败保留；改用受支持路径后完成 push、移走 workspace/cache、remote pull 和 digest exact round-trip；
- PostgreSQL `18.6`：Docker Desktop 在本机启动时因 listener 路径错误失败，事务、锁、重启和备份仍未资格化；
- CycloneDX/Python license/pip-audit 完成；发现 cryptography 49.0.0、diskcache 5.6.3、pytest 8.4.2 三个已知漏洞。MLflow `3.15.2` 的 `<50` 约束阻止 cryptography 升到修复版，故整套 lab 不得原封不动进入 production；
- `requirements.txt` 干净环境的 Workbench import 已实证因缺 `pypdf` 失败；单一 dependency source/lock 是任何集成前置。
- 同 package/version 集的 lab-only Git hash lock、MLflow launcher 和最小复现说明已保存到 `scripts/qualification/`；adapter 会 fail closed 校验 Prefect/Dagster 状态目录，避免默认写回用户目录。

实验目录约 1.94 GiB；D/Z 结束可用约 4.643/16.142 GiB。`D:\FIN_Insight_Agent\data\indexes` 未修改。以上只把候选从“纸面”推进到“确定性 fixture 上的实测控制面结论”，不证明真实来源、金融真值、Evidence、产品或 release 权威。

### 1.2A 2026-08-31 locked profile 与真实 source-bound vertical delta

Owner随后授权上一轮的精确工程前置；截至当前已形成implementation candidate，旧attempt只作可行性证据，最终clean复证仍待跑：

- `pyproject.toml + uv.lock`取代两份手工requirements；当前lock=`157 records`并隔离supply tooling/build backend且含setuptools artifact hashes。v2 actual-env 33/86/88与当时0 known Python vulnerabilities是pre-successor历史，final fresh env、image/OS/Node与法律门仍open；
- Dagster `1.13.20`、dagster-postgres `0.29.20`、dagster-webserver `1.13.20`、filelock `3.32.4`进入独立`control-plane` runtime；psycopg `3.3.4`只在qualification overlay；
- official PostgreSQL `16.15-alpine`固定为exact digest；旧attempt有transaction/lock/restart/dump-restore/Dagster run-event可行性证据，当前hardened runner的clean/runtime/cleanup/host-roundtrip复证待跑；
- 一条真实local source-bound S2 CompanyFacts历史纵切曾各重建1,319 observations并达到24/24 qrels与legacy/Dagster业务投影exact；最终commit与Docker只读source mount复证待跑；
- domain-thin adapter复用现有CLI，同时用成熟filelock并负责路径/凭据/timeout/digest边界；legacy entrypoint保留为canonical business path和rollback，未删除旧代码；
- LangGraph在该确定性数据任务中没有 checkpoint/HITL/Agent graph需求，因此 HOLD且未测试。

`20260831T034026Z-a8700e1b`及`040515`已降为历史可行性证据，不能代表当前实现。只有successor绑定clean HEAD、全新combined locked runtime、start/end文件SHA、cleanup、restart、host-roundtrip restore、Dagster run/event与Docker真实job后，才可把当前candidate升级为bounded adoption；production HA/TLS/PITR/operator/daemon/UI、多租户、全产品migration、Evidence/S2 bridge、report/product/release继续未通过。

### 1.3 目录

- [总体决策矩阵](#3-总体决策矩阵)
- [官方披露、XBRL 与 source connectors](#4-官方披露xbrl-与-source-connectors)
- [PDF/OCR/layout/table](#5-pdfocrlayouttabledocument-intelligence)
- [provenance 与存储](#6-canonical-documentprovenance-与存储)
- [hybrid retrieval](#7-lexicalvectorhybrid-retrieval)
- [embedding 与 reranker](#8-embedding-与-reranker)
- [LLM semantic replacement](#9-llm-source-grounded-semantic-extractionr14-的成熟替代方向)
- [Agent orchestration](#10-agent-orchestrationcheckpointhitl-与-durable-execution)
- [Provider/gateway/MCP](#11-provider-sdk结构化输出gateway-与-mcp)
- [trace/eval/experiment](#12-traceevalexperiment-与-artifact-lineage)
- [policy/IAM/security](#13-schemapreflightpolicyidentity-与-secrets)
- [human review/citation/report](#14-human-reviewgroundingcitation-与报告)
- [Graph 与一体化平台](#15-graph-retrieval-与一体化平台)
- [共同资格门](#17-共同资格门)
- [P0/P1/P2 与 Owner 决策](#18-推荐-p0p1p2-顺序)

## 2. 选型原则

### 2.1 一个组件只解决它真正擅长的问题

- parser 负责解析，不负责 Evidence admission；
- search 负责召回，不负责事实判断；
- reranker 负责排序，不负责来源权威；
- LLM 负责开放语义候选，不负责金融真值；
- workflow 负责状态和恢复，不负责产品版本权威；
- trace backend 负责观测，不是金融证据真源；
- renderer 负责排版，不负责 citation correctness。

### 2.2 每一层最多保留 default、challenger、managed ceiling

不同时长期维护五个 parser、四个向量库、三个 Agent 框架和四个 trace 平台。正式选型通过后，未胜出的 challenger 退出常驻运行。

### 2.3 外部输出只能进入对应层级的 unadmitted canonical envelope

第三方字段名即使叫 evidence、grounding、citation、confidence，也不能自动映射成 FIN 的 admitted Evidence 或 NumericFact；但也不能把所有层级压扁为同一个 Candidate：

- crawl/WARC → SourceCapture；
- parser → ParsedElement / TableCell / Locator；
- XBRL processor → unadmitted FactObservation；
- search/reranker → RetrievalCandidate；
- LLM extraction/judge → SemanticCandidate；
- FIN admission 之后才可能成为 Evidence 或 NumericFact。

### 2.4 先做可退出的 adapter，再做迁移

上层只依赖 FIN canonical contracts。供应商 schema、ID、score、state 和数据库结构不能渗透到 research/report/release 层。

### 2.5 先按关键金融 slice 验收，再看平均指标

必须分别测 issuer、period、unit、scale、amendment、table、footnote、source role、PIT/as-of、negative/counterexample 和 citation locator。平均分提升不能掩盖关键金融 slice 退化。

## 3. 总体决策矩阵

| 能力 | 推荐 default | challenger / ceiling | 当前结论 |
|---|---|---|---|
| 美国监管披露 | SEC EDGAR APIs + raw filing | Arelle validation | ADOPT |
| 静态网页抓取 | Scrapy | Crawl4AI/Firecrawl 仅专项比较 | ADOPT |
| 动态网页 | Playwright | Browsertrix 仅高保真归档 | 已有基础，收敛使用 |
| 原始网页证据 | warcio/WARC | cloud object WORM | ADOPT |
| 本地 PDF/OCR/layout/table | Docling | MinerU | ADOPT，冻结集选型 |
| 托管高难解析 | 不默认 | LlamaParse 或 Azure/Google/AWS 按云战略选一个 | CONDITIONAL |
| XBRL | SEC API + Arelle | xBRL-JSON 互换 | ADOPT，独立主通道 |
| canonical metadata | PostgreSQL | 无第二套 | ADOPT |
| snapshot/analytics | Parquet + DuckDB | 无 | ADOPT |
| raw/artifact store | 当前 hash filesystem | 产品化后 S3/Azure/GCS WORM | ADOPT BY STAGE |
| hybrid retrieval | PostgreSQL+pgvector | OpenSearch | A/B 后只留一个 primary |
| commercial search ceiling | 不默认 | Elastic 或 Azure AI Search 二选一 | CONDITIONAL |
| local reranker | BGE reranker v2-m3 | current baseline | CHALLENGER |
| managed reranker | 不默认 | Cohere | CEILING |
| source-grounded semantic extraction | LangExtract pattern + DeepSeek candidate | 本地 vLLM/另一已资格模型 | SHADOW PILOT ONLY |
| 外层数据/研究 workflow | Dagster `1.13.20` | Prefect `3.8.4` | Dagster S2 shadow implementation candidate已落盘；旧real-slice为历史可行性证据，最终clean receipt与Docker真实job待跑；Prefect仍为challenger；production blocked |
| 内层 Agent state/checkpoint/HITL | LangGraph OSS | 无第二内层 Agent graph | QUALIFICATION PENDING；不得承担外层 pipeline |
| distributed durable jobs | 当前无主实现 | Temporal | TRIGGER-GATED |
| provider transport | official openai SDK → DeepSeek | thin capability adapter | ADOPT PILOT |
| multi-provider gateway | 无 | LiteLLM | TRIGGER-GATED |
| typed contract | Pydantic strict → JSON Schema | provider-specific compiler | ADOPT |
| tool protocol | FIN typed interface | MCP for external read-only tools | P1 |
| trace semantics | OTel + OpenInference | 无 | ADOPT |
| run/eval/artifact backend | MLflow `3.15.2` | Phoenix 一次内部 UX 比较 | LOCAL READBACK PASS / SECURITY+POSTGRES BLOCKED |
| generic eval metrics | deterministic + FIN gold | selected Ragas metrics | ASSISTIVE ONLY |
| enterprise identity | 当前本地 auth | WorkOS/Entra/Auth0/Keycloak 按部署选型 | TRIGGER-GATED |
| dynamic policy | FIN in-code contracts | OPA | TRIGGER-GATED |
| untrusted-content intake security | MIME/magic validation + quarantine + sandbox + egress/SSRF controls | enterprise CDR/malware service after need | ADOPT PILOT |
| evidence review | thin FIN Workbench | Label Studio 仅 gold annotation | KEEP DOMAIN / ADOPT GENERIC UI PATTERNS |
| report rendering | Quarto + Pandoc + CSL | DOCX/PDF visual QA | ADOPT |
| Graph retrieval | 无 | Neo4j after gate | HOLD |
| whole RAG platform | 无 | RAGFlow benchmark only | DO NOT TAKE OVER |
| whole LLM app platform | 无 | Dify reference only | EXCLUDE NOW |
| large artifact versioning | DVC `3.67.1` | object store versioning | Z local remote round-trip PASS；仅大型资产 conditional adopt |
| dependency lock / SBOM | uv `0.10.7` + CycloneDX `7.3.1` + pip-audit `2.10.1` + pip-licenses `5.5.5` | image scanner/signing later | 根pyproject+157-record uv.lock单一依赖candidate；tools/build backend独立locked group；v2 33/86/88是pre-successor；fresh env、image/Node/OS、license legal与final regression仍open |

### 3.1 P0 candidate 部署画像

部署标签含义：

- native_windows：直接在当前 Windows host；
- WSL2：Windows host 上的 Linux userland；
- docker_linux：Docker Desktop 或 Linux container；
- remote_linux：独立 Linux 服务；
- managed：供应商云服务。

下表是建议测试画像，不是已经验证的支持承诺。任何标为 UNTESTED 的路径在实际安装、恢复、升级和性能 proof 前都是 blocker。

| Candidate | 优先资格画像 | 可接受备选 | 当前本机状态 / blocker |
|---|---|---|---|
| Arelle | native_windows Python/CLI | docker_linux | UNTESTED；需 pin Python/package/taxonomy |
| Scrapy/warcio | native_windows | WSL2/docker_linux | UNTESTED；需 filesystem/resume/encoding proof |
| Playwright | native_windows | docker_linux | 仓库已有基础，但新 capture/WARC contract 未资格验证 |
| Docling | native_windows | WSL2/docker_linux | UNTESTED；需 pin core、OCR engine、model weights、CPU/GPU |
| MinerU | WSL2 或 docker_linux 优先 | native_windows challenger | UNTESTED；CUDA/模型下载/许可/资源路径为 blocker |
| PostgreSQL `16.15` exact digest local profile | docker_linux pilot | remote_linux | Docker daemon已可用；旧attempt已验证本地transaction/UNIQUE/advisory-lock/restart/dump-restore可行性；当前hardened clean-commit/host-roundtrip最终复证待跑，HA/TLS/PITR/operator未测 |
| pgvector | 与 PostgreSQL 同 profile | docker_linux/remote_linux | Windows extension build/package 路径未固定 |
| OpenSearch | docker_linux 或 remote_linux 优先 | native Windows ZIP challenger | JVM、filesystem lock、recovery、RAM 未验证 |
| Dagster `1.13.20` | docker_linux target + native_windows qualification | remote_linux | optional locked profile、PostgreSQL run/event历史可行性和S2 adapter candidate存在；最终clean runtime-bound receipt、只读private-source Docker job待跑；schedule/sensor未测，daemon/operator production proof pending |
| Prefect `3.8.4` | native_windows Python | docker_linux/remote_linux | retry/state PASS；默认 home 写入 caveat 已由显式配置消除；作为 challenger |
| LangGraph | native_windows Python | WSL2/docker_linux | 未运行；只测内层 Agent vertical，SQLite/Postgres checkpointer 锁、并发和 crash recovery 未验证 |
| MLflow `3.15.2` | native_windows local pilot | docker_linux/remote_linux + Postgres/object store | tracking/artifact/client readback PASS；Windows job backend、漏洞、迁移/备份未通过 |
| DVC `3.67.1` | native_windows Python | object store remote | Z local path push/pull/digest PASS；Windows `file://` path 失败证据保留 |
| Quarto/Pandoc | native_windows CLI | docker_linux | renderer/font/template/version 未固定 |
| Temporal | remote_linux/managed | docker_linux dev | 当前不进入 P0；Windows 只作为 SDK/client 路径考虑 |

Windows 专项门必须覆盖 rename/replace 原子性、长路径、跨 volume move、file locking、process crash、SQLite/WAL、Docker/WSL volume 和 GPU driver/CUDA identity。不能把“官方说支持 Windows”写成“FIN 当前环境已通过”。

## 4. 官方披露、XBRL 与 source connectors

### 4.1 SEC EDGAR API 应成为美国上市公司正式入口

SEC 的 submissions、companyfacts、companyconcept、frames 和 bulk archives 是公开官方接口，无需 API key，适合成为 filing identity 和结构化事实的第一入口。[SEC EDGAR API 官方文档](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

推荐职责：

- official filing metadata；
- accession、form、filed date、issuer identity；
- XBRL facts 和 bulk backfill；
- raw filing 下载入口。

FIN 仍需负责：

- PIT/as-of；
- amendment/重述与版本关系；
- source role；
- CompanyFact canonicalization；
- conflict 和 admission。

### 4.2 XBRL 必须与 PDF/OCR 分成两条通道

XBRL fact 的 concept、entity、period、unit 和 dimensions 是正式结构语义；视觉表格解析不能自动继承这些权威。[XBRL Essentials](https://specifications.xbrl.org/xbrl-essentials.html)、[XBRL Reporting Requirements](https://specifications.xbrl.org/reporting-requirements.html)

推荐：

- SEC XBRL JSON API：快速、官方结构化入口；
- Arelle：本地 iXBRL/XBRL validation、taxonomy、dimension、duplicate 与 SEC EFM 检查；其官方仓库为 Apache-2.0。[Arelle](https://github.com/Arelle/Arelle)
- xBRL-JSON：vendor-neutral interchange；原始 iXBRL 仍保留。[xBRL-JSON 规范](https://www.xbrl.org/Specification/xbrl-json/REC-2021-10-13%2Berrata-2023-04-19/xbrl-json-REC-2021-10-13%2Bcorrected-errata-2023-04-19.html)

硬边界：

- OCR table 不覆盖已有正式 XBRL fact；
- PDF 与 XBRL 不一致时生成 conflict；
- companyfacts 聚合不能替代 accession-bound raw filing；
- amendment 不覆盖旧 filing。

### 4.3 网页抓取

| 候选 | 适用面 | 许可/运维 | 决策 |
|---|---|---|---|
| Scrapy | 静态/服务端渲染网页，队列、重试、限速、resume | BSD-3-Clause，Python 成熟 | default crawler |
| Playwright | JS、登录、交互、网络监听、HAR/trace | Apache-2.0，成本高于普通 HTTP | 动态页 fallback |
| warcio/WARC | 保存 request/response 原始交换 | Apache-2.0，轻量 | raw web evidence |
| Browsertrix | 高保真浏览器归档、WARC/WACZ、调度 UI | AGPLv3，Docker/K8s 较重 | 合规级需求后 |
| Unstructured Ingest | 企业 source/destination connectors | 开源/托管双形态 | SharePoint/Drive/S3 后续 |
| Airbyte | 数据库/SaaS CDC/ELT | open-core / ELv2 路线 | 公开网页和 EDGAR 不采用 |
| Firecrawl | 托管 JS crawl、markdown、截图 | 商业 credits/retention 要核验 | hard-web ceiling |
| Crawl4AI | 本地 async browser crawl | 本地开源路线 | 与 Scrapy/Playwright 专项比较 |

官方依据：

- [Scrapy architecture](https://docs.scrapy.org/en/latest/topics/concepts.html)
- [Scrapy pause/resume jobs](https://docs.scrapy.org/en/master/topics/jobs.html)
- [Playwright network](https://playwright.dev/docs/network)
- [Playwright tracing](https://playwright.dev/docs/api/class-tracing)
- [warcio](https://github.com/webrecorder/warcio)
- [Browsertrix](https://github.com/webrecorder/browsertrix)
- [Unstructured ingest](https://docs.unstructured.io/open-source/ingestion/overview)
- [Firecrawl crawl](https://docs.firecrawl.dev/features/crawl)
- [Crawl4AI](https://docs.crawl4ai.com/core/simple-crawling/)

抓取验收：

- URL、final URL、redirect chain、status、headers、timestamp、fetcher version；
- raw byte SHA-256；
- WARC round-trip；
- resume 无静默漏抓/重抓；
- page update 新建版本；
- robots/terms/rate limit 明确；
- 当前内容不能冒充历史 as-of 内容。

### 4.4 不可信内容摄入安全

网页、PDF、Office、图片、压缩包和 source-derived instructions 都是不可信输入。文档解析和 LLM 可见内容必须先经过独立安全边界，不能把“来源是公开网站”误写成“文件安全”。

成熟通用能力可以承担：

- MIME 与 magic-byte 双重校验；
- extension allowlist、文件大小、页数、像素、嵌套深度和解压比上限；
- malware 扫描与 quarantine；
- parser sandbox/container、CPU/RAM/time/file-count/temporary-disk 上限；
- HTML/script/active content 禁用或 content disarm；
- URL scheme/domain allowlist、DNS resolution、redirect-chain、SSRF 和内网地址阻断；
- network egress policy；
- managed parser/model/trace 的 DLP、region 和 retention gate。

FIN 必须继续拥有：

- source authority 与 privacy classification；
- 哪些 source/domain/file type 可进入哪个阶段；
- source content 与 system/tool instructions 的分离；
- source-derived strings 不得控制 tool authority、filesystem path、SQL/query、policy 或 model routing；
- prompt injection 只作为内容证据，不作为指令；
- 每次隔离、拒绝、超限、malware/SSRF/prompt-injection finding 的 immutable failure receipt。

推荐 P0 组合不是一个特定安全厂商，而是：libmagic/MIME validation + ClamAV 或等价 malware engine + 隔离 Linux container/resource limits + explicit egress/SSRF policy。企业客户出现 CDR/DLP/合规要求后，再比较托管 malware/CDR 服务。

官方依据：

- [ClamAV documentation](https://docs.clamav.net/)
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP LLM Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

安全验收至少包含：伪造 extension/MIME、zip bomb、oversized image/page、nested object、malformed font、HTML active content、localhost/private/link-local/metadata IP、DNS rebinding/redirect、source prompt injection、path/query/tool injection 和 scanner/parser timeout。任何安全失败必须在解析、索引或模型调用之前 fail closed。

## 5. PDF/OCR/layout/table/document intelligence

### 5.1 推荐 shortlist

| 候选 | 强项 | 风险/边界 | 决策 |
|---|---|---|---|
| Docling | 多格式、layout、reading order、tables、OCR、结构化 DoclingDocument、bbox/provenance；native Windows 是待资格画像 | 模型许可另核；Markdown 会丢复杂 table span；当前本机未运行 | local default candidate |
| MinerU | OCR、公式、图片、表格、跨页表格；WSL2/docker/native Windows 均需实测 | 许可带附加条件，版本、CUDA、模型和资源漂移 | local hard-doc challenger |
| Unstructured | connectors、partition、element chunking | hi_res 多栏阅读顺序风险；财报 table 不是绝对优势 | connector/chunk challenger |
| LlamaParse | 财务 table、cell/line bbox、managed parser version | 云锁定、region、retention、价格、BYOC 并非天然 air-gap | managed ceiling |
| Azure Document Intelligence | paragraphs/spans/polygons/tables/captions/footnotes | Azure lock；container 能力不等同云端全集 | Azure-first ceiling |
| Google Document AI | structured tree、layout、table、bbox | GCP lock、preview/region、跨页 table | GCP-first ceiling |
| AWS Textract | forms/tables/queries/signatures/layout | AWS lock | AWS-first ceiling |

官方依据：

- [Docling DocumentConverter](https://docling-project.github.io/docling/reference/document_converter/)
- [Docling document model](https://docling-project.github.io/docling/concepts/docling_document/)
- [Docling serialization](https://docling-project.github.io/docling/concepts/serialization/)
- [MinerU](https://github.com/opendatalab/mineru)
- [MinerU license](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)
- [Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning)
- [Unstructured chunking](https://docs.unstructured.io/open-source/core-functionality/chunking)
- [LlamaParse](https://developers.llamaindex.ai/llamaparse/parse/)
- [Azure layout](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout)
- [Google layout parser](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk)
- [AWS Textract](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-analyzing.html)

### 5.2 推荐结论

- Docling 做 default；
- MinerU 做 local challenger；
- 最多选一个 managed ceiling；
- 不同时长期维护五套；
- 表格以 cell grid、rowspan/colspan、header relation 和 footnote 验收，不能只看 Markdown；
- parser confidence 不是 financial confidence。

### 5.3 冻结解析语料

必须包含：

- 扫描、双栏/三栏、页眉页脚；
- 括号负数、货币、百分比、单位缩放；
- 合并单元格、跨页表、重复表头；
- table title、footnote；
- narrative 与视觉表冲突；
- page/bbox/char span 可追溯。

每次 parser run 记录 input hash、package/model/version、options、hardware、timestamp 和结构 diff。

## 6. Canonical document、provenance 与存储

### 6.1 FIN 仍需要一层薄 canonical contract

不同 parser 的 object model 不一致。FIN canonical object 至少包含：

- source_object_id、source_version_id、raw hash；
- fetch/published/as-of 时间；
- issuer、filing/accession、document role；
- parser run/model/version/options；
- page、bbox、char span；
- section path 和 parent/child；
- table/cell/row/column/span/header；
- content hash；
- chunk 到原始 element 的一对多映射；
- embedding/index snapshot；
- admission status 和 derivation chain。

可以借鉴 [W3C PROV-O](https://www.w3.org/TR/prov-o/) 的 Entity/Activity/Agent 和 [OpenLineage](https://openlineage.io/docs/) 的 Dataset/Job/Run 概念，但当前无需为了“标准化”部署完整 RDF graph 或 OpenLineage backend。

### 6.2 推荐存储组合

| 能力 | 推荐 | 边界 |
|---|---|---|
| canonical metadata/transaction | PostgreSQL | primary online truth |
| immutable table snapshot/export | Apache Parquet | 不是事务库 |
| local analytics/audit | DuckDB | 不是团队在线权威库 |
| current local raw/artifacts | content-addressed filesystem | 不能冒充真正 WORM |
| production raw/artifacts | S3 Object Lock / Azure Blob immutable / GCS Bucket Lock 按云选一 | 版本和 retention policy |
| large model/corpus/index | DVC 仅达到阈值后 | 不管理小 receipt |

官方依据：

- [PostgreSQL full text and data platform](https://www.postgresql.org/docs/current/)
- [PostgreSQL WAL/PITR](https://www.postgresql.org/docs/18/wal-intro.html)
- [Parquet](https://parquet.apache.org/docs/)
- [DuckDB Parquet](https://duckdb.org/docs/lts/data/parquet/overview)
- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [Azure immutable blobs](https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-storage-overview)
- [GCS Bucket Lock](https://docs.cloud.google.com/storage/docs/bucket-lock)
- [DVC pipelines](https://doc.dvc.org/user-guide/pipelines/defining-pipelines)

MinIO Community 当前官方仓库已归档且是 AGPL 路线，不建议作为新默认自托管对象存储。[MinIO repository](https://github.com/minio/minio)

### 6.3 存储验收

- raw bytes round-trip hash exact；
- metadata backup + object snapshot 可恢复指定 run/as-of；
- PostgreSQL 实际 PITR 演练；
- object overwrite/delete 受 version/WORM 控制；
- index 可由 canonical objects 重建；
- MLflow/trace backend 丢失不改变 FIN Evidence 权威；
- artifact 记录 schema、producer commit、input hash、run/attempt ID。

## 7. lexical/vector/hybrid retrieval

### 7.1 为什么不能只上向量库

FIN 查询包含 ticker、CIK、accession、form、期间、金额、单位、法规编号、source role 等硬约束。语义相似度无法替代 exact lexical matching 和 metadata filters。

### 7.2 候选矩阵

| 候选 | 强项 | 成本/锁定 | 决策 |
|---|---|---|---|
| PostgreSQL + pgvector | relational constraints、JSONB、FTS、exact/ANN vector、transaction、低运维 | hybrid fusion/app RRF 和 selective filter 要实测 | 当前规模 primary challenger |
| OpenSearch | Apache-2.0，BM25+vector、RRF/normalization、filters、search pipeline、explain/profile | 比 Postgres 重 | full-search challenger |
| Elasticsearch/Elastic Cloud | 搜索生态、RRF/retrievers/semantic rerank/运营成熟 | ELv2/商业成本与锁定 | commercial ceiling |
| Azure AI Search | managed BM25+vector+RRF+semantic ranker | Azure lock | Azure-first ceiling |
| Qdrant | dense+sparse、多向量、multi-stage、ColBERT | 传统 analyzer/non-vector ranking 不是目标 | multi-vector 触发后 |
| Weaviate | turnkey hybrid vector application | 对当前 FIN 无决定性优势 | 不进首轮 |
| Milvus | 大规模向量和分布式 | 当前规模过重 | 不采用 |

官方依据：

- [pgvector](https://github.com/pgvector/pgvector)
- [PostgreSQL FTS](https://www.postgresql.org/docs/current/textsearch.html)
- [OpenSearch hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/)
- [OpenSearch relevance optimization](https://docs.opensearch.org/latest/search-plugins/search-relevance/optimize-hybrid-search/)
- [Elastic hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search)
- [Azure AI Search hybrid](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Weaviate hybrid](https://docs.weaviate.io/weaviate/search/hybrid)
- [Milvus full-text hybrid](https://milvus.io/docs/v2.5.x/full_text_search_with_milvus.md)

### 7.3 推荐决策

正式 A/B：

1. PostgreSQL + pgvector：低运维方案；
2. OpenSearch：完整搜索引擎方案；
3. 若已有明确云战略，再加一个 commercial/managed ceiling。

不同时搭建 Qdrant、Weaviate、Milvus。冻结集通过后只保留一个 primary。

### 7.4 检索验收

- exact identifier；
- numeric/period；
- semantic paraphrase；
- table/footnote/narrative；
- negative/counterexample；
- source role 与 PIT/as-of filter；
- Recall@k、MRR、nDCG@10；
- exact-identifier zero-miss；
- p50/p95、RAM、index size、rebuild time；
- snapshot reproducibility；
- BM25/vector/hybrid 独立消融；
- index/query/filter/runtime failure 不得被误写成 public-information gap。

## 8. embedding 与 reranker

| 候选 | 形态 | 许可/锁定 | 决策 |
|---|---|---|---|
| BGE-M3 embedding | multilingual dense/sparse/multi-vector | 官方模型路线 | local baseline/challenger |
| BGE reranker v2-m3 | 0.6B multilingual cross-encoder | model Apache-2.0；FlagEmbedding MIT | local primary challenger |
| Cohere Rerank | managed multilingual/structured input | 商业成本、数据和 model version | managed ceiling |
| Jina reranker | 长上下文/多语言 | 多个权重为 CC-BY-NC，商业需许可 | 默认排除 |
| SentenceTransformers CrossEncoder | 本地训练/推理/eval 工具 | 自己承担模型选择和 serving | 实验工具 |
| vLLM score/serving | 本地 OpenAI-compatible serving | 需要 GPU/运维 | 资源允许后 |

官方依据：

- [BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [BGE reranker v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [FlagEmbedding reranker](https://github.com/FlagOpen/FlagEmbedding/blob/master/examples/inference/reranker/README.md)
- [SentenceTransformers CrossEncoder](https://www.sbert.net/docs/quickstart.html)
- [Cohere reranking](https://docs.cohere.com/docs/reranking-with-cohere)
- [Jina reranker](https://jina.ai/reranker/)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/v0.18.0/serving/openai_compatible_server/)

硬边界：

- reranker 只重排已有候选；
- score 不映射成 Evidence confidence；
- 不修复 missing candidate；
- exact identifier、issuer、period、unit、source role 不能退化；
- model/tokenizer/input serialization/truncation/top-N/digest 全记录；
- 只在 frozen top-N 和 blind qrels 上比较；
- 当前 4B resource/gate 未满足，不因本调研自动获得调用权。

## 9. LLM source-grounded semantic extraction：R14 的成熟替代方向

### 9.1 用户的直觉是对的，但要补上安全边界

DeepSeek Flash/Chat 一类模型完全可以辅助：

- predicate/event/role 候选；
- negation、reported speech、future/actual；
- assertion attribution；
- ambiguous support/contradiction；
- claim decomposition；
- 错误聚类和人审队列排序。

问题不是“能不能让大模型判断”，而是不能让一次模型输出直接获得金融 Evidence 权威。

### 9.2 推荐模式

Google LangExtract 是值得借鉴的成熟模式：LLM 生成结构化抽取，并把每个 extraction 对齐到原文精确位置；支持长文 chunk/multipass、可视化和自定义 provider。它也明确提醒准确性仍依赖模型、提示和样例。[LangExtract](https://github.com/google/langextract)

推荐链：

~~~text
source span + task-specific few-shot
        ↓
DeepSeek candidate extraction
        ↓
strict JSON / tool schema
        ↓
Pydantic post-validation
        ↓
exact/fuzzy source-span alignment
        ↓
deterministic hard validators
  issuer / period / amount / unit / source / locator
        ↓
agreement/disagreement signals + uncalibrated diagnostic score
        ├─ pass as semantic Candidate
        ├─ abstain / partial
        └─ human review
        ↓
FIN Evidence admission（独立）
~~~

模型自报概率、logprob 或多个调用“多数一致”都不能直接称为 calibrated confidence。只有在预注册、case-correct、human-adjudicated validation set 上完成 train/validation/test 分离，报告 reliability、ECE/Brier 或 coverage-risk，并在 model/prompt/schema/corpus 变化后重新校准，才允许使用 calibrated 一词；即使完成校准，关键金融 slice 也不能仅凭分数自动通过。

DeepSeek 官方支持 JSON mode 和 strict tool calls，但 JSON mode 不等于 schema/content correctness；可能截断、空内容，strict 模式也有 schema 子集限制。[DeepSeek JSON mode](https://api-docs.deepseek.com/guides/json_mode/)、[DeepSeek strict tool calls](https://api-docs.deepseek.com/guides/tool_calls/)

### 9.3 R14 challenger 验收

如果 Owner 选择模型辅助路线：

- 当前 R14 27,026 corpus、239 failure、277 mismatch 和所有 digest 不变；
- 先只读 shadow，不写 R14 current artifact；
- RC-S1-109/110 在 replacement 完整通过并由 Owner 明确裁决前继续 open；shadow run 不关闭同阶段根因；
- old parser、LLM candidate、deterministic validators、case-correct human-adjudicated gold 分开存；
- old parser output 只能作为 regression/baseline evidence，不能作为 truth oracle；
- 统计 precision/recall/F1、abstain rate、human escalation；
- 分别看 negation、future、reported speech、synthetic predicate、price attachment；
- exact span 必须存在；
- 错主体/错期间/错金额/错来源关键 slice 为硬失败；
- 低置信和 disagreement 不强行二分类；
- DS Flash 只有在 frozen corpus 和 case-correct real examples 上胜出才可晋升；
- 还必须通过 277/277 mismatch、zero new failure code、原 population/event/price/property/mutation/resource/transaction/privacy gates、禁止 case/text/event 特例以及新的 author-separated read-only review；
- 只有上述门完成后，Owner 才能决定 replacement adapter 是否接管并关闭同一 S1 责任；否则 RC-S1-109/110 保持 blocker；
- 不能用模型判断绕过 16 项 Evidence 人审。

## 10. Agent orchestration、checkpoint、HITL 与 durable execution

### 10.1 外层 workflow 与内层 Agent graph 必须分责

原稿把 LangGraph 预设为“单一全局状态机”，这会再次把数据采集/解析/索引/评测、后台 job 和 LLM 会话三种问题压进一个框架。Step 3 已纠正为：

- Dagster/Prefect 比较外层数据、研究、评测和迁移 pipeline；在真实 FIN fact-mart 代码路径的同一确定性 DELL-shaped PIT fixture 上运行后，Dagster 是 primary candidate，Prefect 是 challenger；
- LangGraph 只在单研究 vertical 中竞争 LLM Agent thread/checkpoint/interrupt/HITL；当前尚未安装或资格化；
- PostgreSQL 负责 canonical transaction/lock state；MLflow/OTel/OpenLineage 负责 experiment/telemetry/lineage；
- Temporal 只在跨 worker、跨重启长任务、timer/signal、Saga 或明确 SLA 出现后加入。

LangGraph 本身提供 thread state、checkpoint、resume、interrupt/HITL 和 time travel；MIT 许可，本地 SQLite/Postgres checkpointer 对当前环境较友好。[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

重要 caveat：含 interrupt 的节点恢复时会从节点开头重新执行。因此：

- provider call、抓取、文件写入和付费工具必须幂等；
- checkpoint 不等于 external exactly-once；
- 每次副作用需要 idempotency key、request hash 和 immutable receipt。

LangGraph 后续资格边界：

- 只做一条 vertical pilot；
- 只允许一个内层 Agent graph；
- 不承担 outer workflow、canonical metadata、experiment backend 或 release authority；
- Haystack 若用于 data pipeline，不再拥有内层 Agent state；
- 不把 product/S-stage/attempt 语义塞进框架内部黑盒。

### 10.2 Temporal：成熟但暂缓

Temporal 适合多 worker、跨重启数小时/数天、timer/signal、生产 SLA 和可靠 job recovery；但 Activity 本质仍需幂等处理，且当前单机 Windows 项目会增加 server、DB、worker 和运维。[Temporal workflow execution](https://docs.temporal.io/workflow-execution)、[Temporal Python error/idempotency guidance](https://docs.temporal.io/develop/python/best-practices/error-handling)

触发条件：

- 多独立 worker；
- 长任务跨重启；
- 本地 runner 已出现任务丢失/重复；
- 可靠 signal/timer；
- 明确 SLA 和运维 owner。

### 10.3 Haystack 与 OpenAI Agents SDK

- Haystack 的 typed pipeline、branch/loop、async、retrieval/eval component 很适合 data plane，但不应成为第二个全局 orchestrator。[Haystack pipelines](https://docs.haystack.deepset.ai/docs/pipelines)
- OpenAI Agents SDK 对 OpenAI provider 很有价值，但当前主要 provider 是 DeepSeek；没有必要把主控制面绑定到另一套 provider/session/tracing 语义。等 OpenAI 成为一等 provider 后再做资格验证。

## 11. Provider SDK、结构化输出、gateway 与 MCP

### 11.1 official OpenAI Python SDK → DeepSeek

DeepSeek 官方以 OpenAI-compatible API 形式示例 official OpenAI SDK。推荐让成熟 SDK 承担 HTTP、streaming、timeout 和 typed response，FIN 只留薄 capability adapter；但 P0 必须显式设置 max_retries=0，不能让 SDK 在 FIN attempt/receipt 之外透明重试。[DeepSeek API quickstart](https://api-docs.deepseek.com/)、[OpenAI Python SDK retries](https://github.com/openai/openai-python#retries)

wire-compatible 不等于 semantic-compatible。必须明确：

- chat vs responses；
- thinking/non-thinking；
- JSON/tool schema；
- complete/incomplete/failed；
- unsupported 或 silent ignored parameters；
- usage/request ID；
- retry count；
- model/deployment/profile。

Retry 硬门：

- 默认 max_retries=0；
- 只有 Owner 批准的 task-specific retry policy 才能开启；
- 每次 wire attempt 都有独立 request hash、idempotency key、开始/终局 receipt、provider request ID 和 exact retry ordinal；
- FIN execution attempt 与 wire attempts 分开记录；
- 未证明 provider-side idempotency 时，timeout/connection reset 终止为 unknown_external_completion 或 duplicate_risk，不得透明重试；
- SDK internal retry count 必须可证明为 0 或与 receipt exact 对齐。

canonical 合同链：

~~~text
Pydantic strict model
  → canonical JSON Schema
  → provider-specific schema compiler
  → provider structured output
  → Pydantic post-validation
  → bounded repair or immutable failure
~~~

官方依据：[Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)、[Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)、[JSON Schema 2020-12](https://json-schema.org/draft/2020-12)

### 11.2 LiteLLM：两个以上 qualified provider 后再用

LiteLLM 提供多 provider、统一错误、fallback、virtual keys、budgets 和 proxy。[LiteLLM docs](https://docs.litellm.ai/docs/)

当前不采用的原因：

- 只有一个主要 provider；
- 多一个 retry/fallback 语义源；
- 多一个 secrets/logging surface；
- 自动 fallback 可能把任务交给未经资格验证的模型；
- budget 路径需要数据库与 fail-closed 验证。

触发条件：

- 至少两个 provider 已通过同一 FIN gold；
- centralized key/quota/budget 是真实需求；
- capability allowlist；
- 禁止未授权跨模型自动 fallback；
- 每次路由记录具体 provider/model/deployment/profile。

### 11.3 MCP：只做外部 typed connector boundary

MCP 适合一个只读 source lookup、第三方数据 connector 或受控本地工具，不适合把内部每个函数 MCP 化，也不替代 workflow、consent、authorization 或 Evidence admission。[MCP architecture](https://modelcontextprotocol.io/specification/2026-07-28/architecture)、[MCP tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

建议 P1 从一个只读 connector 开始，固定 protocol version 并做 conformance tests。

## 12. trace、eval、experiment 与 artifact lineage

### 12.1 OTel + OpenInference 是 trace 标准

OpenTelemetry 提供通用 trace/metric/log 语义，OpenInference 补充 LLM/RAG spans。[OpenTelemetry semantic conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)、[OpenInference specification](https://github.com/Arize-ai/openinference/blob/main/spec/README.md)

记录：

- product/S-stage/contract/attempt；
- node/call/tool ID；
- provider/model/deployment/profile；
- prompt/schema/artifact hash；
- tokens、cost、latency；
- retrieval/tool/evaluator spans；
- status/failure code。

默认不记录：

- API key；
- 未脱敏私有全文；
- chain-of-thought；
- 受许可限制的整段原文。

使用 hash、长度、source ID、locator 和受控 artifact URI。

### 12.2 MLflow 作为当前主要 backend

MLflow 支持 runs、params、metrics、code version、artifacts、datasets、traces、evaluation 和 OTel ingestion；Apache-2.0，本地 SQLite 可起步，后续迁 PostgreSQL/object store。[MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)、[MLflow datasets](https://mlflow.org/docs/latest/genai/datasets/)、[MLflow trace evaluation](https://www.mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/traces/)、[MLflow OTel ingestion](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/ingest/)

正确关系：

~~~text
FIN immutable manifest/receipt = authority
MLflow = run/metric/trace/artifact URI/digest/lineage view
~~~

删除 MLflow 记录不得改变 FIN Evidence 或 release 状态。冻结 gold/corpus 仍由不可变 manifest 绑定。

本机 `3.15.2` qualification 已证明 tracking server、SQLite backend、file artifact、params/metrics 和官方 client readback；同时暴露三条硬边界：Windows job execution backend 不可用、生产 metadata/object store 未证明、`cryptography<50` 与当前安全修复发生冲突。因此 MLflow 仍是主要 backend candidate，但不是已获生产采用权的 winner；在升级/替换能关闭 transitive vulnerability 且 PostgreSQL/object store/backup 通过前，只能用于隔离实验。

### 12.3 Phoenix、Langfuse、LangSmith 与 Ragas

| 候选 | 强项 | 当前结论 |
|---|---|---|
| Phoenix | RAG trace、retrieval inspection、datasets/experiments UX | 与 MLflow 做一次内部 UX 比较；ELv2 下不默认做对外 hosted product |
| Langfuse | 多用户生产 observability、datasets、annotation | self-host 组件较重；多用户生产触发后 |
| LangSmith | LangGraph/LangChain 观测/eval UX | 托管和锁定较强；不做主 backend |
| Ragas | context precision/recall、faithfulness 等 metrics | 选择性 metric library，不做 release authority |

官方依据：

- [Phoenix](https://arize.com/docs/phoenix/)
- [Phoenix license](https://github.com/Arize-ai/phoenix/blob/main/LICENSE)
- [Langfuse observability](https://langfuse.com/docs/observability/overview)
- [Langfuse self-hosting](https://langfuse.com/self-hosting)
- [LangSmith observability](https://docs.langchain.com/langsmith/observability-concepts)
- [Ragas metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)

评测层级：

1. schema、ID、numeric、locator：deterministic；
2. qrel、entity、period、unit、source role：FIN gold；
3. semantic support/completeness：人工 gold 校准后的 LLM judge；
4. material release：作者分离 human + FIN gate。

## 13. schema、preflight、policy、identity 与 secrets

### 13.1 先把 preflight 收敛成数据驱动合同

不应把 14,870 行 project_os_preflight.py 全部机械翻译成另一种 DSL。第一步是：

- Pydantic canonical models；
- contract-version registered validators；
- data-driven invariant registry；
- 去掉 attempt-specific copied branches；
- 只留 product/S-stage/attempt、immutable failure、authority 和金融硬边界。

### 13.2 OPA

OPA 适合 principal/action/resource、tool allow/deny、多租户预算、跨服务统一 policy、bundle 和 decision log；不适合判断财务 claim、period、Evidence 或 R14 event semantics。[OPA integration](https://www.openpolicyagent.org/docs/integration)、[OPA decision logs](https://www.openpolicyagent.org/docs/management-decision-logs)

触发条件：多个服务/租户需要独立、动态更新同一策略。当前暂缓。

### 13.3 企业 IAM/SCIM

OIDC/SAML/SCIM、provisioning/deprovisioning、MFA、audit log 和 secrets 不应自己造。

候选取决于部署战略：

- managed enterprise onboarding：WorkOS/同类，支持 SAML/OIDC SSO 和 Directory Sync/SCIM；[WorkOS SSO/Directory Sync](https://workos.com/docs)、[Directory Sync](https://workos.com/docs/directory-sync)
- Azure-first：Microsoft Entra；
- self-hosted identity：Keycloak 作为 OIDC/SAML/identity broker 候选；SCIM 另做适配/采购；
- cloud-native secrets：AWS/Azure/GCP secret manager 按部署选一。

当前尚无多租户部署、客户 IdP、region 和 procurement 约束，不能假装已经有唯一供应商答案。现在只冻结原则：采用成熟 IAM，不把认证密码、SCIM 和企业 IdP 兼容写成 FIN 自研核心。

## 14. Human review、grounding、citation 与报告

### 14.1 FIN Workbench 应留下，但变薄

成熟平台负责：

- run list、trace waterfall；
- token/cost/latency；
- generic log/artifact；
- experiment comparison；
- generic evaluator 和 annotation utility。

FIN Workbench 负责：

- source role、issuer、as-of、period、unit；
- claim↔locator；
- conflict/amendment；
- admit/reject/reopen；
- material numeric/financial derivation；
- author-separated review；
- release gate 与 immutable audit receipt。

Label Studio 一类工具可用于 gold/corpus 标注，不应直接成为产品 Evidence admission 权威。[Label Studio documentation](https://labelstud.io/guide/)

### 14.2 Grounding 不是事实真值

可采用：

- Ragas faithfulness/context metrics；
- Google Check Grounding 作为 shadow；
- ALCE citation correctness/completeness 方法；
- RAGTruth hallucination/contradiction 测试方法；
- LLM claim support/contradiction judge。

但任何 supplied facts 本身可能错误，grounding score 不知道 FIN 的 source role、period、unit、as-of 或 admission。

官方依据：

- [Google Check Grounding](https://cloud.google.com/generative-ai-app-builder/docs/check-grounding)
- [ALCE paper](https://aclanthology.org/2023.emnlp-main.398/)
- [RAGTruth paper](https://aclanthology.org/2024.acl-long.585/)

FIN 主路径：

1. claim type；
2. canonical Evidence；
3. deterministic entity/value/unit/period；
4. page/bbox/table cell；
5. source role/PIT/admission；
6. model semantic support/contradiction；
7. disagreement → human。

### 14.3 Quarto + Pandoc + CSL

Quarto/Pandoc/CSL 能成熟承接 bibliography、citation、cross-reference、table/figure numbering 和 HTML/PDF/DOCX。[Quarto authoring](https://quarto.org/docs/manuscripts/authoring/)、[Quarto cross references](https://quarto.org/docs/authoring/cross-references.html)、[Pandoc manual](https://pandoc.org/MANUAL.html)、[CSL docs](https://docs.citationstyles.org/)

正确顺序：

~~~text
FIN typed report sections
  claim_id / evidence_id / locator / numeric fact / citation metadata
        ↓
FIN pre-render validation
        ↓
Quarto/Pandoc/CSL rendering
        ↓
PDF/DOCX/HTML visual QA
~~~

Renderer 不负责判断 citation 是否真的支持 claim。

## 15. Graph retrieval 与一体化平台

### 15.1 GraphRAG：HOLD

Microsoft GraphRAG 官方仓库把项目定位为 research project，并进入较低维护强度；标准 pipeline 的 LLM graph extraction 成本高，适合 corpus-level/global sensemaking，不是当前默认检索底座。[Microsoft GraphRAG](https://github.com/microsoft/graphrag)、[query modes](https://microsoft.github.io/graphrag/query/overview/)

只有以下题型在 frozen hybrid baseline 上系统性失败，才开启 graph：

- 跨 filing 多跳关系；
- 多公司供应链/子公司/董事关系；
- corpus-level theme/risk；
- 需要可解释路径而非单文档召回。

若 gate 通过，Neo4j GraphRAG 是现实 challenger；每条 edge 仍需 source span、as-of、valid-from/to，LLM edge 只能是 candidate。[Neo4j GraphRAG](https://neo4j.com/docs/neo4j-graphrag-python/current/)

Kùzu 官方仓库已归档，不作为新产品底座。[Kùzu](https://github.com/kuzudb/kuzu)

### 15.2 RAGFlow：只做隔离 benchmark

RAGFlow 成熟覆盖 document parsing、chunk、hybrid retrieval、rerank、citation、KB、Agent 和 UI；但整体迁入会建立第二套 canonical schema、runtime 和产品栈。[RAGFlow](https://github.com/infiniflow/ragflow)

允许用法：

- 同 corpus/query 黑盒 benchmark；
- parser/retrieval/rerank/citation UI 参考；
- 只导出 candidates；
- 不写 FIN authoritative objects。

### 15.3 Dify：当前排除

Dify workflow/human input/app publishing 很成熟，但与 FIN control plane 高度重叠，且许可证和产品 UI/多租户限制需要单独处理。[Dify license](https://github.com/langgenius/dify/blob/main/LICENSE)

当前不把 Dify/RAGFlow/任何 whole platform 当 FIN 准确性的成品答案。

## 16. 许可、隐私与锁定重点

| 项目 | 重点 |
|---|---|
| Docling | core/model license 分开核 |
| MinerU | 有附加条件，不当成纯 Apache-2.0 |
| Elastic | ELv2/商业订阅与云成本 |
| Phoenix | ELv2，内部用与对外 hosted 边界 |
| Langfuse | open-core，生产 self-host 依赖重 |
| Jina model | 多个权重 NC，商业需许可 |
| RAGFlow | Apache-2.0，但整体栈和迁移锁定高 |
| Dify | 修改版 Apache 路线，产品使用限制需法务核 |
| WorkOS/LlamaParse/Cohere/cloud AI | 数据区域、retention、training/use-of-data、价格和退出方案 |
| Quarto/Pandoc | CLI、extension、bundled renderer 许可分开看 |

任何 managed service 必须冻结：

- region；
- retention/delete；
- training/use-of-data；
- model/parser version；
- request/response logging；
- encryption/key ownership；
- price ceiling；
- timeout/retry；
- export/exit plan。

## 17. 共同资格门

这些门是未来 Owner 授权后的验收标准，不是现在的执行权限。

### G0：权威与输入冻结

- product/S-stage/contract/attempt 映射；
- corpus/gold/query/raw digest；
- framework state vs FIN authority；
- source/domain/file-type allowlist、privacy class、sandbox/egress profile；
- rollback/export；
- 失败不可变。

失败即停：

- 新框架要求合并 product 与 attempt；
- 要改写旧失败；
- 无法表达 immutable artifact；
- 要弱化 release/admission。

### G1：无模型 fixture compatibility

对 provider/parser/search adapters 用 saved fixtures：

- success/timeout/rate/error；
- streaming complete/incomplete/failed；
- empty/truncated/malformed JSON；
- unsupported parameter；
- schema post-validation；
- SDK max_retries=0 与 internal retry count exact；
- 每个 wire attempt 的 request hash/idempotency key/start-terminal receipt/provider request ID；
- timeout/connection reset → unknown_external_completion/duplicate_risk，不透明重试；
- retry/idempotency；
- MIME/magic mismatch、zip bomb、malware、resource limit、SSRF/redirect、active content、prompt/tool/path/query injection 安全 fixtures。

### G2：被动 trace/eval 导入

用现有 R14 frozen artifact：

- 27,026 / 239 / 277 counts/digests 不变；
- product/S-stage/attempt 可追；
- 无 key/private text 泄漏；
- backend 删除不改权威状态。

### G3：document/search frozen challenger

- parser/source/version pinned；
- page/bbox/cell provenance；
- exact identifier、period、unit、table、negative slices；
- BM25/vector/hybrid 消融；
- p95、RAM、index rebuild；
- critical financial slice 不退化。

### G4：LLM semantic shadow

- exact source span；
- strict schema + Pydantic；
- hard validator；
- abstain/disagreement；
- case-correct human-adjudicated gold 与预注册 calibration（若使用 calibrated 一词）；
- R14 corpus/failure/validator/regression baseline 不改；已知错误 parser output 不是真值 oracle；
- RC-S1-109/110 在 same-stage replacement 完整通过并由 Owner 裁决前保持 open；
- 不能自动 Evidence promotion。

### G5：LangGraph checkpoint/HITL/failure injection

注入：

- node 前/中崩溃；
- provider call 后、receipt 前；
- receipt 后、checkpoint 前；
- restart、duplicate resume；
- approve/deny/timeout；
- schema upgrade；
- checkpointer unavailable。

要求：

- 状态恢复准确；
- 副作用幂等；
- 无法证明不重复时写 duplicate-risk receipt 并停止；
- SDK internal retry 默认关闭；每次 wire attempt 与 FIN attempt 分层可追；
- provider completion 不确定时不得自动 resume/retry；
- old/new attempt 一一映射；
- 可回退。

### G6：金融语义 parity

- issuer/as-of/period/unit；
- claim locator；
- numeric derivation；
- admission 不放松；
- old failure 不被框架“成功”掩盖。

### G7：运维、许可、隐私、退出

- version pin、SBOM、license review；
- 每个组件固定 supported deployment profile 与 exact Windows/WSL2/docker/remote/managed 路径；
- Windows local run/recovery、locking、rename、long-path、cross-volume、WAL/SQLite 和 crash proof；
- malware signature/version、sandbox image、resource limit、network egress 与 SSRF policy pin；
- offline export；
- backup/restore；
- retention/delete；
- upgrade rollback；
- framework 退出后 canonical artifact 可恢复。

只有 G0–G7 通过，才允许逐步删除旧代码。

## 18. 推荐 P0/P1/P2 顺序

### P0：Owner 批准后，先做无生产切换 qualification

2026-08-31 状态：Owner已批准dependency/PostgreSQL/单Dagster vertical子集。Dagster/Prefect + MLflow + OTel + OpenLineage + DVC的早期lab证据保留；PostgreSQL Docker环境阻断已解除并形成历史可行性证据；当前hardened候选的final clean receipt、Docker真实job、镜像扫描、全量回归和独立复审仍待跑。下面其余data/model/product pilots未获自动权限，不能因一个控制面纵切而批量执行。

1. Pydantic 单一合同源 spike；
2. untrusted-content intake security fixture/sandbox proof；
3. official OpenAI SDK → DeepSeek fixture parity，max_retries=0；
4. OTel/OpenInference span schema；
5. MLflow 对冻结 artifact 的只读导入；
6. LangGraph 单 vertical failure-injection；
7. Docling vs MinerU frozen hard-PDF；
8. pgvector vs OpenSearch frozen retrieval；
9. LangExtract pattern + DS Flash same-stage replacement shadow；
10. Quarto/Pandoc/CSL reader report rendering proof。

每项单独 attempt、单独变量、单独 stop gate。不能十项一起大重写。

### P1

- MCP 一个只读 connector；
- Ragas 选择性 metrics；
- Label Studio gold annotation；
- Phoenix vs MLflow 一次内部 UX 比较；
- DVC large-artifact pilot；
- 一个 managed parser/reranker ceiling。

### P2：触发后

- Temporal；
- LiteLLM；
- OPA；
- Langfuse；
- enterprise IAM/SCIM；
- cloud WORM/object store；
- Neo4j/GraphRAG。

## 19. 当前明确不做

- 不修改 R14；
- 不开 R15/R16；
- 不跑 formal；
- 不直接执行外源；
- 不下载/调用 4B；
- 不启动 reranker；
- 不做 Evidence admission；
- 不做 S2/S3/new report；
- 不整体迁入 RAGFlow/Dify；
- 不部署多套 parser/vector DB/orchestrator/trace backend；
- 不删除或覆盖历史 artifacts；
- 不以供应商 benchmark 宣称 FIN product pass。

## 20. Owner 决策菜单

Steps 1–3 结果出来后，建议 Owner 下一步只决定，不把多个 data/model/product pilot 一次性并发打开：

1. 是否批准总体 Build/Adopt/Hold/Retire 边界；
2. R14 选 A 满足 S1/128 全部验收门后 legacy，还是 B 在 RC-S1-109/110 继续 open、old parser 只作 baseline、human-adjudicated gold 作真值的前提下证明同阶段 replacement；
3. 已决定：Dagster为外层workflow primary candidate、Prefect为challenger；dependency source/lock、PostgreSQL本地资格画像和单vertical仅获候选实施授权，final bounded adoption仍等待clean-commit证据签发；
4. 已决定：只接一条S2 fact-mart shadow vertical，不做全仓迁移；其后先由Owner选择下一条有用户价值的vertical；
5. pgvector/OpenSearch 是否都进入后续 frozen A/B；
6. managed ceiling 的云战略：none / Azure / AWS / GCP / vendor SaaS；
7. MLflow 是等待无漏洞 upstream 组合，还是另测 Phoenix/其他 backend；
8. 何时才触发 Temporal/LiteLLM/OPA/IAM。

在明确批准前，本文件只有推荐权，没有执行权。
