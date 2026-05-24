# 20260515_phase1_qwen35_27b_gptq_serving_diagnostic

## Run Metadata

- Timestamp: 2026-05-15 21:57-22:18 Asia/Shanghai
- Type: inference serving diagnostic
- Status: diagnostic-only
- Owner/agent: Codex
- Environment: cloud RTX 4090 24GB, Python 3.12, vLLM 0.21.0
- Model artifact: `Qwen/Qwen3.5-27B-GPTQ-Int4` from ModelScope
- Local cloud path: `/root/autodl-tmp/FIN_Insight_Agent/data/models_private/modelscope/Qwen/Qwen3.5-27B-GPTQ-Int4`
- Benchmark script: `/tmp/qwen27b_vllm_bench.py` on cloud
- Cloud logs:
  - `/root/autodl-tmp/FIN_Insight_Agent/reports/demo/qwen27b_vllm_bench_offload14.log`
  - `/root/autodl-tmp/FIN_Insight_Agent/reports/demo/qwen27b_vllm_bench_offload10.log`
  - `/root/autodl-tmp/FIN_Insight_Agent/reports/demo/qwen27b_vllm_bench_offload6_len2048.log`
  - `/root/autodl-tmp/FIN_Insight_Agent/reports/demo/qwen27b_vllm_bench_offload10_graph.log`

## Purpose

用户要求先不要设置 fallback，排查当前 Qwen3.5 27B 4bit 量化版本为什么输出很慢，以及是否误用了 CPU 推理。

## Model Config Finding

当前下载的 `Qwen/Qwen3.5-27B-GPTQ-Int4` 不是理想的纯文本 planner 模型。`config.json` 显示：

- `architectures`: `Qwen3_5ForConditionalGeneration`
- `model_type`: `qwen3_5`
- includes `vision_config`
- includes `image_token_id` and `video_token_id`
- `text_config.model_type`: `qwen3_5_text`
- `text_config.num_hidden_layers`: 64
- `text_config.hidden_size`: 5120
- layer types include many `linear_attention` layers plus periodic `full_attention`
- checkpoint size reported by vLLM: 28.16 GiB

vLLM logs also entered `qwen3_vl.py`, `embed_multimodal`, and `visual` during profiling. This means the model is handled as a multimodal/hybrid architecture, not as a lean text-only 27B LLM.

## Benchmark Results

All successful runs used CUDA, GPTQ Marlin, and FlashAttention. They were not CPU-only inference runs.

| Config | Load/Init | GPU Model Memory | CPU Offload | KV Cache | Generation Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `offload=14GB`, `max_model_len=4096`, `enforce_eager=True` | 223.971s | 13.43 GiB | 14.11 | 65,080 tokens | 17 output tokens in 24.064s / 24.022s, about 0.71 tok/s |
| `offload=10GB`, `max_model_len=4096`, `enforce_eager=True` | 187.470s | 17.53 GiB | 10.03 | 26,396 tokens | 17 output tokens in 18.063s / 17.459s, about 0.94-0.97 tok/s |
| `offload=6GB`, `max_model_len=2048`, `gpu_util=0.98` | failed | 21.57 GiB before failure | 6.0 | not initialized | OOM during vLLM multimodal profiling; tried to allocate 288 MiB with about 23.47 GiB already in use |
| `offload=10GB`, `max_model_len=4096`, `enforce_eager=False` | 360.017s | 17.53 GiB | 10.03 | 25,486 tokens | torch compile took 80.00s; second generation about 0.93 tok/s |

## Interpretation

This is not CPU inference. Evidence:

- vLLM config logs show `device_config=cuda`.
- vLLM used `gptq_marlin` and FlashAttention.
- `nvidia-smi` showed about 21.4 GiB GPU memory in use and 100% GPU utilization during generation.

The slow output is mainly caused by:

- The selected artifact is multimodal/hybrid, not a pure text-only Qwen planner model.
- The checkpoint is 28.16 GiB, far too large to run fully on a 24GB RTX 4090 with KV cache.
- vLLM must CPU-offload 10-14GB of parameters. Reducing offload from 14GB to 10GB improved speed from about 0.71 tok/s to about 0.97 tok/s, which directly confirms offload as a major bottleneck.
- Lower offload to 6GB OOMs even at 2048 max length because vLLM profiles the vision branch and leaves almost no headroom.
- Disabling `enforce_eager` did not materially improve decode throughput; it only increased cold start due to compile and CUDA graph capture.

## Decision

Decision label: stop current model for mainline planner/summarizer demo.

Do not continue building the business demo on this artifact. It can load and generate, but under 4090 24GB it is too slow for an interactive planner-to-summary chain.

## Next Step

Use a text-only quantized instruct model and gate it before business demo:

- Config must not include `vision_config`, `image_token_id`, or `video_token_id`.
- vLLM should not enter `qwen3_vl.py` or multimodal profiling.
- Target serving profile: `cpu_offload_gb=0` if possible, or at most a very small offload.
- Required diagnostic threshold before planner demo: at least several tokens/sec on second generation for short JSON output, preferably comfortably above 5 tok/s on RTX 4090.
- Only after passing this gate should planner, verifier, and summarizer be wired back into the evidence pipeline.

## Safety Notes

- No cloud credentials were written to repo files.
- No fallback-generated business answer is promoted from the aborted demo.
- Existing demo script should be treated as diagnostic scaffolding until fallback behavior is removed or made opt-in.
