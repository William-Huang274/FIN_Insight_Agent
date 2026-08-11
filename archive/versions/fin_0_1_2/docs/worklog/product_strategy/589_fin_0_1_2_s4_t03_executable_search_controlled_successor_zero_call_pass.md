# 589 — FIN 0.1.2 S4-T03 executable search controlled successor 零调用通过

日期：2026-08-04
任务：`FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION`

## 结论

T03 的项目内执行集成缺口已经在原阶段内完成结构修复并通过 fresh zero-call proof。现在不再只有 EvidenceRequest 和 route 名字，而是有一条可执行、可回放、可失败留痕的受限检索链。

本项没有访问外网，没有调用 DeepSeek 或其他模型，没有生成业务 Artifact，也没有把候选直接交给 Writer。RC-P36-114 可以按 engineering boundary 关闭；live 来源是否可达、真实候选质量和 T04 产品研究效果仍需后续证明。

## 实现内容

新增 `fin_0_1_2_s4_t03_executable_agentic_search.py`：

- 把 T02 的三份 NVDA EvidenceRequest 编译成精确 `ExecutableSearchRequest`；
- 将四个 metadata route 绑定到 SEC submissions identity、NVIDIA IR 单一 fallback、只读本地 BM25、relationship graph 和 exact-value SQL；
- SEC response 只负责确认 accession、filing date 与官方 URL，本地 SEC 索引负责文档内容，避免把 filing 列表冒充研究证据；
- source request/response 在 parser 前完整写入内容寻址对象并 readback；本地 raw retrieval rows 在 projection 前同样保存；
- admission 精确绑定三 request digest、`2` 次 source、`8` 次 local、`0` retry、`1` fallback、`0` model/provider/cost、`300s`；
- Evidence Gate 检查 entity、as-of、HTTPS、locator、snapshot、parser、role 和 nonpromotion；
- success、typed gap、project failure 都物化 typed terminal result。

关系图中只有构建时间、没有来源发布日期的行不会进入 current Evidence。实现明确把 `published_at` 留空，让 Gate 拒绝，而不是把 graph build time 伪装成 evidence time。

## Fresh zero-call proof

- Run：`s4_t03_search_run_b30a53a76f5ec2b3afbf`
- Attempt：`s4_t03_search_attempt_0308286d8a6dfe8878d2`
- terminal digest：`a7e9c89b64deb26376dc56d24f250968def0fc86c8808c83490c30570f35fd05`
- 三 Cell accepted/rejected：`6/10`、`6/0`、`6/3`
- simulated source / live source / local invocations：`1 / 0 / 6`
- fallback / retry：`0 / 0`
- model / provider / paid cost：`0 / 0 / USD 0`
- capture objects：`8`
- business Artifacts：`0`

测试：focused `16 passed`；T03、local research、local retrieval 相关回归 `59 passed`；`py_compile` 和 `git diff --check` 通过。当前 Python 环境没有安装 ruff，因此没有虚构 lint green。

## 顺带发现但未扩张的问题

宽回归暴露两个既有问题：

1. 三个历史 T02 测试把当时被内容寻址的 v2_37/T02 记录同时写成“必须永远是 current/tail”。进入 v2_38 后这些断言天然过时；直接改测试又会破坏不可变 T02 package 的 SHA。当前登记为非阻断 immutable-evidence test-design debt，不篡改历史包。
2. local analysis preview 实际返回 `as_of`，API response model 未声明，触发 FastAPI validation failure。该字段与 Case temporal authority 一致，且会直接影响后续 T04 产品 surface，所以只做一行 schema alignment 并以相关回归证明，没有扩大检索合同。

## 下一步和边界

下一项：`FIN-0.1.2-S4-T03-NVDA-CURRENT-SEARCH-CANARY-FRESH-ADMISSION-AUTHORITY-DECISION`。

后续顺序保持不变：authority → fresh admission → scoped preflights → 唯一 live current-search canary。只有 live T03 成功且独立验收通过，才进入 T04 让 DeepSeek 消费 Evidence Gate 后的 evidence pack。T03 engineering pass 不等于 current source-grounded NVDA R2。

本次没有更新 financial research method registry；没有新增金融方法，只完成 Agentic Search 执行与证据留存合同的 runtime consumption。
