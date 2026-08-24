# S1 工作记录 074：大模型 challenger 与材料组选择真相审计

## 结论

- 请求绑定的材料组、同口径时间配对和“先保护完整 bundle、再截有限审阅窗”已经存在于当前 `evidence_set_coverage.py`／`material_evidence_runtime.py`，本轮没有重复改写；两组定向测试共 `35 passed`。
- 已冻结一份只允许 DELL／MU／NVDA development、禁止 COST／hidden／frozen／holdout 的大模型 challenger 程序。候选主线是 Qwen3-Embedding-4B＋Qwen3-Reranker-4B，BGE reranker v2 Gemma 只作次级候选；Jina Embeddings v4、GTE-Qwen2-7B、E5-Mistral-7B 和 Nemotron-8B 分别因多模态／许可证或资源／适配边界延期。
- 当前机器是 RTX 4060 Laptop、总显存 `8,585,216,000` 字节。冻结 profile 是单卡 24GB-class CUDA／FP16（最低 `24,000,000,000` bytes）、载入前至少 20 GiB free，禁止 CPU model fallback、量化资格替代和 profile 偷换。因此预检在下载前以 `resource_blocked_before_download` 停止；网络、Provider、模型调用均为 0。
- 这不是模型质量失败。当前只证明“本机不能合法进入 4B 效果实验”；迁移到合适 GPU 后才按 candidate ceiling → same-pool reranker → role/period mutation → efficiency receipt 的顺序打开新 attempt。

## 为什么不能只换大 reranker

COST R2 的三条有用候选已经在 shared pool 中但位于 rank 21。这个证据说明 4B reranker 可能改善同池排序，却不能代替请求绑定的材料 bundle 保护。反过来，若 material target 根本不在 candidate pool，任何 reranker 都不得继续执行并声称修复召回。

实验门因此固定为：

1. 先检查 target-in-pool@96、material requirement group coverage、exact-object diagnostic 与身份／期间错误；
2. candidate ceiling 不足就停止 reranker；
3. reranker 必须在完全相同的 pool 上比较，pairwise hard-negative accuracy 至少 `0.80` 且比当前 Qwen3-Reranker-0.6B 的 `0.75` 高至少 `0.05`；
4. 任一公司、指标、期间、关系方向或 Evidence Role critical error 都直接拒绝；
5. development 结果最多标为 shadow credible，不能变成 blind qualification、Evidence、NumericFact 或 current Runtime promotion。

## 工程增量

- 新增 v2 Hugging Face 分片权重身份绑定：校验唯一 index、非空 weight map、分片类型、路径不越界和每个 shard 实际存在；digest 同时绑定 index、所有 shard、config 与 tokenizer。历史 v1 runtime 不承担这个新增职责。
- 当前单文件 Qwen3-Embedding-0.6B digest 仍为 `4a3dd5cb...be76c`，Qwen3-Reranker-0.6B 仍为 `9fa9d067...45ad2`，证明历史单文件身份没有漂移。
- 新程序记录了 hypothesis、decision target、baselines、split/leakage、candidate ceiling、stop conditions、efficiency 与两个本地模型节点的 `TokenBudgetBasis`。
- 没有重跑 0.6B 模型。已有内容寻址 baseline 足以冻结比较点，而 4B 在资源门停止；此时重算 0.6B 不改变决策，只会制造额外 attempt。

## 机器凭据

- 程序：`configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_program_v1_0.json`
- 预检：`configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_0.json`
- 分片身份实现：`src/retrieval/model_identity.py`
- 资源门实现：`src/retrieval/large_model_challenger.py`
- 定向回归：model identity／resource gate `14 passed`；材料组／时间 bundle `35 passed`。

## 冻结证据绑定失败与后继修正

第一次全仓门禁得到 `1185 passed, 2 failed, 2 warnings`。两个失败都来自 immutable VS5 策略对 `embedding_runtime.py` 的源码摘要绑定：初版为支持 4B 分片权重而修改了被冻结的 v1 runtime，门禁因此按设计拒绝。没有改旧策略哈希；失败已固化为 `configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_frozen_binding_failure_v1_0.json`。

后继修正是把 `embedding_runtime.py` 恢复为 `e1778f24...bada1`、把 `cross_encoder.py` 恢复为 `d05afdc8...5e21`，再把完整分片／tokenizer 身份绑定放到 `model_identity.py` 的明确 v2 API。两个原失败契约与新身份／资源门定向回归随后共 `15 passed`。预检结果还绑定 v2 identity、resource gate 和 materializer 的实现摘要，避免只有 program、没有执行实现的审计缺口。

最终新 attempt 的全仓门禁为 `1188 passed, 2 warnings`（两条均为既有 SWIG deprecation warning）。另外通过 compileall、9 个变更 Python 文件 pyflakes、984 份 config JSON、8 份 Project OS JSONL／1122 行、active baseline `212 Python／8 frontend／5 detectors／28 resources／0 forbidden`、Workbench TypeScript／production build、7862-file secret scan／0 和 diff check。全仓 pyflakes 仍会报告多个不属于本轮的历史未使用导入及旧 S3 脚本未定义名，本轮没有借 S1／S2 范围静默清理。

## 外部候选依据

- Qwen3-Embedding-4B：<https://huggingface.co/Qwen/Qwen3-Embedding-4B>
- Qwen3-Reranker-4B：<https://huggingface.co/Qwen/Qwen3-Reranker-4B>
- BGE reranker v2 Gemma：<https://huggingface.co/BAAI/bge-reranker-v2-gemma>
- Jina Embeddings v4：<https://huggingface.co/jinaai/jina-embeddings-v4>
- GTE-Qwen2-7B-instruct：<https://huggingface.co/Alibaba-NLP/gte-Qwen2-7B-instruct>

## 当前边界

`resource_blocked`、`engineering selector verified` 和 `development preregistered` 都不是 S1 资格。COST R1/R2 继续不可变且失败，旧 labels 已失盲；下一次资格必须使用 Git 外、独立裁决的新 temporal／heterogeneous labels。当前 `S1_qualified_stable=false`。
