# FIN 0.1.3 S1 VS5 腾讯版式结果与资格对象库计划

日期：2026-08-18

状态：`tencent_layout_parsed / natural_scan_gate_open_failed / unified_object_store_execution_pending`

## 1. 腾讯官方年报的真实结果

绑定后的 parser 全页处理 282 页，全部为 `native_pdf_layout`，共识别 425 个表区、6 个脚注并编译 1,264 个候选金融对象；0 个低置信 material numeric token，0 网络、0 模型调用。该结果证明非 SEC 官方 PDF、CJK／英文混合文本和复杂表格可以进入同一 candidate spine。

同时它也证明该文档不是自然扫描件。预注册的真实扫描来源门因此保持未通过；不得通过人工栅格化页面改写这个资格结果。OCR mutation 仍只是工程回归，不是自然来源泛化证据。

## 2. 为什么不再造 VS5 对象脚本

现有对象库构建器原本把验收写死为 DELL／MU／NVDA＋每案一份行情快照，也只识别旧官方 PDF 对象。继续复制一个 VS5 builder 会重新制造两套 manifest、两套 parent／child 规则和两套验收语义。

本轮改为扩展同一构建器：

- 旧 `current_product` profile 完全保留原 market 门和结果状态；
- 新 `qualification_candidate` profile 复用相同 source digest、parent／child、容量、表边界、alias 与 candidate-not-Evidence 规则，但不要求资格案例拥有行情快照；
- 增加 `parsed_pdf_layout_document` 输入，并通过 digest-bound source spec 复用腾讯解析合同；
- case readiness 不再写死三家公司或 SEC 表单枚举，任何绑定到当前 case 且非 market snapshot 的官方 parent／child 都可计入对象存在性；
- 两个 profile 都不授予 Evidence 或 NumericFact 权威。

## 3. 下一步

先将上述通用化与资格 manifest 作为干净提交推送；随后只运行一次 7 来源对象构建，检查 source digest、公司／期间、parent／child lineage、表边界和对象容量。通过后才物化 runtime-visible qualification inputs 与 evaluator-only references；learned retrieval 仍需另行生成 CUDA／FP16 receipt，禁止 CPU vector fallback。
