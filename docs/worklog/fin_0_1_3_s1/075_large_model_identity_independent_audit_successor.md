# S1 大模型身份独立审计与 v3 successor

日期：2026-08-24

## 结论

提交 `635c943f8efc562091647838132e2aedcca7f8d4` 的 4B 预检结论仍然真实：本机 RTX 4060 Laptop 只有 `8,585,216,000` bytes 总显存，两个模型目录均不存在，流程在下载前停止，network／Provider／model call 均为 0。独立只读审计没有发现伪造的 4B 质量结果，也确认冻结的 0.6B runtime 文件未漂移。

但审计发现 v2 model identity 不能给未来的 4B attempt 签权。v2 只绑定少量顶层 config、weights 和 tokenizer 文件，而实际 SentenceTransformer 路径允许 `trust_remote_code=True`，可能读取 `modules.json`、嵌套 sentence-transformers 配置和本地 Python。调用方还可以直接写入声称的 model ID。该 finding 记入：

- `configs/retrieval/fin_ia_0_1_3_s1_large_model_identity_independent_audit_failure_v1_0.json`

## v3 修正

`src/retrieval/model_identity.py` 保留 v2 供历史收据重放，新增 v3：

1. 模型目录必须有 `fin_ia_model_acquisition_manifest_v1_0.json`；
2. manifest 的 model ID 必须与 preregistered expected ID 完全一致；
3. resolved revision 必须是小写 40-hex commit；
4. acquisition tool 固定为 `huggingface_hub.snapshot_download`；
5. manifest 必须精确列出目录内除自身外的全部 regular files；
6. identity 递归绑定 manifest、自定义 Python、`modules.json`、所有嵌套配置、tokenizer、weight index 和 shards；
7. missing／extra／size drift／digest drift／路径逃逸全部 fail closed。

新程序 `program_v1_1` 只接受 `identity_bound_v3`。旧 `identity_bound` 不能再让资源合格主机进入 development attempt。R1 中内嵌的历史 COST-derived 诊断也从可执行程序移除；R2 只允许 DELL／MU／NVDA development inputs，COST／hidden／frozen／holdout reference loading 继续禁止。

## 当前预检

新 materializer：

- `scripts/data_retrieval/materialize_s1_large_model_challenger_preflight_v2.py`

新收据：

- `configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_1.json`

结果仍为 `resource_blocked_before_download`：GPU total/free memory 均低于冻结的 24GB-class FP16 profile，Qwen3-Embedding-4B 和 Qwen3-Reranker-4B 均 absent，calls=`0/0/0`。这不是模型质量失败或通过；模型未下载、未载入、未计算向量或 rerank score。

## 回归与边界

- v3 identity 覆盖 recursive remote-code drift、冒名 model ID、非法 revision、额外文件和 sharded weight closure；
- large-model gate 只承认 v1.1 program 与 v3 status；
- frozen v1 embedding／cross-encoder runtime 保持 byte-exact，不在本 successor 中修改；
- candidate ceiling 仍先于 reranker；排序不授予 Evidence、NumericFact 或 gap 权威；
- `S1_qualified_stable=false`，hidden／temporal qualification、runtime promotion、publication 和 release 均未授权。

下一有效 attempt 必须在满足冻结显存 profile 的 CUDA 主机上，先以独立 acquisition attempt 生成完整 manifest，再重跑 preflight。不得复用 R1 的 v2 identity 或把本次 resource receipt 追认为 4B quality observation。

## 仓库门禁

相关治理／实现定向 `129 passed`；全仓 `1201 passed, 2 warnings`，两条均为既有 SWIG deprecation。另通过 full compileall、10 个变更 Python 文件 pyflakes、992 份 config JSON、8 份 Project OS JSONL／1137 行、active baseline `212 Python／8 frontend／5 detectors／28 resources／0 forbidden`、Workbench typecheck／production build、7,878-file secret scan／0 和 diff check。
