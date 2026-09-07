# 117 — DELL 报告边界密度与来源充分性审计

## 用户问题

最新 DELL 报告比旧版可靠，但边界说明、无法推断和数据缺口过密。此次工作要求逐项确认它们究竟属于内部数据、外部来源、Harness／Runtime、Agent 研究方式还是真实信息边界，并修复最早责任层；不得继续用“付费数据难获得”解释免费公开源尚未优化。

## 审计结果

对最终 draft、rendered report、六份 workpaper、S2 source-bound numeric review、report authority catalog、S1 readiness、Evidence Pack 和 source-route truth 完成零模型、零网络对账。

- 8 组边界中，4 组属于 operations／method，必须在客户报告前处理；
- 4 组属于本轮材料仍未闭合的 current-run uncertainty；
- 0 组取得 proved public-information boundary 权威；
- 当前报告合同回放为 `0 hard / 17 quality`，其中 12 条直接来自 boundary density。

最具体的内部漂移是 Cash：应收、库存、现金和融资应收已经取得 source-bound NumericFact／presentation authority。复核原始底稿后确认 Cash Agent 已经看见并分析这些值，真正过期的是更早的 `NUM_REF_UNRESOLVED_BALANCES` evaluator finding。Writer 同时收到新权威和旧 finding，导致报告同时出现真实数字与“source-visible but non-covered”的过期说明。

另外两条所谓 gap 是研究者尚未冻结的 thesis／监控阈值。公司没有义务披露研究者自己的失效阈值，因此它们必须移到 S3 Research Method，不能继续进入来源缺口清单。

## 结构修复

1. source-route truth 新增 `research_sufficiency_state`，外部补源由“候选覆盖不足”或“研究仍有 material gap”任一条件触发；
2. Writer 合同禁止执行摘要成为 gap inventory，要求边界只完整描述一次，confidence 不再复述 gap 清单；
3. Writer audit 新增非阻断 boundary-density finding，不由 Harness 自动改写观点；
4. 新增 `ReportBoundaryDisposition` 合同，强制区分 operations-only、resolve-before-report、current-run uncertainty 和 proved information boundary；
5. 新增 provider-neutral source-use policy，允许可信行业／媒体 context 补机制、竞争和反方，同时继续禁止其创造目标公司精确财务事实；
6. 保存 DELL 逐项机器审计，不重写、不重新标注历史 live。

## 产品判断

过去的“官方优先”被实现成了近似“官方之外都不能进入研究”，这是产品理解偏差。精确公司数字应窄授权，但高质量研究还需要客户、供应商、产品配置、行业出货、渠道、竞争和反方。正确控制面不是删掉这些来源，而是明确每类来源能证明什么、需要怎样交叉验证、如何 capture、何时能进入 Evidence。

免费源仍有明显可做空间：issuer IR、对手方官方披露、政府／标准组织、公开行业摘要、客户部署案例、后续季度披露、RSS／GDELT／Common Crawl 的原文发现。目前干净 Runtime 尚未完整接回这些路线，因此不能用当前稀疏材料证明免费公开信息无价值，也不能直接要求购买付费源。

## 下一步边界

下一轮先做 S2→S3 evaluator supersession 和 researcher-threshold ontology 修复；只有新权威改变事实语义时才重裁决 Agent。随后做 DELL 四类 material uncertainty 的免费源 capture 纵切。新资料经过 source-use、parser lineage、Evidence Role、Evidence Gate 和 S2 fact／estimate boundary 后，只重裁决真正受影响的 Demand、Value、Cash、Supply。之后才生成新报告，并用 MU、NVDA 和异质留出案例复证。当前未签发模型调用、网络 source live、S1／S3 验收或发布。

## 最终工程复证

- 定向验证最终为 `48 passed`，并另行验证历史质量策略与当前边界密度策略可以并存；
- 全仓 `977 passed`，仅保留 2 条既有 SWIG deprecation warning；
- `compileall`、Workbench TypeScript typecheck 和 production build 通过；
- active baseline 为 `191 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`；
- archive redirect `6,059` 条通过，secret scan 扫描 `7,560` 个文件、0 发现，`git diff --check` 通过；
- 新质量规则曾使 2026-08-21 的不可变 reference-patch proof 按当前审计规则重算失效。现已显式版本化质量策略：历史 proof 按 legacy policy 复验，但因 implementation SHA 漂移仍拒绝作为当前执行 authority；新报告默认使用 boundary-density policy。历史结果未被改写或重新授权。
