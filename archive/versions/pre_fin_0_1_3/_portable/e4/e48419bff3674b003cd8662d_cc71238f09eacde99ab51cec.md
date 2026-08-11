# FIN 0.1 S3-T09 transport-v2 context-authority failure 根因决策

日期：2026-07-22

## 授权与边界

用户以“授权下一步”只授权 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V2-CONTEXT-AUTHORITY-FAILURE-RESULT-AND-ROOT-CAUSE-DECISION`。本轮只做零调用代码、冻结输入、Provider 可见请求、fixture 与 validator owner 审计；没有实现修复、签发或消费 admission、调用模型/Provider/网络、重跑 Agent、比较 baseline、Human Review 或进入 T10/S4/release/production。

## 结论

直接失败仍是 DeepSeek 返回的 Value/Profit Claim Card 至少含一个不属于当前 Cell candidate＋graph context authority 的 `context_ref`。历史 raw response、ref 值、位置和数量均未保存，因此不能重建它是 Evidence、Numeric、其他 Cell 或任意 ID，也不能据此认定“DeepSeek 自身有缺陷”。

冻结输入在 disposable clone 上重编译后，三个 Cell 的合法 context 值分别为 8/8/7，全部确实出现在 Provider 可见 `authority_refs`。因此不是“允许列表完全没给模型”。但 Value/Profit 的完整模型视图除 8 个合法 context 值外还有 30 个 ref-like 非 context 值；`judgment_layer.context_refs` 字段旁只有泛化的 `exact Candidate or Graph context ref`，没有复制精确闭合 allowlist，也没有规定不使用 context 时必须输出 `[]`。现有 fake Provider 又把生产模型视图 monkeypatch 成 `program_cell_id + authority_refs`，并回放预制合法输出，未测试模型如何从真实拥挤视图选择引用。

因此最早项目可控根因是“字段级闭合 authority 传达＋fixture 真实性＋安全子型 telemetry”缺口；Provider 未遵约是直接失败类和残余风险。本地 membership validator 是正确的，不放宽、不静默删除、不模糊匹配、不重试 consumed identity。

## 选定修复与停止线

下一实现采用独立 transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v3`，保留历史 v1/v2 和 canonical output-v3。Claim Card 请求在 `context_refs` 字段旁显式给出当前 Cell 排序后的精确 allowlist，要求输出只能为其子集；没有使用合法 context 时必须 `[]`；Evidence、Numeric、fact/routing ID 和自由文本均明确禁止。响应前要求逐值 membership 自检，本地 validator 继续 fail-closed，不做任何 normalization。

新增 closed authority telemetry，只允许 segment、字段、`item_not_nonblank_string` / `evidence_or_numeric_ref_misclassified_as_context` / `outside_current_cell_context_authority` 与 failing count；不保存 raw ref、digest、index、任意 key 或 private reasoning。fake Provider 必须使用完整生产 model view，并从请求合同推导合法 ref；正例覆盖 exact subset/empty list，负例覆盖非 string、空白、Evidence、Numeric 和任意越权值的 earliest-stop。

这不是无休止 prompt patch：未来 transport-v3 fixture 若通过，仍需分别授权 proof decision、issuance 和至多一次 fresh exact live execution。若同类 context-authority failure 在显式闭合集合下再次出现，则停止第四轮 prompt-only 修补，把当前 DeepSeek 路线判为 T09 不合格并转 provider-route disposition 或 defer。

## 审计完整性

本轮模型/Provider/网络/新 admission/新逻辑 WorkUnit/Attempt/Run/Artifact 均为 0；目标逻辑对象仍为 `6/6/6/13`，Object tree digest 仍为 `00ac740b...a75`。首次直接 prepare 审计打开了目标 SQLite，主文件物理 digest 变为 `46c7578a...f080`，但逻辑 identity 与对象树未变；之后审计全部转为 disposable clone 或 URI read-only。该程序性缺陷已显式记录，不冒充“物理文件完全未触碰”。

## 产品判断与下一项

本轮只改善根因归属和后续修复边界，没有新增 Evidence、Numeric、Judgment、Report 或 Alpha。RC-P36-039 进入 transport-v3 implementation pending；RC-P36-037、T09、T10、S4、release 与 production 继续 blocked。

验证方面，新决策和相邻合同 `33 passed`；完整 S3-T09 首轮 `143 passed / 21 failed`，21 项均为历史测试对 mutable backlog 游标的滞后断言。机械更新 current-state 断言并同步 latest ledger/SQLite 物理摘要审计后，定向 `36 passed`，最终完整 S3-T09 `164 passed in 264.21s`。configs/docs JSON、Project OS JSONL、9/9 stable source digest、compile、diff check 与 Project OS repository-hygiene closeout 均通过。

当前唯一下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-FIELD-LOCAL-CLOSED-CONTEXT-AUTHORITY-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`，仍需单独授权。它只能实现代码和 fake Provider fixtures，不能签发、执行或比较。
