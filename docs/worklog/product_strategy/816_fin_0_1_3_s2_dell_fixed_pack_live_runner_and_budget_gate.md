# 816 — FIN 0.1.3 S2 DELL fixed-pack live runner and budget gate

日期：2026-08-10

状态：working-tree implementation passed；successor clean proof required

DELL-only live runner 和 authority compiler 已完成。真实执行最多调用 DeepSeek Pro 13 次，不含任何搜索／爬虫／数据库工具，0 retry、0 fallback、0 business promotion。每个模型请求和完整 provider response 在解析前保存到私有 attempt；公开 terminal 只暴露 digest、节点、finish reason、usage 和 finding code，不公开原始报告、源正文或凭据。

本轮主动补出一个旧 clean proof 没覆盖的预算风险：原 Runtime 固定 13 节点并限制单节点 max tokens，但没有在每次真实响应后核对累计 input/output/total tokens 和估算费用。现在每次响应先 capture，再核对累计预算；超限立即 terminal failed，不继续下一个节点。新增 oversize mutation 证明第一次超限响应仍保留 capture，且没有第 2 次调用。

Project OS preflight 初次失败不是 DELL blocker，而是根因账本已经引用 `additional_external_live_attempts` 和旧 same-evidence scope，registry 却没登记，导致全局合同无效。现已补齐这两个历史 scope，并新增 `FIN_0_1_3_S2_FIXED_PACK_DELL_CANARY`；该 scope preflight=pass，RC-P36-157/168 只继续阻断外源／动态研究，不阻断 frozen-pack 分析。

focused=`21 passed`。因为核心 Runtime SHA 已变化，proof `36512cb6...ae24` 只保留为历史，不用来签发新 live。下一步先提交／推送当前实现，再跑 v1.1 两 fresh-worker proof，之后才签发一次 DELL admission。
