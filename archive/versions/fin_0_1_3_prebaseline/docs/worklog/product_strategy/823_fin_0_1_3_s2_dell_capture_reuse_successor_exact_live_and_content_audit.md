# 823 — FIN 0.1.3 S2 DELL capture-reuse successor exact-live 与内容审计

日期：2026-08-10

状态：exact-live completed_with_findings；raw candidate 未晋升；禁止自动重跑

## 执行结果

唯一 successor admission 已 exact-once 消费。Runtime 从 R1 导入 5 个有完整 request/response/capture lineage 的成功节点，旧第 6 次失败 capture 继续只作审计证据；随后只执行逻辑节点 6–13 的 8 次 DeepSeek Pro 调用。8 次均取得响应，0 retry、0 fallback、0 tool/network research。连同 predecessor，本案例累计为 14 次 Provider attempts、13 个逻辑输出。

successor usage=`165,344 input / 20,836 output / 186,180 total tokens / USD 0.1346276`；累计 usage=`270,892 / 27,001 / 297,893 / USD 0.2084369`。公开结果 digest=`f341db71...822f`，完整原始请求和输出继续只存在受限 private capture 中，公开结果不含原文。

## 业务内容到底产出了什么

Final Writer 形成了 8 个实质章节、33 个判断点、14 条 limitation，overall confidence=`medium`，覆盖投资结论、需求与收入、产品竞争、供应执行、利润现金流、估值/price-in、反方以及 what-would-change。它具体使用 DELL AI server orders/revenue、ISG 收入与利润、现金流、客户集中度、GPU/HBM/先进封装风险和出口管制等公司事实，不再是占位模板。

Red Team 给出 10 个问题和 3 个缺失反方。Final Writer 已删除多项无来源的精确余额或同比表述，把 Microsoft 需求明确降为 read-through/bounded inference，并补入相对完整的反方与 gap。说明 Specialist→Synthesis→Draft→Red Team→Final Writer 的研究链确实产生了内容增益。

但它还不是可交付研报：一处文字把应收、存货、应付的变化直接归因于 AI 大单，现有证据只能证明营运资金科目变化，不能证明该因果；WWC 仍多为“显著放缓/严重短缺”等不可执行条件；固定 Pack 没有 point-in-time 股价、估值倍数和情景输入，因此估值章节只能诚实留 gap；若干关键数字在多个章节重复，内容密度仍需提升。

## 为什么公开结果显示 12 个 L1、2 个 L2

这 14 条 finding 不等于 14 个错误事实：

1. `11` 条 `numeric_surface_not_authorized` 多次命中同类表面。Final Writer 共给出 38 个 numeric refs，其中 26 次使用 `NUM`、12 次使用 4 个不同的 `FORM`，但 `PRES=0`。模型能正确引用原始数值和全部 4 个公式，却在写中文“亿元”等等价展示时没有再选择冗长的 `PRES` ID。本地合同因此把合法换算重复报错；同时 classifier 会从 `FY27` 尾部错误抽取 `7`，形成项目侧假阳性。
2. `1` 条 material numeric ref missing 来自 TSMC `77%`：该数字在 E015 原始来源中真实存在，但 13-fact authority inventory 漏编，不是模型凭空创造。
3. `1` 条 evidence binding finding 是真实边界问题：精确 `161.32亿元` 对应 E002 的 `16,132M`，该 point 只绑定了较粗粒度 E001 `16.1B`，需要补 E002 lineage。
4. `1` 条 JSON parse finding 来自 Verifier 被截断。Verifier 输入合同要求逐条重抄完整 claim、status 和 reason；本次在恰好 4,000 output tokens、`finish_reason=length` 时截在 JSON 中段，保存的 raw verifier 为 9,589 字符。它不是“Verifier 判定失败”，而是根本没有形成可解析的完整 VerificationResult。产品口径必须视为 hard incomplete，不能只记普通 L2 后继续晋升。

## 分阶段处置

- RC-P36-169：跨 Attempt resume 路径已被真实 8-call successor 证明，关闭；它不再阻断后续。
- RC-P36-170（S2）：保持 open。下一步应让模型引用 `NUM/FORM`，Harness 从其绑定事实确定性接受或渲染全部授权 presentation surface；补齐 source numeric inventory，并修复 `FY27` tokenization。不能再要求模型同时选择语义重复的 `PRES` ID。
- RC-P36-171（S2，新）：Verifier 改为 compact claim-ID verdict view，不重抄长 claim；`finish_reason=length` 或不完整 JSON 必须 hard incomplete。先零调用 replay/mutation，不自动发新 admission。
- RC-P36-165（S1）：固定 Pack 的真实估值/市场数据与部分外源事实仍缺，继续作为来源充分性问题，不让 S2 Writer 伪造补齐。
- RC-P36-172（S3，新）：因果越界、WWC 不可执行和重复度属于研究内容质量；后传到 S3 八维内容门禁，不在本次 S2 successor 中扩修。

当前 DELL 结论为：恢复链通过，DeepSeek 已证明能完成实质研究综合和公式引用；产品 candidate 因 Verifier 不完整、数字表面合同缺陷与真实内容质量缺口而未通过。不得执行 paired assessment、Owner acceptance、其他五案或 release。

## 收尾验证

- successor live/public-boundary focused：`15 passed`；
- 全部 FIN 0.1.3 S2 contract：`199 passed`；首次 broad run 唯一失败为旧状态断言仍要求已关闭的 RC-P36-169 阻断，更新为当前 RC-P36-170/171 后全绿，未改 Runtime 或门槛；
- public JSON 与两份 Project OS JSONL 全量解析通过；
- `repository_and_git_hygiene` scoped preflight=`pass / 0 open blocker`；
- added-diff 与三个新公开文件 secret scan=`0 hit`；private terminal 继续由 `.gitignore` 排除；
- 本审计、测试和文档收尾新增 Provider/model/network 调用=`0/0/0`。
