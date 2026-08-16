# DELL 五单元 R3 node successor 工程门

日期：2026-08-17

## 目标

不重跑已经完成的 Planner、S1/S2、五个分析和三份有效 Judgment。现有稳定五单元 runner 新增一个受 authority 驱动的 node successor，只允许：

1. 复用 demand、operating、cash 三份有效 Judgment；
2. 校验并复用 value、counter 两份自然完成的分析草案；
3. 为 value、counter 各执行一次 DeepSeek Beta strict 交卷；
4. 五份 Judgment 全部有效后，执行一次综合分析和一次综合交卷。

## 实现边界

- 对 R3 的 request/response capture 重新计算 body digest，核对 run/attempt、消息摘要、finish reason、完整响应标志和保存的分析文本；任意字节漂移 fail closed。
- canonical 金融 Tool 保持 provider-neutral；只在 DeepSeek 边界投影 `$defs→$def` 并剔除 Beta 不支持的 wire 关键字，返回后仍执行完整本地合同。
- 公开结果区分整节点复用和仅分析草案复用，保存 capture receipt 与 canonical/wire Tool digest。
- 不增加新的 attempt runner，不访问网络，不执行模型，不修改 Evidence、NumericFact 或当前产品指针。

## 工程验证

- 成功 fake：精确 4 calls，`0` cell analysis、`2` cell submissions、`3` reused judgments、`2` reused analysis drafts、`1+1` synthesis；
- 失败 fake：第二次交卷失败后保留四份有效判断，综合不执行，总调用 `2`；
- capture 正向与内容突变负向均通过；
- value、counter 和 synthesis 三种真实 Tool 结构都能投影并保留共享 server pattern；
- 相关测试通过，随后全仓 `447 passed`、compileall、活动图 `134 Python / 8 frontend / 10 Runtime / 0 forbidden`、secret scan `6,797 / 0`。

这仍只是工程门。下一项必须把真实 R3 capture receipts、三份有效 Judgment digest、两份 analysis digest、三份 Tool projection digest 和两次独立测试结果写入 formal zero-call proof，再单独签发 live authority。
