# FIN 0.1.3 S1 独立评测资产

状态：`VS5_qualification_preregistered_catalogs_unpopulated_not_qualified`

这里是 S1 从 source／capture 到 Evidence Pack／Workbench 的独立评测程序，不是模型报告评测，也不是一次性 attempt 目录。

## 当前包含什么

- `program_manifest_v1_0.json`：四类 split 的用途、禁止事项、资产 digest 和当前冻结状态；
- `schemas/`：canonical artifact envelope、runtime-visible input、evaluator-only reference 和 program manifest 的 JSON Schema；
- `inputs/train_internal/`：被测 Runtime 可以看到的开发输入；
- `references/train_internal/`：只允许 evaluator 读取的标签、硬门和业务理由；
- 现有 qrels 与 Evidence Role eval 只以 `legacy_development_asset` 引用，不复制、不升级为 hidden test。

当前 8 条 fixture 覆盖日期语义、parent／child lineage、关系方向 query、通用宣传噪声、直接结果证据、false public gap、跨案例污染和 Workbench binding。它们用于证明评测合同和 VS1 基础，不代表来源、OCR、chunk、recall、rerank、Evidence evaluator 或 S1 已通过。

## 为什么资格集已经预注册、catalog 仍然为空

VS1–VS4 合同稳定后，`qualification_preregistration_v1_0.json` 已在读取新案例结果前冻结 6 个新案例、7 个官方文档目标、30 个研究命题、配置 digest、执行次数、CUDA-only 资源要求和 all-positive／material-facet 等验收门。DELL／MU／NVDA／ORCL／ASML／ANET／IFX.DE 均被排除。

`valid_temporal`、`test_frozen`、`holdout_heterogeneous` catalog 当前仍为 `reserved_unpopulated`。原因是官方来源尚未 capture、evaluator-only reference 尚未盲审完成。预注册和 gold 是两件事：先冻结“测什么”，再在不让 Runtime 看见标签的情况下生成输入与 reference。提前把空壳 catalog 改成 active 反而会制造虚假资格。

此前在 VS1–VS3 尚未稳定时就选择隐藏案例，会造成两类问题：

1. 合同变化使标签和 locator 很快失效；
2. 开发者反复看到案例后再把它改名为 hidden test，产生评测泄漏。

当前正确顺序是：预注册已冻结并先提交；随后获取来源、建立 source-bound object 与 evaluator-only gold；正式执行前再冻结 clean commit、模型／缓存和输入 digest。valid temporal 最多两次，test frozen 与 heterogeneous holdout 各一次，hidden 执行后不得调阈值或换路线后沿用通过结论。

## 校验

```powershell
python scripts/data_retrieval/validate_s1_program_foundation.py
pytest -q tests/test_s1_program_foundation.py
```

校验会检查：资产 digest、input／reference 物理分离、标签泄漏、split 角色、A–J 仓库证据引用、canonical parent seam 和 CandidateSet／CandidateRanking／CandidateDecision 边界。
