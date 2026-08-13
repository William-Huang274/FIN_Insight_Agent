# S3 标准 Tool Calls R2 合同编译处置

日期：2026-08-14
状态：`R2_immutable_terminal / project_contract_compiler_root_cause / no_R3_or_five_cell_authority`

## 真实进展

绑定 clean upstream `6f9ed940...` 的唯一 replacement R2 已执行。第一步 Evidence＋NumericFact 安全并行读取成功，R1 的 wire index、parallel policy、receipt identity 和 capture ref 问题得到真实关闭；共保存 2 份 accepted receipt。

第二步模型针对 value-capture 的 unit volume gap 提出业务相关 EvidenceRequest，想用 AI server shipments／compute capacity 区分 volume-led 和 price-led revenue growth。该动作未执行检索、未关闭 gap、未晋升 Evidence／NumericFact，也没有生成 Judgment。

## 最早责任层

失败码为 `finance_loop_evidence_request_intents_invalid`，但根因不是单一 222>120：

1. Tool Schema 没有公开 validator 的 `maxLength`／`maxItems`；
2. Tool Schema 平铺全部 facet 和 metric，未编译 facet→query family→allowed metric 的依赖；
3. proposal-only 的可修复格式/路由错误直接终止整条链，没有 typed rejection＋同预算修正语义。

因此本轮归属 S3 的 provider-neutral Tool Contract Compiler／repair semantics，不归 DeepSeek、不归 S1 实际检索，也不能通过放宽一个长度门或增加 prompt 关闭。

## 后续边界

下一项只做零调用结构处置：从同一 EvidenceRequest／route 合同编译 Schema 与 Validator；将跨 family 研究需求确定性拆成多个兼容 atoms；对 proposal-only 本地格式错误返回 typed rejected-not-executed 结果并保留 gap；用 R2 capture、三案例 fake 和非法组合 mutation 复证。第三次 single-cell live、DELL 五单元、内容评分和 S3 acceptance 均未授权。
