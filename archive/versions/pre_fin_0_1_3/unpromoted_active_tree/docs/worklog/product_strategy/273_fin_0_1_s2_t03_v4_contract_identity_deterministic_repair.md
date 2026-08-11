# FIN 0.1 S2-T03 v4 合同与执行身份确定性修复

日期：2026-07-20
状态：`fixture_proven / no_live_admission / T03_still_blocked`

## 问题与决策

v3 live validation 证明 provider 返回了三个正确 required fields 加五个未知顶层字段，但安全日志没有保存未知键名，不能把“模型回显了哪些字段”写成历史事实。仓库内仍有两个可确定复现的 owned gap：

- v3 user document 把 task、decision question、as-of、contract rules、example 和 candidates 暴露在响应字段的同级 namespace；
- 非 VT1 WorkUnit ID 未绑定 request idempotency/admission identity，相同 Case/input 的隔离执行生成相同 WorkUnit，并继续派生相同 Attempt/ResearchRun ID。

本轮选择 root-cause repair，不通过丢弃未知字段制造假成功，也不再调用模型。

## 实现

- 新增 `fin01.bounded_agent.specialist_lead_output:v4`：request document 只有 `request_contract`、`analysis_input`、`response_shape_example`；response 只有单一 `result` outer key；
- `result` 内只允许 `output_contract_ref`、`specialist_judgment`、`lead_adjudication`；unknown outer/result extension 继续 typed fail-closed，只持久化 count/digest/type；
- enum case/whitespace 和 singleton-list 等既有无损适配只在 `result` 内运行，不 unwrap、flatten 或删除 envelope extension；
- runner/executor 在 provider 前拒绝非 v4 contract；没有签发 v4 admission；
- 非 VT1 WorkUnit canonical identity 增加 `execution_identity=request idempotency_key`，Attempt/Run 由 distinct WorkUnit 继续派生；同 key 重放仍幂等；VT1 单 WorkUnit 合同保持不变；
- 独立复核发现后台分派仍按“同类型恰好一个 pending”选取，两个并发非 VT1 request 可能均不被调度；现改为按本次 request `idempotency_key` 精确选中 pending WorkUnit，并保留旧的无 identity 查询语义；
- canonical failure observation 同时接受历史 v3 shape 与 v4 result-level safe telemetry。

## 验证与独立复核

- focused T02/T03：`26 passed in 41.85s`；
- Point 01 facade + Point 02 execution + S1-T02-T06 + S2-T01-T03 + Workbench：`75 passed in 70.53s`；
- 明确负例覆盖 v3 风格 required 3 + extra 5、result 内 unknown extension、semantic synonym、wrong candidate、empty/truncated JSON、consumed v1-v3 identity；
- shared-store 证明两个不同 execution identity 产生不同 WorkUnit/Attempt/ResearchRun，重复第一 identity 不产生第三次执行；
- 双 pending 回归证明后台分派按 exact execution identity 选择，不再因同类型并发而返回空选择；
- v4 result-level shape telemetry 已通过 canonical `RESEARCH_RUN_FAILED` event 持久化，未知字段名、正文、secret 和 private reasoning 均未写入。

独立复核结论：本轮关闭的是项目内 prompt namespace 与 lineage identity 缺口，不证明 provider 会遵循 v4，也不证明 Agent 研究价值。当前仍使用普通 `json_object`，没有在零网络边界内验证 server-enforced nested schema；这项外部能力只能在未来单独调研或 admission 中确认。

## 边界与下一步

本轮 model/provider/network/external tool=0，新 exact v4 admission=0，live validation=0，Artifact=0。T03、T04、S3、RG1/RG3/RG4、release 与 production 状态不变。下一步必须由用户决定：签发一次新的 exact v4 bounded live validation，或先切换 provider/structured-output strategy；不得自动执行。
