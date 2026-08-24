# S1 工作记录 079：8GB 量化 4B shadow 获取与同池评测

日期：2026-08-24
状态：`acquisition_preregistered / execution_pending`

## 1. 决策目标

用户明确允许在当前 8GB RTX 4060 Laptop GPU 上尝试更大的 embedding／reranker。
本切片建立独立的 `Q4_K_M 4B development shadow`，不修改已经冻结且因 24GB FP16
资源门槛而阻塞的 R3，不把量化运行冒充正式资格化。

当前先完成资产获取证据链；资产成功后才允许在固定的 18-query、86-candidate-occurrence
DELL／MU／NVDA development projection 上运行 0.6B 与 4B 同池对照。COST、ORCL、ASML、
ANET、隐藏 pack binding 和 source-bound input 一律不载入。

## 2. 候选与边界

- embedding：`Qwen/Qwen3-Embedding-4B-GGUF` 官方 `Q4_K_M`，固定 commit 和文件大小；
- reranker：官方 Qwen 目前没有本程序所需的固定 GGUF，选用固定 commit 的 community
  `giladgd/Qwen3-Reranker-4B-GGUF`。该来源差异是 material boundary，不能声称验证了
  官方 FP16 模型；
- runtime：固定 `llama.cpp b10516` Windows CUDA 12.4 两个 release assets，逐个校验
  bytes 与 SHA-256，再安全解压并形成 exact recursive file-closure manifest；
- 所有模型串行加载，禁止 CPU fallback；获取阶段模型调用与 provider 调用预算均为零。

## 3. 预注册判定

后续执行必须在完全相同的 86 个 pair 上重跑 0.6B，历史 0.75 只作背景，不作公平基线。
4B reranker 需达到 pairwise accuracy ≥ 0.80 且相对同池 0.6B 提升 ≥ 0.05；embedding
需达到 ≥ 0.80 且不低于同池 0.6B；DELL、MU、NVDA 任一 case 都不得 pairwise 退化。

即便全部通过，判定也只能是“值得进入 fresh natural-candidate-pool eval”。它不能证明
内源或外源召回、不能关闭 gap、不能提升 current runtime、不能赋予 Evidence/NumericFact
权威，也不能使 S1 qualified。

## 4. 证据与待办

- program：`configs/retrieval/fin_ia_0_1_3_s1_quantized_4b_shadow_acquisition_program_v1_0.json`
- implementation：`src/retrieval/quantized_shadow.py`
- acquisition runner：提交并同步 clean commit 后执行；
- 每个失败 attempt 必须保留 receipt，修复后使用新 attempt ID；
- 获取成功后另建 execution program，绑定实际 model/tool identity 和本工作记录，不从聊天记忆推断。
