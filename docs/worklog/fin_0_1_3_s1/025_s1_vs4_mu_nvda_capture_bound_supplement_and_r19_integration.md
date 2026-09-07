# FIN 0.1.3 S1 VS4 MU／NVDA capture-bound 补证与 R19 集成

日期：2026-08-18
状态：`three_case_VS4_vertical_slice_integrated / VS5_and_S1_qualification_open`

## 1. 本轮目标与边界

在不新增 ticker 专用核心分支、不访问网络、不调用生成模型的前提下，让 MU、NVDA 从自然业务命题复用 DELL 已证明的同一条纵切：

`residual proposition → typed route → candidate → Evidence Role → capture attestation → CandidateDecision → exact Evidence successor → Coverage delta → current Workbench／S3 consumer`

本轮不声称开放式补源完成，不授予 NumericFact，不执行 DeepSeek，不把 DELL／MU／NVDA 当作隐藏资格集，也不宣称 S1 通过。

## 2. CUDA-only learned retrieval

Owner 要求向量计算直接使用 CUDA，禁止 CPU。当前实现已把该要求固化为 fail-closed 合同：

- Embedding、dense／multi-vector 与 Cross-Encoder／reranker：`cuda:0`、FP16；
- 实际设备：NVIDIA GeForce RTX 4060 Laptop GPU，CUDA runtime 12.6，PyTorch 2.10.0+cu126；
- CUDA 不可用时在模型加载前抛出 `candidate_ranking_cuda_required`；
- 不存在 CPU vector／reranker fallback；
- CPU 只运行 BM25、分词、SQL、身份／期间／来源硬过滤、账本和确定性候选／上下文编排；
- v1.7 复用 33,085 对象的 BGE／Qwen 内容寻址 CUDA 缓存，没有重新计算未变化向量。

新增回归测试显式模拟 CUDA 不可用，验证 learned ranking 直接失败。

## 3. 排名与业务判断

三案共 10 个开发命题中，确定性金融短名单实现 10/10 `proposition_any_hit_at_10`，MRR 0.514444，pairwise 1.0；Qwen 通用 reranker 为 5/10，BGE reranker 为 0/10，因此两者均不晋升主路线。Evidence Role 对已审关系为 35/35 positive compatible、18/18 hard negative rejected／abstained；完整候选池正负关系为 31/31 与 7/7。

这个结果不能解释为“资料找全”。有 4 个额外 reviewed positive 没进入 candidate union：

- MU cycle reversal；
- NVDA cancellation；
- NVDA production delay；
- TSM bottleneck tools。

因此 10/10 只记 any-hit 开发指标。VS5 必须新增 all-positive object recall 与 material-facet coverage，不能继承 S1 资格。

## 4. MU／NVDA 业务结果

### MU

- 旧 16 条宽或 legacy Evidence 退役；
- 11 条精确 capture-bound claim 进入 successor；
- 当前为 `11 Evidence / 15 gaps`；
- 2 个 gap 被窄化，0 个关闭；
- 新增 2 个明确归属 S2 的桥接 gap：产品价值捕获的 price／volume／mix bridge，以及 capex 到自由现金流的 cash-conversion bridge；
- 新 gap 不代表公共信息不存在，也不授予 NumericFact。

模型后续可看到更精确的 HBM shipment、客户 commitment、packaging 约束和 counterevidence，但不能从文本直接发明公司级利润桥或现金桥。

### NVDA

- 旧 14 条宽或 legacy Evidence 退役；
- 19 条精确 capture-bound claim 进入 successor；
- 当前为 `19 Evidence / 13 gaps`；
- 3 个 gap 被窄化，0 个关闭。

当前 Pack 更准确地区分本案当期结果、供给承诺、发行人风险和上游背景；跨公司材料不能冒充 NVIDIA 自述或具体分配证明。

### DELL 保持

DELL 继续为 `22 Evidence / 14 gaps`，退役 3、加入 5、窄化 1、关闭 0。其历史 fixed-Pack attempt 继续固定读取各自 authority 绑定的旧 Pack，不受 current R19 指针改写。

三案共同结果：Candidate text 自动晋升 0、NumericFact 新授权 0、hard-negative false accept 0。

## 5. 自然暴露并修复的集成问题

1. **旧父级对象缺少当前 capture 元数据。** 原始官方 HTML 仍在本地，但旧 parent lineage 不满足新合同。处理方式不是放宽 capture-first，而是核对本地文件 digest、source URL 和 exact claim surface 后签发严格 attestation。
2. **旧 hard negative 期间标签混杂。** 不改写这些历史标签、不靠改 qrel 追分；保留负例证明，successor 只绑定精确当期 claim。
3. **多案例 summary digest 不幂等。** 第一版先算外层 digest、后标准化 DELL member；现改为所有 member 先标准化／校验，再计算 set digest，并在写入前重验。
4. **MU 研究单元出现空 Evidence／空 gap。** 退役宽片段后，S1→S2 财务桥没有显式交接。现新增两个 typed bridge gap，避免模型面对空 cell 或系统伪造结论。
5. **NVDA 丰富 Pack 超过单 cell 容量。** Pack 保持完整权威；仅在实际 overflow 时，S3 consumer 确定性选择 primary slot、facet、owner 和来源多样性更高的模型视图，并 receipt 所有 omitted-but-preserved Evidence。未溢出的历史 fixed Pack 保持原顺序和 digest。
6. **Operations 仍按 DELL 单案读取。** 后端、TypeScript 合同和 UI 改为三案 summary set；每案分别展示退役／新增 Evidence、命题覆盖、错误晋升和 gap 处置。

完整失败与处置见 `configs/retrieval/fin_ia_0_1_3_s1_vs4_mu_nvda_materialization_attempt_ledger_v1_0.json`。

## 6. 当前运行时

Runtime Registry 从 R18 升为 R19，资源数仍为 16。current pointers：

- Pack：`configs/runtime/fin_ia_current_research_evidence_pack_result_v1_3.json`；
- anchor：`configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_2.json`；
- Workspace：`configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_3.json`；
- supplement summary set：`configs/retrieval/fin_ia_0_1_3_s1_vs4_case_supplement_vertical_result_v1_0.json`。

三案 Evidence、Retrieval、Workspace、Operations 和 S3 current consumer 读取同一 case-bound canonical lineage；`complete_s1_qualified=false`、`numeric_fact_authorized=false` 保持可见。

## 7. 验证

- 定向 S1／Runtime／Workbench：44 passed；
- S3 三案 current context、zero-call digest 和历史 micro replay：3 passed；
- 前端 TypeScript typecheck：pass；
- 全仓 Python：592 passed；
- Vite production build 与 Operations desktop E2E：pass；
- active baseline：152 Python／8 frontend／16 Runtime resources／0 forbidden reference；repository secret scan：pass；
- CUDA unavailable fail-closed 回归：pass；
- 本轮 0 网络、0 生成模型、0 Provider、0 Evidence 自动晋升。

## 8. 下一步

不继续扩大 VS4。下一门是 VS5：

1. 冻结 any-hit、all-positive、material-facet 和 required-role 四组覆盖指标；
2. 预注册 valid temporal、frozen test 与新的异质留出，DELL／MU／NVDA、ORCL／ASML／ANET 均不得冒充隐藏集；
3. 覆盖 source、OCR／parser、chunk／object、query／route、candidate ceiling、rerank、金融精排、Evidence admission、Coverage／gap 与下游 ceiling；
4. 做顺序扰动、跨案、错期、错单位、缓存／模型身份与双 clean replay；
5. learned retrieval 继续 CUDA／FP16 only；
6. 只有全部硬门和产品质量门通过，才可写 `S1_qualified_stable` 并恢复完整真实产品链。
