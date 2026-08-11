# 663 — FIN 0.1.3 S2-04 共享 Benchmark Evidence 与隐藏 Gold 冻结

日期：2026-08-07
类型：`S2 evaluation input / fairness / leakage control`
状态：`pass_closed / Experiment A admission not issued`

## 1. 目标与关键判断

本项只解决 Experiment A 的公平输入与评分隔离，不评价 DeepSeek，也不修 MCP。Gold 报告不能靠删除结论字段后直接给模型，因为章节标题、材料顺序、分析粒度和反方组织本身会泄漏答案。因此实现采用中性重编译：只把事实、数值、来源 authority、发布日期、截至日、边界和明确缺口放入 model-visible Pack；thesis、机制综合、counter-thesis、WWC 答案和评分目标留在 evaluator-only 对象。

## 2. 冻结产物

- model-visible shared pack：`eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json`，digest=`93a75f3d4863a240ea58824429fe697427edefda31a0a671dddc15f51710030d`；
- model-visible blind input：`eval_sets/fin_0_1_3_same_evidence_v1/model_visible/experiment_a_blind_inputs_v1.json`，digest=`55b474867594c002cd87494fc3d825b39cc60f3000adae06253f8e2256a61688`；
- evaluator-only hidden objects：`eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json`，digest=`4ec201a52eb0d796658faf9a71c22cfcb1902b73ab52d2c3af9d72ecb9a4ebab`；
- freeze manifest：`configs/releases/fin_ia_0_1_3_s2_04_shared_benchmark_evidence_freeze_v1_0.json`。

规模为 `3 cases / 10 sources / 33 evidence items / 12 derived numeric / 12 explicit gaps / 12 hidden targets`。Micron Q3 发布日按 current source-grounded input 修正为 2026-06-24；NVIDIA operating/OCF margin 分别按源数字重算为 `65.60% / 61.68%`。

## 3. 验证与安全边界

编译器与 validator 覆盖：

- model-visible blind 与共享 Pack 的事实面精确相同；
- source published-at 不晚于 as-of；
- evidence ID、issuer 和 case 不得跨案；
- numeric 与 formula 可独立重算；
- Gold/evaluator key 和结论短语不得出现在 model-visible 对象；
- hidden target 必须绑定本案 evidence；
- 任一对象 digest 篡改均 fail closed；
- model-visible 与 evaluator-only 物理分目录，后续 runner 不得通配共同父目录。

focused=`10 passed`；当前 S1–S3 successor 加本项=`146 passed`。扩大执行所有 `FIN_0_1_3` 命名合同测试得到 `276 passed / 8 failed`；8 项是历史 S0/弃用 0.1.4 快照对资产总数、旧 source hash、旧 next-action 或 capability ledger 最后一行的固定假设。它们保持可见，但不属于 S2-04 产品逻辑失败；测试期间产生的两处临时旧哈希改写已恢复，没有用修改历史证据换取全绿。

## 4. 调用与能力声明

- 模型/Provider/网络/MCP/产品业务 run：`0/0/0/0/0`；
- admission：未签发；
- DeepSeek 分析质量、Agentic Search、MCP operational truth、S3 产品证明和 release：均未建立。

## 5. 下一项

严格进入 `FIN-0.1.3-013-S2-05-EXPERIMENT-A-DEEPSEEK-SAME-EVIDENCE-ADMISSION-AUTHORITY-DECISION`。下一项必须把 runner 的读取 allowlist 限定到 `model_visible/experiment_a_blind_inputs_v1.json`，预注册节点顺序、预算、capture-first、首个 material failure 停止与 raw/correction/corrected 分轨；通过后才可签发模型执行 admission。
