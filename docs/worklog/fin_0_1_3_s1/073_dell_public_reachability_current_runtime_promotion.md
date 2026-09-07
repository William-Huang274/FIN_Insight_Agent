# S1 工作记录 073：DELL 公开补源进入 current Runtime

## 结果

- 将已审阅 DELL 补源的 17 个公开页面与 19 个精确内容片段写入 canonical source store，而不是只留在独立 Evidence Pack。
- 页面记录负责来源与 capture lineage；片段记录负责精确可检索内容。同一页面存在多个片段时，各片段使用独立 source record，不能用页面级长文本模糊匹配冒充精确证据。
- current source store 从 1,841 增至 1,877 条记录；金融对象从 34,117 增至 34,166 个。旧对象和向量逐字复用，仅 49 个新对象在 `cuda:0`／FP16 上生成 embedding，CPU fallback、网络和生成式模型调用均为 0。
- current snapshot、kernel、route、hybrid policy、binding policy 和 binding receipt 原子提升到 Runtime Registry R32。Workbench current 路线不再读取旧 v2/R31 快照。

## 真实业务验证

- 用 8 条 DELL 请求覆盖价格／配置、客户部署、行业需求、行业 PVM、渠道配置、价值池、行业供给和反方。
- current BM25＋Qwen dense 共返回 66 个候选；每条请求都有候选，目标信息披露方均进入候选池。
- 只有同时匹配已审 Pack 的页面 lineage 与精确内容 digest 的候选才可重新选择 reviewed Evidence，共恢复 15 条；排序本身不授予 Evidence 或 NumericFact 权限。
- 该结果说明公开补源已从“另一个 JSON”变成产品能实际查询的材料，但不说明动态 Agent 已会主动选择这些路线，也不说明所有 residual gap 已关闭。

## 关键工程发现

- 最初的公开对象只有对象／向量层，没有进入 canonical source store。若直接进入动态 live，Source→Object→Index lineage 会断裂，产品即使搜到内容也不能可靠追溯原文。
- 本轮没有用放宽校验处理，而是补成 `page parent + exact slice` 两层源对象，再由 binding receipt 逐文件核对 source、object、embedding 和 Registry digest。
- 这再次确认：公开资料“已经在 Pack 里”不等于“Agent 工具能够从 current Runtime 找到它”。Pack、source store、candidate index 和 Evidence authority 必须分别绑定。

## 验证与边界

- Runtime／公开对象／检索／Workbench／lineage 初始定向回归：`79 passed`；
  public Evidence Role v4 完整接入金融排序器、历史 v3 固定后，追加定向回归
  `72 passed`，全仓回归 `1,062 passed`。
- `compileall`、active baseline `202 Python／8 frontend／5 detector／28 Runtime／0 forbidden`、
  876 份 config JSON、8 份 Project OS JSONL／959 行、7,680-file secret scan／0
  与 `git diff --check` 均通过。
- current public reachability proof：8 请求、66 候选、15 reviewed Evidence，全部门通过。
- current DELL 动态输入的 25 张数值卡中，23 张按原 NumericFact authority ref
  直接绑定；MU／NVDA 两张供应链库存卡因不同 request lineage 生成不同 ID，现仅在
  公司、指标、值、单位、财年／季度和起止日期全部相同时，按 economic-fact
  signature 绑定到 S2 权威。该绑定不合并来源 lineage，也不赋予新的数值权威。
- 当前仍为 `S1_qualified_stable=false`；未执行自然模型、动态反思、完整 DELL、多 Agent、Writer、泛化或 release。
- 下一步只建立 `value_capture` 动态单元的零调用状态机和 mutation proof，随后才签发一次真实 DeepSeek 调用。
