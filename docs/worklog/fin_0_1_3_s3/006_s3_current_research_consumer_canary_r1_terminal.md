# S3 当前研究消费者 Canary R1 终态

日期：2026-08-13
状态：`terminal_failed_no_retry / zero_call_structural_disposition_next`

唯一一次 DeepSeek Pro 调用已完成：HTTP 成功、exact JSON、5/5 cells，token usage=`14,141 / 2,643 / 16,784`，但只返回 `cells`，首个失败为 `research_consumer_output_envelope_invalid`。没有 retry、fallback、检索、Planner 或产品发布。

保存输出的零调用诊断证明不能只补 envelope：model-visible schema 没列出合法枚举，模型自创 status/confidence/direction；全局 Evidence＋cell allowlist 造成跨 cell 引用；复合证据被同时用于 support/counter；价值单元出现自由数量级表述。内容层还把集团/分部结果、营运资金和上游扩产越界归因到 AI/Dell，并把未证实的供应缓解写成结论。

项目责任与模型责任必须分开：枚举缺失、本地字段回写、cell 数据组织和二元 Evidence role 是项目合同问题；忽略 claim boundary、因果归因和过度乐观判断是本轮自然模型质量问题。R1 永久保持 failed；下一项只做零调用结构处置，不自动签发 R2。
