# FIN 0.1 S2-T03 DeepSeek segmented v4 exact admission issuance

## 结果

用户明确授权“签发全新的 DeepSeek segmented-v4 exact admission”。本轮签发 `fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v6_0.json`，使用新的 admission ID、WorkUnit idempotency key 与 isolated runtime root；身份尚未消费，未开始执行。

Admission 精确绑定同一 NVDA 单 Cell Case/input、`deepseek-v4-pro`、`fin01.bounded_agent.deepseek_segmented_json_object:v1` 与 canonical v4 输出。调用上限为 Specialist、Lead、Writer、Verifier 共 4 个 semantic/provider/network calls；每次 transport attempt=1，retry/fallback=0，成本上限 USD 0.05。source network、external tool、live business Case head write 均关闭。

## 独立复核与零调用证据

复核发现 runner preflight 最初会把 segmented transport 误报为 strict tool；已在签发前修正为 `tool_name=null`、`strict_schema_requested=false`，并加 exact admission 合同测试。Deterministic prepare 与 presence-only preflight 均通过，candidate_count=3、max output tokens=4200、output-only ceiling=USD 0.003654；model/provider/network/external-tool calls 均为 0。Credential 只来自现有进程环境，值未读取、输出、保存或进入 Git。

Focused T03 contracts=`71 passed`；T01+T03+Project OS=`82 passed`；gateway+S2-T01/T02/T03+Project OS 联合回归=`95 passed`。

## 边界

本轮只签发，不授权或执行 DeepSeek live validation。Fixture 与 admission preflight 不能证明 provider 实际会返回合规分段 JSON，也不能证明 closed v4 Agent Artifact 或研究质量。T03 继续 failed，T04、S3、release、production 继续 blocked；下一项必须由用户单独决定是否执行该唯一 admission。
