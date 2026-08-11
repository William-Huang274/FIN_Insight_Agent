# FIN 0.1.2 S4-T02：三案例 Retrieval/Evidence 确定性准备

日期：2026-08-04
状态：`pass closed / S4-T03 authority pending`

## 结论

按用户“继续”的授权，本轮只完成 S4-T02 与其既定 pre-T03 shared-resource prerequisite。当前 Runtime 已能把 T01 的 DELL、MU、NVDA 自然案例分别编译成三份 EvidenceRequest、确定性 route plan、candidate qualification、citation projection 和 typed gaps；没有调用模型、Provider、网络、检索工具，也没有创建或晋升业务 Evidence。

这次最重要的产品边界是：readiness 通过不等于 RAG/Agentic Search 已经运行。DELL/MU 的历史 source pack 可证明 parser、citation、route、authority 和 ceiling 合同可工作，但不具备当前问题的新鲜度；NVDA 只有 exact input manifest，没有 source content，所以系统必须明确返回 current-search gaps。

## 三案例结果

- DELL：`2 accepted / 8 rejected / 2 citations / 0 promoted`，9 个历史 cannot-infer gap；
- MU：`13 accepted / 1 rejected / 13 citations / 0 promoted`，1 个拒绝为 per-request ceiling overflow，9 个历史 cannot-infer gap；
- NVDA：`0/0/0/0`，保留 `current_demand_evidence_search_required`、`current_counterevidence_search_required`、`current_value_evidence_search_required`；
- shared public index as-of=`2026-06-11` 只证明 catalog 可寻址，对当前 Evidence 明确判为 stale；
- readiness 输出不返回历史 statement 或数值正文，citation 也保持 `writer_citable=false`。

## 工程结果

- 新增 current Runtime consumer 与类型化 receipt；receipt 显式保存所有零调用计数；
- 新增 T02 authority 和隔离 content-addressed registry；
- 覆盖正向三案、cross-case、as-of、route、citation、parser、index、promotion、ceiling、排列和未知案例 mutation；
- focused T02=`15 passed`；T02＋default registry=`29 passed`；T01、M6 主链与历史 successor 兼容回归=`93 passed`；
- RC-P36-113 已关闭：共享默认 registry 原子登记 S3 fact-candidate profile，detector 未弱化，unknown-resource 仍 fail closed，default registry=`14 passed`。

## 对后续需求的主动建议

T03 不应一上来运行完整 research 或同时试 DELL/MU/NVDA。当前缺的不是更多本地合同，而是“NVDA 的 current source access 是否真能通过已冻结 route 产生可晋升 Evidence”。因此下一项先做独立零调用 authority decision，明确一条 NVDA bounded canary 的 route、调用/成本上限、capture-first、parser/source 权限、首错停止和零 false promotion；只有 authority 通过后，才在后续续行签发和执行。

## 当前边界

model/provider/execution-network/source-network/tool/retrieval/store-write/admission/Run/Artifact/Human 均为 0。historical fixture 不是 current Evidence；current NVDA R2=false；S4-T03–T08、S5、release、production 均未通过或未开始。

下一项：

`FIN-0.1.2-S4-T03-NVDA-BOUNDED-AGENTIC-SEARCH-CURRENT-CANARY-AUTHORITY-DECISION`
