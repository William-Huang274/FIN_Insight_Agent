# FIN 0.1.3 S3 fixed-Pack 微判断 canonical live gate

日期：2026-08-16

状态：`working_tree_live_gate_implementation_pass / clean_sync_pending / natural_live_not_executed`

## 这轮在业务上解决什么

前一轮只证明“把一张大判断表拆成三段”在本地可执行，但真实调用入口仍只认识旧的 monolithic Judgment 和统一 `max / 16000` 配置。若直接签发 live，正式证明与真实运行会走两套不同路径，R2 的容量问题仍可能原样重现。

本轮没有新增 runner，而是在唯一 `run_s3_current_research_consumer_canary.py` 中增加一个严格受限的 micro authority 分支：

1. 第一步只允许并行读取当前单元的 reviewed Evidence 与 NumericFact，使用 `low / 2000`；
2. 第二至四步依次只允许 thesis、mechanism、counterargument＋WWC 中的一种提交，使用 `high / 8000`；
3. 每一步在 Provider 请求发出前核对活动工具集合；少一个读工具、混入其他工具或判断顺序漂移都会本地失败；
4. 三段仍由模型撰写并选择 relation alias／Evidence／NumericFact／Method／Graph 引用；Harness 只校验、展开已编译 alias 和编译同一个终态 Judgment；
5. 旧 R1/R2、标准 bounded loop、paired lane 和其他案例路径保持原行为。

## Authority 与止损边界

新增 scope decision 明确绑定 immutable R2 容量失败、formal micro proof 和一次 future Chat successor。预算固定为 `4 model call / 5 tool call / 0 EvidenceRequest / 0 retry / 0 fallback`；未授权 Responses、Anthropic、动态 Truth Spine、五单元或产品发布，也没有提高任何 token 上限。

live authority 必须同时绑定：当前 Evidence Pack、Case／cell、Claim Authority、Claim Surface、micro policy、read／judgment profiles、formal proof authority/result、R2 result/capacity assessment、canonical runner、Provider transport、loop implementation和 scope decision。Git HEAD、upstream、tracked worktree、Run/Attempt 输出身份和所有文件摘要必须在调用前通过。

如果自然 successor 再次在最小片段耗尽容量，或形成可见输出但 L1 失败，本项目不会自动签发下一次 R4/R5；第一项停止并进入项目级 Provider/profile/autonomy 处置。只有 natural submission、L1 和内容质量都成立，才进入第二项动态 Truth Spine。

## 零调用验证

- canonical runner 定向测试：`18 passed`；
- canonical runner＋Project OS preflight 联合定向测试：`25 passed`；
- 全仓测试：`320 passed`；
- Python compileall：通过；
- active baseline：`127 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`；
- secret scan：`6,606 files / 0 finding`；
- digest drift、旧失败身份漂移、已消费输出身份和非法活动工具集合均 fail closed；
- micro fake 路径为 `4 provider step / 5 receipt`，节点 profile 选择顺序为 `tool_routing → bounded_financial_judgment × 3`；
- 模型、网络、Provider、embedding、retry 和产品发布调用均为 0。

首次尝试 clean preflight 前发现旧 Project OS 校验器只认识 monolithic／alias 的单 profile、`3 × 16000` 预算。该问题没有被绕过：同一 preflight 现在保留全部旧决策测试，并新增 micro decision 分支，分别核对 formal proof、immutable R2、capacity assessment、read／judgment profiles、最近完整 Provider capture、零 retry 与凭据存在性。旧路径与新路径联合定向 `25 passed`；这只是预检兼容工程通过，真实 clean/synced preflight 尚待本提交推送后执行。

## 尚未证明与下一门

当前只是 working-tree live gate implementation pass，不是 natural fixed-Pack 通过。下一步只能先提交并推送本实现，在 clean/synced commit 上运行 decision-bound Project OS preflight，并对一份尚未使用的 exact-once authority 单独执行入口校验。全部通过后才执行唯一一次 DeepSeek Chat natural successor；执行结果必须先做 L1 与内容质量验收，不能自动进入第二项。
