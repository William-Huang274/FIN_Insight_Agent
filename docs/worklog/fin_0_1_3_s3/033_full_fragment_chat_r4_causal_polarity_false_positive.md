# S3 完整片段 Chat FFJ-R4 因果极性误报

时间：2026-08-16

## 运行结果

FFJ-R4 在 clean/synced commit `ac5b84ca...` 上完成 6/6 次 DeepSeek 调用。三份 analysis 都有可见内容，三份 submission 都只有一个 Tool Call，三个 fragment 均单独通过。执行为 0 retry、0 fallback、0 外源检索、0 embedding、0 协议切换。

自然提交的业务含义：

- thesis：管理层称 AI server 产品盈利符合其目标，但未经独立审计，不能建立产品到分部／公司利润桥；
- mechanism：缺少产品价格、量和配置拆分，产品盈利如何转化为分部／公司利润不可推断；
- counterargument／WWC：公司毛利率同口径方向收缩，只是公司层反向观察，不能归因于单一产品；后续需要同口径财报和产品／分部桥。

没有观察到新的金融 L1，但终局以 `claim_surface_narrative_relation_conflict` 失败，所以 formal L1、内容验收和 fixed-Pack Layer One 仍为 false。

## 真实根因

旧 lexical guard 把三种不同问题混成一个布尔共现：

1. 因果词“使”作为单字子串命中“服务器”；
2. AI server subject、profit outcome 和“转化”等词即使位于不同分句也会被拼起来；
3. “不能据此”“不可推断”“缺乏支持”“无法归因”没有被当作否定极性。

因此模型写的是“桥不存在”，系统却把它解释成“AI server 导致公司利润”。这是项目的 provider-neutral defense-in-depth false positive，不是 DeepSeek 不遵循合同，也不是网络错误。

## 有界修复

- 只在同一分句寻找 subject＋outcome＋causal term；
- 忽略没有独立语义的单字 CJK guard term；
- 明确识别中英文否定／不支持标记；
- 中英文真实跨层正向因果仍以原错误码 fail closed；
- R4 保存参数原样 replay，Harness 不修改模型叙事；
- 同一 formal proof 继续覆盖 R3 claim-local／typed boundary 和三案例 full-fake。

当前定向测试为 `54 passed`，全仓为 `345 passed`；compileall、active baseline `127 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference` 和 secret scan `6,657 files / 0 finding` 均通过。尚未执行 formal two-fresh-process proof或新的模型调用。
