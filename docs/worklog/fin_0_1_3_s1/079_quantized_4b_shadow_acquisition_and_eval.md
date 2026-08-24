# S1 工作记录 079：8GB 量化 4B shadow 获取与同池评测

日期：2026-08-24
状态：`acquisition_r1_succeeded / controlled_shadow_r1_failed / r2_required`

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
- acquisition runner：已从 clean／upstream-equal commit `f26d38d9` 执行；
- 每个失败 attempt 必须保留 receipt，修复后使用新 attempt ID；
- 获取成功后另建 execution program，绑定实际 model/tool identity 和本工作记录，不从聊天记忆推断。

## 5. acquisition-r1 结果

`acquisition-r1` 成功，公开结果为
`configs/retrieval/fin_ia_0_1_3_s1_quantized_4b_shadow_acquisition_result_v1_0.json`，
`result_digest=8655e01c7c6f686bd6a3b93031561151e64deea73ad7c4306291d5758986387e`。

- embedding identity：`8d94e3ac9802c1e6b6105c788d5aafadaf278a9ffc5d0a44df164e508db937f2`；
- reranker identity：`1067660e34c2174f80f827e9984008069425cd002e6210db3ec271b1abc6fd55`；
- llama.cpp identity：`ee50da2b1e2c8883ba0fb7814f94b8a6e3cf887a035c6f0e8e9c710dcad0fc06`；
- 工具自检：build 10516／commit `b95502ba9`，Windows x86_64，return code 0；
- 高层网络调用：2 次固定 HF snapshot + 2 次固定 GitHub release asset；provider 0、模型推理 0；
- 获取后 Z 盘剩余 `20,851,736,576` bytes；没有 CPU inference fallback，也没有运行任何评测。

公开结果与 private full result 逐字节相同，result digest 已重算通过；最终目录重新计算的
model/tool identity 与 transaction staging identity 完全一致。下一步必须先提交该 immutable
acquisition result，再建立 execution program，禁止直接凭成功下载启动无契约推理。

## 6. execution program 与 reranker 路线纠正

tokenizer 预检对完整固定输入实测：embedding query 最大 138 tokens、document 最大
2,199 tokens；reranker 官方完整 prompt 最大 2,397 tokens、p95 为 2,219。因此 execution
统一使用 2,560-token 输入上限和 4,096 server context，不允许静默截断。

设计时发现 `llama.cpp b10516` 虽公开 `/rerank`，但 causal-LM Qwen3 路线仍有 near-zero
score 缺陷（issue #25447）；completion logit-margin 修复 PR #25448 已关闭但没有 merge，
task instruction PR #20009 仍未 merge。直接使用该 endpoint 会生成形式完整但不可信的指标，
故 material correction 为：禁止 `/rerank`，逐 pair 使用与官方 0.6B 完全相同的 token IDs 和
fixed prompt，经 `/completion` 只生成一个 token，读取 raw `yes - no` logprob；任一 token
不在 top-logprobs、tokenization 不一致、发生 truncation 或不能证明 full GPU offload 都
fail closed。

execution program：
`configs/retrieval/fin_ia_0_1_3_s1_quantized_4b_controlled_shadow_program_v1_0.json`，
`result_digest=58fb88666784c2c71fb5c0cdd95ef2df0c8e63535877abe9c57359109b157681`。
其中 `s1c_qrel_03` 只有 positive、没有 hard negative，按既有 metric contract 记为
ineligible query，而不是伪造负样本或拒绝整个 projection；三个 case 都仍有足够比较对。
runner 和 program 必须先提交并与 upstream 相等；由于 GitHub HTTPS 暂时超时／reset，当前
不得绕过 clean-sync gate 启动推理。

## 7. controlled-shadow-r1 immutable failure

GitHub 恢复后，program／runner 与 acquisition receipt 一并同步到 clean commit
`3fcb4ac5`，R1 从该 commit 启动。R1 在完成 0.6B embedding 和全部 4B embedding 输入后
fail closed：不是 OOM、不是 token drift、不是模型输出失败，而是 default log verbosity 3
没有打印底层 layer-offload 行，过窄的 proof parser 因此无法证明 full GPU offload。

- 0.6B embedding：65 scored inputs，114.096 秒，pair input 无截断；peak used VRAM
  3,685 MiB；
- 4B embedding：65 scored inputs，65/65 tokenizer exact match，所有 server task 均显示
  `truncated = 0`；
- 调用：baseline 65 + challenger 65，localhost health 32／tokenize 65／embeddings 65；
  external network 0、provider 0、paid model 0；
- failure result：
  `configs/retrieval/fin_ia_0_1_3_s1_quantized_4b_controlled_shadow_result_v1_0.json`，
  file SHA-256 `110d2f12ad3a0ae8205ad7f69fbebb4617479abe48c47179e8b7e7357421f8d8`，
  `result_digest=80f2ed2727e2ca187dcc9614d27f3880022baf5c3b23f7e4542c34dd0e4eeeaf`；
- private log SHA-256：
  `ec9f786acb03a2fab0ca3591053030bd1a15e321dbd8b517164da69300f59279`，
  20,330 bytes。

R1 结果不得补写成功阶段、不得复用未公开的 embedding score。R2 必须重跑相同四阶段，
唯一 proof 修复为把 llama server log verbosity 固定为 4，并把 observed embeddings
`n_batch=512` 显式写入命令，避免依赖 runtime 自动降档；仍需相同 full-offload gate。
