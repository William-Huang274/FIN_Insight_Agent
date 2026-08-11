# 664 — FIN 0.1.3 S2-05 Experiment A admission authority 暂不签发

日期：2026-08-07
类型：`experiment governance / admission authority / runtime gap`
状态：`authority_not_issued / one zero-call implementation successor allowed`

## 1. 本轮问题

S2-04 已冻结公平的 blind input，下一步原本是判断能否签发 Experiment A。入口审计必须先回答：仓库是否已有真正执行“Research Lead 规划→多研究单元 Specialist→跨单元综合→Writer→Verifier”的 runner，而不是再次把最小结构链当作产品研报。

## 2. 审计结论

暂不签发 admission。当前缺少：

1. Experiment A 专用 runtime policy、runner 和 production entrypoint；
2. 五类自然节点的同源 output contracts；
3. 一案一个 exact-once admission、capture-first 和 terminal 证明；
4. per-node/case/campaign 的 token、cost、timeout envelope；
5. raw model-only、supervisor correction、corrected candidate 与 evaluator-only 的读写隔离。

已有 `s2_natural_canary_runtime.py` 仅执行三次窄 alias 选择；`s3_formal_anchor_runtime.py` 仅执行九次 compact Specialist 选择，Lead/Writer/Verifier 不是 Experiment A 所需的自然模型节点。二者直接复用会高估产品完成度，因此被判定 incompatible，而不是“先跑了再说”。

## 3. 唯一后继实现边界

- 一案一个 admission，顺序 DELL→MU→NVDA；
- Lead 规划 6–8 个研究单元，覆盖需求/客户、产品/技术、供应链/竞争、财务与现金、资本市场/price-in、反方/风险/WWC 六个 family；
- 每单元一个 Specialist，随后各一次 synthesis、Writer、Verifier；
- 每案 10–12 calls，campaign 最大 36，retry/fallback=0；
- 模型只读 S2-04 精确 blind input，不允许父目录通配、hidden Gold、MCP、外网或 out-of-pack 事实；
- 首个 material failure 先保存 request/assistant raw capture，再停当前案，不自动开始下一案；
- raw runner 不得写 supervisor correction 或 corrected candidate。

这个 30–36 次的受控范围不是随意扩大调用，而是从六个研究覆盖 family 和五类节点倒推得到；它修正了旧“三案九次调用即可证明研报质量”的不现实假设。

## 4. 证据与测试

- decision：`configs/releases/fin_ia_0_1_3_s2_05_experiment_a_admission_authority_decision_v1_0.json`；
- focused contract：`7 passed`；
- S2-04 freeze/input SHA 与 canonical digest 重新绑定；
- material blockers、宽目录读取、retry、错误调用上限、admission 越权 mutation 均 fail closed；
- admission、credential value read、model、Provider、network、MCP、business run=`0/0/0/0/0/0/0`。

## 5. 下一项

`FIN-0.1.3-013-S2-05-EXPERIMENT-A-DYNAMIC-NODE-RUNNER-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`。

本决定只允许一个零调用实现包。full-fake/preflight 通过后仍需新的 admission authority decision；不能从本轮自动签发、消费或调用 DeepSeek。
