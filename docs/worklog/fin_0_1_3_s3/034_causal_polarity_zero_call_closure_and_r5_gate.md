# FIN 0.1.3 S3 causal-polarity 零调用闭环与 R5 门

## 为什么需要这一步

FFJ-R4 已自然完成六次 DeepSeek 调用并提交三个单独有效的研究片段，但最终本地校验器把明确否定产品到公司利润桥的文字误判成强因果。根因不是模型或传输：旧规则会把“服务器”中的单字“使”识别为因果词，还会跨分句拼接主体、财务结果和因果词，并忽略“不能据此”“不可推断”“缺乏支持”“无法归因”等否定极性。

## 实现边界

- 在 provider-neutral `claim_surface_authority` 层按分句识别正向命题；
- 无独立语义的单字 CJK 因果词不参与子串命中；
- 明确否定、证据不足和不可归因表述不触发正向因果冲突；
- 中英文真实的产品／驱动因素到公司利润强因果仍硬失败；
- 不修改 R4 原文、不删除模型判断、不为 DeepSeek 增加 attempt-specific 分支。

## 正式证明

- authority SHA256：`e8dbe9d772ad76523e69211f5db4255372f53392a9d8f90e2ec70e3769270b24`
- result SHA256：`885c1ba19fe4a88ee2326bbf26639e1cafff484d72276a3730ffbd3aef43dad0`
- result digest：`d2607c9eb4c62bc1607467ffeb1cba8f3b807bb9b4c783fa5beaf7bdad6f1be8`
- 保存的 R4 terminal Judgment：`3a6214e3dbcb0637dd21a2d436ed72b9455d4c12b148b3768b7f16f5aa3b3b36`
- 保存的 R4 deliverable：`d3ea0ee15f9e478c9826b47626d485b51fb66295a1cdfff02fec4acf1c6bc7cd`
- 两个 fresh process 字节等价；R3 非回归、R4 原文回放、中文／英文正向强因果 mutation、DELL／MU／NVDA full-fake 和污染检查均通过；外部调用全部为 0。
- R5 decision-bound gate 纳入后的最终复证为定向 `34 passed`、全仓 `346 passed`、compileall、active baseline `127 / 8 / 10 / 0`、secret scan `6,662 / 0`。

## R5 决策

新决策只授权一个 clean/synced、exact-once 的 DELL `value_capture` fixed-Pack R5：最多六次模型传输、三个 accepted fragment、零 EvidenceRequest、零 retry、零 fallback。它不是动态 Agentic Research、五单元、泛化、S3 产品验收、S4 或 release 权限。

下一步顺序固定为：完整复证 → clean commit/push → 真实 Project OS preflight → fresh R5 authority → 一次 DeepSeek exact-live → L1 与内容质量评价。
