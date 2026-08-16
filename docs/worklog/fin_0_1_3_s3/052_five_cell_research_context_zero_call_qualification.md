# 052 S3 五单元研究上下文零调用资格化

日期：2026-08-17

## 为什么先做这一步

DELL `value_capture` 动态单单元已经通过，但完整案例还包括需求真实性、经营表现、现金转换和反方／WWC。直接让模型跑五单元会把“模型没得到正确研究方法”“关系上下文跨单元污染”和“模型自身判断失误”混在一起，无法定位责任。

本轮只把五个研究房间的资料边界摆正，不调用模型，也不把 fake 输出当成研报。

## 实际改动

1. 历史 consumer policy v1.2 保持字节不变，新增 successor v1.3。
2. 为五个研究单元各迁移一份最小、case-neutral 的 RoleMethodPack；它只说明怎么分析，不携带 DELL、MU、NVDA 的答案或事实。
3. GraphContextPack 只从当前 Case、当前 Evidence、NumericFact 和 typed relation 即时编译；旧图数据没有恢复，Graph 不授予事实或因果权威。
4. fake payload 记录每个单元实际消费的方法步骤和图关系；方法不足、未知引用、跨单元、跨案例和错误图消费均被拒绝。
5. 完整五单元输入为 76,509 个 user-content 字符，低于当前 80,000 容量门；这只是工程容量，不代表模型质量。

## R1 与 R2

R1 的业务和 mutation 证明通过，但公开结果仍带 runner 中硬编码的旧日期，且 next decision 忽略了 Owner 已有的连续执行授权。R1 保持不可变，不能手工覆盖。

runner 改为从 authority 读取签发时间，并把下一步写成条件化的独立 natural authority。随后签发 R2：

- `recorded_at=2026-08-17T00:36:58+08:00`
- result digest=`da69170a7f21e38b2f74c57d4b8bad1c765992b81f3c4380408758d9e5bdbb7e`
- 19 条模型可见 Evidence，其中 5 条 transcript
- 25 个模型可见 NumericFact
- 10 个 residual gap
- 5 个 RoleMethodPack、5 个 current-case GraphContextPack
- 0 model／Provider／network／embedding call

## 真实结论与边界

五单元上下文工程门通过。它证明每个单元能拿到自己的方法、证据、数字、关系和缺口，也证明错误引用会 fail closed。

它没有证明 DeepSeek 能自然完成五单元，没有证明跨单元综合、完整八维研报质量或 S3 acceptance。下一步必须使用新的 clean exact-once authority 运行自然 DELL 五单元，再做独立 L1、逐单元质量、跨单元综合、paired 和 qualified-human 验收。fake deliverable 不进入 Workbench。
