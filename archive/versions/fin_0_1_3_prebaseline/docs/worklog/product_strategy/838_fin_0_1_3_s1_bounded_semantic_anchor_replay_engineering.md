# FIN 0.1.3 S1 bounded semantic-anchor replay engineering

- 日期：2026-08-10
- 阶段：S1
- 状态：`working_tree_engineering_pass_clean_proof_pending`
- 网络／模型／retry：`0／0／0`

## 问题与判断

历史 source live 已经成功保存 Dell 与 Micron 两份官方长文档，但旧 policy 的 `.*` 在 `DOTALL` 下把短业务句扩成数万字符 match，造成两条存在于正文中的 Evidence 被本地误拒绝。继续重抓网页或调大 span 都不会修复这个根因。

本轮不修改历史 v1 policy、result 或已消费 authority。新增 v2 successor，把任意 regex 输入面替换成短 literal phrase groups；跨短语距离只由受 `max_anchor_span` 约束的最小窗口组合。

## 已完成

- 新增通用 `bounded_semantic_anchor` compiler：literal group 校验、全 occurrence 枚举、原文位置映射、最小窗口和有界 excerpt。
- 分离 `anchor_missing`、`pattern_occurrence_unbounded`、`multi_anchor_window_too_wide`、`final_excerpt_too_large`。
- 新增 S1 capture-replay successor policy/runtime；绑定历史失败 result、原始 22-Evidence predecessor Pack 和两份 immutable Reader response capture。
- 直接回放真实正文：Dell `55,765` 字符，Micron `26,784` 字符；没有网络或 Provider 调用。
- Dell `3/3`、Micron `2/2` fragments 全部恢复，Pack=`22→27 Evidence／15→14 gaps`，`core_research_ready／supplier_context_ready／valuation_input_ready=true/true/true`。
- mutation 覆盖长文重复词、尾部干扰、顺序打乱、缺失 anchor、真实宽窗口、最终 excerpt 过大和旧 regex surface。
- focused＋adjacent tests：`31 passed`。

## 产品增量与边界

补回的两条业务内容是：Dell `$24.4B AI orders／$51.3B AI backlog／demand exceeds supply` 的同段披露，以及 Micron `DRAM/NAND demand exceeds supply／tight beyond calendar 2027` 的供应商侧交叉验证。它们现在进入 corrected Pack 候选，不再被解析器误判为“来源没有”。

当前尚未做双 clean archive proof、持久化 corrected Pack、模型权限或 DeepSeek 报告比较；因此不能声称报告质量已经提高。下一步先提交并推送实现，再由两个 fresh archive worker 重放同一 private captures。
