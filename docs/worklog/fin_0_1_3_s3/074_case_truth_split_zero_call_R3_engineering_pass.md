# 074 Case Truth split zero-call R3：分析、交卷与聚合工程门通过

时间：2026-08-17

## 结论

R3 绑定 clean/synced commit `9529fb2fad5623141ef73fa8d6384be327740295`，正式通过零模型、零 Provider、零网络、零 embedding、零 retry、零候选晋升和零发布的结构复证。R2 的 proof-runner 失败保持不可变，没有被改写为成功。

## 做了什么

1. 把 R7 的 15 个 Judgment surface 按五个 cell 拆成五份不可变 claim-document slice；每份恰好包含 thesis、mechanism、counterargument／WWC 三面，并绑定父 document digest。
2. analysis 节点读取完整 compact Case Truth view 与一个 slice，只形成可见语义草稿，不带 Tool Call。
3. non-thinking submission 节点只读取 packet digest、slice 与草稿，映射到 canonical strict tool，不接收完整 truth catalog。
4. local Validator 分别裁决每份 receipt；Harness 只在五份 slice 互不重叠且完整覆盖父级 15 surface 时聚合。
5. canonical tool 与 Provider wire projection 分责：前者保留 exact count 和金融合同，后者只做兼容投影，本地 Validator 始终为最终权威。

## 复证结果

- `5` 个 cell slice，`3` 个 surface／slice，父级覆盖 `15/15`；
- 原 R7 三条 `asserted_absent_but_present_in_case` 全部保留；
- 合法 product-to-company profit bridge gap 未被误拒绝；
- 缺一个 slice、重复一个 slice、跨 Case、未知 alias、surface digest 漂移和排列 mutation 均 fail closed；
- direct submission user message=`33,092` chars；最大 analysis slice=`28,483`；最大 strict submission=`3,951`；
- direct canonical tool=`6,526` chars；最大 slice tool=`5,213`；
- DELL／MU／NVDA presence aliases 分别为 `61/49/55`，异质 holdout 继续通过；
- pre-proof 整库 `486 passed`，compileall、active baseline=`138 Python / 8 frontend / 11 Runtime / 0 forbidden`，secret scan=`6,847 / 0`。

## 边界与下一门

R3 证明的是节点拓扑和本地金融权威没有因拆分而丢失，不证明 DeepSeek 自然语义判断、R7 修复或报告质量。下一门只允许 Operating 和 Counterevidence 两个受影响 cell：每个 cell 一次 visible analysis 加一次 non-thinking strict submission，共最多四次调用、0 retry。必须自然识别 AI revenue、orders、backlog 三条 false absence，同时保留真实利润桥 gap；通过前不得自动修文、重跑 Planner/S1/S2/五个研究 analysis、进入其他三 cell、Synthesis、泛化或发布。
