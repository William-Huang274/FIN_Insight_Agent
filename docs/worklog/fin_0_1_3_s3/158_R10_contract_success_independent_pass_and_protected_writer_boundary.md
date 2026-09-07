# R10 四节点成功、独立 L1／L2 通过与 protected Writer 边界

## 结论

R10 exact-once authority v1.4 已唯一执行并消费。Demand analysis、Demand strict submission、Lead analysis、Lead strict submission 四个节点全部为 DeepSeek HTTP 200／`tool_calls`，0 retry／fallback；五份非 Demand 底稿逐字节复用，Writer 没有调用。独立零模型复评确认原七项 material finding 全部关闭，当前六份 workpaper 集合通过 L1／L2，但这只让受保护的 Writer 零调用工程门具备资格，不等于 Writer live、最终报告、S3 或产品验收通过。

## 不可变运行证据

- authority：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_authority_v1_4.json`
- public result：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_result_v1_4.json`
- public SHA-256：`8b09565fa3db768a6e93df2416b84b9873e16cbb5717d6d747cf1d33f9a6ef0a`
- public result digest：`83dc3d600ce9d123a073af30fe8646b7bd740b24869c9218d04113557d186112`
- private full result：`data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/dell-current-dynamic-multi-agent-content-reassessment-resume-live-r10-20260823T194751Z/full_result.json`
- private SHA-256：`0b2545f4f688193132dbfa24abb3f0d020499a606503340a36ac9ed28f9e37a8`
- private full digest：`cab0b654f3ff2f99193d299e7c6cc345049d36a087a0e95557120dff1036e900`

四个 capture 的 finish reason 均为 `tool_calls`。合计 prompt 63,984、completion 38,429、reasoning 29,117 tokens；新 S1/S2、retrieval、外源、Candidate promotion 和 Writer 调用均为 0。公开／私有 canonical digest、公开绑定的 private SHA 与 private ref 全部复验通过。

## 独立内容复评

评估文件：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_R10_content_assessment_v1_0.json`
- SHA-256：`a5186450f3eaf743825f22f116a5558e5f74c573e86d10ac0572cb0e8448026d`
- assessment model calls：0。

R10 Demand 的 `thesis`、`mechanism`、`sourced_claims[0]`、`strongest_counterarguments[1]` 与 `stop_reason` 均明确：`$24.4B` 订单与 `$16.1B` 已确认收入只是同季并列信号；收入不能归因于当期订单的季内转化；cohort、交付时点、取消与转化率继续未解决。pull-forward 与消化仍只是未量化的可能路径，`GAP::00730082A5C08C4C` 保留。R9 Cash、Counterevidence、Operating、Supply、Value 五份底稿 digest 与内容逐字节不变。

原七项 finding 的处置为 7/7 closed：贡献桥、同季/cohort、资产负债表 proxy/cash、跨公司客户结构、NVDA 出口管制到 Dell、公司毛利到产品定价权、pull-forward/消化均通过。Lead 的 catalog-bound `proceed_to_evaluation` 与当前材料一致，但不替代本次独立复评。

## 剩余非阻断保护面

workpaper 诊断为 26/28，Q8 在 Writer 报告前不适用。三条 L3 不需要再付费返修 Specialist，但必须进入 Writer 的机器可见保护合同：

1. Operating 的“收入增速放缓使费用杠杆收窄成为算术必然”只能改为条件性概率或省略；
2. Cash 的 `$1.253B` 只能写成三行资产负债表营运资金 proxy 变化，禁止精确 cash absorption 和 AI 归因；
3. Counterevidence 的 NVDA／MU 绝对库存余额没有 typed 跨公司机制和可比尺度时必须省略。

同时必须继续保护七项已关闭的 material boundary。Harness 不得替 Writer 写业务观点，只能编译明确的禁止／降级规则并验证最终报告。

## 下一门

当前只允许 `zero_call_capture_bound_R10_Writer_successor_with_material_and_L3_surface_protections_engineering_only`：绑定 R10 authority／public／private／assessment，复用六份 workpaper 与 Lead decision，证明唯一 fresh frontier、Writer 输入、输出 schema、引用权限、material 与 L3 fail-closed 检查及完整 fake seam。任何 Writer Provider call 仍须等待完整回归、clean commit／push、repository-aware preflight、任务特定 TokenBudgetBasis 与 fresh exact-once authority。最终报告形成后仍须独立 L1／L2、八维质量和产品可读性验收。

## 已消费 scope 的 fail-closed 更正

七项 material issue 关闭后，综合定向第一次复跑为 `1 failed, 114 passed`：旧测试仍期待已消费的 R10 scope 可以通过当前 Project OS preflight。即使在关闭行保留历史 `allowed_run_scopes`，`full_chain_blocker=false` 仍会使当前显式许可为空；这是正确的安全语义，不应把问题重新标成 blocker，也不应放宽 preflight 来允许再次签发。

最终测试改为同时证明两件事：不可变 R10 decision 仍可验证精确四调用合同；当前 `build_preflight` 必须以 `project_os_current_dynamic_multi_agent_content_repair_scope_allowance_missing` fail-closed。修正后综合定向恢复为 `115 passed`。历史许可只用于审计，不是 fresh authority；下一 scope 必须是新的 RC-S3-088 Writer 零调用工程门。
