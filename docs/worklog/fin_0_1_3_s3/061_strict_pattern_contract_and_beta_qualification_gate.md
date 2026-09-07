# S3 strict-pattern 合同与 Beta 资格门

日期：2026-08-17

## 为什么需要这一项

DELL 五单元 R3 的 value 与 counter 分析都自然完成，失败发生在最终 Tool 交卷：模型分别把 `10-Q`、`FY27 Q1` 和 `8-K` 写进了禁止数字、日期、单位、URL 与引用的判断原子。本地校验正确拒绝，但当时 Tool Schema 只有文字说明，没有把同一规则编译成服务端可执行谓词。

## 已完成的结构修复

1. 一份 provider-neutral 模型文本谓词同时驱动本地校验、最终 Judgment、微判断与五单元综合 Schema。
2. 禁止面覆盖数字、币种／百分比／基点、URL、内部引用、中文口头数值区间与 filing/period 中携带的数字。
3. Schema 只保存一份共享定义，避免每个字段重复长正则；加入后的单节点 Tool 体积仍仅为旧单体合同的 56.84%。
4. 历史五单元 proof 改为按当时 Git blob 校验；历史结果仍可复核，但已消费权限不会重新成为当前权限。
5. 实现提交 `e68e34141231e7d90f06c67b1e9068867ac6d694` 已推送；全仓 `437 passed`，活动图 `133 Python / 8 frontend / 10 Runtime / 0 forbidden`，secret scan `6,786 / 0`。

## DeepSeek profile 隔离

DeepSeek 官方 strict Beta 要求 `/beta`、所有函数 `strict=true`，文档使用 `$def` 而非标准 `$defs`，且不支持字符串长度及数组数量约束。当前新增的 Provider 投影只在 DeepSeek profile 边界执行：

- `$defs` 改名为 `$def`，同步重写 `$ref`；
- wire 上剔除其不支持或未资格化的长度／数组数量／唯一性关键字；
- `pattern`、对象 required、additionalProperties、enum 等继续保留；
- 返回后仍执行完整本地金融合同，不能把 Provider 子集当成金融权威。

实现提交 `67e877d4c2f77b59db5b185770bc68e660d90697` 已推送；相关 `124 passed`、全仓 `442 passed`、compileall、活动图 `134 / 8 / 10 / 0` 与 secret scan `6,791 / 0` 通过。

## 当前权限与下一步

零调用结果 `fin_ia_0_1_3_s3_deepseek_strict_pattern_zero_call_result_v1_0.json` 只证明确定性投影，未证明远端接受。当前 scope decision 只允许一次不带金融 Evidence 的 Beta strict-pattern canary：1 model call、1 transport attempt、0 retry/fallback、0 产品晋升。若通过，才建立 R3 node successor，精确复用三份有效 Judgment 与 value/counter 两份分析草案，只执行两次重新交卷与两次综合调用。
