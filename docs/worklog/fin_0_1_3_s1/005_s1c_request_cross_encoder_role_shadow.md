# S1-C 请求入口、Cross-Encoder 与 Evidence Role shadow

日期：2026-08-12
状态：`approved_steps_1_to_6_complete / no_runtime_route_promoted / steps_7_and_8_not_executed`

## 用户批准范围

本轮只执行：qrel successor、请求级 QueryFacetPlan、hard negatives 与 ORCL／ASML／ANET 留出集、现成 Cross-Encoder shadow、Evidence Role 多标签／abstain、跨案例效果判断。用户明确要求微调与 S1-D 等结果出来后再决定。

## 完成结果

1. `05/11` 替换为当前 NVIDIA 10-Q 供给片段，`15` 保留 8-K 并增加当前 10-Q，`16` 绑定当前资产负债／现金流表。18/18 qrels 均有当前对象。
2. 缓存复跑：BM25 `17/18`、BGE-M3 `14/18`、RRF 与旧规则重排 `16/18`。
3. 当前后端新增严格 EvidenceRequest POST；只执行请求明确的 facet、owner、source、period，对跨案或合同漂移 fail closed。0 网络、0 模型，候选不是 Evidence。
4. primary 三案冻结 21 个正例、65 个既有业务 hard negatives；holdout 为 ORCL／ASML／ANET 17 问题、43 个正例、34 个逐条业务对照负例。未明确判断的同案例对象为 unjudged。
5. 本地 `BAAI/bge-reranker-v2-m3` SHA256=`d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`，Apache-2.0。631 pair、CUDA、25.141 秒、约 2.28 GB peak GPU；0 网络、0 generation、0 training。
6. Cross-Encoder：三案 Recall@10 `17/18`、MRR `0.608480`；留出明确正负 pairwise `0.790698`、top1 `0.823529`、top3 `1.0`。
7. 规则角色门：三案 Recall `13/18`；留出 top1 `0.764706`。留出正例 compatibility `0.232558`、abstain `0.697674`，不合格。

## 业务例子

- NVDA 财务桥接：BM25 前三是需求／采购承诺风险，正确现金流表在第 12；Cross-Encoder 将其升至第 1，说明精读 query-document pair 有真实价值。
- DELL AI 风险：BM25 正确风险段第 1；Cross-Encoder 因 query 同时包含结果、库存、收入确认，把公司概览和市场风险放前，正确段落掉到第 19，说明宽 query 与角色混合仍会反转。
- ASML 需求：`customer commitments ... longer-term demand` 是直接需求质量正例，词表角色器却因不认识 commitments 判 incompatible。
- ORCL value capture：当期 operating margin 是正例，规则器无法从 metric-table business meaning 识别利润角色而 abstain；角色判断必须消费结构化 metric 语义，不能只扫长表正文。

## 评测失败的保留

R1 曾将“reviewed pack 没绑定当前 slot”机械视为 hard negative。这会把 ORCL 客户预付款现金流在 relationship 问题中误标为负例。R1 原始策略、评测集、结果和 digest 已完整迁入 `archive/versions/fin_0_1_3_s1c_cross_encoder_role_shadow_r1_invalid_holdout_labels_20260812/`，标记为 holdout discrimination 无效；R2 改成逐条明确业务对照，其余对象 unjudged。该修正不改模型、不改 primary qrels，也不根据模型分数选择标签。

## 下一步建议（未执行）

先做对象级 Evidence Role 数据合同 successor：

- claim、metric/table、parent context 分形态；
- role 多标签，并同时标事实状态、直接性和是否只是背景；
- 明确 positive／hard negative／unjudged；
- 扩充训练案例，ORCL／ASML／ANET 继续留出，不参与调参；
- 复核后重跑固定 shadow。只有仍存在稳定角色错误，才选择微调 Cross-Encoder 或独立角色分类器。

当前不建议直接做第 7 项微调；第 8 项 S1-D 补源也尚未启动。

## 工程复证

- Python：83 passed。
- TypeScript：通过；Vite production build 通过。
- active baseline：75 Python、7 frontend、6 digest-bound Runtime resources；0 unresolved／forbidden reference。
- repository secret scan：6,286 files、0 finding。
