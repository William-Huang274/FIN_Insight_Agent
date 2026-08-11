# 661 — FIN 0.1.3 Codex 三案例 Gold Research Benchmark 启动

日期：2026-08-06

## 用户纠偏

用户指出，当前固定九次调用与空泛 Workpaper 只证明 Harness 可运行，不能证明金融 Agent 平台能够产出有质量研报；API 费用不应凌驾于研究信息增益之上。用户要求 Codex 先使用当前 MCP、现有数据和公开补充来源完成 DELL、MU、NVDA 三份研报，订正为标准答案，再与 DeepSeek 产品运行逐节点对照，并在偏离节点暂停和扶正。

## 决策

- 接受当前 S3 结果只是 minimum formal Anchor/diagnostic，不是产品级 research proof。
- 不预设 9 次或 15–25 次模型调用上限；用 evidence-gap closure 和 information gain 决定停止。
- 先产出三份 `Codex-authored gold candidate`，人工接受前不称最终 gold。
- 当前 Codex 会话未直接注册 FinSight MCP 工具；已通过仓库 stdio FastMCP server 成功执行 `list_tools`，真实暴露 SEC search、exact ledger、market、industry 和 run artifact 工具。relationship/web 工具虽有 registry 合同，但未从当前 stdio server 暴露，后续必须如实区分。
- DeepSeek 对照在三案 gold candidate 冻结后开始，且不能看到参考答案。

## 本轮已完成

- 读取 Project OS、全局产品审视、协作规范、Git 规范和相关 S1/S3 工作日志；
- 检查工作树为 clean，分支 `codex/layered-data-source-expansion` 与 origin 同步；
- 通过真实 stdio MCP session 初始化并列出当前 server tools；
- 新增产品范围与对照协议，作为跨会话恢复源。

## 研究执行结果

- 当前 stdio MCP 的 `list_tools` 与三案 market snapshot 成功，证明协议连接和部分 business handler 可用；SEC search/exact-ledger 在真实调用时分别出现长时间阻塞和 120 秒超时。已停止精确识别的 workspace MCP 进程，没有留下孤儿进程。
- 本轮未把 MCP operational failure 伪装成模型失败，也没有因此放弃研究。复用 S1 已审计本地资产和历史成功 MCP rows，并用 Dell、Micron、NVIDIA、TSMC、Microsoft 的最新一手公开材料补源。
- 完成 DELL、MU、NVDA 三份 `gold_candidate`，均含 thesis、关键数值重算、经济机制、跨公司互证、最强反证、price-in、WWC 与 typed gaps。
- 交叉复核后主动订正 DELL AI server 中个位数营业利润率披露、MU SCA take-or-pay/volume 覆盖，并避免用 NVDA equity gains 放大的 net income 证明主营质量。
- 三案均通过真实性、身份、期间、数值、引用、推断边界和 fair-balance hard gates；由于 MCP 全工具面、竞争/终端 ROI 与 forward valuation 面板仍不完整，只冻结为 gold candidate，不冒充人审最终 gold。

## 结果物

- `docs/research/fin_0_1_3_gold_candidates/DELL_research_gold_candidate_20260806.zh-CN.md`
- `docs/research/fin_0_1_3_gold_candidates/MU_research_gold_candidate_20260806.zh-CN.md`
- `docs/research/fin_0_1_3_gold_candidates/NVDA_research_gold_candidate_20260806.zh-CN.md`
- `docs/research/fin_0_1_3_gold_candidates/THREE_CASE_CROSS_REVIEW_20260806.zh-CN.md`

## 当前边界与下一步

三份研报已完成，DeepSeek 同输入逐节点对比尚未开始。下一步先把 gold candidate 编译成 DeepSeek 不可见的 claim/evidence/conflict/WWC 评分对象，再按 Research Lead → Search/Evidence → Specialist → Lead/Conflict → Writer → Verifier 逐节点执行；发生实质偏离时暂停、记录 supervisor correction 后继续，并区分 model-only、supervisor-augmented 和 deterministic runtime 的贡献。
