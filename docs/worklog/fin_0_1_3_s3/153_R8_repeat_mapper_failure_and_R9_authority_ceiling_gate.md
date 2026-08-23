# R8 重复 mapper 失败与 R9 authority-ceiling 工程门

## 结论

R8 已执行且在第一个 fresh Demand strict submission 后终止。该节点得到完整 HTTP 200 Tool Call，0 retry；模型可见请求包含精确 typed feedback 和 `authority_expansion_allowed=false`，但返回的全部 model-owned 字段与 R7 失败 payload 逐字节一致。唯一失败项仍是 `sourced_claims[9]`：claim digest `84033e8d...120d`，`authority=bounded_inference`，Evidence／NumericFact／Relation 引用全空，同时明确保留既有 `GAP::00730082A5C08C4C`。Operating、Value、Lead 均未调用。

R8 authority 和输出 identity 已消费，public result digest 为 `7a11a025...923`，private full-result digest 为 `ed2946c2...f2b`。R7、R8 及六份 capture 保持不可变；没有同 authority retry，也没有形成 R9 authority 或 R9 Provider 调用。

## 最早责任层与处置

外部边界是 DeepSeek strict mapper 在收到一次明确修正后仍重复原 payload。项目拥有的最早缺口位于 S3 analysis→strict-submission authority compilation：Tool Schema 只暴露 authority enum，未把“非 `not_inferable` claim 必须至少有一个授权引用”的不变量讲清，也没有在唯一、精确 digest、已有 gap 约束下执行机械性降权的本地编译器。

本轮增加了 provider-neutral、fail-closed 的 authority ceiling：只有反馈同时绑定被拒 claim digest、要求 `not_inferable`、目标恰为唯一 zero-ref `bounded_inference` claim，且原文明确命中一个既有 `remaining_gap_ref` 时，才把有效 authority 降为 `not_inferable`。claim 文本、Evidence／NumericFact／Relation 引用和 gap 集合均不变；receipt 同时记录 submitted/effective authority、原后 digest 和零 authority expansion。旧四字段 feedback、digest 漂移、多 claim 或无 gap 均继续失败。

零调用 successor 已重放 R7 的五个可复用节点和 R8 Demand submission，完成上述本地重验，并证明首个 fresh Provider frontier 已移动到 Operating draft。公开 proof digest 为 `af6f5881...ab8`；Cash、Counterevidence、Demand 复用，Supply 不变，只剩 Operating／Value 两个 analysis＋submission pair 和一个 Lead pair，共精确 6 次，0 retry／fallback／新 S1/S2／retrieval／外源／promotion／Writer。

## 预签权审计补漏

静态检查在签权前发现新 R9 authority validator 的分支顺序错误：authority-ceiling 链校验先引用 `paths / scope_decision / zero / common_chain_valid`，后解析 bound inputs。若继续，R9 会在 Provider 前因未定义名称终止。该问题登记为 `RC-S3-086`，已把共享输入解析与 SHA 校验前置，并新增不 monkeypatch validator 的真实 R7／R8／failure-assessment／zero-proof 全链测试。R8 failure assessment 现在也是 authority 的强制摘要绑定输入。该问题没有消耗 authority、Provider、网络或模型调用。

## 当前工程门

- 定向三组：`140 passed`；其中含 digest 负向变异、六 fresh-node 假 Provider seam 和真实 R9 authority validator 全链。
- 全仓：`1147 passed, 2 warnings in 380.94s`；两条仍为既有 SWIG deprecation warning。
- Python compileall、目标 pyflakes：通过。
- active baseline：`211 Python／8 frontend／5 detector／28 Runtime／0 unresolved`。
- R9 scope decision SHA-256：`0196298a9ba3e5f63ec6fff2793127a4b81efa3faa2b161a735ae3c1f77d33c7`；runner SHA-256：`f4f9a1cdeecc9116f1dfc1da180bdeca565569bf86105990d0bcd2d066aa51b6`。
- secret scan：`7,795 files / 0 findings`；943 份 config JSON、8 份 Project OS JSONL／1,048 行和 `git diff --check` 全部通过。

## 下一门

当前只允许精确 staging、完整仓库卫生门、clean commit／push 和 repository-aware Project OS preflight。通过后才能签发一次全新的 R9 authority；它最多允许 Operating／Value／Lead 六个 fresh Provider 节点，四类节点均已有任务特定 `TokenBudgetBasis`。任何失败即消费该 authority 并停止，不自动 retry。即使 R9 合同成功，七项金融 finding 仍须独立 L1／L2 与内容质量复评；Writer、S3 acceptance、MU／NVDA、异质泛化、Workbench publication 和 release 继续冻结。
