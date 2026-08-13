# FIN 0.1.3 S3 当前研究消费者

日期：2026-08-13
状态：`provider-neutral consumer zero-call engineering pass / natural synthesis pending`

## 1. 为什么需要这条链

严格重定基后，活动树保留了研究 Planner，却没有一个当前、版本中立的消费者把 reviewed Evidence Pack 和 S2 NumericFact 变成研究判断、底稿与报告。归档中的旧九调用 runner 与单次 attempt 绑定，直接恢复会重新引入多份 Prompt、Validator、Renderer 和结果物化逻辑。

当前唯一主干因此是：

```text
保存的 Planner atoms
  → 当前 EvidenceRequest / S1-S2 受控执行
  → reviewed Evidence Pack + NumericFact + residual gaps
  → provider-neutral 五单元研究输入
  → 模型判断原子与引用选择
  → 本地确定性绑定事实、数值、日期、引用和结构
  → structured workpaper/report candidate
```

候选检索结果和 rejected Evidence 永远不能绕过 Evidence Gate 进入模型输入。

## 2. 模型与 Harness 的分工

模型可见完整的来源事实摘录和权威 NumericFact，并负责：

- 判断状态与置信基础；
- 支持证据、反方证据、数值事实和缺口的引用选择；
- 公司特定 thesis、经济机制、最强反方；
- 可观察的 what-would-change 条件。

Harness 负责：

- 公司身份、研究截至日和 Case/Pack digest；
- exact number、单位、期间、公式和 citation surface；
- 引用是否属于当前研究单元；
- 五单元覆盖、枚举、长度和无自由数字叙事门；
- 最终 workpaper/report 结构与 lineage。

Harness 不得生成或改写研究结论；模型也不得自由重写精确事实表面。这不是“本地超级拼装”，而是模型作判断、本地作可信渲染。

## 3. 已解决的结构问题

### 3.1 Reviewed source policy 与开放检索 policy 分离

Dell/TSM 官方托管 transcript 已经过人工 route、parser、对象编译和 Evidence Gate，因此可以作为 reviewed Evidence 被 S3 消费；这不会把 `EARNINGS_CALL_TRANSCRIPT` 自动加入 S1 开放检索白名单，也不会让 transcript 数字获得 S2 NumericFact 权限。

### 3.2 request 级重复不能冒充多份经济证据

同一个 S2 事实可能被多个 EvidenceRequest 或 `quarter_discrete/fiscal_ytd` 标签重复暴露。原始受控结果有 45 个 request-level NumericFact；按公司、指标、数值、期间、单位和来源权威合并后为 35 个经济事实，再按每项指标的最新季度、最近财年或最新时点选择 25 个模型可见事实。request、period-role 和 source lineage 仍保存在控制面，不用于虚增模型证据数量。

### 3.3 模型容量由信息选择解决

第一版模型视图约 88,526 字符，主要由内部 ID、digest、request lineage、citation URL 和重复事实造成。当前模型视图为 48,380 字符：保留来源原文、业务含义、claim boundary 和精确 NumericFact；隐藏只供审计的内部字段。没有通过随手放大上限掩盖信息架构问题。

## 4. 零调用 R1 结果

- 当前 DELL Pack：20 Evidence／14 gaps；
- 模型可见：19 Evidence，其中 5 条为已复核 transcript Evidence；
- NumericFact：45 request-level → 35 semantic unique → 25 model-visible；
- 模型可见 residual gaps：10；
- 研究单元：需求质量、经营表现、价值获取、现金转换、反方/WWC，共 5 个；
- fake 输出成功编译 structured workpaper/report preview；
- unknown Evidence ref、cross-cell NumericFact、自由数字叙事、缺失 cell 均 fail closed；
- 网络／模型／provider／embedding 调用均为 0，fake deliverable 未发布产品面。

R1 是脏工作树上的工程证据，必须保留但不能独立签发 live。正式执行前还需一个绑定干净远端提交的 R2。

## 5. 下一自然门与停止规则

R2 通过后只允许一次 DeepSeek Pro 综合 canary：

- 复用保存的 Planner R1，不再次证明规划；
- 不联网、不重新检索、不 fallback、不 retry；
- 只改变 `reviewed Evidence/NumericFact → judgment atoms` 这一节点；
- 完整保存模型可见请求、最终 assistant 输出、参数、usage、finish reason 和 typed terminal；
- 不自动发布到 Workbench，也不宣称 S3 或 FIN 0.1.3 通过。

若模型自然输出通过合同，再做 L1 事实/数值/身份/引用和内容质量审阅。若出现新的 L1，保留 capture 并停在 S3 做一次结构处置；不得恢复旧九调用链或进入逐字段 live 循环。
