# FIN 0.1.3 S1 VS5 来源捕获与解析执行绑定

日期：2026-08-18

状态：`all_sources_captured_once / parser_execution_bound_before_parse_outcome / S1_not_qualified`

## 1. 实际取得了什么

预注册的 7 条官方路线均在各自第一次传输尝试中成功，并先保存完整原始响应、再允许任何解析：Costco FY2024／FY2025 10-K、JPMorgan FY2025 10-K、Caterpillar FY2025 10-K、Novo Nordisk FY2025 20-F、Shell FY2025 20-F，以及腾讯 FY2025 官方年报 PDF。总计 7 次网络请求、0 次模型调用；公开结果只保存状态、字节数和正文摘要，原文仍在 private capture store。

这一步只证明来源可达、身份与正文摘要已绑定，不证明资料已被正确解析、检索、重排或晋升为 Evidence。

## 2. 捕获后发现的治理缺口

原预注册已经冻结案例、来源目标、命题、门槛、隐藏执行次数和 CUDA-only 检索规则，但只绑定了 SEC 对象编译与检索实现，没有明确绑定腾讯 PDF 的 layout／OCR 实现。若直接查看解析结果再决定用什么 parser，会让异质留出受到结果驱动选择。

因此本轮在查看腾讯解析结果前新增不可变 execution binding：

- 绑定 7 份 source body 的 SHA-256 和字节数；
- 绑定 response-body 校验／私有 CAS 物化、PDF layout parser、金融对象编译器和唯一 CLI 的代码摘要；
- 冻结腾讯全页解析和低原生文本页自动 OCR；
- 不改变任何案例、命题、来源路线、阈值或隐藏执行次数；
- 解析产物仍只是 candidate，不授予 Evidence 或 NumericFact 权威。

这是对预注册遗漏的透明补充，不是根据解析好坏移动门槛。

## 3. 向量计算边界

本步骤不计算向量。后续任何 Embedding、dense／multi-vector 或 Cross-Encoder 正式运行仍只允许 CUDA + FP16，并必须保存设备、CUDA runtime、precision、模型和 cache digest。GPU 条件不满足时 fail closed，禁止 CPU fallback。CPU 只承担 PDF／OCR、BM25、SQL、分词、硬过滤、账本和确定性编排；OCR 不属于向量计算。

## 4. 验证与下一步

execution binding 已纳入 split-safe program manifest；foundation validation 显示 6 个预注册案例和 1 份执行绑定。来源捕获、PDF 物化、layout pipeline 和 program foundation 的 37 项定向测试通过。

下一步只能在本提交推送后执行腾讯 PDF 解析，再将 6 个 SEC 文档和腾讯 PDF 编译进同一通用金融对象库。解析结果若没有自然扫描的实质页，`real_scanned_source_qualified` 必须诚实失败，不能用人工 raster mutation 代替。
