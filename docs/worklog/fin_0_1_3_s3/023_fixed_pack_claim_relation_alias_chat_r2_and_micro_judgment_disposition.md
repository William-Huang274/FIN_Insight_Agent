# FIN 0.1.3 S3 fixed-Pack ClaimRelation alias Chat R2 与微判断处置

日期：2026-08-15

状态：`R2 terminal_failed_no_retry / fixed-Pack layer one blocked / micro-judgment successor selected`

## 这次真实运行发生了什么

clean/synced commit `442e505b` 通过 Project OS preflight 后，项目签发了唯一一次 DELL `value_capture` ClaimRelation-alias Chat successor。第一步 DeepSeek 正确并行读取 reviewed Evidence 与 NumericFact，HTTP 200、`finish_reason=tool_calls`，形成两份本案 receipt。

第二步仍未提交 Judgment。Provider 返回完整 HTTP 200 JSON，prompt 为 8,997 token，completion 为 16,000 token，其中 reasoning 仍为 16,000；可见内容为 0，tool call 为 0。Runtime 以 `model_gateway_reasoning_budget_exhausted` 终止，0 retry、0 fallback。L1 与内容质量仍不可评价，动态第二层没有进入。

## 和 R1 相比真正学到了什么

R1 第二步 prompt 是 18,902 token；R2 已降到 8,997，减少超过一半。关系 alias、本地展开、紧凑事实视图、权限卡单次投影和删除零预算 EvidenceRequest 工具都是真实有效的工程改进，但它们不足以让模型完成最终提交。

因此不能再把根因写成“输入仍然太长”，也不能继续删几个字段或增加输出上限。当前最终工具仍要求模型一次完成：全单元结论与置信度、三条关系选择、多组 Evidence/Numeric/Method/Graph refs、thesis、mechanism、counterargument 和 what-would-change。再叠加全局 `thinking=max`，一个业务判断节点被做成了单次超大认知与序列化任务。

中途终端曾把 UTF-8 中文显示为乱码；随后用 Python 读取原始 bytes 并检查 Unicode code point，确认 capture 中没有 U+FFFD，模型输入是合法中文。该乱码来自本地 PowerShell 输出显示链，不能记为产品根因，也未据此修改代码。

## 下一项结构包

仍留在第一项和 S3，不新建版本、不切动态层：

1. 把一个 monolithic Judgment 拆成 provider-neutral 的 bounded micro-judgments；模型仍负责 thesis、mechanism、counterargument 和 WWC 等研究判断，不把内容写死在 Harness；
2. 每个 micro-judgment 只看到当前决策所需的最小 typed refs／alias，Harness 只做校验、alias 展开、lineage 绑定和终态拼合；
3. 把“研究节点复杂度”和 Provider reasoning 参数分开，避免所有节点一律 `max`；最终确定性渲染继续留在本地，不再消耗模型调用；
4. 用同一 DELL Evidence Pack replay、DELL/MU/NVDA fake、跨案例污染、漏原子、重复原子、因果越权和预算 mutation 做零调用证明；
5. 只有 clean proof 和新的 Project OS authority 通过后，才讨论一次新的 natural proof。R2 永不改写，且该 proof 不是 retry。

## 产品边界

这次失败不证明 DeepSeek 的金融研究质量差，因为没有可见 Judgment；也不证明 compact alias 方案无价值，因为 prompt 已实质下降。它证明的是当前 Harness 把研究判断和大合同序列化压进同一节点，无法在该 Provider 的 max-thinking 行为下稳定收束。动态 Truth Spine、单单元 Agentic Research、五单元和三案例仍全部等待 fixed-Pack 第一层形成可验收 Judgment。
