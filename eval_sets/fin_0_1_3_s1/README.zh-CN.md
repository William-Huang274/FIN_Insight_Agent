# FIN 0.1.3 S1 独立评测资产

状态：`VS5_catalogs_active_reference_human_review_pending_cuda_preflight_eligible_not_qualified`

这里是 S1 从 source／capture 到 Evidence Pack／Workbench 的独立评测程序，不是模型报告评测，也不是一次性 attempt 目录。

## 当前包含什么

- `program_manifest_v1_0.json`：四类 split 的用途、禁止事项、资产 digest 和当前冻结状态；
- `schemas/`：canonical artifact envelope、runtime-visible input、evaluator-only reference 和 program manifest 的 JSON Schema；
- `inputs/train_internal/`：被测 Runtime 可以看到的开发输入；
- `references/train_internal/`：只允许 evaluator 读取的标签、硬门和业务理由；
- `inputs/{valid_temporal,test_frozen,holdout_heterogeneous}/`：30 条 label-free qualification input；
- `references/{valid_temporal,test_frozen,holdout_heterogeneous}/`：与输入物理分离、待人工最终确认的 source-bound evaluator reference；
- 现有 qrels 与 Evidence Role eval 只以 `legacy_development_asset` 引用，不复制、不升级为 hidden test。

当前 8 条 fixture 覆盖日期语义、parent／child lineage、关系方向 query、通用宣传噪声、直接结果证据、false public gap、跨案例污染和 Workbench binding。它们用于证明评测合同和 VS1 基础，不代表来源、OCR、chunk、recall、rerank、Evidence evaluator 或 S1 已通过。

## 资格 catalog 当前状态

VS1–VS4 合同稳定后，`qualification_preregistration_v1_0.json` 已在读取新案例结果前冻结 6 个新案例、7 个官方文档目标、30 个研究命题、配置 digest、执行次数、CUDA-only 资源要求和 all-positive／material-facet 等验收门。DELL／MU／NVDA／ORCL／ASML／ANET／IFX.DE 均被排除。

7 份官方来源已经 capture-first 保存并形成 10,618 个统一候选对象；`valid_temporal`、`test_frozen`、`holdout_heterogeneous` catalog 已分别绑定 5／10／15 条 input 与 reference。预注册和人工 final gold 仍是两件事：当前 reference 是 source-bound、evaluator-only 的 `qualification_blinded` 资产，Owner／qualified-human review 尚未完成，因此 catalog active 不代表资格通过。

来源审阅同时保留最早责任层：JPM 四个命题是已捕获 10-K 的 parser／table／objectization 缺失；另外四个命题是发行人单源计划不能满足 independent readthrough。它们都不得误写为 public-information gap。腾讯官方年报 282 页均为 native layout，预注册 natural-scan 硬门已客观失败。

此前在 VS1–VS3 尚未稳定时就选择隐藏案例，会造成两类问题：

1. 合同变化使标签和 locator 很快失效；
2. 开发者反复看到案例后再把它改名为 hidden test，产生评测泄漏。

当前正确顺序是：先提交并推送 active catalog、reference 与 CUDA preflight；再实现单一 qualification runner，先跑 valid temporal。test frozen 与 heterogeneous holdout 各只能执行一次，必须在人工 reference review、clean commit、模型／缓存和输入 digest 全部绑定后执行；hidden 结果可见后不得调阈值或换路线后沿用通过结论。Embedding、multi-vector 与 reranker 只允许 CUDA＋FP16，绝不回退 CPU。

## 校验

```powershell
python scripts/data_retrieval/validate_s1_program_foundation.py
pytest -q tests/test_s1_program_foundation.py
```

校验会检查：资产 digest、input／reference 物理分离、标签泄漏、split 角色、A–J 仓库证据引用、canonical parent seam 和 CandidateSet／CandidateRanking／CandidateDecision 边界。
