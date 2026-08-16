# 042 S3 动态 Truth Spine：EvidenceResponse 零调用工程纵切

日期：2026-08-16  
状态：engineering pass；自然动态研究未执行

## 为什么做

此前模型可以提出补证需求，S1 也能给出候选，S2 也能返回公司财务事实，但三者没有在同一次研究循环里闭合。`submit_evidence_request` 实际只保存 proposal，候选不会形成可审计的 EvidenceResponse，更不能回流到当前研究单元。

本轮只补这条控制面，不扩来源、不调用模型，也不把普通候选自动升级成 Evidence。

## 实现边界

- EvidenceRequest 真正执行当前 S1 hybrid route 与 S2 mart。
- 只有已经存在于当前 immutable reviewed Pack、且通过 case、owner、source type、as-of／period、Evidence Slot 和精确 lineage 复核的对象，才可返回 `accepted`。
- 新候选即使排名靠前、文本相关或 advisory role 正确，也只能是 `needs_human_review`。
- 动态模型视图只包含 accepted Evidence refs、NumericFact／relation、typed gap 和 receipt；不包含未审候选原文。
- 动态 Claim Authority 只能删除本轮没有取回的权限，不能创造新的数字、引用、身份、日期或因果桥。
- 请求执行 gap 与 reviewed Pack gap 不互相改名；二者 facet taxonomy 不同。

## 三案真实结果

### DELL

- 执行 8 个真实 EvidenceRequest。
- 5 个请求取回 reviewed Evidence，共 6 条唯一 Evidence。
- 3 个已审绑定因 Evidence Slot 不属于当前请求而被拒绝。
- 112 个未审候选全部留在候选层，0 自动晋升。
- 保留 12 个 typed gap。
- 当前可诚实支持的 claim authority 收窄为：`bridge_unavailable`、`multi_driver_context_only`、`same_scope_observation_only`。

具体业务上：订单／积压、需求持续性、已报告结果和现金流能取回 SEC Evidence；利润单元只取回一条 10-Q 公司层观察；营运资金、issuer counterevidence 和 upstream counterevidence 没有取回已审材料。模型此时不能获得“产品利润桥已经成立”的权限。

### MU 与 NVDA

两案各执行一个 margin/value-capture 请求，各得到 16 个当前候选，但没有候选能与当前 reviewed Pack 做 exact lineage join：MU 为 0 accepted；NVDA 另有 1 条已审对象因 slot 不匹配被拒绝，仍为 0 accepted。两案均只形成 typed gap，未编译动态研究输入。

## Mutation 与审计

- 候选顺序变化不改变 accepted Evidence。
- 给未审候选注入看似权威的文字，不会改变任何 authority。
- 跨案例候选 fail closed。
- reviewed Pack digest 漂移 fail closed。
- 0 model、0 provider、0 external network、0 candidate promotion。

私有工程结果 digest：`93cc10355b98e164eddf879a5d27bd028e8fb73995d1b1e72c477649fb36bacc`。

## 新暴露的最早责任层问题

Dell Q1 FY2027 官方 transcript 已经进入 reviewed Pack，但当前 S1 candidate object/index 没有该对象，source whitelist 也没有 `EARNINGS_CALL_TRANSCRIPT`。因此 fixed-Pack 测试能看见法说，动态检索却看不见。MU、NVDA 的 0/16 也说明 reviewed Pack 与当前候选对象之间还没有稳定同步合同。

这不是 DeepSeek 问题，也不能靠 S3 把 transcript 静默预喂给模型解决。它归 S1 source/index synchronization。它不阻断一次诚实的 DELL SEC-only 动态实验，但阻断三案例 S1 产品通过和高质量动态报告。

## 下一步

1. 在 clean commit 上重新运行正式零调用 proof，保存公开结果与实现 commit 绑定。
2. 只给自然 DELL `value_capture` planner 用户问题、公司身份、as-of 和工具权限，让其提出 EvidenceRequest。
3. 真实执行 S1/S2、返回 EvidenceResponse，并在当前有限权威下完成一次动态 Judgment。
4. 保留 S1 transcript/index 同步缺口；根据自然纵切结果决定在进入五单元前的最小同步修复，不把缺口偷塞进 S3。
