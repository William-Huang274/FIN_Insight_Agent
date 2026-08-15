# FIN 0.1.3 S3 fixed-Pack 微判断 canonical live gate

日期：2026-08-16

状态：`clean_preflight_pass / natural_micro_R3_terminal_capacity_failure / project_level_disposition_required / no_R4`

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

首次尝试 clean preflight 前发现旧 Project OS 校验器只认识 monolithic／alias 的单 profile、`3 × 16000` 预算。该问题没有被绕过：同一 preflight 现在保留全部旧决策测试，并新增 micro decision 分支，分别核对 formal proof、immutable R2、capacity assessment、read／judgment profiles、最近完整 Provider capture、零 retry 与凭据存在性。旧路径与新路径联合定向 `25 passed`。实现随后分别以提交 `e377e351...` 与 `8ed2d5c0...` 推送；绑定 `8ed2d5c0...` 的真实 decision-bound preflight 通过，Git clean/synced、凭据只验证存在且没有读取或保存其值，模型／网络／Provider 调用为 0。

## Natural micro R3 结果

fresh authority `FIN-0.1.3-S3-DELL-VALUE-CAPTURE-FIXED-PACK-MICRO-JUDGMENT-CHAT-LIVE-AUTHORITY-V1.0` 只执行了一次，Run=`FIN013-S3-DELL-VALUE-CAPTURE-FIXED-PACK-MICRO-JUDGMENT-CHAT-R3`：

1. 第一步用 `low / 2000` 成功读取当前 Evidence 与 NumericFact，形成 2 份 accepted receipt；
2. 第二步只开放 `submit_research_thesis`，使用 `high / 8000`；Provider 返回 HTTP 200、完整且可解析的 JSON，但 `prompt=8,448`、`completion=8,000`、`reasoning=8,000`、可见内容和 Tool Call 均为 0，`finish_reason=length`；
3. Runtime 按 `model_gateway_reasoning_budget_exhausted` 原子终止；mechanism 与 counterargument＋WWC 两步没有尝试，retry／fallback 均为 0；
4. 原始响应、模型可见请求、调用参数、usage、失败阶段和 terminal result 已完整绑定 capture；私有 reasoning 与凭据没有保存。

该结果不是网络、凭据、UTF-8、Evidence reader、NumericFact reader 或本地 Validator 失败。它也不是金融 L1／内容失败，因为模型没有交出任何 thesis 可供评价。与 monolithic R2 相比，prompt 只从 `8,997` 降到 `8,448`，而 reasoning ceiling 从 `16,000` 降到 `8,000`；输出工具虽然缩小到一个 thesis fragment，但完整单元上下文仍然可见，自然 Tool submission 没有收敛。

## 尚未证明与下一门

fixed-Pack 第一层未通过，Owner 授权五项中的第 2–5 项均未开始。不得自动签发 R4、提高 token、切协议或进入动态 Truth Spine。下一项必须是项目级零调用处置，在“片段专属上下文投影”“分析与低／无 thinking 提交分离”“官方 Responses／Anthropic Tool Use 资格化”“更换 Provider／模型自主权 profile”之间做结构选择；只有选择后才能另行决定是否值得做一个单节点 canary。

权威结果为 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_micro_judgment_chat_live_result_v1_0.json`，容量处置为 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_micro_judgment_chat_live_capacity_assessment_v1_0.json`。失败 attempt 必须保持不可变。
