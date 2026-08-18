# 052 S1 来源路线真相与 gap eligibility Runtime

日期：2026-08-19

状态：`engineering_pass / formal_three_case_successor_pending / S1_qualified=false`

## 为什么要做

当前候选 replay 已能说明 BM25、Qwen 和对象索引跑到了哪里，却不能回答更关键的业务问题：候选不足时，SEC、公司 IR、行情、行业资料或诊断搜索到底有没有被执行。没有这层真相，系统会把四种完全不同的状态混在一起：本地对象缺失、路线未执行、传输失败、公开资料确实不披露。

这会直接污染研究结论。比如 MU／NVDA 某个命题当前候选不足，只能说明“现有 Pack 还不够”，不能据此写成“公开信息不存在”。DELL 当前的问题主要是 Evidence 准入，也不应该因此自动再抓一轮网页。

## 实现

- 新增 provider-neutral Source Route Portfolio，分别登记本地快照、SEC 官方、已注册官方文档、发行人 IR、PIT 行情、行业权威源、diagnostic broad web 和人工上传；
- 请求级 compiler 依据 EvidenceRequest、QueryFacetPlan、材料覆盖状态、已注册 Source Intake route 和 capture attempt，生成 `requested / available / executed / terminal / exhausted` 真相；
- transport failure、adapter 未配置、diagnostic provider 和人工 fallback 均不能获得 non-disclosure 或 public-gap 权威；
- 只有 `blocked_by_candidate_coverage` 才触发补源判断。`blocked_by_evidence_admission` 保持在 Evidence Gate，不再误触发外源搜索；
- learned sparse、multi-vector、graph 等未配置候选路线不再自动算“当前必须执行路线”；它们是否进入 FIN 0.1.3 由独立产品价值门决定；
- Workbench request 与 controlled plan 现在都返回同一份 source-route truth；ProductReadiness 可消费该真相并在公开摘要中显示安全状态；
- 新增不可变 zero-call successor materializer：复用历史 candidate replay，只补来源路线真相，不重跑检索、向量或模型。

## 实际三案结果

- DELL：8／8 请求的当前 bounded candidate material 完整，0 个请求需要补源；其主要未就绪原因仍是 Evidence admission，不能靠继续 broad search 修复。
- MU：8 个请求中 4 个候选覆盖不完整。当前可见的是 SEC route 尚未按这些 requirement 执行，部分 transcript 没有 exact registered route，IR adapter 尚未配置；0 个请求具备公开信息 gap 资格。
- NVDA：8 个请求中 3 个候选覆盖不完整；状态与 MU 类似，0 个请求具备公开信息 gap 资格。
- 回放发现并修正一个跨公司供应链身份错误：NVDA 研究中的 TSM 官方资料必须按 Evidence Owner=`TSM` 匹配 route，不能错误按研究 Case=`NVDA` 拒绝。

## 复证

- 三案 immutable replay：DELL `0`、MU `4`、NVDA `3` 个 supplement-required request；公开 gap eligible 均为 `0`；
- Python 全仓：`795 passed`；
- TypeScript typecheck、Vite production build、compileall、active baseline 均通过；
- active baseline：`175 Python / 8 frontend / 27 Runtime / 0 forbidden`；
- secret scan：`7,312 files / 0 findings`；
- 网络、生成模型、learned-vector、CPU vector fallback：`0`。

## 下一步

当前代码与合同已通过，但 current 产品资产尚未重物化。下一步必须在干净提交上分别生成 DELL／MU／NVDA source-truth replay successor，再重算三案 ProductReadiness 并更新 Registry／Runtime Binding。完成前 RC-S1-046 保持打开，旧 readiness 不能被口头追认为已具备 source-route truth。
