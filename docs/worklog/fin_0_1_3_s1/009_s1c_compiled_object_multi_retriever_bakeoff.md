# 2026-08-13 S1-C2 当前对象库多检索器对照

## 本轮动作

1. 标签回放先修复两个对象编译根因：空表跨段吞掉 TSMC claim；Micron 重复 Revenue／Gross margin 行缺少业务单元行组。
2. 重建 20,340 个去重 claim／metric-row／bounded-context 对象，并绑定不可变 digest。
3. 预注册同库、同硬过滤、同预算的 BM25、BGE-M3 三模式和 Qwen Embedding 对照。
4. 本地 GPU 完成 BGE dense／learned sparse 缓存与 multi-vector shadow；没有来源网络或生成模型调用。
5. Qwen 权重经 Xet 416 和一次普通 HTTP 对端中断后停止，本轮保留 typed transport block。
6. 逐题检查业务错例，分开记录检索失败、对象选择失败、标签错位和真实资料缺口。
7. 完整 13,714 行逐候选结果留在 Git 忽略的私有 Workbench 数据区；跟踪摘要压缩为约 48KB，并绑定 full-result digest／SHA256，避免机器运行日志重新膨胀代码仓。

## 结果与处置

- BM25 目标来源前十 13/18；BGE dense 15/18；learned sparse 12/18；multi-vector 14/18。
- BM25 与 BGE dense 前十并集 17/18；各取 64 个候选后目标来源 18/18 均在池中。
- 受复核精确对象只覆盖 6/14，证明 source hit 不能代表选到了可引用证据。
- 当前候选池冻结为 `BM25 + BGE dense union`，但不晋升 Runtime；learned sparse 不保留，multi-vector 只作 shadow。
- Qwen 未执行，不做模型能力判断。
- 不微调、不晋升 Evidence、不关闭 S1。
- 全仓 `114 passed`；活动代码图 `84 Python / 7 frontend / 7 Runtime resources / 0 forbidden reference`；秘密扫描 `6,320 files / 0 findings`。

## 业务错因

- Micron HBM 供给题找到当前 8-K，却把费用／毛利表排在 HBM4 出货句前。
- NVIDIA 供给题中 dense 把保修、现金和应计负债排到制造产能风险前；BM25 反而更准。
- Micron 业绩题中 lexical 偏旧季度和风险，dense 回到当前来源但仍混合业绩、指引和表格。
- qrel 10 的 query 与目标客户协议／现金承诺句不一致，不能用于调参。
- TSMC 仅命中文档，现有材料仍不能证明先进封装容量。

## 数据库边界

本轮 metric-row 全部 `numeric_authority=false`。S2 公司财务事实 mart 仍是 DELL 纵切前硬前置；数值必须通过 typed exact lookup 返回，不能由文本检索或模型排名授予权威。

## 下一项

`FIN_0_1_3_S1C3_SAME_CANDIDATE_RERANKER_AND_EVIDENCE_ROLE_SHADOW`

使用 Runtime query atom 和同一 `BM25 + BGE dense` 候选并集比较 BGE/Qwen reranker，并运行独立 Evidence Role＋abstain。旧 18 条混合 qrel 只保留 source-level 诊断，不用于调参。
