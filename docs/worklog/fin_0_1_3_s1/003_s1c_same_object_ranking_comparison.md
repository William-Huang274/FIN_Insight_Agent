# S1-C 同对象排名对照工作记录

日期：2026-08-12

## 决策

冻结 S1-B 的 1,805 个 child；四条路线只能消费相同对象和相同 18 条 relevance qrels。候选生成后才连接 gold label，Workbench 投影禁止携带目标 ID、命中状态和业务评测码。

## 真实执行

1. 将 18 条 Owner relevance labels 重资格到当前对象：17 条获得当前 child，1 条保留 typed target gap。
2. 本地 GPU 运行 BGE-M3，和 BM25、固定 1:1 RRF、确定性金融规则重排做零网络、零模型同对象比较。
3. 首轮发现三条 TSM 6-K 因新旧 source-tier taxonomy 漂移被排序前错误过滤；修复为通用官方来源 tier 等价后重跑。
4. 对前排候选逐条读取正文，记录“主题相近但不证明业务问题”的具体错误，而非只报 Recall/MRR。
5. 将剥离 qrel identity 的只读投影接入 Workbench；候选仍不能成为 Evidence。

## 结果

- BM25：`14/17` mapped Recall@10，继续作为默认候选路线。
- BGE-M3：`12/17`；经常把保修／诉讼、资本回报、云产品定义等语义近邻误当成需求或供给机制，保留 shadow。
- RRF：`13/17`，MRR 最高但召回低于 BM25，不晋升。
- 确定性金融规则重排：`13/17`，能去掉部分明显噪声但没有超过 BM25；不是 neural cross-encoder。
- 四条 qrel 需要 Owner 复核；实现未擅自修改 accepted labels。

## 阶段边界

本工作项完成的是 S1-C engineering comparison，不是 S1 acceptance。Owner 标签复核后可用缓存复跑；随后才进入 S1-D 定向补源。完整说明见 `docs/architecture/retrieval/FIN_0_1_3_S1C_SAME_OBJECT_RANKING_COMPARISON_20260812.zh-CN.md`。

## 收口复证

- 活动图：72 Python / 7 frontend / 5 Runtime resources / 0 旧版本或 archive 活动引用。
- Python：65 passed。
- TypeScript 与 Vite production build：通过。
- Playwright：真实数据挂载桌面/移动 6/6；无数据桌面/移动 6/6；排名面无横向溢出。
- Secret scan：6,265 files，0 findings。
- Workbench 安全投影不含 target identity、单候选命中结果、单候选业务评测码或 qrel ID；普通 query ID 使用独立 `s1c_{case}_query_*` 命名，只保留无身份泄露的聚合路线指标。
