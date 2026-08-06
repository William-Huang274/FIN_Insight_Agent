# 670 — FIN 0.1.3 S2-05 layered raw-evaluation structural repair

日期：2026-08-07

状态：`zero-call engineering pass / replacement live not authorized`

## 为什么不是再补一个字段

DELL collect-all 证明问题有三个共同根：prompt 与 validator 不是同一份 typed contract；数值门禁混淆合法显示、假设阈值和无权财务推导；formal first-failure 使模型评估在第一条错误处失去后续观测。逐字段补丁无法解决这三个根因。

## 本轮实现

- 用单一 typed contract 编译 Lead、Specialist、Synthesis、Writer、Verifier 的模型可见结构；
- 明确 dependency/conflict 行结构、overall_boundary string 和 material_failure boolean；
- 修复 `B` suffix、percent unit 与合理舍入的 numeric authority；
- 将 stop_condition/what_would_change 中的假设阈值记录为 L3，而不是冒充事实或直接杀死 raw evaluation；
- 保持 narrative 中输入外财务数值为 L1；
- 新增 OCF margin→净利润/P-E 与 backlog→EPS/股价跌幅的确定性金融语义 finding；
- 分离 raw experiment scoreability 与业务晋升：完整链即可以进入 hidden scoring，但任一 L1 都令 `business_promotable=false`。

## 证据

聚焦回归 `39 passed`，宽 S2 回归 `115 passed`，覆盖 DELL/MU/NVDA full-fake、typed contract、数值 mutation、金融语义 mutation 和原有 exact-once runner。新的 successor runner 在三案执行 30 个 fake calls，并在 DELL material numeric mutation 中仍执行满 10 calls 到 Verifier；所有路径 capture-first、exact-once、业务晋升为 0。把真实 DELL 十份 immutable 输出原样 replay 后得到：`raw_chain_complete=true`、`hidden_scoring_eligible=true`、`material_failure=true`、`business_promotable=false`、32 findings。说明新标准既能看完整模型表现，也没有放过实质错误。

下一步不是自动再跑 live；successor execution binding 已零调用证明，先提交并推送干净修复链，再单独决定是否签发一次 DELL replacement admission。
