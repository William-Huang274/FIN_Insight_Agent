# 018 S1 全链标准范式与独立评测完成定义更正

日期：2026-08-17

状态：`owner_direction_accepted / source_docs_updated / runtime_and_qualification_pending`

## Owner 更正

Owner 指出此前的 S1 最终验收仍偏向 Evidence Pack 终态和 DELL／MU／NVDA 案例闭环。S1 真正结束时必须交付一套完整标准范式，覆盖 chunk 切分、OCR／parser 与数据清洗、对象化、索引、检索、重排、金融精排、Evidence 晋升、补证和 gap；案例只用于检验这套范式，不能替代它。

Owner 同时要求：S1 评测在项目现有 L0–L5、Financial Truth、Evidence Authority、对抗测试和研究质量上游 ceiling 基础上，增加独立 S1 资格。只有 S1 通过并稳定后，才运行用于产品资格的完整真实链。

## 本轮判断

原 16.40 第一修复包仍然必要，因为 candidate 无全账、reviewed binding 漏失、0 dynamic promotion 和 gap 归责混淆是已证实的最早断点。但它只能标记为 S1 的第一实现切片，不能被解释为 S1 完成的充分条件。

修订后的 S1 范式按十个责任面组织：

1. source／capture；
2. HTML／PDF／OCR／table／feed parsing 与 cleaning；
3. chunk／parent-child／claim-table-context object；
4. store／index／graph／S2 SQL sibling；
5. EvidenceRequest／QueryFacetPlan／route；
6. candidate recall；
7. semantic rerank；
8. finance-aware fine rank／Evidence Role／Gate；
9. Coverage／supplement／GapEligibility；
10. observability／replay／qualification。

“重排”和“金融精排”被有意分开：前者判断语义相关性，后者判断候选以什么证据角色、在什么期间和关系方向下能否服务当前命题。可以由同一实现组合计算，但评测和权威不能混成一个分数。

## 文档更新

- PRD 新增 16.41，正式把 S1 完成定义为全链标准范式和独立资格；
- S1 技术范式纳入 OCR／parser／cleaning、chunk／object、index、recall、rerank、fine rank 与最终必交付物；
- FIN 0.1.3 当前计划新增 4E，冻结“先独立 S1、后完整真实链”的顺序；
- 新增独立 S1 评测标准，定义 split、案例角色、E1–E10、硬门／性能门、泛化和稳定性；
- Project OS full-chain checklist／policy 增加 S1 资格前置；
- current context、capability／root-cause ledger 和当前 checklist 同步本次更正。

## 案例与评测边界

- DELL／MU／NVDA：开发、尸检和回归；
- ORCL／ASML／ANET 及其他已观察案例：结构回归，不是隐藏 test；
- 新异质留出：在读取结果前预注册，覆盖行业、来源形态、语言、关系、资料边界和故障类型；
- frozen test 不得用于同一轮调参；新问题回到 train／valid，再开启下一 test cycle。

不可补偿硬门包括身份、期间、单位、source locator、跨案污染、critical false promotion、公开信息 false gap、lineage 和 test leakage。性能指标包括 OCR／table／chunk gold、target-in-pool、useful@k、ranking、Evidence Role、abstain、信息增量、延迟和资源；阈值在 gold／baseline 建立后、查看 frozen test 前冻结。

## 本轮边界

- 0 Runtime／OCR／parser／chunk／index／Embedding／Reranker／model／Provider／network／source promotion／full-chain；
- 没有改写 DELL／MU／NVDA 历史结果；
- 没有宣称 S1、S3 或 FIN 0.1.3 通过；
- 当前第一修复包保持有效，但完整 S1 program 需要先建立实现覆盖矩阵和独立评测资产。

## 复证

- Project OS decision-bound preflight tests：`31 passed`；
- `full_chain_preflight_checklist.json`、capability ledger 和 root-cause ledger 解析通过；
- active baseline：`138 Python／8 frontend／11 Runtime resources／0 forbidden reference`；
- repository secret scan：`6,872 files／0 findings`；
- `git diff --check` 通过；
- 0 Runtime／OCR／parser／chunk／index／model／Provider／network／source promotion／full-chain。

## 下一门

先建立 S1-A–S1-J 的当前实现／消费者／评测覆盖矩阵和 program ticket，再实现 CoverageState／candidate ledger／binding／capture-bound promotion 的第一切片。每个后续切片都按独立 S1 标准在最早责任层验收；只有 frozen test、异质留出和稳定资格通过后，才签发完整真实产品链。
