# FIN 0.1.3 S1 VS5 独立资格预注册

日期：2026-08-18
状态：`qualification_preregistered_before_new_case_outcome_inspection / qualification_not_executed / S1_not_qualified`

## 1. 为什么必须先预注册

VS4 已证明 DELL／MU／NVDA 能复用同一条开发纵切，但这些案例与 ORCL／ASML／ANET／IFX.DE 都已被开发过程观察，不能再改名为隐藏集。三案的 `10/10` 也只是每个命题至少命中一条；另有 4 条 reviewed positive 未进入 candidate union。若直接继续跑分，会把“有一个可用片段”误报为“资料与反方已经找全”。

本轮因此先冻结案例、研究问题、来源形态、配置 digest、执行次数、CUDA 资源要求和非补偿硬门；冻结前没有读取新案例的检索结果，也没有建立 outcome gold。

## 2. 资格集

- `valid_temporal`：COST，固定比较 FY2024／FY2025 两份 10-K，检查同公司跨期、同口径和期间隔离；最多两次，只能用于配置选择。
- `test_frozen`：JPM 与 CAT 的 FY2025 10-K，分别覆盖银行复杂报表／监管资本与工业需求／经销商库存／价格成本；正式执行一次。
- `holdout_heterogeneous`：NVO、SHEL 的 FY2025 20-F，以及腾讯 FY2025 官方中英文年报 PDF，覆盖 IFRS、外国发行人、医药、能源、互联网平台、CJK 和非 SEC PDF；正式执行一次。

DELL、MU、NVDA、ORCL、ASML、ANET、IFX.DE 被机器合同明确排除。资格集共 6 个新案例、7 个官方文档目标、30 个预注册研究命题。

## 3. 新的覆盖口径

四类指标必须分别计算：

1. `proposition_any_hit`：命题至少有一条有效材料进入窗口；
2. `all_positive_object_recall`：全部经盲审认定为 material positive 的对象是否进入候选审阅窗口；
3. `material_facet_coverage`：直接证据、反方、替代解释、数值桥和独立 read-through 是否各自覆盖；
4. `required_role_coverage`：direct／counter／bridge／context 是否按任务需要齐全。

候选审阅窗口预注册为 20。any-hit 必须为 100%，all-positive 至少 90%，material facet 至少 85%，required-role 必须为 100%。跨案、错期、错单位、hard-negative false accept 和 false public gap 均必须为 0；平均分不能补偿任何硬门。

## 4. CUDA 约束

- learned Embedding、dense／multi-vector 与 Cross-Encoder／reranker 只允许 CUDA FP16；
- CUDA 不可用时资格运行失败，不允许 CPU fallback；
- CPU 只允许 BM25、分词、SQL、硬过滤、账本和确定性编排；
- 资格阶段不允许生成模型调用，避免把 S1 数据链与 S3 模型能力混在一起。

## 5. 扫描件与真实性边界

异质资格仍要求至少一份自然扫描的官方实质页面。人工把 native PDF 栅格化只能作为 OCR mutation，不能满足该门。腾讯官方 PDF 的真实形态将在 capture 后裁决；若没有自然扫描实质页，该硬门保持失败，不能为了通过临时更换结果更好的资料并沿用本次预注册。

## 6. 工程资产

- `eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json`：案例、命题、来源、配置、资源和阈值；
- `src/retrieval/evaluation_assets.py`：机器校验 unseen case、split 覆盖、配置 digest、CUDA-only、一次性 hidden execution 和非补偿门；
- `eval_sets/fin_0_1_3_s1/schemas/qualification_preregistration.schema.json`：对应 schema；
- `eval_sets/fin_0_1_3_s1/program_manifest_v1_0.json`：内容寻址绑定预注册与 schema。

当前 program foundation 校验为 6 个预注册案例、2 个 active development catalog、3 个仍空的 qualification catalog。空 catalog 不是遗漏：只有 capture、对象化与 evaluator-only gold 完成并在正式执行前物理分离后，才能从 `reserved_unpopulated` 转成 active。

## 7. 下一步与不可误读

下一步先提交并推送这份预注册，形成不可变时间边界；之后才允许发现官方 URL、capture-first 获取来源、离线解析和盲审 reference。test／holdout 第一次正式运行前还要绑定当时的 clean commit、模型目录 digest、CUDA device receipt 与输入／reference digest。

本轮没有访问新来源、没有计算新向量、没有建立新 gold、没有执行 valid／test／holdout，也没有授予 S1 资格。
