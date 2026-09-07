# FIN 0.1.3 成熟技术栈调研来源与版本资格快照清单

日期：2026-08-30
状态：LANDSCAPE SOURCE SNAPSHOT / PREDECESSOR DAGSTER+POSTGRES S2 SHADOW TESTED / CURRENT EXACT CANDIDATE FINAL CLEAN QUALIFICATION PENDING / DATA-MODEL-LEGAL QUALIFICATION PENDING
父决策包：[成熟技术栈全景与采用决策包](FIN_0_1_3_MATURE_TECH_STACK_LANDSCAPE_AND_ADOPTION_DECISION_PACKET_20260830.zh-CN.md)

## 1. 这份清单解决什么问题

主决策包引用的是滚动官方网页、仓库和标准。它们能支持 2026-08-30 时点的 landscape 判断，但不能自动构成可复现的生产 build。

本清单明确区分：

- observed source：本轮访问的官方入口；
- observed status：本轮据官方来源形成的高层事实；
- exact version snapshot：是否已固定 tag/commit/package/model digest；
- license snapshot：是否已固定 core/model/enterprise/hosted 条款；
- deployment profile：建议在哪种环境资格验证；
- blocker：进入 P0 前还缺什么。

除明确写为 PINNED 的项以外，全部视为 UNPINNED。每个实际 challenger 必须有机器可读 qualification manifest，至少绑定：

- package/version/tag/commit；
- source URL 和访问时间；
- source/license file digest；
- model repo/revision/weight/tokenizer digest；
- Python/Java/CUDA/driver/OS/container image；
- config/schema/prompt digest；
- region/retention/training/use-of-data/pricing snapshot；
- SBOM 与 transitive license review；
- export/rollback/exit plan。

### 1.1 2026-08-31 PINNED 控制面补充快照

以下子集已在 Z 盘隔离环境安装并真实运行，不能再归类为“未安装”；但 `PINNED/TESTED` 不等于 production adopted：

| Item | Exact snapshot | Runtime evidence | Remaining blocker |
|---|---|---|---|
| Python / resolver | Python `3.13.7` / uv `0.10.7` | 277-package unified hash lock 安装成功 | 生产依赖源尚未统一 |
| Prefect | `3.8.4` | 真实 FIN fact-mart 代码路径 + 确定性 DELL-shaped PIT fixture、native retry、state readback、最终 Z-only state PASS | 非现场 SEC 来源回放；默认 home 写入 caveat；只保留 challenger |
| Dagster / webserver / Postgres adapter | `1.13.20` / `1.13.20` / `0.29.20` | 同一确定性 fixture、native retry、persistent run、新进程 readback PASS | 非金融真值/source admission 资格；PostgreSQL storage 和生产 daemon/UI 未测 |
| MLflow | `3.15.2` | tracking server、metrics、artifact、client readback PASS | Windows job backend、PostgreSQL/object store、cryptography blocker |
| DVC | `3.67.1` | Z local remote push/pull、workspace+cache removal、digest exact PASS | `file://` Windows 失败；仅大型资产 conditional adopt |
| OpenLineage | `1.52.0` | FileTransport START/COMPLETE 同 run ID PASS | backend 未部署，当前不需要第二 lineage store |
| OpenTelemetry SDK/exporter | `1.44.0` | 4-span FIN slice PASS | collector/backend 与 privacy production proof pending |
| psycopg | `3.3.4` | package installed | PostgreSQL server未启动，连接/事务/锁全部未测 |
| compliance tooling | CycloneDX BOM `7.3.1` / pip-audit `2.10.1` / pip-licenses `5.5.5` | SBOM 277 components、license list 272 packages、audit 完成 | 3 个漏洞未关闭 |

固定文件：

- `requirements.in` SHA-256=`5e35ca47ee11ea1adef95cf81858f36068b729d88f03de7b4d508cea67572f73`；
- `requirements.lock` SHA-256=`5e252aefef18946160692f4a396ab6315f9b34942d8402ba543768cb4189dc1e`；
- 仓库 lab-only 重建 lock `scripts/qualification/requirements.lock` SHA-256=`ec3ccbd13d2a51acc3a067b3706e6f11747c7a79cbe99702d13a137256198782`，与实际 Z 盘 lock 的 277 个 package/version 条目完全一致；最小命令和状态目录约束见 `scripts/qualification/README.zh-CN.md`；
- CycloneDX SBOM SHA-256=`75fc7da0bba130264146e917a4cb3cdb7e9c45a17ea9c46107056b76ff53c96f`；
- vulnerability audit SHA-256=`176bbc02f5ff2c587e7e821c3da93e85efbb8a08050c6a3065602586f3ac1116`；
- qualification summary SHA-256=`c6750a23b729b80b769cb6c850a7320cded818ca9d50443f680d5c6afbea8150`。

实际漏洞：cryptography `49.0.0` / `PYSEC-2026-3552`（fix 50.0.0，但 MLflow 3.15.2 要求 `<50`）、diskcache `5.6.3` / `PYSEC-2026-2447`（审计时无 fix）、pytest `8.4.2` / `PYSEC-2026-1845`（fix 9.0.3）。因此本快照只可复现 control-plane fixture 实验，不可直接复制为 production lock，也不能用来声称真实 SEC 数据或金融真值已资格化。

## 2. 数据面来源快照

| Family | Official source observed 2026-08-30 | Observed status | Exact version / license snapshot | Qualification profile / blocker |
|---|---|---|---|---|
| SEC EDGAR APIs | [SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | official submissions/XBRL/bulk interface | API behavior UNPINNED；government source | rate/user-agent/schema/receipt fixture |
| XBRL standard | [XBRL Essentials](https://specifications.xbrl.org/xbrl-essentials.html) | fact concept/entity/period/unit/dimensions | standard version to pin | canonical mapping and amendment fixtures |
| xBRL-JSON | [Recommendation](https://www.xbrl.org/Specification/xbrl-json/REC-2021-10-13%2Berrata-2023-04-19/xbrl-json-REC-2021-10-13%2Bcorrected-errata-2023-04-19.html) | vendor-neutral interchange | recommendation URL observed；digest UNPINNED | round-trip and raw iXBRL lineage |
| Arelle | [Official repository](https://github.com/Arelle/Arelle) | XBRL/iXBRL processor and validation | package/tag/commit UNPINNED；Apache-2.0 observed | native_windows/docker fixture, taxonomy pin |
| Scrapy | [Concepts](https://docs.scrapy.org/en/latest/topics/concepts.html) | crawler queue/middleware/pipeline | package/tag UNPINNED；BSD-3-Clause observed | native_windows resume/rate/retry proof |
| Playwright | [Network](https://playwright.dev/docs/network) | browser/network/HAR/trace | package/browser revision UNPINNED；Apache-2.0 observed | existing repo use is not new contract qualification |
| warcio | [Official repository](https://github.com/webrecorder/warcio) | WARC request/response read/write | package/commit UNPINNED；Apache-2.0 observed | byte round-trip and S3/local path proof |
| Browsertrix | [Official repository](https://github.com/webrecorder/browsertrix) | browser archiving/WARC/WACZ | image/tag UNPINNED；AGPLv3 observed | not P0；future compliance need |
| Firecrawl | [Crawl docs](https://docs.firecrawl.dev/features/crawl) | managed crawl/JS rendering | API/model/pricing/retention UNPINNED；commercial | managed ceiling only |
| Crawl4AI | [Official docs](https://docs.crawl4ai.com/core/simple-crawling/) | local async browser crawl | package/commit/license digest UNPINNED | optional Scrapy/Playwright comparison |
| Unstructured | [Partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning) | partition/chunk/connectors | core/cloud/version/license split UNPINNED | connector-oriented challenger |
| Docling | [Document model](https://docling-project.github.io/docling/concepts/docling_document/) | layout/table/OCR/provenance | core/model/OCR versions and licenses UNPINNED | native_windows first; model and hard-PDF proof |
| MinerU | [Repository](https://github.com/opendatalab/mineru) | OCR/layout/table/formula | commit/model/CUDA/license digest UNPINNED；additional conditions observed | WSL2/docker first; legal/resource blocker |
| LlamaParse | [Official docs](https://developers.llamaindex.ai/llamaparse/parse/) | managed document parser | API/parser/model/region/price/retention UNPINNED | one managed ceiling only |
| Azure Document Intelligence | [Layout](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout) | managed layout/table/OCR | API/model/region/pricing/container matrix UNPINNED | Azure-first only |
| Google Document AI | [Layout parser](https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk) | managed structured layout/chunks | processor/model/region/pricing UNPINNED | GCP-first only |
| AWS Textract | [Official docs](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-analyzing.html) | managed text/forms/tables/layout | API/model/region/pricing UNPINNED | AWS-first only |
| PostgreSQL | [Official docs](https://www.postgresql.org/docs/current/) | relational canonical metadata/transaction/PITR | major/minor/build/license digest UNPINNED；PostgreSQL License observed | native_windows pilot; backup/PITR/locking |
| pgvector | [Official repository](https://github.com/pgvector/pgvector) | exact/HNSW/IVFFlat vectors | extension version/build/commit UNPINNED | Windows package/build blocker |
| OpenSearch | [Hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/) | BM25/vector/fusion/filter/pipeline | server/plugin/JVM/image UNPINNED；Apache-2.0 observed | docker/remote Linux preferred |
| Elasticsearch | [Hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search) | mature commercial/managed search | version/license/subscription UNPINNED；ELv2/commercial paths observed | commercial ceiling |
| Qdrant | [Hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/) | dense/sparse/multi-stage/multi-vector | version/image/commit UNPINNED；Apache-2.0 observed | only multi-vector trigger |
| BGE-M3 | [Model card](https://huggingface.co/BAAI/bge-m3) | multilingual retrieval model | repo revision/weights/tokenizer/license digest UNPINNED | no call authority |
| BGE reranker v2-m3 | [Model card](https://huggingface.co/BAAI/bge-reranker-v2-m3) | local cross-encoder reranker | repo revision/weights/tokenizer UNPINNED；Apache-2.0 observed | frozen top-N/resource proof |
| Cohere Rerank | [Official overview](https://docs.cohere.com/v2/docs/rerank-overview) | managed reranker | API/model/pricing/retention/deployment UNPINNED | managed ceiling only |
| Jina Reranker | [Official page](https://jina.ai/reranker/) | managed/local reranker family | exact model/license UNPINNED；NC restrictions observed for relevant weights | exclude absent commercial license |
| Parquet | [Official docs](https://parquet.apache.org/docs/) | portable columnar snapshot | format version/writer package UNPINNED | schema/version/round-trip proof |
| DuckDB | [Parquet docs](https://duckdb.org/docs/stable/data/parquet/overview) | embedded local analytics | engine/storage version UNPINNED | audit only, not online authority |
| S3 Object Lock | [AWS docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) | versioned WORM retention/legal hold | cloud region/policy/pricing UNPINNED | productization trigger |
| MinIO Community | [Official repository](https://github.com/minio/minio) | archive/maintenance and AGPL risk observed | exact archive/license snapshot UNPINNED | excluded as new default |
| ClamAV | [Official docs](https://docs.clamav.net/) | malware scanning engine | engine/signature/container/license UNPINNED | intake security pilot |
| OWASP upload/SSRF/prompt injection | [File upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | security control guidance | guidance revision UNPINNED | translate to executable fixtures |

## 3. 语义与控制面来源快照

| Family | Official source observed 2026-08-30 | Observed status | Exact version / license snapshot | Qualification profile / blocker |
|---|---|---|---|---|
| LangExtract | [Official repository](https://github.com/google/langextract) | structured LLM extraction with source alignment | package/commit/provider plugin/license digest UNPINNED | pattern candidate; human gold required |
| DeepSeek JSON/tool | [JSON mode](https://api-docs.deepseek.com/guides/json_mode/) | JSON/strict tool capabilities and caveats | model alias/API/schema subset/pricing UNPINNED | no call authority; fixture first |
| OpenAI Python SDK | [Official repository](https://github.com/openai/openai-python) | HTTP/streaming/typed transport and retry controls | package version/commit/license UNPINNED | max_retries=0 P0 fixture |
| Pydantic | [Strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) | strict validation/JSON Schema | package/Python/schema draft UNPINNED；MIT observed | one canonical contract source |
| LangGraph | [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Agent state/checkpoint/interrupt/HITL | package/checkpointer/schema/license UNPINNED；MIT observed | native_windows pilot; replay/idempotency proof |
| Temporal | [Workflow execution](https://docs.temporal.io/workflow-execution) | durable distributed workflow | server/SDK/storage/image/license UNPINNED；MIT observed | trigger-gated, not P0 |
| Haystack | [Pipelines](https://docs.haystack.deepset.ai/docs/pipelines) | typed data/RAG pipelines | package/commit/license UNPINNED；Apache-2.0 observed | data plane only, not second global state |
| LiteLLM | [Official docs](https://docs.litellm.ai/docs/) | multi-provider proxy/routing/budget | version/license directory/DB behavior UNPINNED | two qualified providers trigger |
| MCP | [Architecture 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/architecture) | external tool/resource protocol | protocol version observed；SDK commit/license UNPINNED | one read-only connector P1 |
| OpenTelemetry | [Semantic conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/) | telemetry standard | spec/SDK/exporter versions UNPINNED | schema/privacy/collector proof |
| OpenInference | [Specification](https://github.com/Arize-ai/openinference/blob/main/spec/README.md) | LLM/RAG span semantics | spec/package/commit UNPINNED | privacy defaults and field mapping |
| MLflow | [Tracking](https://mlflow.org/docs/latest/ml/tracking/) | run/metric/artifact/dataset/trace/eval | package/server/schema/license UNPINNED；Apache-2.0 observed | native_windows local pilot; export/restore |
| Phoenix | [Official docs](https://arize.com/docs/phoenix/) | RAG/LLM trace/eval UX | version/license digest UNPINNED；ELv2 observed | internal UX bakeoff only |
| Langfuse | [Official docs](https://langfuse.com/docs/observability/overview) | production observability/datasets/annotation | version/image/open-core split UNPINNED | trigger-gated, operationally heavy |
| Ragas | [Metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) | RAG/eval metric library | package/evaluator/model/prompt UNPINNED；Apache-2.0 observed | assistive only |
| OPA | [Integration](https://www.openpolicyagent.org/docs/integration) | cross-service policy decision engine | binary/bundle/Rego/version/license UNPINNED | multi-service/tenant trigger |
| WorkOS | [Official docs](https://workos.com/docs) | managed SSO/Directory Sync/SCIM | product/API/region/pricing/retention UNPINNED | enterprise deployment trigger |
| Label Studio | [Official docs](https://labelstud.io/guide/) | generic annotation workflow | version/license/open-core split UNPINNED | gold annotation only |
| Quarto | [Authoring](https://quarto.org/docs/manuscripts/authoring/) | citations/crossref/multi-format rendering | CLI/version/license/dependency digest UNPINNED | native_windows render/visual proof |
| Pandoc | [Manual](https://pandoc.org/MANUAL.html) | document conversion/citations | binary/version/license UNPINNED | renderer pin and visual QA |
| CSL | [Specification/docs](https://docs.citationstyles.org/) | citation style standard | spec/style file/version UNPINNED | style and locale pin |
| GraphRAG | [Official repository](https://github.com/microsoft/graphrag) | research graph RAG and maintenance caveat observed | commit/config/model/license UNPINNED；MIT observed | HOLD until hybrid failure gate |
| Neo4j GraphRAG | [Official docs](https://neo4j.com/docs/neo4j-graphrag-python/current/) | graph retrieval framework | package/server/license/subscription UNPINNED | graph trigger only |
| Kùzu | [Official repository](https://github.com/kuzudb/kuzu) | archived repository observed | archive commit/license snapshot UNPINNED | excluded as new default |
| RAGFlow | [Official repository](https://github.com/infiniflow/ragflow) | whole RAG/KB/Agent platform | version/images/dependencies/license UNPINNED；Apache-2.0 observed | isolated benchmark only |
| Dify | [License](https://github.com/langgenius/dify/blob/main/LICENSE) | whole LLM app/workflow platform | version/license/hosted restrictions UNPINNED | excluded as current core |

## 4. 仍未验证的事项与边界

- 上述控制面子集以外的 package/model 在当前 host 的实际安装、启动或恢复；
- 任一模型在 FIN corpus 上的质量；
- 任一 cloud/managed service 的实时价格、region、retention、training/use-of-data；
- 任一许可证的正式法律意见；
- data/model 候选的 exact SBOM 或 transitive license；
- PostgreSQL、pgvector、OpenSearch、LangGraph、Docling、MinerU、Quarto/Pandoc 的 current Windows/WSL2/Docker/CUDA compatibility；
- PostgreSQL transaction/lock/restart/backup：Docker Desktop startup 环境阻断；
- 控制面 lock 的 3 个漏洞修复与 production deployment profile；
- upstream rolling page 在未来日期是否仍保持同一内容。

因此，主决策包中的 data/model ADOPT、CHALLENGER、CEILING 仍只是进入资格验证的推荐；控制面子集也只达到 qualification evidence，不是 production qualification、迁移完成或产品 PASS。

## 5. 2026-08-31 locked profile successor snapshot

本节取代第 4 节中“PostgreSQL环境阻断”和“旧 control-plane lock漏洞未隔离”两项前序状态；其他未验证事项继续有效。

| Family | Exact build | Locked profile result | Remaining boundary |
|---|---|---|---|
| uv project | uv `0.10.7`; root `pyproject.toml + uv.lock` | single-source candidate；当前lock=`157 records`并含独立locked supply tooling与setuptools artifact hashes；pre-successor v2 actual env=`33/86/88`且当时Python known vulnerabilities=`0/0/0` | 最终fresh env、平台marker、镜像/Node/OS、license legal与未晋升extras仍须分别审计 |
| Dagster | `1.13.20` | optional `control-plane` extra、Docker target与一条S2 shadow adapter candidate已实现；旧attempt有PostgreSQL run/event readback可行性证据 | 当前hardened clean-commit receipt与Docker真实job待跑；schedule/sensor user state未测，daemon/operator/production deployment未资格 |
| dagster-postgres | `0.29.20` | 旧attempt实际写入PostgreSQL 16.15并由新instance读回run/event；当前hardened candidate待clean successor | schedule/sensor未测；HA/TLS/secret rotation/PITR未资格 |
| psycopg | `3.3.4` + binary；qualification-only overlay | 旧attempt有host transaction/UNIQUE/advisory-lock/restart/dump-restore可行性证据；最终runner将完整版本/inventory绑定receipt | 不属于control-plane镜像；application pool/timeout/failover未资格 |
| PostgreSQL | official `16.15-alpine`; `postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685` | 旧attempt有local loopback、Z data、native transaction/lock、restart、dump/restore可行性证据；当前host-roundtrip hardened successor待跑 | 不是production topology或canonical cutover |
| real FIN vertical | existing S2 CompanyFacts CLI + domain-thin Dagster op | 旧attempt在DELL/MU/NVDA local source-bound captures得到1,319 observations、24/24 qrels与legacy/Dagster semantic exact；最终commit/Docker复证待跑 | 不新增事实、Evidence、S2 bridge或产品能力 |
| LangGraph | not installed | `HOLD / NOT TESTED`，该确定性数据任务没有 checkpoint/HITL/Agent graph | 仅未来内层 Agent vertical触发 |

旧76-package control-plane manifests已被后续dagster-webserver/filelock/profile split取代。`...\manifests\20260831_locked_profiles_v2`记录pre-supply-lock actual env core/control-plane/combined=`33/86/88`与当时0 known Python vulnerabilities；当前157-record lock的final successor尚待clean commit后生成，因此v2不得作final。旧277-package comparison lab的三个漏洞仍是真实历史，但该组合没有被复制进现行optional profile。

`20260831T034026Z-a8700e1b`与`040515`已降为历史可行性证据。最终exact attempt必须来自候选实现提交后的clean HEAD、全新combined locked env与当前hardened runner；在该successor生成前，dependency/PostgreSQL/单vertical只能称implementation candidate，不能称最终bounded adoption。完整失败链、路径和边界见S1/131。
