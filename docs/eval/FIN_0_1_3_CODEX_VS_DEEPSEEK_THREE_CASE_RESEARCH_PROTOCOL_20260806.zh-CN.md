# FIN 0.1.3 Codex vs DeepSeek 三案例研究对照协议

日期：2026-08-06  
状态：`active / Codex gold candidates complete / DeepSeek supervised comparison pending`

## 1. 比较顺序

1. 冻结 DELL、MU、NVDA 的 research objective、as-of、source authority 与质量 Rubric；
2. Codex 通过当前 MCP、本地数据和允许的公开来源完成三案研究；
3. Codex 对事实、数字、机制、反方和报告进行交叉核验并形成 gold candidate；
4. 冻结每案 gold candidate、Evidence Pack、Claim/Judgment、修订记录和 score packet；
5. DeepSeek 在不接触 gold answer 的条件下消费同一 objective、as-of、工具权限与源数据；
6. supervisor 持续轮询节点产物；首个 material 偏离即暂停，不让错误传播到 Writer；
7. 记录偏离属于检索、证据晋升、数值、身份/时间、机制判断、Lead 综合、Writer 或 Verifier；
8. 通过定向补充证据、缩小任务、修正合同或明确人工反馈扶正，然后从受影响节点继续；
9. 比较原始输出、扶正后输出和 gold candidate，不把扶正后的结果冒充独立一次成功。

## 2. 公平性与防泄漏

- DeepSeek 不可读取 Codex 最终答案、评分结论或逐条修订；
- 两者使用同一冻结问题、as-of 和 source authority；
- Codex 可使用更丰富工具发现标准答案，但比较时必须单独报告两者实际可见证据差异；
- 如 MCP/tool 能力不对称，应分别报告 `model gap`、`tool/runtime gap` 和 `evidence availability gap`；
- supervisor 的每次扶正都记录触发节点、反馈内容、追加证据、额外调用和结果影响。

## 3. 节点级暂停条件

遇到以下情况暂停当前案例：

- 公司、期间、单位、币种或来源身份错误；
- 关键数字无法回算或把 proxy 当作 exact authority；
- 将 boundary-only evidence 晋升为 thesis support；
- 遗漏已有的重大反向证据；
- 核心机制没有连接到财务或估值影响；
- Lead 未处理 material conflict 就允许 Writer；
- Writer 引入 Evidence Pack 之外的新事实；
- Verifier 只验证结构、不验证实质研究质量。

非关键措辞或版式问题记录为质量 finding，不中断研究主链。

## 4. 产物

每案必须保留：

- research objective 与 DecisionSurface revisions；
- ToolUseLedger、原始来源 capture、解析结果和 rejected candidates；
- Evidence Pack、Numeric checks、Claim/Judgment Cards；
- Lead review、repair history、Writer input/output、Verifier findings；
- Codex gold candidate、DeepSeek raw candidate、扶正后 candidate；
- 八维评分、逐差异说明和 reviewer decision。
