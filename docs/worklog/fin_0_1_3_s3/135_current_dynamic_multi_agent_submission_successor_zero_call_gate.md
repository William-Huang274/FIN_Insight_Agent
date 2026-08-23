# FIN 0.1.3 S3 DELL current 动态多 Agent 提交 successor 零调用门

时间：2026-08-23

状态：`provider_neutral_submission_contract_implemented / R1_capture_replay_exact / successor_live_authority_pending`

## 这轮解决的不是研究内容，而是“分析完以后怎么可靠交卷”

R1 已经完成六个 Specialist 的自然请求选择和六轮 current S1/S2。最早失败发生在 Reflection／Workpaper 的严格提交边界，因此本轮没有重跑检索、没有新增资料，也没有让 Harness 改写观点。

统一合同现在把一次模型节点拆成两个可审计职责：

1. 研究／写作节点产生模型可见草稿，允许它完整分析经济机制、反方和 WWC；
2. non-thinking submission 节点只把已保存草稿映射到严格 Tool Contract，不允许新增事实、数字、引用或结论；
3. `schema_version`、Agent／round identity 和 lineage 由本地 binder 注入；
4. 图关系只提交 compact predicate，机制叙事留在 `research_use`；
5. 模型只能提出停止建议，正式 StopDecision 由 Harness 按 coverage、剩余请求、gap 和 FeedbackReceipt 编译。

这套合同位于 provider-neutral Runtime，不是 DeepSeek 专用分支。未来模型提交更稳定时，可以减少严格映射节点，但不需要改变金融 Evidence、身份、期间和停止控制骨架。

## R1 capture-bound 零调用复证

正式 proof 绑定：

- R1 public SHA-256：`28fc993e6c8ab53f43499fd999f4cf6d23a6b765e6369fbd1da679efd21b3bbd`；
- R1 private SHA-256：`71ac85a6e494fafaae34fdf6a5abb6e0d24012d1ef182ee8a67d7c50fb35014a`；
- 六个 predecessor S1/S2 batch 均重新编译出完全相同的 `round_response_digest`；
- 6 份 Reflection capture 与 Demand／Counterevidence 2 份 Workpaper capture 完整可读，且只作为审计草稿，不能直接晋升业务事实；
- Demand／Counterevidence 的 Reflection 不需再次调用模型，只重新编译本地 StopDecision；
- Counterevidence Workpaper 在只移除模型不应填写的本地 envelope 后通过完整 Validator；
- Operating／Value／Cash／Supply 的 Reflection 明确需要 strict mapper；
- Supply 唯一未覆盖请求为 `REQ::21dc7bfb04d38fa5cc8749f8`，新合同只允许 `continue`，不得把目录未覆盖冒充充分停止。

公开 proof：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_zero_call_result_v1_0.json`，result digest=`7ad7966f9d63c3dd3a05d6225f4a4459ec40866be9cc5f9cb47b01c0fd32390b`。

## successor 的有界新工作

旧 14 次 Provider attempt、12 个 request、6 个 retrieval round 均保持不可变。新 authority 的最大 25 次调用不是“随手给一个上限”，而由以下实际节点相加：

- 4 次 R1 Reflection 草稿严格映射；
- Supply 追加 1 个 current S1/S2 request 后，1 次新 Reflection 草稿＋1 次严格提交；
- Operating／Value／Cash／Supply 4 份新 Workpaper 草稿；
- Demand 加上述四角色共 5 次 Workpaper 严格提交，Counterevidence 只做本地 requalification；
- Lead 最多两轮，每轮 1 次分析草稿＋1 次严格提交；
- 最多三个 role-local repair，每个 1 次修订草稿＋1 次严格提交。

每类付费节点必须在 authority 中保存完整 `TokenBudgetBasis`。新运行只允许 1 个 S1/S2 request、1 个 retrieval round、0 外源网络、0 Candidate promotion、0 retry、0 fallback 和 0 current pointer mutation。

## 当前边界

本轮工程门为定向 `52 passed`、全仓 `1123 passed`（仅 2 条既有 SWIG warning）。零调用 proof 不代表自然 successor、Lead、L1、八维内容质量、DELL 报告、Writer、S3、Workbench publication 或 release 通过。

下一步必须先形成 clean commit／push，并用该提交、R1 public/private、zero-call proof、current Evidence Pack、S2 quantitative input 和两类 Provider profile 签发 fresh authority。只有 successor live 形成六份有效 Workpaper 和 Lead 结果后，才进入独立 L1 与内容质量验收。
