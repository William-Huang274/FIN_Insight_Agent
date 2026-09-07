# S3 typed validation repair：零调用闭环与唯一 live gate

时间：2026-08-16
阶段：FIN 0.1.3 / S3 / fixed-Pack Layer One

## 为什么需要这一项

R7 已证明 DeepSeek 在关闭 thinking 后可以正常提交 Tool Call，但它一边选择“利润桥接无法推断”，一边又把未经证明的因素写成公司毛利率回落的正向驱动。现有因果门禁正确拒绝了这段话；真正缺少的是把拒绝原因返回给模型、让模型自行修正一次的标准 Agent 能力。

## 实现边界

本轮没有新增 attempt 专用 runner，也没有放宽金融规则。provider-neutral 核心新增一个同片段 repair compiler：保存原 Tool Call，把 `claim_surface_narrative_relation_conflict`、通用违规说明和修正要求作为 Tool result 放回原会话，只允许同一个 counter／WWC Tool 再提交一次。

明确禁止：

- 重跑 R6/R7 前六个成功模型节点；
- 新增 Evidence、NumericFact 或关系权限；
- 由 Harness 改写模型文字或选择结论；
- 放宽因果门禁；
- 第二次 repair、retry、fallback 或协议切换。

## 零调用结果

- R5 完整终态回放通过；
- R6 非思考失败节点 successor 回放通过；
- R7 rejected fragment、typed feedback 和一次 repair 消息序列均按 digest 绑定；
- 错误 failure code、真实正向因果越界、跨案例 identity／Graph 污染均 fail closed；
- DELL、MU、NVDA full-fake 均通过；
- 两个 fresh process 字节等价；
- model／provider／network／embedding／retry 均为 0；
- formal result digest：`2328029bf8f7ebdb19f570b52ffb8b204bab5b0916158e3c61427340b9958e82`。

首次编排时 authority 少绑定了 R5 回放依赖，runner 在产生结果前即 fail closed；补齐该静态依赖后才产生当前 formal result。它是证明配置遗漏，不是产品 Runtime 或模型失败，也没有被包装成一次成功运行。

## 下一门

Project OS 只允许一条新 authority：复用 R7 的六个模型节点，执行一次非思考 counter／WWC 修复提交。成功后仍必须独立检查 L1、八维内容质量和 paired gain；失败后不得自动增加第二个 repair turn。动态 Truth Spine、五单元、异质泛化、S3 acceptance 与发布继续禁止。
