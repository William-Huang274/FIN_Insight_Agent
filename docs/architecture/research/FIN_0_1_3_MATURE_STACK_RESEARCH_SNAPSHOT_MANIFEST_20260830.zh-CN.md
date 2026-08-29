# FIN 0.1.3 成熟技术栈调研来源与版本资格快照清单

日期：2026-08-30
状态：LANDSCAPE SOURCE SNAPSHOT / EXACT BUILD UNPINNED / LEGAL AND RUNTIME QUALIFICATION PENDING
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

除明确写为 PINNED 的项以外，全部视为 UNPINNED。Owner 批准 P0 后，每个实际 challenger 必须新增机器可读 qualification manifest，至少绑定：

- package/version/tag/commit；
- source URL 和访问时间；
- source/license file digest；
- model repo/revision/weight/tokenizer digest；
- Python/Java/CUDA/driver/OS/container image；
- config/schema/prompt digest；
- region/retention/training/use-of-data/pricing snapshot；
- SBOM 与 transitive license review；
- export/rollback/exit plan。

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

## 4. 本轮没有验证的事项

- 任一 package 在当前 host 实际安装、启动或恢复；
- 任一模型在 FIN corpus 上的质量；
- 任一 cloud/managed service 的实时价格、region、retention、training/use-of-data；
- 任一许可证的正式法律意见；
- exact SBOM 或 transitive license；
- current Windows/WSL2/Docker/CUDA driver compatibility；
- upstream rolling page 在未来日期是否仍保持同一内容。

因此，主决策包中的 ADOPT、CHALLENGER、CEILING 都只是进入资格验证的推荐，不是 production qualification。
