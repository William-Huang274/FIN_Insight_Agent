# 859 — FIN 0.1.3 S2 provider-neutral 数字展示等价与本地渲染

日期：2026-08-11

状态：working-tree 零调用 successor 通过；旧 live terminal 不改；clean proof 待执行

## 为什么不能加一个 `surpassing` 白名单

旧 canary 在真正的数字权限门之前要求逐字出现 `customer count surpassed 5,000`。唯一 live 写成 `surpassing`，但 NUM ref、5,000、strict-greater-than 方向、Dell／Q1 FY27 身份和 E022 lineage 都正确。把 `surpassing` 单独加进 whitelist 虽能让本案通过，却不能阻止 `not surpassing`、`below`、`at most`、HPE 或 FY26 等真实错误，也会继续围绕当前 Provider 逐词修补。

本轮采用结构处置：模型保留 thesis、机制、反方、边界和 Evidence／NUM 选择；本地控制面只把绑定 NumericFact 的受保护数字片段渲染为 canonical presentation。兼容 v1 自由叙事时，先把 count relation 编译为 typed direction，并校验 negation、entity 和 period；长期 v2 应直接让模型返回 `NUM ref + relation/qualifier enum`，不再解析自由 prose 猜关系。

## Immutable capture replay

没有再调用 DeepSeek，也没有改写或追认旧 terminal。对 capture=`7cfd3c82...b9b6` 的 `provider_response.content` 原始输出运行 successor：四个 NUM 全部保留，三个金额表面原样通过，只有 `customer count surpassing 5,000` 被本地规范为 `customer count surpassed 5,000`；非受保护叙事、E018／E023 角色和 conversion／margin boundary 不变。successor validation=`35a06db4...2036`，support renderer receipt=`94371589...3f4d`，shared numeric guard=`c8130130...d25`。此前本地未推送结果中的两项 receipt 摘要来自错误的证明形状，已在 amend 和首次 push 前改为真实 capture replay 值，未用测试 fixture 冒充 immutable capture。

负向验证覆盖：否定关系、below、at-most、foreign entity、wrong fiscal period、wrong scale、wrong count value 和额外未绑定 inflected count；全部 fail closed。旧 `model_exact_surface` validator 仍按历史行为失败，证明没有暗中重标 failed run。

## 当前边界与下一步

这是 working-tree engineering pass，不是 clean proof。formal live 仍 failed，admission 已消费，Provider/model/network/source/retry=`0/0/0/0/0`，没有业务 Artifact、DELL 全报告、S2 closeout、Owner acceptance 或 release。

下一步提交并推送代码与合同，从 clean commit 建立两个 Git archive／fresh process，分别跑 renderer、旧模式回归、mutation 和 immutable capture 注入 replay。若 byte-equivalent 且全部通过，再单独做 S2 closeout／S3 entry 决策；不再签第二次模型 canary。
