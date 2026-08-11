# FIN 0.1 S2-T03 DeepSeek segmented v4 adapter

## 实现

保留 canonical `fin01.bounded_agent.specialist_lead_output:v4` 严格嵌套合同不变，新增 `fin01.bounded_agent.deepseek_segmented_json_object:v1`：

1. Specialist 只生成 flat `specialist_judgment`；
2. 本地验证 candidate allowlist、文本、enum 与 findings；
3. Lead 只消费已验证 Specialist，生成 flat `lead_adjudication`；
4. 本地验证 evidence refs 同时属于输入 candidates 和 Specialist findings；
5. deterministic assembler 生成 exact v4 envelope，再复用最终 v4 validator；
6. Writer 与 Verifier 路径不变。

未来 exact admission 的 semantic/provider/network cap 需从 3 调整为 4，并显式绑定独立 `lead_max_output_tokens`；retry 仍为 0。原 combined DeepSeek strict-tool 与 OpenAI native routes 保留，未静默切换默认应用。

## 验证与边界

Positive fixture 证明 4-call 路径可生成 exact v4 artifacts；negative fixture 证明 Lead 引用未供应 candidate 时在 Writer 前 fail-closed。该轮 paid/live provider calls=0，不代表 DeepSeek v4 协议已真实通过，也不关闭 T03。下一步必须先决定是否签发一份 fresh DeepSeek segmented exact live admission，不能复用任何历史 admission。

Focused T03 contracts=`70 passed`；gateway + S2-T01/T02/T03 + Project OS 联合回归=`94 passed`。
