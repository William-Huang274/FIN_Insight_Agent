# DELL external capture replay compiler 修复门

日期：2026-08-23
阶段：FIN 0.1.3 / S1
状态：通用 parser／date／relationship-facet 修复与正式 replay 模式工程通过；clean-bound replay 待执行

## 修复内容

1. 公共网页不再按整页最大文本选择正文，而是优先选择 `article/main`、article body、module body、entry content 等受限正文容器；只有受限容器成立时才允许 `div/br` 文本节点回退。
2. ASP.NET IR 页面的全页 `<form>` 改为 unwrap；异常包裹整篇正文的 header/nav/footer 也只 unwrap，普通导航／页尾仍删除。避免 NVIDIA IR 和 EE Times 原文随容器一起被删除。
3. publication-date adjudicator 优先使用发布 meta；没有 meta 时，只从正文容器及其最近文章祖先恢复可见日期。页尾推荐文章日期仍保留诊断但不能与正文日期同级争夺权威。
4. Candidate screening 按 `expected_output_ids` 编译 relationship facet。供应释放仍要求 capacity／shipment 等信号；“供应商点名 Dell／平台交付关系”则使用 deliver／available／support／partner 等关系动作，不再被错误套用产能词门槛。
5. 原 runner 新增正式 capture-replay 模式：绑定 predecessor terminal、plan digest 和每份 capture SHA，只重新编译 source object／candidate，显式记录 0 网络、0 Provider、0 模型和 route status delta，不再新增一次性回放脚本。

## 零网络实物诊断

对 R3 的同一 49 份 immutable capture 就地诊断，原始编译 `15 source objects／15 proposals／供应链 0` 改善为 `26 source objects／24 proposals／供应链 11`；publication-date unresolved `26→22`，parse rejected `8→1`。恢复的候选包括 NVIDIA 三期 IR、三篇 NVIDIA Newsroom 点名 Dell 的关系／可用性材料、CRN 供应连续性上下文和 The Next Platform 价值池反方。

这只是工程诊断，尚未物化 formal successor，也没有 CandidateDecision。未恢复的 Dell 价格、Dell 台数／份额以及 403、timeout、无日期产品页继续分别保留，不得被本修复伪关闭。

## 工程门

- 定向测试：`20 passed`；
- 全仓测试：`1040 passed`，仅 2 条既有 SWIG warning；
- compileall：通过；
- active baseline：`200 Python／8 frontend／5 detector／28 Runtime／0 forbidden`；
- secret scan：`7,628 files／0 findings`；
- 0 网络／0 Provider／0 模型／0 Evidence promotion。

下一步只能在 clean commit 上执行一次正式 `dell-external-residual-r3-capture-replay-r1`。该 replay 通过后，逐条审查 24 条 proposal，再经 Evidence Gate 决定哪些可进入 current Pack。
