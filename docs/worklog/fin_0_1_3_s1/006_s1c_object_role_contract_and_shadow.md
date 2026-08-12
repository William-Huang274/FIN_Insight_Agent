# S1-C 对象级 Evidence Role 合同与固定模型 shadow

日期：2026-08-12
状态：`development_contract_complete / query_and_object_successor_required / no_training_or_promotion`

## 用户批准范围

先建立对象级金融证据角色合同，让 claim、财务表格和父级上下文带有可复核的多标签角色、事实状态、直接性及 positive／hard negative／unjudged；复核一批后再决定是否微调 Cross-Encoder、训练独立角色分类器或进入 S1-D。

## 实现

- `src/retrieval/evidence_role_contract.py`：建立 label-free `EvidenceObjectView`、独立 `EvidenceObjectAnnotation` 和 query-specific `EvidenceQueryRelation`。claim 必须绑定唯一原文 span，metric table 必须保持 balanced table，parent context 只能 `unjudged/context_only`。
- `src/retrieval/cross_encoder.py`：把本地固定 Cross-Encoder 的身份、加载和评分从 attempt 脚本提取成共享 adapter；旧 shadow 与本轮 successor 共用同一实现。
- `scripts/data_retrieval/materialize_s1c_object_role_review_set.py`：把 frozen adjudication 与当前 1,805 child／28 parent、qrels 和三案 Pack 绑定；验证 digest、父子 lineage、公司身份和 holdout 隔离。
- `scripts/data_retrieval/run_s1c_object_role_shadow.py`：先对 35 个 query-object pair 评分，再连接人工标签；0 网络、0 generation、0 training。

## 开发复核批次

- 24 object：13 claim、6 metric table、3 parent context、1 mixed source segment、1 navigation／empty table。
- 35 query relation：17 positive、12 explicit hard negative、6 unjudged；DELL=13、MU=10、NVDA=12。
- ORCL／ASML／ANET 没有进入对象选择、标签、评分或调参。
- 三案当前 reviewed Pack 共有 45 个 Evidence item 仍只有 source segment 与人工业务说明，没有 claim text 或 structured metric 精确表面。这不追溯否定既有 Pack，但这些条目不能直接用于角色训练。

## 固定模型结果

本地 `BAAI/bge-reranker-v2-m3` 评分 35 pair，CUDA 耗时 1.505 秒，峰值显存约 1.18 GB。结果为：

- 12 个明确正负 pair 中正例胜出 6 个，pairwise=`0.50`。
- 10 个同时含正负例的 query 中 top1 positive=`0.60`，top3 positive=`1.0`。
- 旧规则角色层 positive compatibility=`0.705882`、hard-negative suppression=`0.416667`、multi-label micro-F1=`0.507936`。

## 真实业务错误

1. MU supply：旧季度业务单元收入／毛利表以 0.008 的微小分差压过 HBM4 已高量出货 claim；模型对两者都给极低分，未稳定识别“财务结果”和“供给执行”。
2. MU financial reconciliation：泛化国际经营风险长段压过绑定采购量和客户存款 claim。旧 query 同时混入监管、风险、库存、承诺和营运资金。
3. NVDA results：泛化风险提示开场压过当期收入、利润表和 MD&A 汇总表。旧 results query 尾部仍要求 counterevidence。
4. NVDA cash reconciliation：供给风险 claim 压过现金流表。旧 mixed slot 与 table 语义投影同时失真。
5. TSMC supply：当前 target 只证明领先制程需求和 2nm ramp，不含 CoWoS／先进封装产能、良率或客户分配；三条 relation 均保留 unjudged，不追改历史 ranking relevance。

## 决策

- 不微调 Cross-Encoder：错误合同尚未清除，35 个关系／3 个开发案例远低于训练门。
- 不训练独立角色分类器：对象训练表面仍不完整，现有标签数量不足。
- 不整体进入 S1-D：除 TSMC 先进封装外，大部分错误仍属于 S1-C query/object，不应靠更多网页掩盖。
- 当前下一项：`S1-C query-family decomposition and deterministic object-view compiler successor`。先拆 results、guidance、counterevidence、cash 和 regulatory query，补相关实体需求 read-through facet，并将表格编译成表头／期间／单位／metric row／父章节。修复后复用同一固定模型 shadow。
- 只有至少 200 个源绑定关系、6 个开发案例且独立留出不参与调参后，才允许重新判断独立角色分类器或 Cross-Encoder 微调。

## 权威边界

本轮结果是开发复核，不是 Owner acceptance、Evidence promotion、Runtime route promotion、S1 通过或产品 release。完整机器结果见：

- `configs/retrieval/fin_ia_0_1_3_s1c_object_role_review_set_v1_0.json`
- `configs/retrieval/fin_ia_0_1_3_s1c_object_role_shadow_result_v1_0.json`
- `configs/retrieval/fin_ia_0_1_3_s1c_object_role_business_assessment_v1_0.json`

## 收口复证

- review set 重物化 digest=`8a9021df26a590b9cb2501c45c386dc61aa47f9a8ebff7bd2f2957714f03932c`，与首次结果一致。
- 对象合同、shadow、旧 Evidence Role 和旧金融角色评测共 18 个定向测试通过；全仓 91 个 Python tests 通过。
- 新旧 retrieval 源码和脚本通过 `compileall`；active baseline 为 79 Python／7 frontend／6 Runtime resources，0 unresolved／forbidden reference。
- secret scan 扫描 6,298 个文件，0 finding；本轮没有访问网络、调用生成模型或晋升产品 Runtime 路由。
