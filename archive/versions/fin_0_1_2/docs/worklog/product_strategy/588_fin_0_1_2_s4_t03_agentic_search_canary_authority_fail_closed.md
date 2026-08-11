# 588 — FIN 0.1.2 S4-T03 Agentic Search canary authority fail-closed

日期：2026-08-04
任务：`FIN-0.1.2-S4-T03-NVDA-BOUNDED-AGENTIC-SEARCH-CURRENT-CANARY-AUTHORITY-DECISION`

## 结论

权限决策范围通过，但 NVDA current Agentic Search canary 的 execution authority 必须 fail closed；没有签发 admission，也没有执行搜索、来源访问、工具、模型、Provider、Run 或 Artifact。

首因是项目自己的 T03 执行集成缺口，不是 DeepSeek 不遵循、Provider transport 失败或外部数据不存在。T02 已经正确证明 EvidenceRequest、metadata route、candidate ceiling、parser/citation qualification 和 false-promotion 边界，但这些是“搜索意图与验收条件”，不是可执行搜索。

## 发现了什么

1. T02 使用的四个 metadata route ID 在任何 Python executor/route registry 中都没有绑定。
2. 三份 NVDA request 只有 objective digest 和 metadata route，没有 immutable query、source locator、domain allowlist、adapter snapshot 或 parser binding。
3. `NonExecutingLocalRetrievalSkeleton` 明确不调用 adapter；LangGraph 在没有注入 callback 时只保留 `state_stub`。
4. `web_evidence_snapshot` 只把调用方给定的 URL 包装成 `context_only` metadata，artifact path 为空；它不是 HTTP fetch 或 source capture 证据。
5. 现有 Provider capture 解决的是模型 request/output，不是来源 request/response 的 capture-before-parse。T03 也没有 fresh WorkUnit/Attempt/Run envelope、issuer、runner 和 typed terminal result。

因此如果现在签发 live，可能出现三种假绿：route 名字存在但没有执行；URL metadata 被当成已抓取来源；historical fixture 或模型叙事被当成 current Evidence。三者都会直接破坏金融研究的引用、时间口径和可追溯性。

## 选择的受控后继

下一项仍在 S4-T03，且只能是一个合并的零调用实现包：

`FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该包需要一次补齐：

- `ExecutableSearchRequest`：query、locator、source policy、allowlist、adapter、parser、as-of 全部精确绑定；
- metadata-to-executable adapter registry；
- 只读 BM25/object-BM25、relationship graph、exact-value SQL adapters；
- 受控 SEC official route 与单一 NVDA IR fallback；
- source request/response 在 parse 前原子保存、内容寻址、受限访问与 readback；
- fresh canary identity envelope、issuer、runner、typed terminal result；
- candidate-to-current-Evidence gate，以及 T03 不得 writer-citable/进入 Judgment/生成业务 Artifact 的边界。

预期 canary 上限被冻结为 1 case / 3 requests / 2 source network calls / 8 local retrieval-or-tool invocations / 0 retry / 1 controlled fallback / 0 model calls / 0 provider calls / USD 0 paid API / 300 seconds。这个预算只属于未来实现后的另行 admission，不是本次授权。

## 为什么没有立即 live

live 不能证明一个尚不存在的 adapter binding，也不应该用付费或外部调用来发现已知的本地合同缺口。先用 fixture、mutation 和 exact source-capture failure 注入证明结构，再另行签发一次受控 canary，才是最短路径。

全局产品审视规则对本项产生了实际影响：没有把 T02 的“资格管道已准备”夸大为 F05 Agentic Search 已落地，也没有为了赶进度让模型生成搜索结果。产品能力增量因此诚实记为 0；工程增量是确定了真实 executable boundary 与唯一下一包。

## 证据与边界

- decision：`configs/releases/fin_ia_0_1_2_s4_t03_nvda_bounded_agentic_search_current_canary_authority_decision_v1_0.json`
- current projection：`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_38.json`
- focused authority contract：`7 passed`
- T03 closeout、Project OS、T01/T02、M6 EvidenceRequest/CandidateBundle/local retrieval/Evidence Gate 与历史 successor compatibility 合并回归：`119 passed`
- 新 issue：`RC-P36-114-fin-0-1-2-s4-t03-metadata-route-to-executable-search-and-source-capture-binding-gap`
- model/provider/execution network/source network/tool/retrieval/store/admission/Run/Artifact/Human：全部 0
- current NVDA R2：false
- S4-T04–T08、S5、release、production：未开始或未获资格

相邻回归还暴露了一个历史测试边界：T02 implementation 把当时的 closeout test 作为 byte-addressed immutable binding，而该测试内部又读取 mutable backlog/ledger 的“当前最后一项”。进入 T03 后直接修改它会破坏 T02 不可变证据；原文件因此保持原 SHA，不重写。当前 v2.38/backlog/ledger 的兼容性由新增 T03 closeout test 严格验证，不把旧 T02 快照测试当成 current mutable-state gate。该现象不阻断本次 authority decision，也不能通过改写旧 manifest 解决；后继实现应避免把 mutable-current 断言放进 immutable stage package。

最终双向 Project OS 预检首次发现 RC-P36-114 的概念性下划线 scope 与实际任务名不精确相等，导致 canary 负向探针意外 pass。没有放过该结果：以同 issue ID 追加 superseding row，改成 wildcard block＋精确 controlled-successor allowlist。修正后 next scope pass，canary scope blocked；这证明机器门禁与文档边界一致。

第二次负向探针又发现预检器只识别标准精确状态词，描述性 `open_T03_...` 不等于机器可读的 `open`。最终 latest row 使用 `status=open`，描述放入 `status_detail`；这项约束已进入回归。历史 issue 的全仓状态规范化另属 Project OS 治理债务，本项没有顺手扩张范围。

本次没有更新 financial research method registry：没有新增、提升或淘汰研究方法，只是关闭一个执行权限并定义检索基础设施边界。
