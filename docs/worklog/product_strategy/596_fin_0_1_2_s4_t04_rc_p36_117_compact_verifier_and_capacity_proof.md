# FIN 0.1.2 S4-T04 RC-P36-117：Verifier 视图与容量证明

日期：2026-08-04

结论：零调用工程处置通过，允许签发并执行一条 fresh R3 exact-live；不允许自动重试或 R4。

R2 不是模型输出或 JSON 失败，而是第九次 Verifier 输出先被完整 capture 后，累计输入 63,419 超过固定 60,000。根因是 T04 没有按 current Evidence 编译容量，Verifier 同时收到完整 specialist/lead/writer、numeric、identity，并在请求顶层重复 numeric/identity。

本轮把本地完整验证对象与模型可见视图分开：本地仍保存和校验全部对象；Verifier 模型视图保留六条 Claim 的绑定 Fact 或 cannot-support、scope、qualification、WWC、Writer rendering，以及完整 cross-cell Lead。只把重复的 runtime/numeric/identity 大对象替换为 digest binding，顶层保留一份供本地响应分类器使用的 numeric/identity contract。

R2 真实 capture 零模型重编译显示，Verifier 请求字符数从 60,959 降为 38,816，保守估算从 31,296 降为 20,224。按 R2 其余八次请求不变计算，全链保守估算 91,527，低于编译上限 108,000，余量 16,473。108,000 仍低于 USD 0.06、10,000 output token 和 cache-miss 定价推导的绝对输入上限 117,931；在硬上限处最大估算成本 USD 0.05568。

共享 runner 不再在执行层写死 60k，而读取当前不可变 execution envelope。历史 S3/T03 envelope 仍是 60k，未改写。测试结果：T04 current integration 9 passed；S3/T03 atomic runner 11 passed；三案例 numeric/identity regression 41 passed；R3 admission/full-fake 2 passed；所有这些证明均为零 Provider/模型/网络调用。

RC-P36-117 当前状态只能记为 `zero_call_repaired / live reproof pending`。R3 成功后仍需正式九件套、独立 L1、paired L1–L4 与 owner decision，不能因容量工程通过直接宣称 current NVDA R2。
