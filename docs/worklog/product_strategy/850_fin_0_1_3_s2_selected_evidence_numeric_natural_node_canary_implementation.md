# 850 — FIN 0.1.3 S2 数字视图最小自然节点 canary 零调用实现

日期：2026-08-11

状态：working-tree engineering pass；待双 clean archive／fresh process 复证；未调用 DeepSeek

## 做了什么

本包没有重新跑 DELL 报告，而是把已批准的单节点 canary 做成可执行控制面。编译器直接复用前序 clean-proven 的 DELL selected-Evidence numeric co-compilation，只选 E022、E018、E023 和 AI server revenue、customer count、orders、backlog 四个 NUM。最终 provider request 为 11,838 字符，未发送完整 27-Evidence Pack 或 raw `source_text`。

Runtime 先用共享 SQLite ledger 消费 fixture admission，再保存 request；Provider 返回后先完整保存 response capture，之后才检查 `finish_reason`、JSON、字段、case/node、Evidence role、NUM ref、允许展示、研究边界和本地金融数字门。成功结果也只生成 no-promotion terminal；失败保留 raw capture，但公开 terminal 不复制内容。相同 admission 在不同 attempt root 再次执行仍被 exact-once 拒绝。

## 真实发现

合法 fixture 首次没有通过。原因不是模型，也不是 `$16.1B` 或 5,000 客户错误，而是共享数字门把全案 inventory 中 `context_only` 的裸 `2027／3／7` 与整段输出做 substring 匹配；只要写 `FY2027 Q1` 或普通文本就可能误杀。这说明“禁止输出候选”本身还必须带 materiality 和 selected-Evidence scope，不能把 parser 产生的每个数字 token 都当交付层金融事实。

修复没有取消 guard。candidate literal 分支只接收三条 selected Evidence 中带货币、百分比或 typed count 语义的 surface；独立 money／percent／count scanner 仍扫描全文。验证中新增 `$17.2 billion` 仍 hard fail，错单位、HPE read-through 当 Dell direct proof、缺反方、缺持续性边界、target price、截断和 invalid JSON 也都 fail closed。

## 结果与边界

- focused fake／mutation：19 passed；
- 连同决策、共编和相邻合同：35 passed；
- Project OS scoped preflight：pass；
- model/provider/network/source/retry：0/0/0/0/0；
- live scope：未注册；live admission：未签发；business promotion：false。

机器结果：`configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_minimum_zero_call_implementation_v1_0.json`，digest=`47dc0b3817adc310604b46414422a40b0cf049e329c57b40905bb30f6cce654b`。

下一步必须先把本实现提交并推送，再从该 clean commit 建立两个独立 Git archive／fresh process，断网、去凭据执行相同 fake／mutation 并要求规范化输出逐字节一致。通过后仍只能做一次新的 live authority 决策，不能自动调用 DeepSeek 或恢复 DELL 全链。
